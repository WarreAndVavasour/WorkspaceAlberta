"""Commodity prefilter and TypeSafe Jev supply-fit classification.

Keyword overlap is a weak first step: "food" drifts into laboratory jobs and
"training" into defence construction. For a free-text business description this
module does two cheaper, bounded things instead:

1. Expand the description with a fixed lexicon of UNSPSC and GSIN prefixes plus
   a few specific terms (no LLM). That cuts the open CanadaBuys and Alberta
   Purchasing Connection catalogues to a small candidate set.
2. Ask TypeSafe Jev, once per candidate, whether this business could supply the
   notice (yes / partial / no) and as which capability (goods supply, services,
   training, subcontract). Ranking uses that verdict first, then the existing
   keyword score and Buy Canadian bonus.

Jev is a classifier, not a generative model. The same ``call_jev`` client,
auth handling, and retry rules as ``classify_tender`` are reused. The API key
is read from ``TYPESAFE_API_KEY`` (or ``JEV_API_KEY``) and is never returned.

Bounds, per fit pass:

- at most ``MAX_CANDIDATES`` (12) notices are classified
- at most 4 requests in flight, 1 retry, 6 s per request
- the whole classification stops at 8 s (``DEADLINE_SECONDS``)
- answers are cached in-process by prompt version, model, and the exact
  business and notice text, so a repeat lookup does not call Jev again

Cost. Jev 1.13 bills input tokens only, at ``jev.PRICE_PER_MTOK`` USD per
million ($0.042). A candidate state is about 500 input tokens. Twelve notices
are about 6,000 tokens, roughly $0.0003, and a cache hit is free. Output
tokens are not billed.

When the key is missing, rejected, or no answer arrives before the deadline,
callers fall back to keyword ranking and surface the warning strings below.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any

from procurement_core import usage
from procurement_core.requirements import jev

FIT_PROMPT_VERSION = "jev-fit-v1"
PROGRAM_PROMPT_VERSION = "jev-program-v1"
DEFAULT_MODEL = jev.DEFAULT_MODEL

MAX_CANDIDATES = 12
MAX_PROGRAMS = 8
CONCURRENCY = 4
DEADLINE_SECONDS = 8.0
PROGRAM_DEADLINE_SECONDS = 6.0
REQUEST_TIMEOUT = 6.0
MAX_RETRIES = 1
BUSINESS_CHARS = 500
NOTICE_CHARS = 600
CACHE_MAX = 512

# Verdict weights are for ordering only. yes outranks partial, which outranks
# a notice the deadline left unclassified. "no" is dropped by the caller.
VERDICT_RANK = {"yes": 3, "partial": 2, "unclassified": 1, "no": 0}

CAPABILITY_LABELS = {
    "goods_supply": "goods supply",
    "services": "services",
    "training": "training",
    "subcontract": "subcontract",
    "none": "none",
}

UNCONFIGURED_WARNING = (
    "TypeSafe Jev is not configured (set TYPESAFE_API_KEY); showing keyword ranking."
)
UNAUTHENTICATED_WARNING = (
    "TypeSafe Jev rejected this server's API key; showing keyword ranking."
)
UNAVAILABLE_WARNING = (
    "TypeSafe Jev did not answer before the time limit; showing keyword ranking."
)
PROGRAM_UNAVAILABLE_WARNING = (
    "TypeSafe Jev did not answer; program matches used the business description and eligibility tags."
)

# Words that pulled the wrong notices in keyword search. They are not used as
# loose terms. A concept can still add a specific phrase such as "food service".
_DRIFT = frozenset({
    "food", "foods", "training", "service", "services", "supply", "supplies",
    "licence", "license", "licences", "licenses", "scale", "providing",
    "products", "product", "general", "arrangement", "arrangements",
})

_PLACES = frozenset({
    "alberta", "edmonton", "calgary", "lethbridge", "canada", "canadian",
    "ontario", "toronto", "quebec", "winnipeg", "regina", "saskatoon",
    "montreal", "vancouver", "british", "columbia", "saskatchewan", "manitoba",
    "ottawa", "red", "deer",
})

_STOP = frozenset({
    "that", "this", "with", "from", "have", "been", "will", "your", "they",
    "their", "about", "which", "would", "could", "should", "these", "those",
    "other", "some", "into", "also", "make", "made", "and", "the", "for",
    "our", "are", "was", "business", "company", "provide", "provides",
    "including", "based", "located", "across", "within", "where", "what",
    "work", "works", "shop",
})

# Jev 1.13 leans toward the first Choice option, so the rejection ("no" /
# "none") is last, matching the requirement classifier.
_SUPPLY_CRITERIA = {
    "yes": "The business's stated work is what this notice is buying, or a standing supply arrangement for that work.",
    "partial": "The business could supply a real part of this notice: a good, a service, training, or a subcontract. Not the whole buy.",
    "no": "The notice buys something this business does not do.",
}
_CAPABILITY_CRITERIA = {
    "goods_supply": "Supplying the goods, products, or materials the notice buys.",
    "services": "Performing the services the notice buys.",
    "training": "Delivering training, instruction, or a curriculum the notice buys.",
    "subcontract": "Supplying a component or specialty a prime contractor would buy, not the whole contract.",
    "none": "No supply role. The notice is unrelated.",
}

FIT_QUESTIONS = {
    "supplies": {
        "type": "choice",
        "instructions": (
            "`business` describes a supplier, including where it works. "
            "`notice_title`, `notice_buyer`, `notice_codes` and `notice_text` are one public procurement notice. "
            "Could this business plausibly supply what the notice is buying? "
            "Judge the goods, services, or training the notice asks a supplier to deliver. "
            "Ignore incidental words such as food in a laboratory name or training in a construction title. "
            "Pick partial when the business could supply one real part, such as baked goods inside a food-service "
            "arrangement or culinary instruction inside a training buy, but not the whole notice. "
            "Pick no when the notice is a different trade."
        ),
        "criteria": _SUPPLY_CRITERIA,
    },
    "capability": {
        "type": "choice",
        "instructions": (
            "Which role would this business play on this notice? "
            "Use goods_supply for products and standing supply arrangements, services for performed work such as "
            "catering or food service, training for instruction or curriculum, subcontract when the business would "
            "supply a component to a prime, and none when supplies is no."
        ),
        "criteria": _CAPABILITY_CRITERIA,
    },
}

PROGRAM_QUESTIONS = {
    "relevance": {
        "type": "choice",
        "instructions": (
            "`business` describes a Canadian firm. `program_name`, `program_summary`, `program_eligibility` and "
            "`program_industries` describe one public support program. "
            "Does this program plausibly relate to what the business does? "
            "Pick yes when the business's work is inside the program's sector or eligibility test. "
            "Pick partial when the program is open across sectors, so the firm can ask, but the description does not "
            "name that test. Pick no when the program is for a different sector."
        ),
        "criteria": {
            "yes": "The business's work matches this program's sector or eligibility test.",
            "partial": "The program is not limited to one sector. The description does not name its test.",
            "no": "The program is for a different sector than this business.",
        },
    },
}


# triggers are matched on normalized text (lowercase, slashes and hyphens as spaces).
# prefixes are digit strings matched against UNSPSC, GSIN, and APC commodity codes.
_CONCEPTS: tuple[dict[str, Any], ...] = (
    {
        "id": "bakery_goods",
        "label": "bakery goods",
        "triggers": ("bakery", "bakeries", "baking", "baker", "pastry", "pastries", "bread"),
        "prefixes": ("5018", "501815", "501817", "501819", "501820", "5019", "8920"),
        "terms": ("bakery", "baking", "bread", "pastry", "baked goods", "baked"),
    },
    {
        "id": "food_service",
        "label": "food service",
        "triggers": ("catering", "culinary", "food service", "banquet", "cafeteria", "food services"),
        "prefixes": ("9010", "901015", "901016", "901017", "901018"),
        "terms": ("catering", "culinary", "food service", "food services", "banquet", "cafeteria"),
    },
    {
        "id": "food_supply",
        "label": "food supply",
        "triggers": ("food supply", "food service supply", "provisions", "grocery", "groceries"),
        "prefixes": ("5012", "5013", "5015", "5016", "5017", "5020", "5022", "8910", "8915", "8940", "8950"),
        "terms": ("food supply", "food service supply", "provisions", "grocery"),
    },
    {
        "id": "culinary_training",
        "label": "culinary training",
        "triggers": (
            "culinary training", "baking training", "cook training", "chef training",
            "culinary arts", "baking instruction", "cookery",
        ),
        "prefixes": ("8610", "8611", "861015", "861017", "861115"),
        "terms": ("culinary training", "culinary arts", "cook training", "chef", "cookery", "baking instruction"),
    },
    {
        "id": "training",
        "label": "training",
        "triggers": ("training", "curriculum", "workshop", "professional development"),
        "prefixes": ("8610", "8611", "8613", "8614"),
        "terms": ("training services", "curriculum", "professional development", "vocational"),
    },
    {
        "id": "steel",
        "label": "steel and welding",
        "triggers": ("steel", "welding", "metal fabrication", "fabrication"),
        "prefixes": ("111017", "301017", "111016", "2324"),
        "terms": ("steel", "welding", "fabrication"),
    },
    {
        "id": "construction",
        "label": "construction",
        "triggers": ("construction", "renovation", "demolition"),
        "prefixes": ("7210", "7211", "7214"),
        "terms": ("construction", "renovation"),
    },
    {
        "id": "software",
        "label": "software",
        "triggers": ("software", "cybersecurity", "saas"),
        "prefixes": ("4323", "8111"),
        "terms": ("software", "cybersecurity"),
    },
    {
        "id": "cleaning",
        "label": "cleaning",
        "triggers": ("janitorial", "custodial", "floor scrub"),
        "prefixes": ("7611", "4713"),
        "terms": ("janitorial", "custodial", "floor scrub"),
    },
    {
        "id": "healthcare",
        "label": "healthcare",
        "triggers": ("healthcare", "health care", "hospital", "clinical", "nursing"),
        "prefixes": ("8510", "4214", "4217"),
        "terms": ("healthcare", "hospital", "clinical", "nursing"),
    },
)

_FOODISH = frozenset({"bakery_goods", "food_service", "food_supply"})


def typesafe_api_key() -> str:
    """Return the TypeSafe key, or an empty string when it is not configured."""
    for name in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def normalize_text(value: str) -> str:
    """Lowercase and treat hyphens and slashes as spaces."""
    text = str(value or "").lower().replace("/", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def phrase_in(phrase: str, text: str) -> bool:
    """True when ``phrase`` appears as words in already-normalized ``text``."""
    parts = [re.escape(part) for part in normalize_text(phrase).split() if part]
    if not parts or not text:
        return False
    return re.search(r"\b" + r"\s+".join(parts) + r"\b", text) is not None


def _distinctive_tokens(text: str) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"[a-z]{5,}", text):
        if token in _STOP or token in _DRIFT or token in _PLACES or token in found:
            continue
        found.append(token)
    return found[:12]


class Expansion:
    """Codes and terms derived from one business description."""

    def __init__(self, labels: list[str], prefixes: list[str], terms: list[str]) -> None:
        self.labels = labels
        self.prefixes = prefixes
        self.terms = terms

    @property
    def has_signal(self) -> bool:
        return bool(self.prefixes or self.terms)


def expand(description: str, extra_terms: list[str] | None = None) -> Expansion:
    """Map a description to commodity prefixes and specific notice terms.

    Bare words that caused bad keyword matches (food, training, service,
    supply, licence) are not added on their own. A concept adds them only
    inside a specific phrase such as "food service" or "culinary training".
    """
    text = normalize_text(description)
    selected: dict[str, dict[str, Any]] = {}
    for concept in _CONCEPTS:
        if concept["id"] == "culinary_training":
            continue
        if any(phrase_in(trigger, text) for trigger in concept["triggers"]):
            selected[concept["id"]] = concept
    culinary = next(item for item in _CONCEPTS if item["id"] == "culinary_training")
    foodish = bool(_FOODISH & set(selected))
    if any(phrase_in(trigger, text) for trigger in culinary["triggers"]) or (
        foodish and phrase_in("training", text)
    ):
        selected["culinary_training"] = culinary

    labels: list[str] = []
    prefixes: list[str] = []
    terms: list[str] = []
    for concept in _CONCEPTS:
        if concept["id"] not in selected:
            continue
        labels.append(concept["label"])
        for prefix in concept["prefixes"]:
            if prefix not in prefixes:
                prefixes.append(prefix)
        for term in concept["terms"]:
            normalized = normalize_text(term)
            if normalized and normalized not in terms:
                terms.append(normalized)
    for token in _distinctive_tokens(text):
        if token not in terms:
            terms.append(token)
    for extra in extra_terms or []:
        normalized = normalize_text(extra)
        if not normalized or normalized in _DRIFT or normalized in _STOP or normalized in _PLACES:
            continue
        if normalized not in terms and len(normalized) >= 4:
            terms.append(normalized)
    return Expansion(labels, prefixes, terms[:24])


def activity_label(description: str) -> str:
    """Short phrase naming what the description says the business does."""
    expansion = expand(description)
    if expansion.labels:
        return ", ".join(expansion.labels[:4])
    tokens = _distinctive_tokens(normalize_text(description))
    return ", ".join(tokens[:6])


def _code_tokens(value: str) -> list[str]:
    return re.findall(r"\d{4,8}", str(value or ""))


def prefix_hit(prefixes: list[str], code_text: str) -> str:
    """Return the longest lexicon prefix that matches a code in ``code_text``."""
    codes = _code_tokens(code_text)
    if not codes or not prefixes:
        return ""
    best = ""
    for prefix in prefixes:
        for code in codes:
            if code.startswith(prefix) or (len(code) >= 4 and prefix.startswith(code)):
                if len(prefix) > len(best):
                    best = prefix
    return best


def notice_code_text(opportunity: dict) -> str:
    """UNSPSC, GSIN, and APC commodity codes on a normalized notice."""
    return " ".join(
        str(opportunity.get(field) or "")
        for field in ("unspsc", "gsin", "commodity_codes")
    )


def notice_class_text(opportunity: dict) -> str:
    """Human-readable classification text, not the free-text description."""
    return normalize_text(" ".join(
        str(opportunity.get(field) or "")
        for field in (
            "unspsc_description", "gsin_description", "commodity_titles", "category",
        )
    ))


_NEGATION = re.compile(r"\b(?:not|no|never|without|excluding|neither|nor|except)\b")


def affirmative_text(text: str) -> str:
    """Drop clauses that negate the words in them.

    A defence notice that says "Not a culinary or baking program" is not a
    bakery mention. The clause is removed before description terms are scored.
    """
    kept: list[str] = []
    for clause in re.split(r"[.;:!?]", text):
        if _NEGATION.search(clause):
            continue
        if clause.strip():
            kept.append(clause)
    return " ".join(kept)


def prefilter_score(opportunity: dict, expansion: Expansion) -> tuple[int, list[str]]:
    """Score one normalized notice against the expansion. Zero means drop it.

    A description mention is not enough on its own. The notice must match a
    commodity code, the title, or the classification text. Description terms
    only raise the score of a notice that already matched one of those.
    """
    if not expansion.has_signal:
        return 0, []
    score = 0
    reasons: list[str] = []
    matched = prefix_hit(expansion.prefixes, notice_code_text(opportunity))
    title = normalize_text(str(opportunity.get("title") or ""))
    class_text = notice_class_text(opportunity)
    description = affirmative_text(normalize_text(str(opportunity.get("description") or "")))
    title_hits = [term for term in expansion.terms if phrase_in(term, title)]
    class_hits = [
        term for term in expansion.terms
        if phrase_in(term, class_text) and term not in title_hits
    ]
    if not matched and not title_hits and not class_hits:
        return 0, []
    if matched:
        score += 40
        reasons.append(f"commodity code {matched}")
    described = [
        term for term in expansion.terms
        if phrase_in(term, description) and term not in title_hits and term not in class_hits
    ]
    if title_hits:
        score += 18 * len(title_hits[:3])
        reasons.append("title: " + ", ".join(title_hits[:3]))
    if class_hits:
        score += 12 * len(class_hits[:3])
        reasons.append("classification: " + ", ".join(class_hits[:3]))
    if described:
        score += 5 * len(described[:3])
        reasons.append("description: " + ", ".join(described[:3]))
    return score, reasons


def select_candidates(
    opportunities: list[dict],
    expansion: Expansion,
    *,
    limit: int = MAX_CANDIDATES,
) -> tuple[list[dict], int]:
    """Return ``(top candidates, number of notices that scored at all)``.

    Candidates keep their prefilter reasons on ``prefilter_reasons``. The
    input notices are not mutated.
    """
    scored: list[tuple[int, dict]] = []
    for opportunity in opportunities:
        score, reasons = prefilter_score(opportunity, expansion)
        if score <= 0:
            continue
        carried = dict(opportunity)
        carried["prefilter_score"] = score
        carried["prefilter_reasons"] = reasons
        scored.append((score, carried))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("reference") or "")))
    return [item[1] for item in scored[:limit]], len(scored)


def fit_state(profile: dict, opportunity: dict) -> dict[str, str]:
    """The named fields Jev sees for one notice. Truncated to bound tokens."""
    codes = " ".join(
        part for part in (
            str(opportunity.get("unspsc") or ""),
            str(opportunity.get("unspsc_description") or ""),
            str(opportunity.get("gsin") or ""),
            str(opportunity.get("gsin_description") or ""),
            str(opportunity.get("commodity_codes") or ""),
            str(opportunity.get("commodity_titles") or ""),
            str(opportunity.get("category") or ""),
        ) if part
    )
    return {
        "business": str(profile.get("description") or "")[:BUSINESS_CHARS],
        "location": str(profile.get("location") or "")[:160],
        "notice_title": str(opportunity.get("title") or "")[:240],
        "notice_buyer": str(opportunity.get("buyer") or "")[:160],
        "notice_codes": codes[:400],
        "notice_text": str(opportunity.get("description") or "")[:NOTICE_CHARS],
    }


def program_state(profile: dict, program: dict) -> dict[str, str]:
    industries = ", ".join(str(item) for item in program.get("industries") or [])
    tags = ", ".join(str(item) for item in program.get("eligibility_tags") or [])
    return {
        "business": str(profile.get("description") or "")[:BUSINESS_CHARS],
        "location": str(profile.get("location") or "")[:160],
        "program_name": str(program.get("name") or "")[:200],
        "program_summary": str(program.get("summary") or "")[:400],
        "program_eligibility": str(program.get("eligibility") or "")[:400],
        "program_industries": (industries + (" " + tags if tags else ""))[:240],
    }


def parse_fit(body: dict) -> dict[str, Any]:
    """Read the supplies and capability choices from one Jev response."""
    answers = body["answers"]
    supplies = answers["supplies"]
    capability = answers["capability"]
    verdict = str(supplies.get("choice") or "no")
    if verdict not in _SUPPLY_CRITERIA:
        verdict = "no"
    chosen = str(capability.get("choice") or "none")
    if chosen not in _CAPABILITY_CRITERIA or verdict == "no":
        chosen = "none"
    supply_probs = supplies.get("probabilities") or {}
    capability_probs = capability.get("probabilities") or {}
    return {
        "verdict": verdict,
        "verdict_prob": _float_or_none(supply_probs.get(verdict)),
        "capability": chosen,
        "capability_prob": _float_or_none(capability_probs.get(chosen)),
        "model": str(body.get("model") or ""),
    }


def parse_program(body: dict) -> dict[str, Any]:
    relevance = body["answers"]["relevance"]
    verdict = str(relevance.get("choice") or "partial")
    if verdict not in {"yes", "partial", "no"}:
        verdict = "partial"
    return {
        "verdict": verdict,
        "verdict_prob": _float_or_none((relevance.get("probabilities") or {}).get(verdict)),
        "model": str(body.get("model") or ""),
    }


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Drop cached Jev answers. Tests use this so cases do not leak."""
    with _cache_lock:
        _cache.clear()


