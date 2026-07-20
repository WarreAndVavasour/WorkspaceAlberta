"""Local analytics store for OPERA Cloud query results.

Query results land as CSV exports (for Excel) and DuckDB tables (for
pandas/SQL analysis), all under a caller-supplied data directory.
"""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError:  # pragma: no cover - exercised only without duckdb
    duckdb = None

__all__ = ["DataStore"]

_INVALID_TABLE_CHARS = re.compile(r"[^a-z0-9_]+")
_READ_ONLY_KEYWORDS = ("select", "with", "describe", "show")


def _flatten_value(value: Any) -> Any:
    """Scalar stays, dict/list becomes a compact JSON string, None stays None."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return value


def _flatten_row(row: dict) -> dict:
    return {str(key): _flatten_value(value) for key, value in row.items()}


def _sanitize_table_name(table: str) -> str:
    """Lowercase the name and replace anything outside [a-z0-9_] with '_'."""
    cleaned = _INVALID_TABLE_CHARS.sub("_", table.strip().lower()).strip("_")
    if not cleaned:
        raise ValueError(f"table name {table!r} has no usable characters")
    return cleaned


class DataStore:
    """CSV + DuckDB landing zone for OPERA query results."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def exports_dir(self) -> Path:
        """Return <data_dir>/exports, creating it if needed."""
        path = self.data_dir / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_csv(self, name: str, rows: list[dict]) -> Path:
        """Write rows to <data_dir>/exports/<name>-<UTC timestamp>.csv.

        Nested dicts/lists are flattened to compact JSON strings. Columns are
        the union of all row keys, in first-seen order.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.exports_dir() / f"{name}-{stamp}.csv"
        flat = [_flatten_row(row) for row in rows]
        fieldnames: list[str] = []
        for row in flat:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat)
        return path

    def save_table(self, table: str, rows: list[dict], mode: str = "replace") -> int:
        """Create/replace or append a DuckDB table from rows; return rows saved.

        The table lives in <data_dir>/opera.duckdb. Table names are sanitized
        to [a-z0-9_]. Nested dicts/lists are flattened to compact JSON
        strings; None stays NULL. mode is 'replace' (default) or 'append';
        appended rows must use the same columns as the existing table.
        """
        if mode not in ("replace", "append"):
            raise ValueError(f"mode must be 'replace' or 'append', got {mode!r}")
        name = _sanitize_table_name(table)
        flat = [_flatten_row(row) for row in rows]
        if not flat:
            if mode == "replace":
                with self._connect() as connection:
                    connection.execute(f'DROP TABLE IF EXISTS "{name}"')
            return 0

        # read_json_auto does type inference for us; stage the payload in a
        # temp file because table-function arguments cannot be bound params.
        self.data_dir.mkdir(parents=True, exist_ok=True)
        fd, payload_path = tempfile.mkstemp(suffix=".json", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(flat, handle, ensure_ascii=False)
            source = f"read_json_auto('{payload_path.replace(chr(39), chr(39) * 2)}')"
            with self._connect() as connection:
                exists = connection.execute(
                    "SELECT count(*) FROM information_schema.tables"
                    " WHERE table_schema = 'main' AND table_name = ?",
                    [name],
                ).fetchone()[0]
                if mode == "replace" or not exists:
                    connection.execute(
                        f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM {source}'
                    )
                else:
                    connection.execute(
                        f'INSERT INTO "{name}" BY NAME SELECT * FROM {source}'
                    )
        finally:
            os.unlink(payload_path)
        return len(flat)

    def list_tables(self) -> list[dict]:
        """Return [{'table': name, 'rowcount': n}, ...] for every stored table."""
        if not (self.data_dir / "opera.duckdb").exists():
            return []
        with self._connect() as connection:
            names = [
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = 'main' ORDER BY table_name"
                ).fetchall()
            ]
            return [
                {
                    "table": name,
                    "rowcount": connection.execute(
                        f'SELECT count(*) FROM "{name}"'
                    ).fetchone()[0],
                }
                for name in names
            ]

    def run_sql(self, sql: str) -> dict:
        """Run a read-only query; return {columns, rows, rowcount}.

        Only statements starting with SELECT, WITH, DESCRIBE, or SHOW are
        allowed, and semicolons inside the statement are rejected so multiple
        statements cannot be stacked.
        """
        statement = sql.strip().rstrip(";").strip()
        keyword = statement.split(None, 1)[0].lower() if statement else ""
        if keyword not in _READ_ONLY_KEYWORDS or ";" in statement:
            raise ValueError(
                "run_sql is read-only: only single SELECT/WITH/DESCRIBE/SHOW"
                " statements are allowed"
            )
        with self._connect() as connection:
            result = connection.execute(statement)
            columns = [description[0] for description in result.description or []]
            rows = [list(row) for row in result.fetchall()]
        return {"columns": columns, "rows": rows, "rowcount": len(rows)}

    def _connect(self) -> Any:
        if duckdb is None:
            raise ImportError(
                "duckdb is required for table storage; install it with"
                " `python -m pip install duckdb`"
            )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.data_dir / "opera.duckdb"))
