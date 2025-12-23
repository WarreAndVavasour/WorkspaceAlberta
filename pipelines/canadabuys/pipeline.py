import argparse
import csv
import json
import re
import sys
from datetime import datetime
from urllib.parse import unquote, urlsplit
from pathlib import Path
from urllib.request import Request, urlopen
from io import TextIOWrapper


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://canadabuys.canada.ca/en/tender-opportunities",
}

REGION_FIELDS = [
    "regionsOfOpportunity-regionAppelOffres-eng",
    "regionsOfOpportunity-regionAppelOffres-fra",
    "regionsOfDelivery-regionsLivraison-eng",
    "regionsOfDelivery-regionsLivraison-fra",
]

TEXT_FIELDS = [
    "title-titre-eng",
    "title-titre-fra",
    "tenderDescription-descriptionAppelOffres-eng",
    "tenderDescription-descriptionAppelOffres-fra",
]

SORT_DATE_FIELD = "tenderClosingDate-appelOffresDateCloture"
SORT_CATEGORY_FIELD = "procurementCategory-categorieApprovisionnement"
SORT_ENTITY_FIELD_EN = "contractingEntityName-nomEntitContractante-eng"
SORT_ENTITY_FIELD_FR = "contractingEntityName-nomEntitContractante-fra"

PROJECT_FIELDS = [
    "referenceNumber-numeroReference",
    "amendmentNumber-numeroModification",
    "solicitationNumber-numeroSollicitation",
    "publicationDate-datePublication",
    "tenderClosingDate-appelOffresDateCloture",
    "expectedContractStartDate-dateDebutContratPrevue",
    "expectedContractEndDate-dateFinContratPrevue",
    "tenderStatus-appelOffresStatut-eng",
    "tenderStatus-appelOffresStatut-fra",
    "noticeType-avisType-eng",
    "noticeType-avisType-fra",
    "procurementMethod-methodeApprovisionnement-eng",
    "procurementMethod-methodeApprovisionnement-fra",
    "procurementCategory-categorieApprovisionnement",
    "regionsOfOpportunity-regionAppelOffres-eng",
    "regionsOfDelivery-regionsLivraison-eng",
    "gsin-nibs",
    "gsinDescription-nibsDescription-eng",
    "unspsc",
    "unspscDescription-eng",
    "contractingEntityName-nomEntitContractante-eng",
    "contractingEntityName-nomEntitContractante-fra",
    "contactInfoName-informationsContactNom",
    "contactInfoEmail-informationsContactCourriel",
    "contactInfoPhone-contactInfoTelephone",
    "noticeURL-URLavis-eng",
    "noticeURL-URLavis-fra",
    "attachment-piecesJointes-eng",
    "attachment-piecesJointes-fra",
    "attachment_urls",
    "attachment_working",
    "attachment_missing",
    "attachment_unchecked",
    "attachment_downloaded",
]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_code(value: str) -> str:
    return re.sub(r"[^0-9]", "", value or "")


def build_code_rules(config: dict) -> list[dict]:
    rules = []
    industries = config.get("industries", {})
    for industry, data in industries.items():
        for code in data.get("macro_unspsc", []):
            rules.append(build_rule(industry, "macro", code))
        for code in data.get("commodity_unspsc", []):
            rules.append(build_rule(industry, "commodity", code))
        feeders = data.get("feeders", {})
        for feeder_type, codes in feeders.items():
            for code in codes:
                rules.append(build_rule(industry, f"feeder_{feeder_type}", code))
    return [rule for rule in rules if rule]


def build_rule(industry: str, category: str, code: str) -> dict | None:
    digits = normalize_code(code)
    if not digits:
        return None
    if digits.endswith("0"):
        prefix = digits.rstrip("0")
        match_type = "prefix"
    else:
        prefix = digits
        match_type = "exact"
    return {
        "industry": industry,
        "category": category,
        "code": digits,
        "match_type": match_type,
        "prefix": prefix,
    }