def _cache_key(version: str, model: str, state: dict) -> str:
    blob = json.dumps({"v": version, "m": model, "s": state}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    with _cache_lock:
        found = _cache.get(key)
        if found is None:
            return None
        _cache.move_to_end(key)
        return dict(found)


def _cache_put(key: str, value: dict[str, Any]) -> None:
    with _cache_lock:
        _cache[key] = dict(value)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)


class Classification:
    """Outcome of one bounded Jev pass."""

    def __init__(self, status: str, verdicts: dict[str, dict], warnings: list[str]) -> None:
        self.status = status
        self.verdicts = verdicts
        self.warnings = warnings


def _run_payloads(
    jobs: list[tuple[str, dict]],
    api_key: str,
    *,
    deadline: float,
) -> tuple[dict[str, dict], str]:
    """Classify ``jobs`` until ``deadline``. Return ``(verdicts, failure)``.

    ``failure`` is ``unauthenticated`` when Jev rejects the key, ``unavailable``
    when nothing came back, and ``""`` when at least one answer arrived.
    """
    verdicts: dict[str, dict] = {}
    if not jobs:
        return verdicts, "unavailable"
    stop = threading.Event()

    def work(payload: dict) -> tuple[dict | None, str, int]:
        return jev.call_jev(
            payload, api_key, MAX_RETRIES, REQUEST_TIMEOUT, deadline=deadline, stop=stop,
        )

    pool = ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="jev-fit")
    try:
        futures = {pool.submit(usage.bind(work), payload): key for key, payload in jobs}
        pending = set(futures)
        auth_failed = False
        while pending and not stop.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                key = futures[future]
                try:
                    body, _error, attempts = future.result()
                except jev.AuthError:
                    auth_failed = True
                    stop.set()
                    break
                except Exception:
                    continue
                if attempts == 0 or not isinstance(body, dict):
                    continue
                try:
                    parsed = parse_fit(body) if "supplies" in (body.get("answers") or {}) else parse_program(body)
                except (KeyError, TypeError, ValueError):
                    continue
                verdicts[key] = parsed
                _cache_put(key, parsed)
            if auth_failed:
                break
        if auth_failed:
            return {}, "unauthenticated"
        if not verdicts:
            return {}, "unavailable"
        return verdicts, ""
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _classify(
    states: list[tuple[str, dict]],
    questions: dict,
    version: str,
    *,
    deadline_seconds: float,
    parser_hint: str,
) -> Classification:
    """Shared cache, batch, and fallback status for notice and program calls.

    ``parser_hint`` is unused at runtime; parsing is chosen from the response
    shape so a cached program answer is not re-read as a notice.
    """
    del parser_hint  # kept so callers document which question set they sent
    api_key = typesafe_api_key()
    if not api_key:
        return Classification("unconfigured", {}, [UNCONFIGURED_WARNING])
    model = os.environ.get("TYPESAFE_MODEL", "").strip() or DEFAULT_MODEL
    verdicts: dict[str, dict] = {}
    jobs: list[tuple[str, dict]] = []
    index_by_cache: dict[str, str] = {}
    for reference, state in states:
        key = _cache_key(version, model, state)
        index_by_cache.setdefault(key, reference)
        cached = _cache_get(key)
        if cached is not None:
            verdicts[reference] = cached
            continue
        if key in {job[0] for job in jobs}:
            continue
        jobs.append((key, {"model": model, "state": state, "questions": questions}))
    if not jobs and verdicts:
        return Classification("ok", verdicts, [])
    if not jobs:
        return Classification("unavailable", {}, [UNAVAILABLE_WARNING])
    fresh, failure = _run_payloads(jobs, api_key, deadline=time.monotonic() + deadline_seconds)
    if failure == "unauthenticated":
        return Classification("unauthenticated", {}, [UNAUTHENTICATED_WARNING])
    for key, parsed in fresh.items():
        reference = index_by_cache.get(key)
        if reference:
            verdicts[reference] = parsed
    if not verdicts:
        warning = UNAVAILABLE_WARNING if version == FIT_PROMPT_VERSION else PROGRAM_UNAVAILABLE_WARNING
        return Classification("unavailable", {}, [warning])
    warnings: list[str] = []
    if len(verdicts) < len(states):
        warnings.append(
            f"TypeSafe Jev classified {len(verdicts)} of {len(states)} "
            f"before the time limit."
        )
    return Classification("ok", verdicts, warnings)


