"""Read-only Oil Sands Growth Program catalog.

The catalog is a checked-in JSON file of what official pages said when they
were retrieved. It is not an application, an eligibility ruling, or a live
scrape. A refresh only checks that the official release still contains the
program name. If that check fails, the stored copy is returned with a warning.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CATALOG_PATH = Path(__file__).resolve().parent / "content" / "oil_sands_growth.json"
RELEASE_MARKER = "Oil Sands Growth Program"
TOPICS = ("overview", "eligibility", "royalty", "timeline", "pipelines", "suppliers", "sources")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Return the Oil Sands Growth Program catalog. Cached for the process lifetime."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _sources(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in catalog.get("sources") or []}


def _source_line(source: dict[str, Any] | None) -> str:
    if not source:
        return ""
    published = f", published {source['published']}" if source.get("published") else ""
    retrieved = source.get("retrieved_on") or ""
    return (
        f"{source.get('publisher', '')}: [{source.get('title', 'Source')}]({source.get('url', '')})"
        f"{published}. Retrieved {retrieved}."
    )


def _header(catalog: dict[str, Any], title: str) -> list[str]:
    program = catalog["program"]
    lines = [
        f"# {title}",
        "",
        catalog.get("disclaimer", ""),
        "",
        f"**Retrieved:** {catalog.get('retrieved_on', '')}. "
        f"**Catalog:** {catalog.get('catalog_version', '')}.",
        f"**Official release:** [{program.get('official_release_title', 'Release')}]"
        f"({program.get('official_release_url', '')}), {program.get('announced', '')}.",
        "",
    ]
    return lines


def confirm_official_release(fetch: Any = None, timeout: float = 8) -> dict[str, str]:
    """Check that the stored release URL still contains the program name.

    A failure leaves the stored catalog in place. This does not parse new rules
    out of the page.
    """
    catalog = load_catalog()
    url = str(catalog["program"].get("official_release_url") or "")
    opener = fetch or urlopen
    try:
        request = Request(url, headers={"User-Agent": "workspaceAlberta oil-sands-growth catalog"})
        with opener(request, timeout=timeout) as response:
            raw = response.read(200_000)
        text = raw.decode("utf-8", "replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {
            "ok": "false",
            "url": url,
            "note": (
                f"Live check failed ({exc.__class__.__name__}). "
                f"Showing the copy retrieved {catalog.get('retrieved_on', '')}."
            ),
        }
    if RELEASE_MARKER in text:
        return {
            "ok": "true",
            "url": url,
            "note": "The official release URL still contains the program name. No new rules were parsed from the page.",
        }
    return {
        "ok": "false",
        "url": url,
        "note": (
            "The page loaded but the program name was not found. "
            f"Showing the copy retrieved {catalog.get('retrieved_on', '')}."
        ),
    }


def _section_overview(catalog: dict[str, Any]) -> list[str]:
    program = catalog["program"]
    lines = [
        "## What it is",
        "",
        program.get("summary", ""),
        "",
        f"- **Administrator:** {program.get('administrator', '')}",
        f"- **Status:** Announced {program.get('announced', '')}. Detailed rules were not published on the pages retrieved {catalog.get('retrieved_on', '')}.",
        f"- **Mechanism:** {program.get('mechanism', '')}",
        "",
    ]
    return lines


def _section_royalty(catalog: dict[str, Any]) -> list[str]:
    schedule = catalog.get("royalty_schedule") or {}
    lines = ["## Royalty framework", "", schedule.get("basis", ""), "", schedule.get("note", ""), ""]
    for step in schedule.get("years") or []:
        lines.append(f"- **{step.get('label', '')}:** {step.get('rate_percent', '')} per cent")
    lines.append("")
    lines.append("After the 10-year framework, the written release does not itself say which royalty regime applies. CBC reported a return to the regular regime. That point is under reported remarks, not in the release.")
    lines.append("")
    return lines


def _section_eligibility(catalog: dict[str, Any]) -> list[str]:
    lines = ["## Eligibility, as published", ""]
    for point in catalog.get("official_points") or []:
        lines.append(f"- {point}")
    lines.append("")
    lines.append("### Reported at the news conference, not in the written release")
    lines.append("")
    sources = _sources(catalog)
    for item in catalog.get("reported_not_in_release") or []:
        source = sources.get(str(item.get("source_id")))
        lines.append(f"- {item.get('text', '')}")
        if source:
            lines.append(f"  - Source: {_source_line(source)}")
    lines.append("")
    lines.append("### Not confirmed")
    lines.append("")
    for item in catalog.get("unconfirmed") or []:
        lines.append(f"- {item}")
    lines.append("")
    context = catalog.get("current_royalty_context") or {}
    if context:
        lines.append("### Current royalty regime, for context")
        lines.append("")
        lines.append(context.get("text", ""))
        source = sources.get(str(context.get("source_id")))
        if source:
            lines.append("")
            lines.append(f"Source: {_source_line(source)}")
        lines.append("")
    return lines


def _section_timeline(catalog: dict[str, Any]) -> list[str]:
    lines = ["## Timeline", ""]
    for point in catalog.get("official_points") or []:
        if any(token in point for token in ("2026", "2027", "2029", "2040", "2060")):
            lines.append(f"- {point}")
    lines.append("")
    lines.append(
        "A 2035 production year and a possible end-of-2029 construction deadline were reported "
        "from the news conference. They are not in the written release. See the eligibility section."
    )
    lines.append("")
    return lines


def _section_pipelines(catalog: dict[str, Any]) -> list[str]:
    sources = _sources(catalog)
    lines = ["## Pipelines and related projects", ""]
    for item in catalog.get("pipelines") or []:
        lines.append(f"### {item.get('name', 'Project')}")
        lines.append("")
        lines.append(item.get("detail", ""))
        lines.append("")
        for source_id in item.get("urls") or []:
            if source_id == "release":
                continue
            source = sources.get(str(source_id))
            if source:
                lines.append(f"- {_source_line(source)}")
        lines.append("")
    if catalog.get("alliance_context"):
        lines.append("### Oil Sands Alliance memorandum")
        lines.append("")
        lines.append(catalog["alliance_context"])
        lines.append("")
    return lines


def _section_suppliers(catalog: dict[str, Any]) -> list[str]:
    reading = catalog.get("supplier_reading") or {}
    lines = [
        "## What this means for suppliers",
        "",
        f"- **Producers:** {reading.get('direct', '')}",
        f"- **Suppliers, fabricators, trades, and service companies:** {reading.get('supply_chain', '')}",
        f"- **Public tenders:** {reading.get('public_procurement', '')}",
        f"- **Location:** {reading.get('location_note', '')}",
        "",
        "### Companies quoted in the release",
        "",
        "A quote is interest or a company plan. It is not an approved Oil Sands Growth Program project.",
        "",
    ]
    for operator in catalog.get("operators") or []:
        lines.append(f"- **{operator.get('name', '')}.** {operator.get('statement', '')}")
    lines.append("")
    return lines


def _section_sources(catalog: dict[str, Any]) -> list[str]:
    lines = ["## Sources", ""]
    for source in catalog.get("sources") or []:
        lines.append(f"- {_source_line(source)} {source.get('role', '')}")
    lines.append("")
    return lines


def render_overview(topic: str = "") -> str:
    """Render the program brief. An unknown topic returns the topic list."""
    catalog = load_catalog()
    chosen = str(topic or "").strip().lower()
    if chosen and chosen not in TOPICS:
        return (
            "Unknown topic. Use one of: " + ", ".join(TOPICS) + ".\n\n"
            + render_overview("")
        )
    lines = _header(catalog, "Oil Sands Growth Program")
    if not chosen or chosen == "overview":
        lines.extend(_section_overview(catalog))
    if not chosen or chosen in {"overview", "royalty"}:
        lines.extend(_section_royalty(catalog))
    if chosen == "timeline":
        lines.extend(_section_timeline(catalog))
    if not chosen or chosen in {"overview", "eligibility"}:
        lines.extend(_section_eligibility(catalog))
    if not chosen or chosen in {"overview", "pipelines"}:
        lines.extend(_section_pipelines(catalog))
    if not chosen or chosen in {"overview", "suppliers"}:
        lines.extend(_section_suppliers(catalog))
    if not chosen or chosen == "sources":
        lines.extend(_section_sources(catalog))
    return "\n".join(lines).rstrip() + "\n"


def _contains(phrase: str, text: str) -> bool:
    return phrase.lower() in text


def assess_fit(description: str, location: str = "", company_name: str = "") -> dict[str, Any]:
    """Classify a business as producer, supplier, both, or neither.

    This is a reading of the published program, not an eligibility decision.
    """
    catalog = load_catalog()
    signals = catalog.get("fit_signals") or {}
    text = " ".join([description or "", location or "", company_name or ""]).lower()
    producer_hits = [item for item in signals.get("producer") or [] if _contains(item, text)]
    supplier_hits = [item for item in signals.get("supplier") or [] if _contains(item, text)]
    location_hits = [item for item in catalog.get("location_markers") or [] if _contains(item, text)]
    if producer_hits and supplier_hits:
        path = "both"
    elif producer_hits:
        path = "producer"
    elif supplier_hits:
        path = "supplier"
    else:
        path = "none"
    return {
        "path": path,
        "producer_hits": producer_hits,
        "supplier_hits": supplier_hits,
        "location_hits": location_hits,
        "described": bool(str(description or "").strip()),
    }


def render_fit(
    *,
    description: str = "",
    location: str = "",
    company_name: str = "",
) -> str:
    """Explain how a business could benefit, directly or through operator spending."""
    catalog = load_catalog()
    company = company_name.strip() or "This business"
    fit = assess_fit(description, location, company_name)
    reading = catalog.get("supplier_reading") or {}
    lines = _header(catalog, f"Oil Sands Growth Program fit reading for {company}")
    if description.strip():
        lines.append(f"**Described as:** {description.strip()}")
    else:
        lines.append("**Described as:** not provided. The reading below is the general supplier path.")
    if location.strip():
        lines.append(f"**Location:** {location.strip()}")
    lines.append("")
    lines.append("## How this business could benefit")
    lines.append("")
    if fit["path"] == "producer":
        lines.append(f"{company} described itself in producer terms ({', '.join(fit['producer_hits'])}).")
        lines.append("")
        lines.append(reading.get("direct", ""))
        lines.append("")
        lines.append("The written release does not publish the eligibility test, the application, or a minimum volume. Do not treat this reading as approval.")
    elif fit["path"] == "supplier":
        lines.append(f"{company} looks like a supplier into oil sands work ({', '.join(fit['supplier_hits'][:8])}), not a royalty recipient.")
        lines.append("")
        lines.append(reading.get("supply_chain", ""))
    elif fit["path"] == "both":
        lines.append(f"{company} used both producer language ({', '.join(fit['producer_hits'])}) and supplier language ({', '.join(fit['supplier_hits'][:6])}).")
        lines.append("")
        lines.append(reading.get("direct", ""))
        lines.append("")
        lines.append(reading.get("supply_chain", ""))
    else:
        lines.append("Nothing in the description matches an oil sands producer or a supplier into oil sands construction and operations.")
        lines.append("")
        lines.append("The program does not pay unrelated businesses. There is no published community grant or general business credit in the 13 November 2026 release.")
    lines.append("")
    if fit["location_hits"]:
        lines.append(f"Location words ({', '.join(fit['location_hits'])}) put the business near oil sands production or the Edmonton-region shop corridor. {reading.get('location_note', '')}")
        lines.append("")
    lines.append("## What stays unpublished")
    lines.append("")
    for item in (catalog.get("unconfirmed") or [])[:4]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(reading.get("public_procurement", ""))
    lines.append("")
    lines.append("Next: read the official release, then use `find_oil_sands_supply_opportunities` for public notices that name an operator. Verify any private bid directly with the buyer.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def relevance_reasons(text: str) -> list[str]:
    """Return catalog terms found in a notice. Empty means no oil sands hit."""
    catalog = load_catalog()
    lowered = text.lower()
    return [term for term in catalog.get("notice_terms") or [] if term in lowered]


def render_supply(
    matches: list[tuple[dict[str, Any], list[str]]],
    warnings: list[str],
    *,
    limit: int = 8,
    keywords: str = "",
) -> str:
    """Render operator statements plus any public notices that name them."""
    catalog = load_catalog()
    lines = _header(catalog, "Oil sands supply-chain opportunities")
    lines.append(catalog.get("supplier_reading", {}).get("public_procurement", ""))
    lines.append("")
    lines.append("## Operators quoted in the 13 November 2026 release")
    lines.append("")
    lines.append("These are company statements carried in the government release. None is an approved Oil Sands Growth Program project.")
    lines.append("")
    for operator in catalog.get("operators") or []:
        lines.append(f"- **{operator.get('name', '')}.** {operator.get('statement', '')}")
    lines.append("")
    lines.append("## Public notices on file")
    lines.append("")
    if keywords.strip():
        lines.append(f"Extra filter: `{keywords.strip()}`. A notice has to name an oil sands term and this filter.")
        lines.append("")
    if warnings:
        lines.append("### Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    shown = matches[:limit]
    if not shown:
        lines.append("No open CanadaBuys or Alberta Purchasing Connection notice on file matched an oil sands operator or the words oil sands or bitumen.")
        lines.append("")
        lines.append("That is normal. Operator expansions are usually private procurement. Use the operator list above as a watchlist, and keep using `search_opportunities` for public work in fabrication, construction, camps, and maintenance.")
    else:
        lines.append(f"Showing {len(shown)} of {len(matches)} matching public notices.")
        lines.append("")
        for index, (opportunity, reasons) in enumerate(shown, 1):
            title = str(opportunity.get("title") or "Untitled notice")
            reference = str(opportunity.get("reference") or "")
            source = str(opportunity.get("source") or "")
            buyer = str(opportunity.get("buyer") or "")
            closing = str(opportunity.get("closing") or "")
            url = str(opportunity.get("url") or "")
            lines.append(f"### {index}. {title}")
            lines.append("")
            lines.append(f"- **Source:** {source}")
            if reference:
                lines.append(f"- **Reference:** `{reference}`")
            if buyer:
                lines.append(f"- **Buyer:** {buyer}")
            if closing:
                lines.append(f"- **Closing:** {closing}")
            if reasons:
                lines.append(f"- **Why it surfaced:** {', '.join(reasons)}")
            if url:
                lines.append(f"- **Link:** {url}")
            lines.append("")
        lines.append("A keyword hit is not a finding that the notice is an Oil Sands Growth Program project. Open the posting.")
    lines.append("")
    lines.append("## Related pipelines")
    lines.append("")
    for item in catalog.get("pipelines") or []:
        lines.append(f"- **{item.get('name', '')}.** {item.get('detail', '')}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_updates(*, refresh: bool = False, fetch: Any = None) -> str:
    """Return stored official and related announcements, newest first."""
    catalog = load_catalog()
    lines = _header(catalog, "Oil Sands Growth Program updates")
    if refresh:
        check = confirm_official_release(fetch=fetch)
        state = "Confirmed" if check.get("ok") == "true" else "Not confirmed"
        lines.append(f"**Live check:** {state}. {check.get('note', '')}")
        lines.append(f"**Checked URL:** {check.get('url', '')}")
        lines.append("")
    else:
        lines.append(
            "This is the stored catalog. Pass `refresh: true` to check that the official "
            "release URL is still online. A failed check does not change these entries."
        )
        lines.append("")
    updates = list(catalog.get("updates") or [])
    updates.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    sources = _sources(catalog)
    for item in updates:
        kind = str(item.get("kind") or "note")
        lines.append(f"### {item.get('date', '')} — {item.get('title', 'Update')}")
        lines.append("")
        lines.append(f"- **Kind:** {kind}")
        lines.append(f"- **What it says:** {item.get('summary', '')}")
        source = sources.get(str(item.get("source_id")))
        if source:
            lines.append(f"- **Source:** {_source_line(source)}")
        lines.append("")
    lines.append("Program rules are the 13 November 2026 release until Alberta publishes a regulation, a guideline, or an application page. The 17 November 2026 post does not add rules.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
