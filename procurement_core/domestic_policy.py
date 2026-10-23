"""Buy Canadian and domestic-preference signals on public tender notices.

CanadaBuys publishes trade agreements in
``tradeAgreements-accordsCommerciaux-eng``. Notices also describe the policy
in the title or description. This module turns that text into stable flags.
It does not decide whether a supplier qualifies.
"""

from __future__ import annotations

import re

# Stable order is the order callers render and store.
POLICY_ORDER = (
    "buy_canadian_materials",
    "buy_canadian_strategic",
    "canadian_suppliers_only",
    "reciprocal_procurement",
    "cfta_domestic_only",
)

POLICY_LABELS = {
    "buy_canadian_materials": (
        "Policy on Prioritizing Canadian Materials in Federal Procurements "
        "(Canadian steel, aluminum, and wood on construction and defence procurements of $25 million or more)"
    ),
    "buy_canadian_strategic": (
        "Policy on Prioritizing Canadian Suppliers and Canadian Content in Strategic Federal Procurements "
        "($5 million or more)"
    ),
    "canadian_suppliers_only": "Limited to Canadian suppliers",
    "reciprocal_procurement": "Policy on Reciprocal Procurement",
    "cfta_domestic_only": "CFTA only, or no international trade-agreement coverage",
}

POLICY_SHORT_LABELS = {
    "buy_canadian_materials": "Buy Canadian materials",
    "buy_canadian_strategic": "Buy Canadian strategic suppliers and content",
    "canadian_suppliers_only": "Canadian suppliers only",
    "reciprocal_procurement": "Reciprocal procurement",
    "cfta_domestic_only": "CFTA only or no international coverage",
}

_INTERNATIONAL_FTA = (
    r"\bceta\b",
    r"\bcptpp\b",
    r"\bwto\b",
    r"\bgpa\b",
    r"\bnafta\b",
    r"\bcusma\b",
    r"\bckfta\b",
    r"\bccfta\b",
    r"\bcpafta\b",
    r"\bchfta\b",
    r"\bcufta\b",
    r"comprehensive economic and trade agreement",
    r"comprehensive and progressive",
    r"agreement on government procurement",
    r"world trade organization",
    r"canada[-–]european",
    r"canada[-–]united kingdom",
    r"canada[-–]uk\b",
    r"canada[-–]korea",
    r"canada[-–]chile",
    r"canada[-–]peru",
    r"canada[-–]colombia",
    r"canada[-–]honduras",
    r"canada[-–]panama",
    r"canada[-–]ukraine",
    r"trans-pacific",
)

_DOMESTIC_AGREEMENT = (
    r"\bcfta\b",
    r"canadian free trade agreement",
    r"\bait\b",
    r"agreement on internal trade",
    r"\bnwpta\b",
    r"new west partnership",
)

_NO_INTERNATIONAL = (
    "cfta only",
    "cfta-only",
    "only the cfta",
    "only cfta",
    "no international trade agreement",
    "no international fta",
    "not covered by an international",
    "not subject to any international",
    "without international trade agreement",
    "domestic trade agreements only",
)

_EMPTY_COVERAGE = {
    "none",
    "n/a",
    "na",
    "nil",
    "not applicable",
    "no trade agreements",
    "no trade agreement",
    "not covered",
}

_MATERIALS_NAME = (
    "policy on prioritizing canadian materials",
    "prioritizing canadian materials",
    "canadian materials in federal procurement",
)

_STRATEGIC_NAME = (
    "policy on prioritizing canadian suppliers",
    "prioritizing canadian suppliers and canadian content",
    "canadian content in strategic federal",
    "strategic federal procurement",
)

_SUPPLIERS_ONLY = (
    "canadian suppliers only",
    "limited to canadian suppliers",
    "restricted to canadian suppliers",
    "open only to canadian suppliers",
    "must be a canadian supplier",
    "suppliers must be canadian",
    "this requirement is limited to canadian",
    "this procurement is limited to canadian",
    "this tender is limited to canadian",
)

_CANADIAN_PLACES = (
    "canada",
    "canadian",
    "alberta",
    "british columbia",
    "saskatchewan",
    "manitoba",
    "ontario",
    "quebec",
    "québec",
    "new brunswick",
    "nova scotia",
    "prince edward",
    "newfoundland",
    "labrador",
    "yukon",
    "northwest territor",
    "nunavut",
    "calgary",
    "edmonton",
    "red deer",
    "lethbridge",
    "fort mcmurray",
    "grande prairie",
    "medicine hat",
    "toronto",
    "ottawa",
    "vancouver",
    "winnipeg",
    "montreal",
    "montréal",
    "halifax",
    "regina",
    "saskatoon",
    "victoria",
    "quebec city",
    "québec city",
)

