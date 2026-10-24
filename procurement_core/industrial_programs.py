"""Read-only matcher for the industrial and tariff support catalog.

The catalog is a checked-in JSON file. Matching uses the business description:
eligibility tags and industry words first, then a short activity phrase so a
broad program explains why it surfaced. When ``TYPESAFE_API_KEY`` is set, a
bounded TypeSafe Jev pass labels each featured program yes, partial, or no.
A sector program Jev calls unrelated is left out of the applies list. This
never submits an application or treats a keyword overlap as eligibility.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from procurement_core import business_fit

# Hints taken from each program's published eligibility. They explain a match.
# They are not an application test. ``program["eligibility_tags"]`` overrides.
ELIGIBILITY_TAGS: dict[str, tuple[str, ...]] = {
    "prairiescan-rtri": ("tariff", "export", "liquidity"),
    "ised-strategic-response-fund": (
        "steel", "aluminum", "lumber", "manufacturing", "automotive", "forestry", "defence", "energy", "tariff",
    ),
    "ised-canada-strong-diversification-fund": ("manufacturing", "steel", "aluminum", "capital"),
    "joint-steel-action-fund": ("steel",),
    "ontario-auto-modernization": ("automotive",),
    "bdc-pivot-to-grow": ("tariff", "liquidity", "export"),
    "bdc-metals-envelope": ("steel", "aluminum", "copper", "metal", "fabrication"),
    "nrcan-first-and-last-mile-fund": ("mining", "critical mineral"),
    "nrcan-critical-minerals-accelerator": ("mining", "critical mineral"),
    "pspc-buy-canadian-framework": ("procurement", "buy canadian", "supplier"),
    "buy-ontario-policy": ("buy ontario",),
    "ring-of-fire-roads": ("ring of fire",),
}

CATALOG_PATH = Path(__file__).resolve().parent / "content" / "industrial_programs.json"

_ONTARIO_MARKERS = (
    "ontario", "toronto", "hamilton", "mississauga", "london, ontario", "ottawa, ontario",
)
_ALBERTA_MARKERS = (
    "alberta", "edmonton", "calgary", "red deer", "lethbridge", "fort mcmurray",
    "grande prairie", "medicine hat", "airdrie", "spruce grove", "st. albert",
)
_PRAIRIE_MARKERS = (
    "saskatchewan", "manitoba", "regina", "saskatoon", "winnipeg", "prairie", "prairies",
)


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Return the industrial-program catalog. Cached for the process lifetime."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def location_bucket(location: str) -> str:
    """Classify a supplier location for program geography.

    An empty location is read as Alberta, because workspaceAlberta's public
    catalog is written for Alberta firms. The rendered brief says so.
    """
    text = str(location or "").lower().strip()
    if not text:
        return "alberta"
    has_ontario = any(marker in text for marker in _ONTARIO_MARKERS)
    has_alberta = any(marker in text for marker in _ALBERTA_MARKERS)
    has_prairie = any(marker in text for marker in _PRAIRIE_MARKERS)
    if has_alberta and not has_ontario:
        return "alberta"
    if has_ontario and not has_alberta and not has_prairie:
        return "ontario"
    if has_prairie and not has_ontario:
        return "prairies"
    if has_alberta:
        return "alberta"
    if re.search(r"\b(canada|canadian)\b", text):
        return "canada"
    return "other"


def _tag_list(program: dict[str, Any]) -> list[str]:
    raw = program.get("eligibility_tags")
    if isinstance(raw, list) and raw:
        return [str(item).lower().strip() for item in raw if str(item).strip()]
    return [item.lower() for item in ELIGIBILITY_TAGS.get(str(program.get("id") or ""), ())]


def _program_score(
    program: dict[str, Any],
    text: str,
    industries: list[str],
    activity: str,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    industry_labels = {item.lower() for item in industries if item.strip()}
    program_industries = {item.lower() for item in program.get("industries") or []}
    overlap = sorted(industry_labels & program_industries)
    if overlap:
        score += 5 * len(overlap)
        reasons.append("industry " + ", ".join(overlap))
    elif "any" in program_industries and program.get("audience") == "broad":
        score += 1
        if activity:
            reasons.append(f"open to any sector; business described as {activity}")
        else:
            reasons.append("open across industries")
    for tag in _tag_list(program):
        if tag and tag != "any" and business_fit.phrase_in(tag, text):
            score += 4
            label = f"eligibility: {tag}"
            if label not in reasons:
                reasons.append(label)
    for keyword in program.get("keywords") or []:
        token = str(keyword).lower().strip()
        if len(token) >= 3 and token in text:
            score += 3
            if token not in reasons:
                reasons.append(token)
    return score, reasons


def _section_for(program: dict[str, Any], bucket: str) -> str:
    """Return applies, ontario_only, prairie_only, or national_note."""
    geography = program.get("geography")
    if program.get("ontario_only") or geography == "ontario":
        if bucket == "ontario":
            return "applies"
        return "ontario_only"
    if geography == "prairies":
        if bucket in {"alberta", "prairies"}:
            return "applies"
        return "prairie_only"
    if bucket == "other":
        return "national_note"
    return "applies"


def _render_program(program: dict[str, Any], reasons: list[str]) -> str:
    lines = [f"### {program.get('name', 'Program')}", ""]
    lines.append(f"- **Administrator:** {program.get('administrator', '')}")
    if program.get("ontario_only"):
        lines.append("- **Geography:** Ontario-only. This entry does not apply to an Alberta business.")
    elif program.get("geography") == "prairies":
        lines.append("- **Geography:** Alberta, Saskatchewan, and Manitoba.")
    elif program.get("geography") == "national":
        lines.append("- **Geography:** National. An Alberta business can ask.")
    if reasons:
        lines.append(f"- **Why it surfaced:** {', '.join(reasons[:6])}")
    if program.get("summary"):
        lines.append(f"- **What it is:** {program['summary']}")
    if program.get("amount"):
        lines.append(f"- **Published amount:** {program['amount']}")
    if program.get("eligibility"):
        lines.append(f"- **Who it is written for:** {program['eligibility']}")
    if program.get("url"):
        lines.append(f"- **Official page:** {program['url']}")
    lines.append("")
    return "\n".join(lines)


def render_program_matches(
    profile: dict[str, Any],
    *,
    limit: int = 12,
) -> str:
    """Render the catalog against a business profile as markdown."""
    catalog = load_catalog()
    description = str(profile.get("description") or "")
    capabilities = [str(item) for item in profile.get("capabilities") or [] if str(item).strip()]
    industries = [str(item) for item in profile.get("industries") or [] if str(item).strip()]
    location = str(profile.get("location") or "")
    company = str(profile.get("company_name") or "Your business")
    text = business_fit.normalize_text(
        " ".join([description, " ".join(capabilities), " ".join(industries), location])
    )
    activity = business_fit.activity_label(description) if description.strip() else ""
    broad_reason = (
        f"open to any sector; business described as {activity}" if activity else "open across industries"
    )
    bucket = location_bucket(location)
    directory = not description.strip() and not capabilities and not industries

    grouped: dict[str, list[tuple[int, dict[str, Any], list[str]]]] = {
        "applies": [],
        "ontario_only": [],
        "prairie_only": [],
        "national_note": [],
    }
    for program in catalog.get("programs") or []:
        score, reasons = _program_score(program, text, industries, activity)
        section = _section_for(program, bucket)
        audience = program.get("audience")
        if directory:
            grouped[section].append((score, program, reasons or ["listed in the catalog"]))
            continue
        if section != "applies":
            grouped[section].append((score, program, reasons))
            continue
        if audience == "broad" or score > 0:
            grouped[section].append((score, program, reasons or [broad_reason]))

    classifier_warnings = _apply_program_classifier(profile, grouped)

    for rows in grouped.values():
        rows.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))

    package = catalog.get("package") or {}
    lines = [f"# Industrial and tariff support for {company}", ""]
    lines.append(catalog.get("disclaimer") or "")
    lines.append("")
    if package:
        lines.append(
            f"**{package.get('name', 'Package')}** ({package.get('announced', '')}, "
            f"${package.get('amount_cad', '')} CAD). {package.get('summary', '')}"
        )
        lines.append("")
        if package.get("source_url"):
            lines.append(f"Package announcement: {package['source_url']}")
            lines.append("")
    if bucket == "alberta" and not location.strip():
        lines.append(
            "No location was given, so this read assumes an Alberta business. "
            "Pass a location when the firm is elsewhere."
        )
        lines.append("")
    elif bucket == "other":
        lines.append(
            "The location does not read as a Canadian province. National programs below "
            "are written for Canadian businesses. Confirm that before treating one as relevant."
        )
        lines.append("")

    applies_source = grouped["national_note"] if bucket == "other" else grouped["applies"]
    applies = applies_source[:limit]
    lines.append("## Applies")
    lines.append("")
    if not applies:
        lines.append("No catalog entry matched this description strongly enough to feature. Browse the official pages in the disclaimer sources, or pass a fuller description.")
        lines.append("")
    else:
        if directory:
            lines.append("No business description was given, so this is the catalog rather than a ranked match.")
            lines.append("")
        for _score, program, reasons in applies:
            lines.append(_render_program(program, reasons))

    def _dump(title: str, intro: str, rows: list[tuple[int, dict[str, Any], list[str]]]) -> None:
        if not rows:
            return
        lines.append(f"## {title}")
        lines.append("")
        lines.append(intro)
        lines.append("")
        for _score, program, reasons in rows:
            lines.append(_render_program(program, reasons))

    if bucket == "ontario":
        _dump(
            "Prairie programs",
            "PrairiesCan delivers these in Alberta, Saskatchewan, and Manitoba. They are not an Ontario application.",
            grouped["prairie_only"],
        )
    else:
        _dump(
            "Ontario-only",
            "These streams were announced for Ontario. They do not apply to an Alberta business. They are listed so that difference is visible.",
            grouped["ontario_only"],
        )
        _dump(
            "Prairie programs",
            "These are delivered in Alberta, Saskatchewan, and Manitoba.",
            grouped["prairie_only"],
        )
    if classifier_warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in classifier_warnings:
            lines.append(f"- {warning}")
        lines.append("")
    lines.append(
        f"Catalog version {catalog.get('catalog_version', '')}. "
        "Verify every figure on the official page before you act on it."
    )
    return "\n".join(lines).strip() + "\n"


def _apply_program_classifier(
    profile: dict[str, Any],
    grouped: dict[str, list[tuple[int, dict[str, Any], list[str]]]],
) -> list[str]:
    """Ask Jev about featured programs when a key is configured.

    A sector program judged unrelated drops out of Applies. A broad program
    stays, with the verdict in the reason, because it is not sector-limited.
    """
    description = str(profile.get("description") or "").strip()
    if not description or not business_fit.typesafe_api_key():
        return []
    featured = [program for _score, program, _reasons in grouped["applies"][: business_fit.MAX_PROGRAMS]]
    if not featured:
        return []
    classification = business_fit.classify_programs(profile, featured)
    if classification.status != "ok":
        return list(classification.warnings)
    kept: list[tuple[int, dict[str, Any], list[str]]] = []
    for score, program, reasons in grouped["applies"]:
        verdict = (classification.verdicts.get(str(program.get("id") or "")) or {}).get("verdict")
        if verdict == "no" and program.get("audience") != "broad":
            continue
        if verdict in {"yes", "partial", "no"}:
            note = f"classifier: {verdict}"
            reasons = [note, *reasons]
            if verdict == "yes":
                score += 6
            elif verdict == "partial":
                score += 2
        kept.append((score, program, reasons))
    kept.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    grouped["applies"] = kept
    return list(classification.warnings)
