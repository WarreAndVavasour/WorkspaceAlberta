import csv
import json
import tempfile
import unittest
from pathlib import Path

from opera_core.store import DataStore


ROWS = [
    {
        "reservation_id": 1001,
        "guest": {"first": "Ada", "last": "Lovelace"},
        "tags": ["vip", "returning"],
        "balance": 125.5,
        "note": None,
    },
    {
        "reservation_id": 1002,
        "guest": {"first": "Alan", "last": "Turing"},
        "tags": [],
        "balance": 0,
        "note": "late checkout",
    },
]
EXTRA_ROW = {
    "reservation_id": 1003,
    "guest": {"first": "Grace", "last": "Hopper"},
    "tags": ["vip"],
    "balance": 42.0,
    "note": None,
}


class DataStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = DataStore(Path(self._tmp.name))

    def test_save_csv_round_trip(self) -> None:
        path = self.store.save_csv("reservations", ROWS)

        self.assertTrue(path.exists())
        self.assertEqual(path.parent, self.store.exports_dir())
        self.assertTrue(path.name.startswith("reservations-"))
        self.assertTrue(path.name.endswith(".csv"))

        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["reservation_id"], "1001")
        self.assertEqual(
            json.loads(rows[0]["guest"]), {"first": "Ada", "last": "Lovelace"}
        )
        self.assertEqual(json.loads(rows[0]["tags"]), ["vip", "returning"])
        self.assertEqual(rows[0]["note"], "")

    def test_save_table_create_and_append(self) -> None:
        self.assertEqual(self.store.save_table("Reservations", ROWS), 2)
        self.assertEqual(
            self.store.save_table("reservations", [EXTRA_ROW], mode="append"), 1
        )

        result = self.store.run_sql("SELECT count(*) AS n FROM reservations")
        self.assertEqual(result["rows"][0][0], 3)

        self.assertEqual(self.store.save_table("reservations", [EXTRA_ROW]), 1)
        result = self.store.run_sql("SELECT count(*) AS n FROM reservations")
        self.assertEqual(result["rows"][0][0], 1)

        row = self.store.run_sql(
            "SELECT guest, tags, note FROM reservations WHERE reservation_id = 1003"
        )
        self.assertEqual(
            json.loads(row["rows"][0][0]), {"first": "Grace", "last": "Hopper"}
        )
        self.assertEqual(json.loads(row["rows"][0][1]), ["vip"])
        self.assertIsNone(row["rows"][0][2])

    def test_run_sql_select_returns_columns_rows_rowcount(self) -> None:
        self.store.save_table("reservations", ROWS)

        result = self.store.run_sql(
            "SELECT reservation_id, balance FROM reservations"
            " ORDER BY reservation_id"
        )
        self.assertEqual(result["columns"], ["reservation_id", "balance"])
        self.assertEqual(result["rows"], [[1001, 125.5], [1002, 0]])
        self.assertEqual(result["rowcount"], 2)

        result = self.store.run_sql("with x as (select 7 as n) select n from x;")
        self.assertEqual(result["rows"], [[7]])

    def test_run_sql_rejects_writes(self) -> None:
        self.store.save_table("reservations", ROWS)

        for bad_sql in (
            "DROP TABLE reservations",
            "INSERT INTO reservations VALUES (1, 2)",
            "UPDATE reservations SET balance = 0",
            "DELETE FROM reservations",
            "SELECT 1; DROP TABLE reservations",
        ):
            with self.assertRaises(ValueError, msg=bad_sql):
                self.store.run_sql(bad_sql)

        result = self.store.run_sql("SELECT count(*) AS n FROM reservations")
        self.assertEqual(result["rows"][0][0], 2)

    def test_list_tables_reports_counts(self) -> None:
        self.assertEqual(self.store.list_tables(), [])

        self.store.save_table("reservations", ROWS)
        self.store.save_table("Folio Lines!", [{"line": 1, "amount": 9.99}])
        self.store.save_table("reservations", [EXTRA_ROW], mode="append")

        tables = {entry["table"]: entry["rowcount"] for entry in self.store.list_tables()}
        self.assertEqual(tables, {"folio_lines": 1, "reservations": 3})


if __name__ == "__main__":
    unittest.main()
