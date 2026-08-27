# Offline procurement fixtures

Checked-in CanadaBuys CSV and Alberta Purchasing Connection JSON used to prove unified search without touching live sites.

| File | Source shape |
|---|---|
| `canadabuys-open-tenders.csv` | CanadaBuys open-tender snapshot (bilingual headers) |
| `alberta-apc-search.json` | APC `POST /api/opportunity/search` response (`values`, `totalCount`) |

These are trades/SBO postings (a CWB welding shop in Red Deer), not hospitality maps. The hospitality rows are distractors so the shop query cannot accidentally pass on catering.

## Run with no network

From the repo root:

```bash
python -m unittest tests.test_procurement_fixtures
python -m unittest tests.test_canadabuys_mcp_smoke
```

Or point any local server at the same files:

```bash
export PROCUREMENT_FIXTURE_DIR="$PWD/tests/fixtures/procurement"
export CANADABUYS_DATA_DIR="$(mktemp -d)"
python -m unittest tests.test_procurement_fixtures
```

`PROCUREMENT_FIXTURE_DIR` is test/offline only. Do not set it on the hosted MCP.
