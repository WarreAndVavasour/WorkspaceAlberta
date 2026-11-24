"""Historical Contract Awards & Competitor Intelligence (CanadaBuys + Alberta APC).

Answers the highest-value pre-bid question an estimator asks before investing
20+ hours into a proposal:
- Who won this buyer's past similar contracts?
- What were the actual award amounts (min / median / max CAD)?
- Is there an entrenched repeat winner (incumbent)?
- On Alberta APC, how many interested suppliers competed on similar postings?

Design:
- **Zero LLM / zero per-query COGS.** Pure deterministic Python + stdlib SQLite.
- **Memory-safe on Cloud Run (512 MiB):** CanadaBuys fiscal-year award CSVs
  (current + previous Canadian federal fiscal year, Apr-Mar) are streamed row by
  row into a slimmed SQLite index at ``DATA_DIR/awards.db`` (dropping French
  duplicates and contact boilerplate). Peak RAM stays under ~20 MB; queries run
  in milliseconds.
- **Alberta APC live awards:** queries ``purchasing.alberta.ca/api`` with
  ``status="AWARD"`` and fetches bounded details (4 workers, max 8 postings) to
  extract winning supplier names, award values, award dates, and interested
  supplier counts.
- **Offline / fixture support:** honours ``PROCUREMENT_FIXTURE_DIR/awards.csv``
  and ``CANADABUYS_AWARDS_URLS`` for fast deterministic unit tests.
"""

from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

AWARDS_DB_FILENAME = "awards.db"
AWARDS_CACHE_TTL_SECONDS = 24 * 60 * 60
AWARDS_DOWNLOAD_TIMEOUT = 90
APC_AWARD_DETAIL_CAP = 8
APC_AWARD_WORKERS = 4
USER_AGENT = "WorkspaceAlberta-Awards/1.0"

_STOP_WORDS = frozenset(
    {
        "the", "and", "for", "with", "from", "that", "this", "into", "over",
        "canada", "canadian", "alberta", "government", "public", "services",
        "service", "supply", "project", "contract", "tender", "notice",
        "request", "proposal", "rfp", "rfq", "rft", "standing", "offer",
        "arrangement", "department", "ministry", "city", "town", "county",
        "general", "various", "annual", "phase", "year", "years", "work",
    }
)


def current_fiscal_years(now: datetime | None = None, count: int = 2) -> list[str]:
    """Return the most recent Canadian federal fiscal year labels (Apr 1 - Mar 31)."""
    dt = now or datetime.now(timezone.utc)
    start_year = dt.year if dt.month >= 4 else dt.year - 1
    return [f"{start_year - i}-{start_year - i + 1}" for i in range(max(1, count))]


def award_csv_urls(now: datetime | None = None) -> list[tuple[str, str]]:
    """Return ``[(fiscal_year, url), ...]`` for CanadaBuys award notices."""
    override = os.environ.get("CANADABUYS_AWARDS_URLS", "").strip()
    if override:
        items: list[tuple[str, str]] = []
        for idx, raw in enumerate(override.split(",")):
            url = raw.strip()
            if url:
                items.append((f"custom-{idx + 1}", url))
        if items:
            return items
    return [
        (fy, f"https://canadabuys.canada.ca/opendata/pub/{fy}-awardNotice-avisAttribution.csv")
        for fy in current_fiscal_years(now=now, count=2)
    ]


def awards_db_path() -> Path:
    from procurement_core import service

    return Path(service.DATA_DIR) / AWARDS_DB_FILENAME


def _parse_amount(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "").replace("$", "")
    if not text:
        return None
    try:
        val = float(text)
    except ValueError:
        return None
    return val if val > 0 else None