def extract_unspsc_codes(value: str) -> list[str]:
    if not value:
        return []
    return re.findall(r"[0-9]{4,8}", value)


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None


def build_request(url: str, method: str = "GET") -> Request:
    return Request(url, headers=REQUEST_HEADERS, method=method)


def sanitize_filename(value: str) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def select_project_id(row: dict, index: int) -> str:
    for field in [
        "referenceNumber-numeroReference",
        "solicitationNumber-numeroSollicitation",
    ]:
        candidate = sanitize_filename(row.get(field, ""))
        if candidate:
            amendment = sanitize_filename(row.get("amendmentNumber-numeroModification", ""))
            if amendment:
                return f"{candidate}-amendment-{amendment}"
            return candidate
    return f"record-{index:06d}"


def parse_attachment_urls(row: dict) -> list[str]:
    urls: list[str] = []
    for field in ["attachment-piecesJointes-eng", "attachment-piecesJointes-fra"]:
        value = row.get(field, "")
        if not value:
            continue
        for item in value.split(","):
            candidate = item.strip()
            if candidate:
                urls.append(candidate)
    seen = set()
    ordered = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def filename_from_url(url: str) -> str:
    parts = urlsplit(url)
    name = Path(parts.path).name
    if not name:
        return "document"
    return unquote(name)


def render_project_markdown(row: dict) -> str:
    title_en = row.get("title-titre-eng", "").strip()
    title_fr = row.get("title-titre-fra", "").strip()
    description_en = row.get("tenderDescription-descriptionAppelOffres-eng", "").strip()
    description_fr = row.get("tenderDescription-descriptionAppelOffres-fra", "").strip()
    notice_en = row.get("noticeURL-URLavis-eng", "").strip()
    notice_fr = row.get("noticeURL-URLavis-fra", "").strip()
    header_title = title_en or title_fr or "Tender opportunity"

    lines = [f"# {header_title}"]
    if title_en and title_fr and title_en != title_fr:
        lines.append("")
        lines.append(f"**Title (FR):** {title_fr}")

    lines.append("")
    lines.append("## Snapshot")
    lines.append(f"- Reference: {row.get('referenceNumber-numeroReference', '')}")
    lines.append(f"- Solicitation: {row.get('solicitationNumber-numeroSollicitation', '')}")
    lines.append(f"- Status: {row.get('tenderStatus-appelOffresStatut-eng', '')}")
    lines.append(f"- Closing date: {row.get('tenderClosingDate-appelOffresDateCloture', '')}")
    lines.append(f"- Procurement category: {row.get('procurementCategory-categorieApprovisionnement', '')}")
    lines.append(f"- Contracting entity: {row.get('contractingEntityName-nomEntitContractante-eng', '')}")
    lines.append(f"- Regions (opportunity): {row.get('regionsOfOpportunity-regionAppelOffres-eng', '')}")
    lines.append(f"- Regions (delivery): {row.get('regionsOfDelivery-regionsLivraison-eng', '')}")

    lines.append("")
    lines.append("## Matching")
    lines.append(f"- Match industries: {row.get('match_industries', '')}")
    lines.append(f"- Match codes: {row.get('match_codes', '')}")
    lines.append(f"- Match categories: {row.get('match_categories', '')}")
    lines.append(f"- Match sources: {row.get('match_sources', '')}")
    lines.append(f"- Match keywords: {row.get('match_keywords', '')}")

    lines.append("")
    lines.append("## Codes")
    lines.append(f"- UNSPSC: {row.get('unspsc', '')}")
    lines.append(f"- UNSPSC description: {row.get('unspscDescription-eng', '')}")
    lines.append(f"- GSIN: {row.get('gsin-nibs', '')}")
    lines.append(f"- GSIN description: {row.get('gsinDescription-nibsDescription-eng', '')}")

    attachment_urls = [url for url in row.get("attachment_urls", "").split(";") if url.strip()]
    if attachment_urls:
        working = [url for url in row.get("attachment_working", "").split(";") if url.strip()]
        missing = [url for url in row.get("attachment_missing", "").split(";") if url.strip()]
        unchecked = [url for url in row.get("attachment_unchecked", "").split(";") if url.strip()]

        lines.append("")
        lines.append("## Supporting documents")
        if working:
            for url in working:
                name = filename_from_url(url)
                lines.append(f"- [{name}]({url})")
        else:
            if unchecked and not missing:
                lines.append("- Attachments found but not checked. Run with --check-attachments.")
            else:
                lines.append("- No working attachment URLs found.")
        if missing:
            lines.append(f"- Missing: {len(missing)}")
        if unchecked:
            lines.append(f"- Unchecked: {len(unchecked)}")

    if description_en:
        lines.append("")
        lines.append("## Description (EN)")
        lines.append(description_en)

    if description_fr:
        lines.append("")
        lines.append("## Description (FR)")
        lines.append(description_fr)

    if notice_en or notice_fr:
        lines.append("")
        lines.append("## Notice links")
        if notice_en:
            lines.append(f"- English: {notice_en}")
        if notice_fr:
            lines.append(f"- French: {notice_fr}")

    return "\n".join(lines).strip() + "\n"


