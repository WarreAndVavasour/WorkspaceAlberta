# CanadaBuys MVP Pipeline (Alberta + Steel/Lumber/Aluminum)

This is a minimal pipeline to validate access to CanadaBuys tender data via CKAN and the
public CSV feeds, then filter for Alberta opportunities tied to steel, lumber, and aluminum.

## Data sources

- CKAN package (metadata): https://open.canada.ca/data/api/action/package_show?id=6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2
- Open tender notices CSV (live): https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv
- New tender notices CSV (incremental): https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv
- Awards dataset: https://open.canada.ca/data/api/action/package_show?id=a1acb126-9ce8-40a9-b889-5da2b1dd20cb
- Contract history dataset: https://open.canada.ca/data/api/action/package_show?id=4fe645a1-ffcd-40c1-9385-2c771be956a4

## What it does

1. Downloads the tender CSV (open or new).
2. Filters rows where regions of opportunity/delivery include "Alberta".
3. Matches UNSPSC codes from the provided industry map.
4. Falls back to keyword matching in title/description if UNSPSC is missing.
5. Sorts by closing date, procurement category, and contracting entity.
6. Writes filtered CSV + summary JSON to `output/canadabuys/`.

## Run the pipeline

```bash
python pipelines/canadabuys/pipeline.py --source open
```

Quick test with only the first 200 rows:

```bash
python pipelines/canadabuys/pipeline.py --source open --max-rows 200
```

Use the incremental feed:

```bash
python pipelines/canadabuys/pipeline.py --source new
```

Use a local CSV file:

```bash
python pipelines/canadabuys/pipeline.py --source C:\path\to\openTenderNotice.csv
```

## Outputs

Generated files:

- `output/canadabuys/filtered-YYYYMMDD-HHMMSS.csv`
- `output/canadabuys/summary-YYYYMMDD-HHMMSS.json`
- `output/canadabuys/latest.csv`
- `output/canadabuys/latest.json`
- `output/canadabuys/projects/<reference-or-solicitation>.md`

The CSV includes extra columns:

- `match_regions`
- `match_industries`
- `match_codes`
- `match_categories`
- `match_sources`
- `match_keywords`

Each markdown file includes:

- Snapshot fields (reference, closing date, category, entity, regions)
- Matching metadata (industries, codes, keywords)
- UNSPSC/GSIN codes and descriptions
- Tender description (EN/FR when available)
- Notice links
- Supporting documents (only working URLs when attachment checks are enabled)

## Attachment checks and downloads

Attachment URLs are provided in the CSV as comma-separated values in:

- `attachment-piecesJointes-eng`
- `attachment-piecesJointes-fra`

You can validate these URLs and optionally download a sample.

Check attachments (HEAD requests) and label markdown links:

```bash
python pipelines/canadabuys/pipeline.py --source open --check-attachments
```

Limit checks to the first N unique attachment URLs:

```bash
python pipelines/canadabuys/pipeline.py --source open --check-attachments --attachment-check-limit 50
```

Download attachments (defaults to 10 files; set 0 for no limit):

```bash
python pipelines/canadabuys/pipeline.py --source open --check-attachments --download-attachments
python pipelines/canadabuys/pipeline.py --source open --check-attachments --download-attachments --download-limit 0
```

## Configuration

All industry codes, feeders, and keywords live in:

- `pipelines/canadabuys/config.json`

Edit that file to adjust:

- UNSPSC lists (macro, commodity, feeders)
- Region filters
- Keywords
- Source URLs

## CKAN API notes (quick reference)

CKAN Action API docs: https://docs.ckan.org/en/2.8/api/index.html

Useful actions:

- `package_show`: dataset metadata for known IDs.
- `package_search`: keyword discovery across datasets.
- `recently_changed_packages_activity_list`: change feed.

Example:

```
https://open.canada.ca/data/en/api/3/action/package_search?q=spending
```
