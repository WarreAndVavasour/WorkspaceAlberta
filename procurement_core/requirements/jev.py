"""TypeSafe Jev (System One) questions and a small stdlib HTTP client.

API (https://docs.typesafe.ai/api)::

    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <TYPESAFE_API_KEY>
    {"model": ..., "state": {...}, "questions": {...}}

The response carries ``answers`` (per question: ``choice`` and ``probabilities`` for a
Choice, ``noul`` for a Noul), ``model`` and ``usage.input_tokens``.

The question definitions here are shared with the research scripts in
``pipelines/requirement_classifier/`` so the hosted tool and the evaluation runs ask
exactly the same questions:

- L0, one request per unit: ``response_type`` (Choice over RESPONSE_TYPES, ``none`` last),
  ``in_bid`` (Noul) and ``mandatory`` (Noul); unit gate in :func:`derive`;
- pages, one request per page: ``document_part`` (Choice) and ``bid_content`` (Noul);
- L1, one request per gated unit: ``sub_tag`` (Choice over the type's sub-tags, reject last).

The API key is passed in by the caller, sent only in the Authorization header, and never
included in any return value, exception message or log line.
"""

from __future__ import annotations

import collections
import http.client
import json
import random
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from procurement_core.requirements import tags

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"  # pinned; "jev-latest" moves when a new release ships
PRICE_PER_MTOK = 0.042  # USD per million input tokens, output free (docs.typesafe.ai/models)
RETRY_STATUSES = {408, 429} | set(range(500, 600))  # same set as the Python SDK's RetryPolicy
USER_AGENT = "WorkspaceAlberta-RequirementClassifier/1.0"

L0_PROMPT_VERSION = "jev-req-v2"
PAGES_PROMPT_VERSION = "jev-pages-v1"
L1_PROMPT_VERSION = "jev-l1-v2"

RESPONSE_TYPES = tags.RESPONSE_TYPES

# --------------------------------------------------------------------------- L0 (per unit)

# Jev 1.13 can lean toward the first Choice option (docs: model-jaggedness/jev-1.13),
# so the catch-all "none" goes last rather than first.
OPTION_ORDER = [k for k in RESPONSE_TYPES if k != "none"] + ["none"]

# Dates and submission logistics are acted on before bids close (calendar, checklist), but Jev's
# in_bid score for them is low because nothing is "put in" the bid. They skip the in_bid gate.
GATE_EXEMPT = {"attendance", "submission_instruction"}
IN_BID_THRESHOLD = 0.5


def derive(row: dict) -> dict:
    """requires_response = a response type was chosen and it passes the in_bid gate."""
    label, ib = row.get("label"), row.get("in_bid_prob")
    if label:
        row["requires_response"] = label != "none" and (ib is None or ib >= IN_BID_THRESHOLD or label in GATE_EXEMPT)
    return row


QUESTIONS = {
    "response_type": {
        "type": "choice",
        "instructions": (
            "`clause` is one clause from a Canadian public-sector tender document. "
            "What must the bidder put in its bid submission, before bids close, because of `clause`? "
            "Judge what the bidder must do, not what the clause is about. "
            "Use `section`, `text_before` and `text_after` only as context. "
            "Pick 'none' for background, definitions, the buyer's process, specifications of the work, "
            "the printed wording of a form, bond or contract, and any duty of the contractor after award."
        ),
        "criteria": {k: RESPONSE_TYPES[k][0] for k in OPTION_ORDER},
    },
    "in_bid": {
        "type": "noul",
        "instructions": (
            "Must the bidder include something in its bid or proposal, or do something before bids close "
            "(such as attend a site visit), because of `clause`? Duties after contract award, definitions, "
            "specifications of the work and printed form wording do not count."
        ),
        "criteria": {
            "true": "The bidder must put something in its bid, or act before bids close, because of this clause.",
            "false": "Nothing goes in the bid because of this clause, or it only applies after award.",
        },
    },
    "mandatory": {
        "type": "noul",
        "instructions": (
            "Does `clause` say that something the bidder must put in its bid is mandatory or required, "
            "or that a bid will be rejected or disqualified without it? Mandatory duties after award do not count."
        ),
        "criteria": {
            "true": "The clause states the item is mandatory or required, or a bid without it is rejected.",
            "false": "The clause does not make anything mandatory for the bid, or the bidder supplies nothing.",
        },
    },
}