def classify_notices(
    profile: dict,
    opportunities: list[dict],
    *,
    deadline_seconds: float = DEADLINE_SECONDS,
) -> Classification:
    """Classify each candidate notice. Keys in ``verdicts`` are references."""
    states = [
        (str(opportunity.get("reference") or ""), fit_state(profile, opportunity))
        for opportunity in opportunities
        if str(opportunity.get("reference") or "").strip()
    ]
    return _classify(
        states, FIT_QUESTIONS, FIT_PROMPT_VERSION,
        deadline_seconds=deadline_seconds, parser_hint="fit",
    )


def classify_programs(
    profile: dict,
    programs: list[dict],
    *,
    deadline_seconds: float = PROGRAM_DEADLINE_SECONDS,
) -> Classification:
    """Classify up to ``MAX_PROGRAMS`` support programs. Keys are program ids."""
    states = [
        (str(program.get("id") or ""), program_state(profile, program))
        for program in programs[:MAX_PROGRAMS]
        if str(program.get("id") or "").strip()
    ]
    result = _classify(
        states, PROGRAM_QUESTIONS, PROGRAM_PROMPT_VERSION,
        deadline_seconds=deadline_seconds, parser_hint="program",
    )
    if result.status == "unconfigured":
        # Tags still explain the match. Silence is better than a warning on every call.
        return Classification("unconfigured", {}, [])
    if result.status == "unauthenticated":
        return Classification(
            "unauthenticated", {}, [PROGRAM_UNAVAILABLE_WARNING],
        )
    return result


