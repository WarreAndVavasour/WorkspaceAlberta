"""Offline fixture ingest for CanadaBuys CSV and Alberta APC JSON.

Set ``PROCUREMENT_FIXTURE_DIR`` to a directory containing:

- ``canadabuys-open-tenders.csv`` — CanadaBuys open-tender snapshot
- ``alberta-apc-search.json`` — APC ``/opportunity/search`` response shape

When that directory is set, :func:`procurement_core.service.fetch_all_contracts`
and :func:`procurement_core.service.search_alberta_api` read these files
instead of the live CanadaBuys open-data URL and APC API. Production and the
hosted MCP URL are unchanged unless this env var is set.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any


FIXTURE_DIR_ENV = "PROCUREMENT_FIXTURE_DIR"
CANADABUYS_CSV_NAME = "canadabuys-open-tenders.csv"
APC_SEARCH_JSON_NAME = "alberta-apc-search.json"


def fixture_dir() -> Path | None:
    """Return the configured fixture directory, or None when unset."""
    raw = os.environ.get(FIXTURE_DIR_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def parse_canadabuys_csv_text(text_data: str) -> list[dict]:
    """Parse a CanadaBuys open-tender CSV body into row dicts."""
    lines = [line for line in text_data.split("\n") if line.strip()]
    if not lines:
        return []
    return list(csv.DictReader(lines))


def load_canadabuys_rows() -> list[dict] | None:
    """Load CanadaBuys fixture rows when ``PROCUREMENT_FIXTURE_DIR`` is set.

    Returns None when fixture mode is off so callers can use the live path.
    """
    directory = fixture_dir()
    if directory is None:
        return None
    path = directory / CANADABUYS_CSV_NAME
    if not path.is_file():
        raise FileNotFoundError(f"CanadaBuys fixture missing: {path}")
    return parse_canadabuys_csv_text(path.read_text(encoding="utf-8-sig"))


def load_apc_search_payload() -> dict[str, Any] | None:
    """Load an APC search fixture when ``PROCUREMENT_FIXTURE_DIR`` is set.

    Returns None when fixture mode is off so callers can use the live path.
    """
    directory = fixture_dir()
    if directory is None:
        return None
    path = directory / APC_SEARCH_JSON_NAME
    if not path.is_file():
        raise FileNotFoundError(f"Alberta APC fixture missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Alberta APC fixture must be a JSON object with a values list.")
    if "values" not in payload or not isinstance(payload["values"], list):
        raise ValueError("Alberta APC fixture must include a values list.")
    return payload


def _apc_row_text(row: dict[str, Any]) -> str:
    """Return lowercase searchable text for one APC fixture row."""
    parts = [
        str(row.get("title") or ""),
        str(row.get("shortTitle") or ""),
        str(row.get("contractingOrganization") or ""),
        str(row.get("projectDescription") or ""),
        str(row.get("referenceNumber") or ""),
        " ".join(str(value) for value in row.get("commodityCodeTitles") or []),
    ]
    region = row.get("regionOfDelivery") or []
    if isinstance(region, list):
        parts.append(" ".join(str(item) for item in region))
    else:
        parts.append(str(region))
    return " ".join(parts).lower()


def filter_apc_search_payload(
    payload: dict[str, Any],
    *,
    query: str = "",
    status: str = "OPEN",
    category: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """Apply light local filters so fixture ingest mirrors the live search call."""
    rows = list(payload.get("values") or [])
    status_norm = (status or "").strip().upper()
    if status_norm and status_norm not in {"ALL", "ANY"}:
        rows = [row for row in rows if str(row.get("statusCode") or "").upper() == status_norm]
    if category:
        rows = [row for row in rows if str(row.get("categoryCode") or "").upper() == category.upper()]
    query_norm = (query or "").strip().lower()
    if query_norm:
        tokens = [token for token in query_norm.replace(",", " ").split() if token]
        if tokens:
            rows = [row for row in rows if all(token in _apc_row_text(row) for token in tokens)]
    limited = rows[: max(1, int(limit or 10))]
    return {
        "values": limited,
        "totalCount": payload.get("totalCount", len(rows)),
    }