def build_state(unit: dict) -> dict:
    """The unit and its context as named fields (same content as the LLM labeller's prompt)."""
    return {
        "document": unit.get("doc_name", ""),
        "section": unit.get("section") or "(none)",
        "page": unit.get("page"),
        "text_before": unit.get("prev_text") or "(start)",
        "clause": unit.get("text", ""),
        "text_after": unit.get("next_text") or "(end)",
    }


def parse_l0(body: dict) -> dict:
    """L0 answers -> label, probabilities, in_bid/mandatory probabilities and the unit gate."""
    rt = body["answers"]["response_type"]
    probs = {k: float(v) for k, v in rt["probabilities"].items()}
    row: dict[str, Any] = {
        "label": rt["choice"],
        "prob": probs.get(rt["choice"]),
        "confidence": rt.get("confidence"),
        "probabilities": probs,
        "in_bid_prob": None,
        "mandatory": None,
        "mandatory_prob": None,
    }
    ib = body["answers"].get("in_bid")
    if ib is not None:
        row["in_bid_prob"] = float(ib["noul"])
    md = body["answers"].get("mandatory")
    if md is not None:
        row["mandatory_prob"] = float(md["noul"])
        row["mandatory"] = row["mandatory_prob"] >= 0.5
    return derive(row)


# --------------------------------------------------------------------------- pages

BID_CONTENT_THRESHOLD = 0.5
PAGE_MAX_CHARS = 6000

PAGE_QUESTIONS = {
    "document_part": {
        "type": "choice",
        "instructions": "`page_text` is one page of a public-sector tender package. Which part of the package is this page?",
        "criteria": dict(tags.DOCUMENT_PARTS),
    },
    "bid_content": {
        "type": "noul",
        "instructions": (
            "Does this page tell the bidder what it must prepare, fill in, sign or submit WITH ITS BID, "
            "before bids close? Pages about what the contractor must do or submit after award count as no."
        ),
        "criteria": {
            "true": "The page sets out content, forms or documents the bidder submits with its bid.",
            "false": "The page is about the process, the contract, the work, or anything due after award.",
        },
    },
}


def page_state(units: list[dict], page: int, document: str = "") -> dict:
    """One page's request state, built from that page's units (no extra PDF parsing)."""
    heads = list(dict.fromkeys(u["section"].split(" > ")[-1] for u in units if u.get("section")))[:8]
    text = "\n".join(u["text"] for u in units)[:PAGE_MAX_CHARS]
    return {"document": units[0].get("doc_name", "") if units else document, "page": page, "headings": heads,
            "page_text": text or "(no text extracted on this page)"}


def page_states(units: list[dict], pages: int) -> dict[int, dict]:
    """Request state per page 1..pages for one document's units."""
    by_page = collections.defaultdict(list)
    for u in sorted(units, key=lambda u: u["unit_index"]):
        by_page[u["page"]].append(u)
    return {p: page_state(by_page.get(p, []), p) for p in range(1, pages + 1)}


def parse_page(body: dict) -> dict:
    a = body["answers"]
    probs = {k: float(v) for k, v in a["document_part"]["probabilities"].items()}
    part = a["document_part"]["choice"]
    bc = float(a["bid_content"]["noul"])
    return {"part": part, "part_prob": probs.get(part), "part_probabilities": probs, "bid_content_prob": bc,
            "page_gate": part in tags.BID_PARTS or bc >= BID_CONTENT_THRESHOLD}


# --------------------------------------------------------------------------- L1 (per gated unit)