def capability_label(capability: str) -> str:
    return CAPABILITY_LABELS.get(capability, capability.replace("_", " "))


def rank_notices(
    candidates: list[dict],
    verdicts: dict[str, dict],
    scores: dict[str, tuple[int, int, list[str]]],
) -> list[tuple[int, int, dict, list[str]]]:
    """Order candidates by Jev verdict, then the existing score, then closing.

    ``scores`` maps a reference to ``(existing_score, days_until, reasons)``.
    Notices classified ``no`` are omitted. A notice with no verdict, after a
    partial timeout, stays in the list below yes and partial.
    """
    ranked: list[tuple[int, int, int, dict, list[str]]] = []
    for opportunity in candidates:
        reference = str(opportunity.get("reference") or "")
        parsed = verdicts.get(reference)
        existing, days_until, reasons = scores.get(reference, (0, 9999, []))
        if parsed is None:
            verdict = "unclassified"
            capability = ""
        else:
            verdict = str(parsed.get("verdict") or "no")
            capability = str(parsed.get("capability") or "")
        if verdict == "no":
            continue
        shown = dict(opportunity)
        shown["fit_verdict"] = verdict
        shown["fit_capability"] = capability
        if verdict == "unclassified":
            line = "Fit: not classified before the time limit"
        else:
            label = capability_label(capability) if capability and capability != "none" else verdict
            line = f"Fit: {verdict} ({label})" if capability else f"Fit: {verdict}"
        shown["fit_line"] = line
        fit_reasons = [line, *reasons]
        rank = VERDICT_RANK.get(verdict, 0)
        ranked.append((rank, existing, days_until, shown, fit_reasons))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2], str(item[3].get("reference") or "")))
    return [(score, days_until, opportunity, reasons) for _rank, score, days_until, opportunity, reasons in ranked]