def _clean_multiline(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    parts = [line.lstrip("* ").strip() for line in text.splitlines() if line.strip()]
    return "; ".join(parts)


def _normalize_canadabuys_award_row(row: dict[str, str], fiscal_year: str) -> tuple[Any, ...] | None:
    title = (row.get("title-titre-eng") or "").strip()
    supplier = (row.get("supplierLegalName-nomLegalFournisseur-eng") or "").strip()
    buyer = (row.get("contractingEntityName-nomEntitContractante-eng") or "").strip()
    if not (title or supplier or buyer):
        return None
    amount = _parse_amount(row.get("contractAmount-montantContrat")) or _parse_amount(
        row.get("totalContractValue-valeurTotaleContrat")
    )
    return (
        (row.get("referenceNumber-numeroReference") or "").strip(),
        (row.get("solicitationNumber-numeroSollicitation") or "").strip(),
        title,
        buyer,
        _clean_multiline(row.get("endUserEntitiesName-nomEntitesUtilisateurFinal-eng")),
        supplier,
        (row.get("supplierAddressCity-fournisseurAdresseVille-eng") or "").strip(),
        (row.get("supplierAddressProvince-fournisseurAdresseProvince-eng") or "").strip(),
        amount,
        (row.get("contractCurrency-contratMonnaie") or "CAD").strip() or "CAD",
        (row.get("contractAwardDate-dateAttributionContrat") or row.get("publicationDate-datePublication") or "").strip(),
        _clean_multiline(row.get("unspsc")),
        _clean_multiline(row.get("unspscDescription-eng")),
        _clean_multiline(row.get("gsin-nibs")),
        _clean_multiline(row.get("gsinDescription-nibsDescription-eng")),
        _clean_multiline(row.get("regionsOfDelivery-regionsLivraison-eng")),
        (row.get("procurementMethod-methodeApprovisionnement-eng") or "").strip(),
        (row.get("awardDescription-descriptionAttribution-eng") or "").strip()[:500],
        fiscal_year,
    )


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT,
            solicitation TEXT,
            title TEXT,
            buyer TEXT,
            end_user TEXT,
            supplier TEXT,
            supplier_city TEXT,
            supplier_province TEXT,
            amount REAL,
            currency TEXT,
            award_date TEXT,
            unspsc TEXT,
            unspsc_description TEXT,
            gsin TEXT,
            gsin_description TEXT,
            region TEXT,
            procurement_method TEXT,
            description TEXT,
            fiscal_year TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_date ON awards(award_date DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_buyer ON awards(buyer)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_awards_supplier ON awards(supplier)")


def _ingest_csv_stream(conn: sqlite3.Connection, text_stream: io.TextIOBase, fiscal_year: str) -> int:
    reader = csv.DictReader(text_stream)
    batch: list[tuple[Any, ...]] = []
    inserted = 0
    sql = (
        "INSERT INTO awards ("
        "reference, solicitation, title, buyer, end_user, supplier, supplier_city, "
        "supplier_province, amount, currency, award_date, unspsc, unspsc_description, "
        "gsin, gsin_description, region, procurement_method, description, fiscal_year"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    for row in reader:
        rec = _normalize_canadabuys_award_row(row, fiscal_year)
        if rec is None:
            continue
        batch.append(rec)
        if len(batch) >= 1000:
            conn.executemany(sql, batch)
            inserted += len(batch)
            batch.clear()
    if batch:
        conn.executemany(sql, batch)
        inserted += len(batch)
    return inserted


def _fixture_awards_csv() -> Path | None:
    fixture_dir = os.environ.get("PROCUREMENT_FIXTURE_DIR", "").strip()
    if not fixture_dir:
        return None
    candidate = Path(fixture_dir) / "awards.csv"
    return candidate if candidate.exists() else None


def ensure_awards_cache(*, force_refresh: bool = False, allow_network: bool = True) -> tuple[Path | None, list[str]]:
    """Build or refresh the local SQLite cache of CanadaBuys award notices.

    Returns ``(db_path_or_none, warnings)``. Never raises on upstream errors so
    Alberta APC awards can still answer if CanadaBuys open data is slow.
    """
    warnings: list[str] = []
    db_path = awards_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    fixture_csv = _fixture_awards_csv()
    if fixture_csv is not None:
        if force_refresh or not db_path.exists():
            tmp = db_path.with_suffix(".db.tmp")
            if tmp.exists():
                tmp.unlink()
            conn = sqlite3.connect(str(tmp))
            try:
                _init_db(conn)
                with fixture_csv.open("r", encoding="utf-8-sig", newline="") as fh:
                    count = _ingest_csv_stream(conn, fh, "fixture")
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    ("built_at", str(int(time.time()))),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                    ("row_count", str(count)),
                )
                conn.commit()
            finally:
                conn.close()
            tmp.replace(db_path)
        return db_path, warnings

    if db_path.exists() and not force_refresh:
        age = time.time() - db_path.stat().st_mtime
        if age < AWARDS_CACHE_TTL_SECONDS:
            return db_path, warnings

    if not allow_network:
        return (db_path if db_path.exists() else None), warnings

    tmp = db_path.with_suffix(".db.tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    total_rows = 0
    loaded_fys: list[str] = []
    try:
        _init_db(conn)
        for fy, url in award_csv_urls():
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"})
            try:
                with urlopen(req, timeout=AWARDS_DOWNLOAD_TIMEOUT) as resp:
                    text_stream = io.TextIOWrapper(resp, encoding="utf-8-sig", errors="replace", newline="")
                    rows_added = _ingest_csv_stream(conn, text_stream, fy)
                    total_rows += rows_added
                    loaded_fys.append(fy)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                warnings.append(f"CanadaBuys award notices ({fy}) unavailable: {exc}")
        if total_rows > 0:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("built_at", str(int(time.time()))),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("fiscal_years", ",".join(loaded_fys)),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("row_count", str(total_rows)),
            )
            conn.commit()
    finally:
        conn.close()

    if total_rows > 0:
        tmp.replace(db_path)
        return db_path, warnings
    if tmp.exists():
        tmp.unlink()
    if db_path.exists():
        warnings.append("Using previously cached CanadaBuys awards snapshot.")
        return db_path, warnings
    return None, warnings


def _tokenize_terms(text: str, limit: int = 5) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", (text or "").lower())
    out: list[str] = []
    for w in words:
        if w in _STOP_WORDS or w.isdigit():
            continue
        if w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def _extract_code_prefix(raw: str) -> str:
    match = re.search(r"\b(\d{4,8})\b", str(raw or ""))
    if not match:
        return ""
    code = match.group(1)
    return code[:4] if len(code) >= 4 else code


def query_canadabuys_awards(
    *,
    buyer: str = "",
    keywords: str = "",
    unspsc: str = "",
    gsin: str = "",
    province: str = "",
    supplier: str = "",
    limit: int = 25,
    allow_network: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Query cached CanadaBuys historical contract awards."""
    db_path, warnings = ensure_awards_cache(allow_network=allow_network)
    if db_path is None:
        return [], warnings

    clauses: list[str] = []
    params: list[Any] = []

    if buyer.strip():
        buyer_tokens = [t for t in re.split(r"[\s,/&-]+", buyer.strip()) if len(t) >= 3][:3]
        if buyer_tokens:
            sub = " AND ".join("(lower(buyer) LIKE ? OR lower(end_user) LIKE ?)" for _ in buyer_tokens)
            clauses.append(f"({sub})")
            for tok in buyer_tokens:
                like = f"%{tok.lower()}%"
                params.extend([like, like])

    if supplier.strip():
        clauses.append("lower(supplier) LIKE ?")
        params.append(f"%{supplier.strip().lower()}%")

    if province.strip():
        p = f"%{province.strip().lower()}%"
        clauses.append("(lower(region) LIKE ? OR lower(supplier_province) LIKE ?)")
        params.extend([p, p])

    code_filters: list[str] = []
    unspsc_prefix = _extract_code_prefix(unspsc)
    if unspsc_prefix:
        code_filters.append("unspsc LIKE ?")
        params.append(f"%{unspsc_prefix}%")
    if gsin.strip():
        code_filters.append("lower(gsin) LIKE ?")
        params.append(f"%{gsin.strip().lower()[:6]}%")

    kw_terms = _tokenize_terms(keywords, limit=4)
    kw_filters: list[str] = []
    for tok in kw_terms:
        like = f"%{tok}%"
        kw_filters.append(
            "(lower(title) LIKE ? OR lower(unspsc_description) LIKE ? OR lower(gsin_description) LIKE ? OR lower(description) LIKE ?)"
        )
        params.extend([like, like, like, like])

    if code_filters and kw_filters:
        clauses.append(f"(({' OR '.join(code_filters)}) OR ({' OR '.join(kw_filters)}))")
    elif code_filters:
        clauses.append(f"({' OR '.join(code_filters)})")
    elif kw_filters:
        # Require at least one keyword match across title/descriptions
        clauses.append(f"({' OR '.join(kw_filters)})")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    fetch_limit = min(200, max(limit * 4, 40))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT reference, solicitation, title, buyer, end_user, supplier,
                   supplier_city, supplier_province, amount, currency, award_date,
                   unspsc, unspsc_description, gsin, gsin_description, region,
                   procurement_method, fiscal_year
            FROM awards
            {where_sql}
            ORDER BY award_date DESC, amount DESC
            LIMIT ?
            """,
            (*params, fetch_limit),
        ).fetchall()
    finally:
        conn.close()

    # Score rows so exact multi-keyword + buyer + UNSPSC matches rise to the top.
    scored: list[tuple[int, str, dict[str, Any]]] = []
    buyer_l = buyer.strip().lower()
    for row in rows:
        item = dict(row)
        hay = f"{item['title']} {item['unspsc_description']} {item['gsin_description']}".lower()
        score = 0
        if buyer_l and (buyer_l in (item["buyer"] or "").lower() or buyer_l in (item["end_user"] or "").lower()):
            score += 20
        if unspsc_prefix and unspsc_prefix in (item["unspsc"] or ""):
            score += 15
        for tok in kw_terms:
            if tok in hay:
                score += 10
        if item.get("amount"):
            score += 2
        loc = ", ".join(p for p in (item.get("supplier_city"), item.get("supplier_province")) if p)
        normalized = {
            "source": "CanadaBuys",
            "reference": item["reference"] or item["solicitation"],
            "title": item["title"],
            "buyer": item["buyer"] or item["end_user"],
            "supplier": item["supplier"] or "Not listed",
            "supplier_location": loc,
            "amount": item["amount"],
            "currency": item["currency"] or "CAD",
            "award_date": item["award_date"],
            "unspsc": item["unspsc"],
            "region": item["region"],
            "procurement_method": item["procurement_method"],
            "interested_suppliers": None,
            "url": (
                f"https://canadabuys.canada.ca/en/tender-opportunities/award-notice/{item['reference']}"
                if item["reference"]
                else ""
            ),
        }
        scored.append((score, item["award_date"] or "", normalized))

    scored.sort(key=lambda pair: (pair[0], pair[1]), reverse=True)
    return [entry for _, _, entry in scored[:limit]], warnings


def _extract_apc_award_record(detail: dict[str, Any], fallback_item: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn an APC opportunity detail response into one normalized award per winner."""
    opp = detail.get("opportunity") or {}
    ref = str(opp.get("referenceNumber") or fallback_item.get("referenceNumber") or "").strip()
    title = str(opp.get("shortTitle") or fallback_item.get("shortTitle") or "").strip()
    buyer = str(
        opp.get("contractingOrganizationName")
        or fallback_item.get("purchasingOrganization")
        or (detail.get("contractingEntityContactInformation") or {}).get("organizationName")
        or "Alberta public sector"
    ).strip()
    interested_count = len(detail.get("interestedSuppliers") or [])
    bidders_count = len(detail.get("bidders") or [])
    awards = detail.get("awards") or []
    url = f"https://purchasing.alberta.ca/posting/{ref}" if ref else ""

    records: list[dict[str, Any]] = []
    if awards:
        for aw in awards:
            supplier = (
                aw.get("alternativeSupplierDisplayName")
                or aw.get("operatingOrTradeName")
                or "Not listed"
            )
            addr = aw.get("address") or {}
            loc = ", ".join(p for p in (addr.get("city"), addr.get("stateProvince")) if p)
            amount = _parse_amount(aw.get("amount")) or _parse_amount(opp.get("actualValue"))
            award_date = str(aw.get("awardDate") or opp.get("awardedOnUtc") or "")[:10]
            records.append(
                {
                    "source": "Alberta APC",
                    "reference": ref,
                    "title": title,
                    "buyer": buyer,
                    "supplier": str(supplier).strip(),
                    "supplier_location": loc,
                    "amount": amount,
                    "currency": "CAD",
                    "award_date": award_date,
                    "unspsc": "",
                    "region": "Alberta",
                    "procurement_method": str(opp.get("solicitationTypeCode") or ""),
                    "interested_suppliers": interested_count or None,
                    "bidders_count": bidders_count or None,
                    "url": url,
                }
            )
    elif opp.get("actualValue") or opp.get("awardedOnUtc"):
        records.append(
            {
                "source": "Alberta APC",
                "reference": ref,
                "title": title,
                "buyer": buyer,
                "supplier": "Not disclosed on posting",
                "supplier_location": "",
                "amount": _parse_amount(opp.get("actualValue")),
                "currency": "CAD",
                "award_date": str(opp.get("awardedOnUtc") or "")[:10],
                "unspsc": "",
                "region": "Alberta",
                "procurement_method": str(opp.get("solicitationTypeCode") or ""),
                "interested_suppliers": interested_count or None,
                "bidders_count": bidders_count or None,
                "url": url,
            }
        )
    return records


def query_alberta_awards(
    *,
    buyer: str = "",
    keywords: str = "",
    supplier: str = "",
    limit: int = 8,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Query live Alberta Purchasing Connection awarded opportunities."""
    from procurement_core import service

    warnings: list[str] = []
    search_terms = " ".join(part for part in (keywords.strip(), buyer.strip(), supplier.strip()) if part).strip()
    search_limit = min(APC_AWARD_DETAIL_CAP, max(1, limit))
    try:
        resp = service.search_alberta_api(
            query=search_terms[:120],
            status="AWARD",
            limit=search_limit,
            timeout=6,
        )
    except Exception as exc:  # noqa: BLE001
        return [], [f"Alberta APC award search unavailable: {exc}"]

    raw_items = resp.get("values") or []
    if not raw_items and buyer.strip() and keywords.strip():
        # Retry with keywords only if buyer+keywords was overly narrow.
        try:
            resp = service.search_alberta_api(
                query=keywords.strip()[:120],
                status="AWARD",
                limit=search_limit,
                timeout=6,
            )
            raw_items = resp.get("values") or []
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Alberta APC award fallback search unavailable: {exc}")
            raw_items = []

    refs = [
        (str(item.get("referenceNumber") or "").strip(), item)
        for item in raw_items[:APC_AWARD_DETAIL_CAP]
        if item.get("referenceNumber")
    ]
    if not refs:
        return [], warnings

    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=APC_AWARD_WORKERS) as pool:
        futures = {pool.submit(service.get_alberta_api_details, ref): (ref, item) for ref, item in refs}
        for future in as_completed(futures):
            ref, item = futures[future]
            try:
                detail = future.result()
            except Exception:  # noqa: BLE001
                continue
            records.extend(_extract_apc_award_record(detail, item))

    if supplier.strip():
        sup_l = supplier.strip().lower()
        records = [r for r in records if sup_l in (r.get("supplier") or "").lower()]

    records.sort(key=lambda r: (r.get("award_date") or "", r.get("amount") or 0), reverse=True)
    return records[:limit], warnings


def summarize_awards(awards: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute pricing stats, winning supplier concentration, and incumbent signals."""
    amounts = [float(a["amount"]) for a in awards if a.get("amount") is not None and float(a["amount"]) > 0]
    interested = [int(a["interested_suppliers"]) for a in awards if a.get("interested_suppliers")]

    supplier_counts: Counter[str] = Counter()
    supplier_totals: defaultdict[str, float] = defaultdict(float)
    for aw in awards:
        name = str(aw.get("supplier") or "").strip()
        if not name or name.lower().startswith("not "):
            continue
        supplier_counts[name] += 1
        if aw.get("amount"):
            supplier_totals[name] += float(aw["amount"])

    total_named = sum(supplier_counts.values())
    top_suppliers = []
    incumbents = []
    for name, wins in supplier_counts.most_common(5):
        share = round(wins / total_named, 2) if total_named else 0.0
        entry = {
            "supplier": name,
            "wins": wins,
            "share": share,
            "total_awarded_cad": round(supplier_totals[name], 2),
        }
        top_suppliers.append(entry)
        if wins >= 2 or (total_named >= 3 and share >= 0.4):
            incumbents.append(entry)

    return {
        "count": len(awards),
        "priced_count": len(amounts),
        "min_cad": round(min(amounts), 2) if amounts else None,
        "median_cad": round(statistics.median(amounts), 2) if amounts else None,
        "max_cad": round(max(amounts), 2) if amounts else None,
        "total_cad": round(sum(amounts), 2) if amounts else None,
        "avg_interested_suppliers": round(sum(interested) / len(interested), 1) if interested else None,
        "top_suppliers": top_suppliers,
        "incumbents": incumbents,
    }


def _fmt_cad(amount: float | None) -> str:
    if amount is None:
        return "Not disclosed"
    return f"C${amount:,.0f}" if amount >= 1000 else f"C${amount:,.2f}"


def quick_cached_award_teaser(opportunity: dict[str, Any]) -> str:
    """Fast, zero-network teaser for free bid/no-bid scorecards using local awards.db."""
    buyer = str(opportunity.get("buyer") or "").strip()
    unspsc = str(opportunity.get("unspsc") or "").strip()
    title = str(opportunity.get("title") or "").strip()
    kw = " ".join(_tokenize_terms(title, limit=3))
    awards, _ = query_canadabuys_awards(
        buyer=buyer,
        keywords=kw,
        unspsc=unspsc,
        limit=10,
        allow_network=False,
    )
    if not awards:
        return (
            "Run `get_buyer_award_history` with this reference to inspect historical winners, "
            "contract values, and incumbent concentration across CanadaBuys and Alberta APC."
        )
    stats = summarize_awards(awards)
    range_txt = (
        f" (median {_fmt_cad(stats['median_cad'])}, range {_fmt_cad(stats['min_cad'])}–{_fmt_cad(stats['max_cad'])})"
        if stats["median_cad"] is not None
        else ""
    )
    incumbent_hint = (
        f"; repeat winner detected ({stats['incumbents'][0]['wins']} wins)"
        if stats["incumbents"]
        else ""
    )
    return (
        f"{stats['count']} comparable historical award(s) found{range_txt}{incumbent_hint}. "
        "Run `get_buyer_award_history` to see winning suppliers, award values, and competition data."
    )


def build_bid_room_award_context(opportunity: dict[str, Any]) -> str:
    """Compact historical awards context block for Cohere/Bid Room prompts (local cache only)."""
    buyer = str(opportunity.get("buyer") or "").strip()
    unspsc = str(opportunity.get("unspsc") or "").strip()
    title = str(opportunity.get("title") or "").strip()
    kw = " ".join(_tokenize_terms(title, limit=3))
    awards, _ = query_canadabuys_awards(
        buyer=buyer,
        keywords=kw,
        unspsc=unspsc,
        limit=6,
        allow_network=False,
    )
    if not awards:
        return ""
    stats = summarize_awards(awards)
    lines = [
        f"Historical comparable awards ({stats['count']} found; median {_fmt_cad(stats['median_cad'])}, "
        f"range {_fmt_cad(stats['min_cad'])}-{_fmt_cad(stats['max_cad'])}):"
    ]
    for aw in awards[:5]:
        lines.append(
            f"- {aw['award_date'] or 'n/a'} | {aw['supplier']} | {_fmt_cad(aw['amount'])} | {aw['buyer']} | {aw['title'][:70]}"
        )
    if stats["incumbents"]:
        top = stats["incumbents"][0]
        lines.append(
            f"Repeat winner signal: {top['supplier']} ({top['wins']} wins, {_fmt_cad(top['total_awarded_cad'])} total)."
        )
    return "\n".join(lines)


def render_awards_markdown(
    awards: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    heading: str,
    context_note: str = "",
    warnings: list[str] | None = None,
) -> str:
    lines = [f"# {heading}", ""]
    if context_note:
        lines.extend([context_note, ""])

    if not awards:
        lines.append("No matching historical contract awards were found for those filters.")
        lines.append("")
        lines.append("Try broadening `keywords`, removing `province`, or searching by `buyer` alone.")
    else:
        lines.append("## Pricing & Competition Summary")
        lines.append(f"- **Matching awards:** {summary['count']} ({summary['priced_count']} with disclosed value)")
        if summary["median_cad"] is not None:
            lines.append(
                f"- **Award range:** {_fmt_cad(summary['min_cad'])} – {_fmt_cad(summary['max_cad'])} "
                f"(**median {_fmt_cad(summary['median_cad'])}**, total {_fmt_cad(summary['total_cad'])})"
            )
        if summary["avg_interested_suppliers"] is not None:
            lines.append(
                f"- **Avg. interested suppliers (Alberta APC):** {summary['avg_interested_suppliers']} firms downloaded the package"
            )
        if summary["incumbents"]:
            inc_text = ", ".join(
                f"**{i['supplier']}** ({i['wins']} wins, {_fmt_cad(i['total_awarded_cad'])})"
                for i in summary["incumbents"][:3]
            )
            lines.append(f"- **Potential incumbent(s):** {inc_text}")
        elif summary["top_suppliers"]:
            lines.append("- **Incumbent signal:** No single repeat winner dominated this sample.")
        lines.append("")

        if summary["top_suppliers"]:
            lines.append("## Top Winning Suppliers")
            for sup in summary["top_suppliers"]:
                pct = int(round(sup["share"] * 100))
                lines.append(
                    f"- **{sup['supplier']}** — {sup['wins']} win{'s' if sup['wins'] != 1 else ''} "
                    f"({pct}% of named awards, {_fmt_cad(sup['total_awarded_cad'])})"
                )
            lines.append("")

        lines.append("## Recent Comparable Awards")
        lines.append("| Date | Winning Supplier | Award Value | Buyer | Title | Source |")
        lines.append("|---|---|---|---|---|---|")
        for aw in awards:
            date_s = aw.get("award_date") or "—"
            sup_s = aw.get("supplier") or "Not listed"
            if aw.get("supplier_location"):
                sup_s = f"{sup_s} ({aw['supplier_location']})"
            amt_s = _fmt_cad(aw.get("amount"))
            if aw.get("interested_suppliers"):
                amt_s += f" · {aw['interested_suppliers']} interested"
            buyer_s = str(aw.get("buyer") or "—")[:45].replace("|", "/")
            title_s = str(aw.get("title") or "—")[:65].replace("|", "/")
            ref = aw.get("reference") or ""
            src_s = f"[{aw.get('source', '')}]({aw['url']})" if aw.get("url") else f"{aw.get('source', '')} `{ref}`"
            lines.append(f"| {date_s} | {sup_s.replace('|', '/')} | {amt_s} | {buyer_s} | {title_s} | {src_s} |")
        lines.append("")

    lines.append(
        "---"
        "\n*Historical contract awards are public market intelligence from CanadaBuys open data and Alberta Purchasing Connection. "
        "Past prices and winners inform bid/no-bid judgment and pricing sanity checks; they do not predict future bids or guarantee eligibility.*"
    )
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings[:4]:
            lines.append(f"- {w}")
    return "\n".join(lines)


async def get_buyer_award_history_result(args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Run unified historical award lookup and return ``(markdown, structured_payload)``."""
    from procurement_core import extensions, service

    reference = str(args.get("reference") or "").strip()
    buyer = str(args.get("buyer") or "").strip()
    keywords = str(args.get("keywords") or "").strip()
    unspsc = str(args.get("unspsc") or "").strip()
    gsin = str(args.get("gsin") or "").strip()
    province = str(args.get("province") or "").strip()
    supplier = str(args.get("supplier") or "").strip()
    source = str(args.get("source") or "all").strip().lower()
    limit = service.clamp_int(args.get("limit"), default=15, minimum=1, maximum=40)

    warnings: list[str] = []
    resolved_ref: dict[str, Any] | None = None
    context_note = ""

    if reference:
        opp, ref_warnings = extensions._find_opportunity(reference)
        warnings.extend(ref_warnings)
        if opp:
            resolved_ref = opp
            if not buyer:
                buyer = str(opp.get("buyer") or "").strip()
            if not unspsc:
                unspsc = str(opp.get("unspsc") or "").strip()
            if not gsin:
                gsin = str(opp.get("gsin") or "").strip()
            if not keywords:
                keywords = " ".join(_tokenize_terms(str(opp.get("title") or ""), limit=4))
            if source == "all" and opp.get("source_key") == "alberta":
                province = province or "Alberta"
            context_note = (
                f"Resolved from live reference `{reference}` (**{str(opp.get('title') or '')[:80]}**) · "
                f"Buyer: `{buyer or 'any'}` · Keywords: `{keywords or 'any'}`"
                + (f" · UNSPSC: `{unspsc[:8]}`" if unspsc else "")
            )
        else:
            warnings.append(f"Could not resolve live reference '{reference}'; searching directly with supplied filters.")

    if not any((buyer, keywords, unspsc, gsin, supplier, province)):
        msg = (
            "Provide a `reference` (e.g. `AB-2026-06788`), `buyer`, `keywords`, `unspsc`, or `supplier` "
            "to look up historical contract awards."
        )
        return msg, {"kind": "award_history", "count": 0, "warnings": warnings, "summary": {}, "awards": []}

    want_federal = source in {"", "all", "both", "federal", "canadabuys", "canada", "national"}
    want_alberta = source in {"", "all", "both", "alberta", "apc"}
    if province and "alberta" not in province.lower() and source == "all":
        want_alberta = False

    awards: list[dict[str, Any]] = []
    if want_federal:
        fed_awards, fed_warnings = query_canadabuys_awards(
            buyer=buyer,
            keywords=keywords,
            unspsc=unspsc,
            gsin=gsin,
            province=province,
            supplier=supplier,
            limit=limit,
        )
        awards.extend(fed_awards)
        warnings.extend(fed_warnings)

    if want_alberta:
        ab_awards, ab_warnings = query_alberta_awards(
            buyer=buyer,
            keywords=keywords,
            supplier=supplier,
            limit=min(APC_AWARD_DETAIL_CAP, limit),
        )
        awards.extend(ab_awards)
        warnings.extend(ab_warnings)

    awards.sort(key=lambda a: (a.get("award_date") or "", a.get("amount") or 0), reverse=True)
    awards = awards[:limit]
    summary = summarize_awards(awards)

    heading = (
        f"Historical Contract Awards — `{reference}`"
        if reference
        else f"Historical Contract Awards — {buyer or supplier or keywords or unspsc}"
    )
    markdown = render_awards_markdown(
        awards,
        summary,
        heading=heading,
        context_note=context_note,
        warnings=warnings,
    )
    structured = {
        "kind": "award_history",
        "reference": reference or None,
        "resolved_buyer": buyer or None,
        "count": len(awards),
        "summary": summary,
        "warnings": warnings,
        "awards": awards,
    }
    return markdown, structured


async def get_buyer_award_history(args: dict[str, Any]) -> str:
    markdown, _ = await get_buyer_award_history_result(args)
    return markdown
