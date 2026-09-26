"""Cohere tool-calling query planner: natural language -> structured APC filter.

Why this exists
---------------
Relevance used to be decided by substring matching a user's capability phrases
against a flattened text blob (see ``score_alberta_opportunity``), and the APC
filter's native ``unspsc`` field was always sent empty. Multi-word capability
phrases such as "custom software development and systems integration" never
appear verbatim in a tender title, so capability matching contributed nothing.

The unstructured input in this system is the *user's intent*, not the corpus:
APC rows already arrive with UNSPSC codes, categories and regions. So we spend
exactly one LLM call per query turning intent into a structured filter, and let
APC do authoritative code-level filtering server-side.

The model is grounded in the live ``CommodityCodes`` facet, so it selects from
segments that actually exist in the corpus rather than recalling UNSPSC from
memory. Any code it returns that is not in the vocabulary is dropped.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

# UNSPSC segment titles, derived from the codes APC actually returns. Segment
# level (first two digits + "000000") is the right granularity here: it is
# stable, small enough to put in a prompt, and matches how APC facets.
SEGMENT_TITLES = {
    "10000000": "Live plants, animals, farming and fishing",
    "11000000": "Mineral, textile and inedible plant/animal materials",
    "12000000": "Chemicals including bio chemicals and gas materials",
    "13000000": "Resin, rosin, rubber, foam, film and elastomeric materials",
    "14000000": "Paper materials and products",
    "15000000": "Fuels, fuel additives, lubricants and anti corrosives",
    "20000000": "Mining, well drilling machinery and accessories",
    "21000000": "Farming and fishing and forestry machinery",
    "22000000": "Building and construction machinery and accessories",
    "23000000": "Industrial manufacturing and processing machinery",
    "24000000": "Material handling, conditioning and storage machinery",
    "25000000": "Commercial, military and private vehicles",
    "26000000": "Power generation and distribution machinery",
    "27000000": "Tools and general machinery",
    "30000000": "Structures and building and construction components",
    "31000000": "Manufacturing components and supplies",
    "32000000": "Electronic components and supplies",
    "39000000": "Electrical systems, lighting, components and supplies",
    "40000000": "Distribution and conditioning systems and equipment",
    "41000000": "Laboratory, measuring, observing and testing equipment",
    "42000000": "Medical equipment and accessories and supplies",
    "43000000": "Information technology broadcasting and telecommunications",
    "44000000": "Office equipment and accessories and supplies",
    "45000000": "Printing and photographic and audio and visual equipment",
    "46000000": "Defense and law enforcement and security and safety",
    "47000000": "Cleaning equipment and supplies",
    "48000000": "Service industry machinery and equipment",
    "49000000": "Sports and recreational equipment and supplies",
    "50000000": "Food beverage and tobacco products",
    "51000000": "Drugs and pharmaceutical products",
    "52000000": "Domestic appliances and consumer electronic products",
    "53000000": "Apparel and luggage and personal care products",
    "54000000": "Timepieces, jewellery and gemstone products",
    "55000000": "Published products",
    "56000000": "Furniture and furnishings",
    "60000000": "Musical instruments, games, toys, arts and crafts",
    "64000000": "Financial instruments, products, contracts and agreements",
    "70000000": "Farming and fishing and forestry and wildlife services",
    "71000000": "Mining and oil and gas services",
    "72000000": "Building, facility construction and maintenance services",
    "73000000": "Industrial production and manufacturing services",
    "76000000": "Industrial cleaning services",
    "77000000": "Environmental services",
    "78000000": "Transportation and storage and mail services",
    "80000000": "Management and business professionals and administrative services",
    "81000000": "Engineering and research and technology based services",
    "82000000": "Editorial, design, graphic and fine art services",
    "83000000": "Public utilities and public sector related services",
    "84000000": "Financial and insurance services",
    "85000000": "Healthcare services",
    "86000000": "Education and training services",
    "90000000": "Travel, food, lodging and entertainment services",
    "91000000": "Personal and domestic services",
    "92000000": "National defense and public order and security services",
    "93000000": "Politics and civic affairs services",
    "94000000": "Organizations and clubs",
}

CATEGORY_CODES = {
    "SRV": "Services",
    "GD": "Goods",
    "CNST": "Construction",
}

PLANNER_TOOL = {
    "type": "function",
    "function": {
        "name": "set_opportunity_filter",
        "description": (
            "Translate a supplier's description of its business into a structured "
            "Alberta Purchasing Connection filter. Select only UNSPSC segments that "
            "correspond to work the supplier could actually deliver."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "unspsc_segments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "UNSPSC segment codes (8 digits ending in 000000) chosen from "
                        "the provided vocabulary. Order by relevance, most relevant first."
                    ),
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(CATEGORY_CODES)},
                    "description": "APC category codes: SRV (Services), GD (Goods), CNST (Construction).",
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Short single- or two-word search terms that would plausibly "
                        "appear in a matching tender. Not whole sentences."
                    ),
                },
                "regions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Delivery regions mentioned, e.g. 'Alberta', 'Calgary'.",
                },
            },
            "required": ["unspsc_segments", "categories", "keywords"],
        },
    },
}


def cohere_api_key() -> str | None:
    for name in ("COHERE_API_KEY", "COHERE_PROD_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    return None


def vocabulary_from_facets(facets: dict[str, Any]) -> list[tuple[str, str, int]]:
    """Build a grounded (code, title, count) vocabulary from the live APC facet.

    Sub-segment codes are rolled up to their segment so the prompt stays small.
    """
    counts: dict[str, int] = {}
    if not isinstance(facets, dict):
        return []
    entries = facets.get("CommodityCodes")
    if not isinstance(entries, list):
        return []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("value") or "")
        if len(code) != 8 or not code.isdigit():
            continue
        segment = code[:2] + "000000"
        try:
            count = max(0, int(entry.get("count") or 0))
        except (TypeError, ValueError):
            continue
        counts[segment] = counts.get(segment, 0) + count
    rows = [(code, SEGMENT_TITLES.get(code, "Unknown"), n) for code, n in counts.items()]
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows


def _render_vocabulary(vocab: list[tuple[str, str, int]]) -> str:
    return "\n".join(f"{code}  {title}  ({n} open)" for code, title, n in vocab)


def _post_chat(payload: dict, api_key: str, url: str, timeout: float = 6) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def plan_query(
    intent: str,
    vocab: list[tuple[str, str, int]],
    *,
    api_key: str | None = None,
    model: str | None = None,
    url: str | None = None,
    post_fn: Any = None,
    timeout: float = 6,
) -> dict[str, Any]:
    """Turn a natural-language business description into a structured filter.

    Returns a dict with ``unspsc``, ``categories``, ``keywords``, ``regions``
    and ``source``. ``source`` is "cohere" on success and "fallback" when no
    key is configured or the model declined to call the tool, so callers can
    always proceed.
    """
    api_key = api_key or cohere_api_key()
    if not api_key:
        return _fallback(intent, "no-api-key")
    if not vocab:
        return _fallback(intent, "no-vocabulary")

    # Imported lazily so this module stays importable without service.py.
    from procurement_core.service import (  # noqa: PLC0415
        COHERE_CHAT_COMPLETIONS_URL,
        COHERE_MODEL,
    )

    payload = {
        "model": model or COHERE_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You map a supplier's business description onto Alberta Purchasing "
                    "Connection filters. Call set_opportunity_filter exactly once.\n\n"
                    "Choose UNSPSC segments ONLY from this vocabulary:\n"
                    + _render_vocabulary(vocab)
                    + "\n\nBe selective: pick the segments where this supplier could "
                    "credibly win work, not everything adjacent."
                ),
            },
            {"role": "user", "content": intent[:8000]},
        ],
        "tools": [PLANNER_TOOL],
        # NB: command-a-plus rejects `tool_choice` ("not supported for this
        # model"), so we rely on the instruction above and fall back cleanly if
        # the model answers in prose instead of calling the tool.
        "temperature": 0.2,
    }

    try:
        endpoint = url or COHERE_CHAT_COMPLETIONS_URL
        data = (post_fn(payload, api_key, endpoint) if post_fn else
                _post_chat(payload, api_key, endpoint, timeout=timeout))
    except Exception:  # noqa: BLE001 - never let planning break search
        return _fallback(intent, "request-failed")

    try:
        calls = ((data.get("choices") or [{}])[0].get("message") or {}).get("tool_calls") or []
        if not calls:
            return _fallback(intent, "no-tool-call")
        if not isinstance(calls, list) or len(calls) != 1:
            return _fallback(intent, "bad-tool-call")
        if calls[0]["function"]["name"] != "set_opportunity_filter":
            return _fallback(intent, "bad-tool-call")
        args = json.loads(calls[0]["function"]["arguments"])
        if not isinstance(args, dict):
            return _fallback(intent, "bad-arguments")
        for field in ("unspsc_segments", "categories", "keywords", "regions"):
            value = args.get(field, [] if field == "regions" else None)
            if (not isinstance(value, list) or len(value) > 20
                    or any(not isinstance(v, str) or len(v) > 200 for v in value)):
                return _fallback(intent, "bad-arguments")
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return _fallback(intent, "bad-arguments")

    allowed = {code for code, _, _ in vocab}
    # Drop anything outside the grounded vocabulary: the model cannot invent codes.
    codes = [c for c in _as_list(args.get("unspsc_segments")) if c in allowed]
    categories = [c for c in _as_list(args.get("categories")) if c in CATEGORY_CODES]

    return {
        "unspsc": codes,
        "categories": categories,
        "keywords": _as_list(args.get("keywords")),
        "regions": _as_list(args.get("regions")),
        "source": "cohere",
    }


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(v.strip() for v in value if isinstance(v, str) and v.strip()))


def _fallback(intent: str, reason: str) -> dict[str, Any]:
    """Keyword-only plan so search still works without Cohere."""
    from procurement_core.service import tokenize_keywords  # noqa: PLC0415

    return {
        "unspsc": [],
        "categories": [],
        "keywords": tokenize_keywords(intent)[:8],
        "regions": [],
        "source": "fallback",
        "reason": reason,
    }