_PROVINCE_ABBREVIATIONS = frozenset({
    "ab", "bc", "sk", "mb", "on", "qc", "nb", "ns", "pe", "nl", "yt", "nt", "nu",
})


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _has_international_fta(trade: str) -> bool:
    return _contains_any(trade, _INTERNATIONAL_FTA)


def _has_domestic_agreement(trade: str) -> bool:
    return _contains_any(trade, _DOMESTIC_AGREEMENT)


def _cfta_domestic_only(trade: str, blob: str) -> bool:
    """True when coverage is domestic, or the notice says there is no international FTA."""
    if any(phrase in blob for phrase in _NO_INTERNATIONAL):
        return True
    cleaned = re.sub(r"\s+", " ", trade).strip(" .;")
    if cleaned in _EMPTY_COVERAGE:
        return True
    if not cleaned:
        return False
    return _has_domestic_agreement(trade) and not _has_international_fta(trade)


def _materials_policy(blob: str) -> bool:
    if any(phrase in blob for phrase in _MATERIALS_NAME):
        return True
    metals = [token for token in ("steel", "aluminum", "aluminium", "wood") if token in blob]
    if len(metals) < 2:
        return False
    mandated = any(token in blob for token in ("mandatory", "required", "must use", "shall use", "priorit"))
    canadian = "canadian" in blob or "produced in canada" in blob
    return mandated and canadian


def _strategic_policy(blob: str) -> bool:
    if any(phrase in blob for phrase in _STRATEGIC_NAME[:3]):
        return True
    return "strategic federal procurement" in blob and (
        "canadian content" in blob or "canadian supplier" in blob
    )


def detect_domestic_policies(trade_agreements: str = "", *texts: str) -> list[str]:
    """Return domestic-preference flags found in a notice, in stable order.

    ``trade_agreements`` is the CanadaBuys trade-agreement column. Extra
    strings (title, description) are scanned for policy names. An empty trade
    column is unknown coverage, not CFTA-only, unless the notice says so.
    """
    trade = str(trade_agreements or "").lower()
    blob = " ".join([trade, *[str(text or "").lower() for text in texts]])
    blob = re.sub(r"\s+", " ", blob)
    found = {
        "buy_canadian_materials": _materials_policy(blob),
        "buy_canadian_strategic": _strategic_policy(blob),
        "canadian_suppliers_only": any(phrase in blob for phrase in _SUPPLIERS_ONLY),
        "reciprocal_procurement": (
            "reciprocal procurement" in blob or "policy on reciprocal" in blob
        ),
        "cfta_domestic_only": _cfta_domestic_only(trade, blob),
    }
    return [flag for flag in POLICY_ORDER if found[flag]]


def format_domestic_policies(flags: list[str], *, short: bool = False) -> str:
    """Join flag labels for markdown. Unknown flags are shown as given."""
    labels = POLICY_SHORT_LABELS if short else POLICY_LABELS
    rendered = [labels.get(flag, flag.replace("_", " ")) for flag in flags]
    return "; ".join(rendered)


def render_domestic_policy_section(flags: list[str]) -> list[str]:
    """Markdown lines for an opportunity dossier. Empty when there are no flags."""
    if not flags:
        return []
    lines = [
        "## Domestic preference",
        "",
        "Read from the notice text and trade-agreement field. A flag is not a finding that a supplier qualifies.",
    ]
    for flag in flags:
        lines.append(f"- **{POLICY_SHORT_LABELS.get(flag, flag)}:** {POLICY_LABELS.get(flag, flag)}")
    lines.append("")
    return lines


def is_canadian_business(location: str) -> bool:
    """True when a profile location names Canada, a province, or a major Canadian city."""
    text = str(location or "").lower()
    if any(place in text for place in _CANADIAN_PLACES):
        return True
    tokens = set(re.findall(r"[a-z]+", text))
    return bool(tokens & _PROVINCE_ABBREVIATIONS)


def domestic_preference_bonus(flags: list[str], location: str) -> tuple[int, list[str]]:
    """Reward a Canadian or Alberta business when the notice prefers domestic suppliers.

    Callers add this only after a content match, so the bonus cannot by itself
    pull in an unrelated tender.
    """
    if not flags or not is_canadian_business(location):
        return 0, []
    return 10, [
        "domestic preference favours a Canadian or Alberta supplier: "
        + format_domestic_policies(flags, short=True)
    ]