def match_regions(row: dict, regions: list[str]) -> set[str]:
    combined = []
    for field in REGION_FIELDS:
        value = row.get(field, "")
        if value:
            combined.append(value)
    haystack = " ".join(combined).lower()
    matched = set()
    for region in regions:
        if region.lower() in haystack:
            matched.add(region)
    return matched


def match_keywords(row: dict, keyword_map: dict) -> dict:
    text_parts = [row.get(field, "") for field in TEXT_FIELDS if row.get(field)]
    haystack = " ".join(text_parts).lower()
    matches = {}
    for industry, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword.lower() in haystack:
                matches.setdefault(industry, set()).add(keyword)
    return matches


def match_unspsc(row_codes: list[str], rules: list[dict]) -> list[dict]:
    hits = []
    for rule in rules:
        if rule["match_type"] == "exact":
            if rule["prefix"] in row_codes:
                hits.append(rule)
        else:
            for code in row_codes:
                if code.startswith(rule["prefix"]):
                    hits.append(rule)
                    break
    return hits


def resolve_source(config: dict, source: str) -> str:
    if source == "open":
        return config["sources"]["open_tenders_csv"]
    if source == "new":
        return config["sources"]["new_tenders_csv"]
    return source


def open_source(path_or_url: str):
    path = Path(path_or_url)
    if path.is_file():
        return path.open("r", encoding="utf-8-sig", newline="")
    request = build_request(path_or_url)
    return TextIOWrapper(urlopen(request), encoding="utf-8-sig", newline="")


def build_output_dir(output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "output" / "canadabuys"


def sort_key(row: dict) -> tuple:
    date_value = parse_date(row.get(SORT_DATE_FIELD, ""))
    category = row.get(SORT_CATEGORY_FIELD, "").lower()
    entity = row.get(SORT_ENTITY_FIELD_EN, "") or row.get(SORT_ENTITY_FIELD_FR, "")
    return (date_value or datetime.max, category, entity.lower())


def write_outputs(output_dir: Path, rows: list[dict], summary: dict) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    csv_path = output_dir / f"filtered-{timestamp}.csv"
    json_path = output_dir / f"summary-{timestamp}.json"

    if not rows:
        fieldnames = []
    else:
        fieldnames = list(rows[0].keys())

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)

    latest_csv = output_dir / "latest.csv"
    latest_json = output_dir / "latest.json"
    latest_csv.write_bytes(csv_path.read_bytes())
    latest_json.write_bytes(json_path.read_bytes())

    return csv_path, json_path


def write_project_markdowns(output_dir: Path, rows: list[dict]) -> int:
    projects_dir = output_dir / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for index, row in enumerate(rows, start=1):
        project_id = select_project_id(row, index)
        filename = f"{project_id}.md"
        path = projects_dir / filename
        content = render_project_markdown(row)
        path.write_text(content, encoding="utf-8")
        count += 1
    return count