def l1_questions(l0_label: str) -> dict:
    return {
        "sub_tag": {
            "type": "choice",
            "instructions": (
                f"`clause` comes from a public-sector tender and was classified as '{l0_label}': "
                f"{RESPONSE_TYPES[l0_label][0]} Which kind of '{l0_label}' does the bidder have to "
                "supply in its bid because of `clause`? Use the other fields only as context."
            ),
            "criteria": tags.sub_tag_options(l0_label),  # reject option is last (first-option bias)
        },
    }


def parse_l1(body: dict, l0_label: str) -> dict:
    a = body["answers"]["sub_tag"]
    probs = {k: float(v) for k, v in a["probabilities"].items()}
    st = a["choice"]
    return {"sub_tag": st, "sub_prob": probs.get(st), "sub_probabilities": probs,
            "tag": None if st == tags.NOT_A_REQUIREMENT[0] else f"{l0_label}.{st}"}


def input_tokens(body: dict | None) -> int:
    try:
        return int(((body or {}).get("usage") or {}).get("input_tokens") or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


# --------------------------------------------------------------------------- HTTP client

class AuthError(RuntimeError):
    """TypeSafe refused the API key (HTTP 401/403)."""


def redact(text: str, api_key: str | None) -> str:
    """Remove the key from any text that might be shown or logged."""
    text = str(text)
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return text


def retry_delay(headers: Any, attempt: int) -> float:
    if headers is not None:
        ms = headers.get("retry-after-ms")
        sec = headers.get("retry-after")
        try:
            if ms:
                return min(60.0, float(ms) / 1000)
            if sec:
                return min(60.0, float(sec))
        except ValueError:
            pass
    return min(30.0, 0.5 * 2 ** attempt) * (1 + random.uniform(-0.25, 0.25))


def call_jev(
    payload: dict,
    api_key: str,
    max_retries: int = 6,
    timeout: float = 60.0,
    *,
    deadline: float | None = None,
    stop: Any = None,
) -> tuple[dict | None, str, int]:
    """Return ``(body, error, attempts)``; raise :class:`AuthError` on HTTP 401/403.

    ``attempts == 0`` means no request was sent (time limit or stop); that is not a
    classifier failure.

    Same retry rules as the research client: retry connection errors, timeouts and HTTP
    408/429/5xx with ``retry-after-ms``/``retry-after`` or exponential backoff with jitter.
    ``deadline`` (``time.monotonic()`` value) bounds every request timeout and backoff
    sleep; a call that cannot finish before it gives up. ``stop`` is an optional
    ``threading.Event`` checked before each attempt.
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    error = ""
    attempts = 0
    for attempt in range(max_retries + 1):
        if stop is not None and stop.is_set():
            return None, error or "stopped before the request was sent", attempts
        request_timeout = timeout
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining < 1:
                return None, error or "time limit reached before the request was sent", attempts
            request_timeout = min(timeout, remaining)
        request = Request(API_URL, data=data, method="POST", headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        attempts = attempt + 1
        headers = None
        try:
            with urlopen(request, timeout=request_timeout) as response:
                raw = response.read()
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                return None, "invalid JSON in the classifier response", attempts
            if not isinstance(body, dict):
                return None, "unexpected classifier response (not a JSON object)", attempts
            return body, "", attempts
        except HTTPError as exc:
            headers = exc.headers
            try:
                body = exc.read()[:500].decode("utf-8", errors="replace")
            except Exception:
                body = ""
            error = redact(f"HTTP {exc.code}: {body}", api_key)
            if exc.code in (401, 403):
                raise AuthError(f"HTTP {exc.code}: the classifier rejected this server's API key.") from None
            if exc.code not in RETRY_STATUSES:
                return None, error, attempts
        except (URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            error = redact(f"{type(exc).__name__}: {str(reason)[:200]}", api_key)
        if attempt < max_retries:
            delay = retry_delay(headers, attempt)
            if deadline is not None and time.monotonic() + delay >= deadline - 1:
                return None, error, attempts
            if stop is not None:
                if stop.wait(delay):
                    return None, error, attempts
            else:
                time.sleep(delay)
    return None, error, attempts