def head_status(url: str, timeout: int) -> int | None:
    request = build_request(url, method="HEAD")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status
    except Exception as exc:
        code = getattr(getattr(exc, "code", None), "value", None)
        if code is None:
            code = getattr(exc, "code", None)
        return code


def check_attachment_urls(urls: list[str], timeout: int, limit: int) -> dict[str, int | None]:
    status_map: dict[str, int | None] = {}
    for index, url in enumerate(urls, start=1):
        if limit and index > limit:
            break
        status_map[url] = head_status(url, timeout)
    return status_map


def download_attachment(url: str, destination: Path, timeout: int) -> bool:
    request = build_request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break
                    handle.write(chunk)
        return True
    except Exception:
        return False


def run_pipeline(
    config_path: Path,
    source: str,
    output_dir: str | None,
    max_rows: int | None,
    check_attachments: bool,
    attachment_check_limit: int,
    attachment_timeout: int,
    download_attachments: bool,
    download_limit: int,
) -> tuple[Path, Path]:
    config = load_config(config_path)
    regions = config.get("filters", {}).get("regions", [])
    keyword_map = {
        industry: data.get("keywords", [])
        for industry, data in config.get("industries", {}).items()
    }
    rules = build_code_rules(config)
    source_url = resolve_source(config, source)

    results = []
    summary = {
        "source": source_url,
        "regions": regions,
        "matched_total": 0,
        "processed_total": 0,
        "industry_counts": {},
        "match_sources": {"unspsc": 0, "keyword": 0},
        "attachment_urls_total": 0,
        "attachment_urls_checked": 0,
        "attachment_urls_ok": 0,
        "attachment_urls_missing": 0,
        "attachment_urls_other": 0,
        "attachment_download_attempted": 0,
        "attachment_downloaded": 0,
    }

    with open_source(source_url) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            summary["processed_total"] += 1
            if max_rows and summary["processed_total"] > max_rows:
                break

            region_matches = match_regions(row, regions)
            if not region_matches:
                continue

            unspsc_codes = extract_unspsc_codes(row.get("unspsc", ""))
            unspsc_hits = match_unspsc(unspsc_codes, rules)
            keyword_hits = match_keywords(row, keyword_map)

            if not unspsc_hits and not keyword_hits:
                continue

            match_industries = set()
            match_codes = set()
            match_categories = set()
            match_sources = set()
            matched_keywords = set()

            if unspsc_hits:
                match_sources.add("unspsc")
                summary["match_sources"]["unspsc"] += 1
                for hit in unspsc_hits:
                    match_industries.add(hit["industry"])
                    match_codes.add(hit["code"])
                    match_categories.add(f"{hit['industry']}:{hit['category']}")

            if keyword_hits:
                match_sources.add("keyword")
                summary["match_sources"]["keyword"] += 1
                for industry, keywords in keyword_hits.items():
                    match_industries.add(industry)
                    matched_keywords.update(keywords)

            for industry in match_industries:
                summary["industry_counts"][industry] = summary["industry_counts"].get(industry, 0) + 1

            output_row = dict(row)
            output_row["match_regions"] = ";".join(sorted(region_matches))
            output_row["match_industries"] = ";".join(sorted(match_industries))
            output_row["match_codes"] = ";".join(sorted(match_codes))
            output_row["match_categories"] = ";".join(sorted(match_categories))
            output_row["match_sources"] = ";".join(sorted(match_sources))
            output_row["match_keywords"] = ";".join(sorted(matched_keywords))
            attachments = parse_attachment_urls(row)
            output_row["attachment_urls"] = ";".join(attachments)
            output_row["attachment_working"] = ""
            output_row["attachment_missing"] = ""
            output_row["attachment_unchecked"] = ""
            output_row["attachment_downloaded"] = ""

            results.append(output_row)
            summary["matched_total"] += 1

    results.sort(key=sort_key)

    summary["output_rows"] = len(results)
    summary["generated_at_utc"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    attachment_urls: list[str] = []
    if results:
        seen = set()
        for row in results:
            urls = [u for u in row.get("attachment_urls", "").split(";") if u.strip()]
            for url in urls:
                if url in seen:
                    continue
                seen.add(url)
                attachment_urls.append(url)
    summary["attachment_urls_total"] = len(attachment_urls)

    status_map: dict[str, int | None] = {}
    if check_attachments and attachment_urls:
        status_map = check_attachment_urls(attachment_urls, attachment_timeout, attachment_check_limit)
        summary["attachment_urls_checked"] = len(status_map)
        summary["attachment_urls_ok"] = sum(1 for status in status_map.values() if status == 200)
        summary["attachment_urls_missing"] = sum(1 for status in status_map.values() if status == 404)
        summary["attachment_urls_other"] = sum(
            1 for status in status_map.values() if status not in (200, 404)
        )

    download_remaining = download_limit if download_limit else None
    if download_attachments and attachment_urls:
        output_root = build_output_dir(output_dir)
        for index, row in enumerate(results, start=1):
            project_id = select_project_id(row, index)
            urls = [u for u in row.get("attachment_urls", "").split(";") if u.strip()]
            if not urls:
                continue
            downloaded = []
            for url in urls:
                if download_remaining is not None and download_remaining <= 0:
                    break
                status = status_map.get(url)
                if status not in (None, 200):
                    continue
                filename = sanitize_filename(filename_from_url(url))
                if not filename:
                    filename = "document"
                destination = output_root / "attachments" / project_id / filename
                summary["attachment_download_attempted"] += 1
                if download_attachment(url, destination, attachment_timeout):
                    summary["attachment_downloaded"] += 1
                    downloaded.append(url)
                    if download_remaining is not None:
                        download_remaining -= 1
            row["attachment_downloaded"] = ";".join(downloaded)

    if status_map:
        for row in results:
            urls = [u for u in row.get("attachment_urls", "").split(";") if u.strip()]
            working = [u for u in urls if status_map.get(u) == 200]
            missing = [u for u in urls if status_map.get(u) == 404]
            unchecked = [
                u
                for u in urls
                if status_map.get(u) not in (200, 404)
            ]
            row["attachment_working"] = ";".join(working)
            row["attachment_missing"] = ";".join(missing)
            row["attachment_unchecked"] = ";".join(unchecked)

    output_root = build_output_dir(output_dir)
    summary["markdown_count"] = write_project_markdowns(output_root, results)
    summary["markdown_dir"] = str((output_root / "projects").resolve())
    csv_path, json_path = write_outputs(output_root, results, summary)
    return csv_path, json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter CanadaBuys open tender notices for Alberta + UNSPSC/keyword matches."
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_name("config.json")),
        help="Path to config.json (default: pipelines/canadabuys/config.json).",
    )
    parser.add_argument(
        "--source",
        default="open",
        help="Data source: open, new, or a URL/path to a CSV file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: output/canadabuys).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Process only the first N rows (useful for quick tests).",
    )
    parser.add_argument(
        "--check-attachments",
        action="store_true",
        help="Check attachment URLs with HEAD requests and label markdown links.",
    )
    parser.add_argument(
        "--attachment-check-limit",
        type=int,
        default=0,
        help="Limit attachment checks to the first N unique URLs (0 = no limit).",
    )
    parser.add_argument(
        "--attachment-timeout",
        type=int,
        default=20,
        help="Timeout in seconds for attachment checks/downloads.",
    )
    parser.add_argument(
        "--download-attachments",
        action="store_true",
        help="Download attachment files to output/canadabuys/attachments.",
    )
    parser.add_argument(
        "--download-limit",
        type=int,
        default=10,
        help="Maximum number of attachments to download (0 = no limit).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.download_attachments and not args.check_attachments:
        args.check_attachments = True
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1
    csv_path, json_path = run_pipeline(
        config_path,
        args.source,
        args.output_dir,
        args.max_rows,
        args.check_attachments,
        args.attachment_check_limit,
        args.attachment_timeout,
        args.download_attachments,
        args.download_limit,
    )
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
