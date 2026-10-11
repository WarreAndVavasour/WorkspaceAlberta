#!/usr/bin/env python3
"""
Procurement Core Service — the engine behind every WorkspaceAlberta tool.

This module is the single source of truth for procurement logic. It has no MCP
dependency of its own: the stdio adapter (``mcp-servers/canadabuys/server.py``)
and the hosted HTTP adapter (``mcp-servers/canadabuys/server_http.py``) are both
thin wrappers that dispatch into :func:`call_tool_text` here. That means every
tool behaves identically whether it is called over stdio MCP, StreamableHTTP
MCP, or the REST/OpenAPI mirror.

Layout (top to bottom):

1.  **Configuration & env loading** — repo-local ``.env`` support, data-cache
    directory, CanadaBuys open-data URL, Cohere/Hugging Face model routes, and
    Alberta Purchasing Connection (APC) API bases and category-code maps.
2.  **Model routing** — :func:`call_cohere_chat` prefers direct Cohere keys
    (``COHERE_API_KEY`` then ``COHERE_PROD_API_KEY`` failover on rate/quota
    errors, see :func:`is_cohere_limit_error`) and falls back to the Hugging
    Face OpenAI-compatible router for the W4A4 community route.
3.  **Alberta Purchasing Connection client** — filter/payload builders,
    search (:func:`search_alberta_api`), public detail fetch, markdown
    renderers, and profile scoring for APC rows.
4.  **Business profile** — keyword extraction, industry inference,
    UNSPSC-prefix maps, and deterministic contract scoring
    (:func:`score_contract`). Profiles persist to ``DATA_DIR/profile.json``.
5.  **Unified opportunity layer** — normalizes CanadaBuys CSV rows and APC
    JSON into one shared shape (see :func:`normalize_canadabuys_contract` and
    :func:`normalize_alberta_opportunity`) so search, deadlines, matching, and
    the daily brief can treat both sources the same way.
6.  **Tool dispatch** — ``TOOL_NAMES`` lists every public tool; each name maps
    to an async handler function of the same name in this module. Handlers
    accept an arguments ``dict`` and return markdown text.
7.  **Bid room bridge** — :func:`process_bid_room_artifact` hands off to
    ``procurement_core.e2b_bid_room`` for sandboxed attachment processing.

Data flow: CanadaBuys publishes a full open-tender CSV which is fetched with
:func:`fetch_all_contracts` and cached at ``DATA_DIR/latest.csv``; APC is
queried live per request. Scoring is deterministic; APC candidate retrieval
uses an optional bounded Cohere query planner with lexical fallback. The model layer
also supports judgment tools (``analyze_contract_with_cohere`` and the
sandboxed bid-room review).

Configuration (environment variables):
    CANADABUYS_DATA_DIR                    Cache dir (default ``~/.canadabuys/``)
    CANADABUYS_LOAD_ENV_FILE               Set 0/false to skip .env loading
    COHERE_API_KEY / COHERE_PROD_API_KEY   Direct Cohere routes (failover order)
    HF_TOKEN / HUGGINGFACEHUB_API_TOKEN    Hugging Face router fallback
    CANADABUYS_COHERE_MODEL                Default ``command-a-plus-05-2026``
    CANADABUYS_COHERE_REASONING_EFFORT     Only sent when explicitly set
    ALBERTA_APC_API_BASE / _APP_BASE       APC endpoint overrides
    PROCUREMENT_FIXTURE_DIR                Offline CanadaBuys CSV + APC JSON fixtures
"""

import asyncio
import csv
import gzip
import json
import os
import re
from datetime import date, datetime, timedelta, timezone, tzinfo
import time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import fixtures
from .apc_documents import APC_ACCESS_MESSAGE, apc_document_manifest, apc_posting_url


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    """Load repo-local .env values for local MCP runs without printing secrets."""
    if os.environ.get("CANADABUYS_LOAD_ENV_FILE", "1").lower() in {"0", "false", "no"}:
        return

    for env_path in (ROOT_DIR / ".env", Path.cwd() / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value.strip().strip('"').strip("'")


load_local_env()

# Configuration
DATA_DIR = Path(os.environ.get("CANADABUYS_DATA_DIR", Path.home() / ".canadabuys"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# CanadaBuys open data URLs
OPEN_TENDERS_URL = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"

REQUEST_HEADERS = {
    "User-Agent": "CanadaBuys-MCP/1.0",
    "Accept": "*/*",
}

HF_CHAT_COMPLETIONS_URL = os.environ.get(
    "CANADABUYS_HF_CHAT_COMPLETIONS_URL",
    "https://router.huggingface.co/v1/chat/completions",
)
COHERE_CHAT_COMPLETIONS_URL = os.environ.get(
    "CANADABUYS_COHERE_CHAT_COMPLETIONS_URL",
    "https://api.cohere.ai/compatibility/v1/chat/completions",
)
COHERE_MODEL = os.environ.get(
    "CANADABUYS_COHERE_MODEL",
    "command-a-plus-05-2026",
)
COHERE_HF_MODEL = os.environ.get(
    "CANADABUYS_COHERE_HF_MODEL",
    "CohereLabs/command-a-plus-05-2026-w4a4:cohere",
)
COHERE_API_KEY_ENV_NAMES = (
    "COHERE_API_KEY",
    "COHERE_PROD_API_KEY",
)
HF_TOKEN_ENV_NAMES = (
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
)
MAX_CONTRACT_PROMPT_CHARS = 12000

ALBERTA_APC_API_BASE = os.environ.get(
    "ALBERTA_APC_API_BASE",
    "https://purchasing.alberta.ca/api",
).rstrip("/")
ALBERTA_APC_APP_BASE = os.environ.get(
    "ALBERTA_APC_APP_BASE",
    "https://purchasing.alberta.ca",
).rstrip("/")
ALBERTA_CATEGORY_CODES = {
    "construction": "CNST",
    "cnst": "CNST",
    "goods": "GD",
    "good": "GD",
    "gd": "GD",
    "services": "SRV",
    "service": "SRV",
    "srv": "SRV",
}
ALBERTA_CATEGORY_LABELS = {
    "CNST": "Construction",
    "GD": "Goods",
    "SRV": "Services",
}


def parse_date(value: str) -> datetime | None:
    """Parse a date string into a datetime object."""
    if not value:
        return None
    raw = value.strip()
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


# ============== Closing times ==============

def load_alberta_tz() -> ZoneInfo:
    """America/Edmonton from the bundled tzdata package, else the system database.

    tzdata 2026c (pip tzdata 2026.3) carries Alberta's move to year-round
    UTC-06:00 from 2026-11-01. A host database older than that puts Alberta
    an hour off from November on, so the packaged copy is preferred.
    """
    try:
        from importlib import resources

        path = resources.files("tzdata").joinpath("zoneinfo").joinpath("America").joinpath("Edmonton")
        with path.open("rb") as handle:
            return ZoneInfo.from_file(handle, key="America/Edmonton")
    except (ImportError, OSError, ValueError):
        return ZoneInfo("America/Edmonton")


# Deadlines are counted and shown in Alberta time, because that is where the
# businesses reading them are.
ALBERTA_TZ = load_alberta_tz()

# APC returns closing times without an offset, in Alberta local time
# (the usual APC close is 14:00:59 local).
APC_SOURCE_TZ = ALBERTA_TZ

# CanadaBuys open data publishes tenderClosingDate at a fixed UTC-05:00 offset,
# not daylight-adjusted Eastern time. Source: PSPC, "Understanding the new
# CanadaBuys tender and award notices datasets"
# (https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/soutien-support-eng.html).
CANADABUYS_SOURCE_TZ = timezone(timedelta(hours=-5), "UTC-05:00")

SOURCE_TIMEZONES: dict[str, tzinfo] = {
    "federal": CANADABUYS_SOURCE_TZ,
    "alberta": APC_SOURCE_TZ,
}

DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_date_only(value: str) -> bool:
    """True when a source value carries a date but no time of day."""
    return bool(DATE_ONLY_RE.match(str(value or "").strip()))


def parse_closing(value: str, source_tz: tzinfo) -> datetime | None:
    """Parse a source closing value into a timezone-aware datetime.

    Values without an offset are read in the source's published time zone.
    A bare date closes at the end of that day, not at its start.
    """
    parsed = parse_date(str(value or ""))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        if is_date_only(value):
            parsed = parsed.replace(hour=23, minute=59, second=59)
        parsed = parsed.replace(tzinfo=source_tz)
    return parsed


def canadabuys_closing(contract: dict) -> datetime | None:
    """Closing time of a raw CanadaBuys row."""
    return parse_closing(get_field(contract, "tenderClosingDate-appelOffresDateCloture"), CANADABUYS_SOURCE_TZ)


def alberta_closing(opp: dict) -> datetime | None:
    """Closing time of a raw APC row."""
    return parse_closing(str(opp.get("closeDateTime") or ""), APC_SOURCE_TZ)


def source_timezone_for_reference(reference: str) -> tzinfo:
    """Source time zone for a stored reference (APC refs start with AB-)."""
    return APC_SOURCE_TZ if is_alberta_reference(reference) else CANADABUYS_SOURCE_TZ


def opportunity_closing(opportunity: dict) -> datetime | None:
    """Closing time of a normalized opportunity, using its source's time zone."""
    source_tz = SOURCE_TIMEZONES.get(str(opportunity.get("source_key") or ""), timezone.utc)
    return parse_closing(str(opportunity.get("closing") or ""), source_tz)


def alberta_today(now: datetime | None = None) -> date:
    """Today's date in Alberta."""
    return (now or datetime.now(timezone.utc)).astimezone(ALBERTA_TZ).date()


def days_until_close(closing: datetime, now: datetime | None = None) -> int:
    """Calendar days from today to the closing date, both in Alberta time.

    0 means it closes today and 1 means tomorrow. Counting whole 24-hour
    periods instead understates by one day whenever the closing time of day
    is earlier than the current time of day.
    """
    return (closing.astimezone(ALBERTA_TZ).date() - alberta_today(now)).days


def has_closed(closing: datetime, now: datetime | None = None) -> bool:
    """True once the closing time has passed."""
    return closing <= (now or datetime.now(timezone.utc))


def describe_days_until(days: int) -> str:
    """Plain wording for a calendar-day count from days_until_close."""
    if days < 0:
        return "closed"
    if days == 0:
        return "closes today"
    if days == 1:
        return "closes tomorrow"
    return f"closes in {days} days"


def describe_closing(closing: datetime | None, now: datetime | None = None) -> str:
    """Plain wording for how long is left, or '' when the closing is unknown."""
    if closing is None:
        return ""
    if has_closed(closing, now):
        return "closed"
    return describe_days_until(days_until_close(closing, now))


def format_closing(raw: str, source_tz: tzinfo) -> str:
    """Show a source closing value in Alberta time with its UTC offset.

    APC values become e.g. '2026-10-01 14:00 Alberta time (UTC-06:00)'.
    CanadaBuys values also keep the published value so it can be checked
    against the notice, e.g. '2026-10-21 15:00 Alberta time (UTC-06:00);
    CanadaBuys: 16:00 UTC-05:00'. The offset is shown instead of a zone
    abbreviation because tzdata labels Alberta's year-round UTC-06:00 as
    "CST" from November 2026. Unparseable values are returned unchanged.
    """
    closing = parse_closing(raw, source_tz)
    if closing is None:
        return str(raw or "")
    local = closing.astimezone(ALBERTA_TZ)
    if is_date_only(raw):
        return local.strftime("%Y-%m-%d")
    offset = local.strftime("%z")
    text = f"{local.strftime('%Y-%m-%d %H:%M')} Alberta time (UTC{offset[:3]}:{offset[3:]})"
    if source_tz is CANADABUYS_SOURCE_TZ and parse_date(raw).tzinfo is None:
        text += f"; CanadaBuys: {closing.strftime('%H:%M')} UTC-05:00"
    return text


def format_opportunity_closing(opportunity: dict) -> str:
    """format_closing for a normalized opportunity."""
    source_tz = SOURCE_TIMEZONES.get(str(opportunity.get("source_key") or ""), timezone.utc)
    return format_closing(str(opportunity.get("closing") or ""), source_tz)


def fetch_all_contracts() -> list[dict]:
    """Fetch all contracts from CanadaBuys, or from fixtures when configured."""
    fixture_rows = fixtures.load_canadabuys_rows()
    if fixture_rows is not None:
        return fixture_rows

    request = Request(OPEN_TENDERS_URL, headers=REQUEST_HEADERS)

    with urlopen(request, timeout=120) as response:
        raw_data = response.read()

        # Decompress if gzipped
        if raw_data[:2] == b'\x1f\x8b':
            raw_data = gzip.decompress(raw_data)

        text_data = raw_data.decode("utf-8-sig")
        return fixtures.parse_canadabuys_csv_text(text_data)


def save_contracts(contracts: list[dict]) -> Path:
    """Save contracts to local cache."""
    latest_path = DATA_DIR / "latest.csv"

    if not contracts:
        return latest_path

    # Filter out None keys
    fieldnames = [k for k in contracts[0].keys() if k is not None]

    with latest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(contracts)

    # Save summary
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_contracts": len(contracts),
    }
    with (DATA_DIR / "latest.json").open("w") as f:
        json.dump(summary, f, indent=2)

    return latest_path


def load_contracts() -> list[dict]:
    """Load contracts from local cache."""
    latest_path = DATA_DIR / "latest.csv"
    if not latest_path.exists():
        return []

    with latest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_field(contract: dict, *field_names: str) -> str:
    """Get first non-empty field value from contract."""
    for name in field_names:
        val = contract.get(name, "")
        if val:
            return str(val)
    return ""


def get_cohere_api_key() -> tuple[str, str]:
    """Return the first configured Cohere API key and its env var name."""
    for name in COHERE_API_KEY_ENV_NAMES:
        token = os.environ.get(name, "").strip()
        if token:
            return token, name
    return "", ""


def get_cohere_api_keys() -> list[tuple[str, str]]:
    """Return configured Cohere API keys in preferred failover order."""
    keys = []
    for name in COHERE_API_KEY_ENV_NAMES:
        token = os.environ.get(name, "").strip()
        if token:
            keys.append((token, name))
    return keys


def get_hf_token() -> tuple[str, str]:
    """Return the first configured Hugging Face token and its env var name."""
    for name in HF_TOKEN_ENV_NAMES:
        token = os.environ.get(name, "").strip()
        if token:
            return token, name
    return "", ""


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    """Clamp user-provided integer tool arguments to a safe range."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def strip_cohere_thinking(text: str) -> str:
    """Remove Command A+ thinking blocks if the provider returns them."""
    cleaned = re.sub(
        r"<\|START_THINKING\|>.*?<\|END_THINKING\|>",
        "",
        text,
        flags=re.DOTALL,
    )
    cleaned = re.sub(
        r"<START_THINKING>.*?<END_THINKING>",
        "",
        cleaned,
        flags=re.DOTALL,
    )
    return cleaned.strip()


class CohereApiError(RuntimeError):
    """Cohere API failure with status details for controlled failover."""

    def __init__(self, status_code: int, message: str, key_name: str) -> None:
        self.status_code = status_code
        self.message = message
        self.key_name = key_name
        super().__init__(f"Cohere API returned HTTP {status_code}: {message[:300]}")


def is_cohere_limit_error(error: CohereApiError) -> bool:
    """Return true for failures where the prod key should be tried."""
    if error.status_code in {402, 429}:
        return True

    message = error.message.lower()
    return any(
        phrase in message
        for phrase in (
            "rate limit",
            "rate_limit",
            "too many requests",
            "quota",
            "credit",
            "billing",
            "trial",
            "limit exceeded",
        )
    )


def call_cohere_hf_chat(
    messages: list[dict[str, str]],
    max_tokens: int = 800,
    temperature: float = 0.2,
) -> str:
    """Call Command A+ through the Hugging Face OpenAI-compatible router."""
    token, _ = get_hf_token()
    if not token:
        names = " or ".join(HF_TOKEN_ENV_NAMES[:2])
        raise RuntimeError(f"Hugging Face token is not configured. Set {names}.")

    payload = {
        "model": COHERE_HF_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.95,
        "reasoning_effort": "none",
        "stream": False,
    }
    request = Request(
        HF_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "CanadaBuys-MCP/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_body = json.loads(raw_body)
            error_message = str(error_body.get("error", raw_body))
        except json.JSONDecodeError:
            error_message = raw_body

        if exc.code == 403 and "Inference Providers" in error_message:
            raise RuntimeError(
                "Hugging Face token is present but lacks Inference Providers permission. "
                "Create or update a fine-grained token with 'Make calls to Inference Providers'."
            ) from exc
        raise RuntimeError(
            f"Hugging Face router returned HTTP {exc.code}: {error_message[:300]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Hugging Face router: {exc.reason}") from exc

    choices = body.get("choices", [])
    if not choices:
        raise RuntimeError("Hugging Face router returned no choices.")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Hugging Face router returned an empty message.")
    return strip_cohere_thinking(content)


def call_cohere_direct_chat(
    messages: list[dict[str, str]],
    max_tokens: int = 1200,
    temperature: float = 0.2,
    token: str = "",
    key_name: str = "",
) -> str:
    """Call Command A+ through Cohere's OpenAI-compatible endpoint."""
    if not token:
        token, key_name = get_cohere_api_key()
    if not token:
        names = " or ".join(COHERE_API_KEY_ENV_NAMES)
        raise RuntimeError(f"Cohere API key is not configured. Set {names}.")
    if not key_name:
        key_name = "Cohere API key"

    cohere_messages = [
        {
            "role": "developer" if message.get("role") == "system" else message.get("role", "user"),
            "content": message.get("content", ""),
        }
        for message in messages
    ]
    payload = {
        "model": COHERE_MODEL,
        "messages": cohere_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 0.95,
        "stream": False,
    }
    # Cohere's compatibility endpoint returns HTTP 500 for some prompts when
    # reasoning_effort is pinned; only send it when explicitly configured.
    reasoning_effort = os.environ.get("CANADABUYS_COHERE_REASONING_EFFORT")
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    request = Request(
        COHERE_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "CanadaBuys-MCP/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_body = json.loads(raw_body)
            error_message = str(
                error_body.get("message") or error_body.get("error") or raw_body
            )
        except json.JSONDecodeError:
            error_message = raw_body
        raise CohereApiError(exc.code, error_message, key_name) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Cohere API: {exc.reason}") from exc

    choices = body.get("choices", [])
    if not choices:
        raise RuntimeError("Cohere API returned no choices.")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Cohere API returned an empty message.")
    return strip_cohere_thinking(content)


def call_cohere_chat(
    messages: list[dict[str, str]],
    max_tokens: int = 1200,
    temperature: float = 0.2,
) -> tuple[str, str, str]:
    """Call the configured Cohere route, preferring direct Cohere keys."""
    cohere_keys = get_cohere_api_keys()
    if cohere_keys:
        last_error = None
        for index, (token, key_name) in enumerate(cohere_keys):
            try:
                content = call_cohere_direct_chat(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    token=token,
                    key_name=key_name,
                )
                provider = "Cohere API"
                if index > 0:
                    provider += f" via `{key_name}` fallback"
                return content, provider, COHERE_MODEL
            except CohereApiError as exc:
                last_error = exc
                has_next_key = index + 1 < len(cohere_keys)
                if not has_next_key or not is_cohere_limit_error(exc):
                    raise

        if last_error:
            raise last_error

    return (
        call_cohere_hf_chat(messages, max_tokens=max_tokens, temperature=temperature),
        "Hugging Face Inference Providers",
        COHERE_HF_MODEL,
    )


# ============== Alberta Purchasing Connection ==============


def apc_selectable(value: str) -> dict[str, Any]:
    """Build APC's selectable filter shape."""
    return {"value": value, "selected": True, "count": 0}


def normalize_alberta_category(category: str) -> str:
    """Normalize user-facing category names to APC category codes."""
    raw = (category or "").strip().lower()
    return ALBERTA_CATEGORY_CODES.get(raw, raw.upper())


def parse_alberta_reference(reference: str) -> tuple[int, int]:
    """Parse references like AB-2026-03908 into APC public detail path parts."""
    match = re.search(r"AB-(\d{4})-(\d+)", reference.strip(), flags=re.IGNORECASE)
    if not match:
        raise ValueError("Use an Alberta APC reference like `AB-2026-03908`.")
    return int(match.group(1)), int(match.group(2))


def read_json_request(request: Request, timeout: float = 120) -> dict:
    """Read a JSON HTTP response with a useful error message."""
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
            message = parsed.get("message") or parsed.get("title") or parsed.get("error") or body
            if "errors" in parsed:
                message = f"{message}: {parsed['errors']}"
        except json.JSONDecodeError:
            message = body
        raise RuntimeError(f"HTTP {exc.code}: {str(message)[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach source: {exc.reason}") from exc
    except (TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError("Source timed out or returned an invalid response") from exc


def build_alberta_filter(
    *,
    status: str = "OPEN",
    category: str = "",
    close_start: str = "",
    close_end: str = "",
    post_start: str = "",
    post_end: str = "",
    unspsc: list[str] | None = None,
) -> dict[str, Any]:
    """Build the APC opportunity filter payload.

    ``unspsc`` takes plain 8-digit code strings (APC rejects the ``selectable``
    object shape used by ``categories``/``statuses`` with a 400). Passing codes
    here lets APC filter by commodity server-side, which is far more precise
    than matching the code titles as free text.
    """
    statuses = []
    if status and status.lower() not in {"all", "any"}:
        statuses.append(apc_selectable(status.strip().upper()))

    categories = []
    if category:
        categories.append(apc_selectable(normalize_alberta_category(category)))

    filt: dict[str, Any] = {
        "solicitationNumber": "",
        "categories": categories,
        "statuses": statuses,
        "agreementTypes": [],
        "solicitationTypes": [],
        "opportunityTypes": [],
        "deliveryRegions": [],
        "deliveryRegion": "",
        "organizations": [],
        "unspsc": [str(code).strip() for code in (unspsc or []) if str(code).strip()],
        "postDateRange": "$$custom",
        "closeDateRange": "$$custom",
        "onlyBookmarked": False,
        "onlyInterestExpressed": False,
    }
    if close_start:
        filt["closeDateStart"] = close_start
    if close_end:
        filt["closeDateEnd"] = close_end
    if post_start:
        filt["postDateStart"] = post_start
    if post_end:
        filt["postDateEnd"] = post_end
    return filt


def search_alberta_api(
    *,
    query: str = "",
    status: str = "OPEN",
    category: str = "",
    limit: int = 10,
    offset: int = 0,
    sort_field: str = "PostDateTime",
    sort_direction: str = "desc",
    close_start: str = "",
    close_end: str = "",
    post_start: str = "",
    post_end: str = "",
    unspsc: list[str] | None = None,
    timeout: float = 5,
) -> dict:
    """Search Alberta Purchasing Connection opportunities.

    ``offset`` is a PAGE index, not a row offset: APC starts the result window
    at ``offset * limit``. See ``fetch_all_alberta_opportunities`` for paging.
    """
    limit = clamp_int(limit, default=10, minimum=1, maximum=100)
    offset = clamp_int(offset, default=0, minimum=0, maximum=100)
    fixture_payload = fixtures.load_apc_search_payload()
    if fixture_payload is not None:
        return fixtures.filter_apc_search_payload(
            fixture_payload,
            query=query,
            status=status,
            category=category,
            limit=limit,
            offset=offset,
            unspsc=unspsc,
            close_start=close_start,
            close_end=close_end,
        )
    payload = {
        "query": query or "",
        "queryMode": "standard",
        "includeEnhancedMatchIds": True,
        "filter": build_alberta_filter(
            status=status,
            category=category,
            close_start=close_start,
            close_end=close_end,
            post_start=post_start,
            post_end=post_end,
            unspsc=unspsc,
        ),
        "limit": limit,
        "offset": offset,
        "sortOptions": [{"field": sort_field, "direction": sort_direction}],
    }
    request = Request(
        f"{ALBERTA_APC_API_BASE}/opportunity/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": f"{ALBERTA_APC_APP_BASE}/search",
            "User-Agent": "CanadaBuys-MCP/1.0",
        },
        method="POST",
    )
    return read_json_request(request, timeout=timeout)


def fetch_all_alberta_opportunities(
    *,
    status: str = "OPEN",
    category: str = "",
    unspsc: list[str] | None = None,
    page_size: int = 100,
    max_pages: int = 100,
    query: str = "",
    close_start: str = "",
    close_end: str = "",
    timeout_seconds: float = 20,
) -> tuple[list[dict], str]:
    """Enumerate every matching APC opportunity by paging the search API.

    APC's ``offset`` is a page index (the window starts at ``offset * limit``),
    so the whole open corpus is reachable in ``ceil(total / 100)`` requests --
    about 17 calls and a few seconds for the ~1,600 currently-open records.

    Search rows already carry ``projectDescription``, ``commodityCodes`` and
    ``commodityCodeTitles``, so no per-record detail call is needed to enrich
    them. Returns ``(rows, warning)``; ``warning`` is non-empty when paging
    stopped before the reported total.
    """
    page_size = clamp_int(page_size, default=100, minimum=1, maximum=100)
    seen: dict[str, dict] = {}
    total = None
    deadline = time.monotonic() + max(0, timeout_seconds)
    max_pages = clamp_int(max_pages, default=100, minimum=1, maximum=100)
    stop_reason = f"the {max_pages}-page ceiling was reached"
    complete = False

    for page in range(max_pages):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop_reason = "the retrieval time budget was exhausted"
            break
        try:
            response = search_alberta_api(
                query=query, status=status, category=category,
                limit=page_size, offset=page, unspsc=unspsc,
                close_start=close_start, close_end=close_end,
                timeout=min(5, remaining),
            )
        except RuntimeError:
            stop_reason = "an APC page request failed"
            break
        reported = response.get("totalCount")
        if isinstance(reported, int) and reported >= 0:
            total = reported
        rows = response.get("values") or []
        if not rows:
            complete = total is None or len(seen) >= total
            stop_reason = "APC returned an empty page before its reported total"
            break
        previous_count = len(seen)
        for row in rows:
            reference = str(row.get("referenceNumber") or row.get("id") or "")
            if reference:
                seen[reference] = row
        if total is not None and len(seen) >= total:
            complete = True
            break
        if len(seen) == previous_count:
            stop_reason = "APC repeated a page without new references"
            break
        if total is None and len(rows) < page_size:
            complete = True
            break

    warning = ""
    if not complete:
        warning = (
            f"Partial enumeration: retrieved {len(seen)} of "
            f"{total if total is not None else 'an unknown number of'} APC records; {stop_reason}."
        )
    return list(seen.values()), warning


def collect_alberta_candidates(
    intent: str, *, category: str = "", status: str = "OPEN",
    close_start: str = "", close_end: str = "", profile_search: bool = False,
) -> tuple[list[dict], list[str]]:
    """Plan once, retrieve bounded pages, and retain explicit caller filters.

    Location inferred from a supplier's address is not a delivery restriction.
    Multiple inferred categories are also not collapsed into a single category.
    """
    from procurement_core import query_planner

    deadline = time.monotonic() + 25
    warnings: list[str] = []
    plan = None
    if intent.strip():
        vocab = []
        if fixtures.fixture_dir() is not None:
            plan = query_planner._fallback(intent, "fixture-mode")
        elif query_planner.cohere_api_key():
            try:
                facets = search_alberta_api(status=status, category=category, limit=1, timeout=4)
                vocab = query_planner.vocabulary_from_facets(facets.get("facets", {}))
            except RuntimeError:
                warnings.append("APC filter vocabulary unavailable; using keyword fallback.")
        if plan is None:
            plan = query_planner.plan_query(intent, vocab, timeout=6)
        if plan["source"] == "fallback":
            warnings.append(f"APC query planner fallback ({plan['reason']}); using lexical matching.")

    codes = plan["unspsc"] if plan else []
    planned = bool(plan and plan["source"] == "cohere" and codes)
    if plan and plan["source"] == "cohere" and not codes:
        warnings.append("APC query planner returned no usable commodity codes; using lexical matching.")
    # An inferred commodity segment can narrow candidates. Explicit categories
    # and status always win; inferred regions never narrow supplier coverage.
    effective_category = category
    if planned and not category and len(plan["categories"]) == 1:
        effective_category = plan["categories"][0]
    rows, warning = fetch_all_alberta_opportunities(
        status=status, category=effective_category, unspsc=codes if planned else None,
        query="" if planned or profile_search else intent,
        close_start=close_start, close_end=close_end,
        timeout_seconds=max(0, deadline - time.monotonic()),
    )
    if warning:
        warnings.append(warning)
    if not rows and planned and not warning:
        warnings.append("No APC records matched inferred filters; retrying with explicit filters only.")
        rows, warning = fetch_all_alberta_opportunities(
            status=status, category=category,
            query="" if profile_search else intent,
            close_start=close_start, close_end=close_end,
            timeout_seconds=max(0, deadline - time.monotonic()),
        )
        if warning:
            warnings.append(warning)
        planned = False
    if not profile_search:
        if planned:
            terms = plan["keywords"] or [intent]
            rows = [row for row in rows if any(
                capability_hit(term, alberta_opportunity_text(row)) for term in terms
            )]
            rows.sort(key=lambda row: (
                sum(capability_hit(term, alberta_opportunity_text(row)) for term in terms),
                alberta_posted_date(row),
            ), reverse=True)
        else:
            rows, relevance_warning = rank_by_token_coverage(
                rows, intent, alberta_opportunity_text, alberta_posted_date,
            )
            if relevance_warning:
                warnings.append(relevance_warning)
    return rows, warnings


def collect_alberta_matches(profile: dict, days: int) -> tuple[list[tuple], list[str]]:
    """Use the same retrieval and relevance gate for unified and APC matching."""
    now = datetime.now(timezone.utc)
    today = alberta_today(now)
    capabilities = [str(kw) for kw in profile.get("capabilities", []) if str(kw).strip()]
    intent = str(profile.get("description") or "") + " " + "; ".join(capabilities)
    if not intent.strip():
        return [], ["No business capabilities were supplied for APC matching."]
    rows, warnings = collect_alberta_candidates(
        intent, profile_search=True,
        close_start=today.strftime("%Y-%m-%d"),
        close_end=(today + timedelta(days=days)).strftime("%Y-%m-%d"),
    )
    scored = []
    for opp in rows:
        closing = alberta_closing(opp)
        if not closing or has_closed(closing, now):
            continue
        days_until = days_until_close(closing, now)
        if days_until > days:
            continue
        score, reasons = score_alberta_opportunity(opp, profile)
        # Region and imminent-close bonuses alone do not establish supplier fit.
        if not any("matches:" in reason for reason in reasons):
            continue
        scored.append((score, days_until, opp, reasons))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored, warnings


def get_alberta_api_details(reference: str) -> dict:
    """Fetch public APC details for an opportunity reference."""
    year, draft_id = parse_alberta_reference(reference)
    request = Request(
        f"{ALBERTA_APC_API_BASE}/opportunity/public/{year}/{draft_id}",
        headers={
            "Accept": "application/json",
            "Referer": f"{ALBERTA_APC_APP_BASE}/search",
            "User-Agent": "CanadaBuys-MCP/1.0",
        },
    )
    return read_json_request(request)


def render_alberta_opportunity_line(opp: dict, index: int) -> str:
    """Render one APC result for a search listing."""
    title = str(opp.get("title") or opp.get("shortTitle") or "Untitled opportunity")[:90]
    ref = opp.get("referenceNumber", "")
    org = str(opp.get("contractingOrganization") or "")[:70]
    category = ALBERTA_CATEGORY_LABELS.get(opp.get("categoryCode"), opp.get("categoryCode", ""))
    close_date = format_closing(str(opp.get("closeDateTime") or ""), APC_SOURCE_TZ)
    solicitation = opp.get("solicitationTypeCode") or ""
    return (
        f"**{index}. {title}**\n"
        f"   Reference: `{ref}`\n"
        f"   Organization: {org}\n"
        f"   Category: {category} | Type: {solicitation}\n"
        f"   Closing: {close_date}\n"
    )


def render_alberta_details_markdown(data: dict) -> str:
    """Render an APC opportunity detail response as markdown."""
    opp = data.get("opportunity", {})
    title = opp.get("title") or opp.get("shortTitle") or "Untitled Alberta Opportunity"
    ref = opp.get("referenceNumber", "")
    public_url = apc_posting_url(ref, ALBERTA_APC_APP_BASE) if ref else ALBERTA_APC_APP_BASE
    contact_info = data.get("contractingEntityContactInformation") or {}
    organization = (
        opp.get("contractingOrganization")
        or opp.get("contractingOrgName")
        or contact_info.get("organizationName")
        or (str(title).split(" - ", 1)[0] if " - " in str(title) else "")
    )

    lines = [f"# {title}", ""]
    lines.append("## Overview")
    lines.append(f"- **Source:** Alberta Purchasing Connection")
    lines.append(f"- **Reference:** {ref}")
    lines.append(f"- **Solicitation:** {opp.get('solicitationNumber', '')}")
    lines.append(f"- **Status:** {opp.get('statusCode', '')}")
    lines.append(f"- **Category:** {ALBERTA_CATEGORY_LABELS.get(opp.get('categoryCode'), opp.get('categoryCode', ''))}")
    lines.append(f"- **Solicitation Type:** {opp.get('solicitationTypeCode', '')}")
    lines.append(f"- **Opportunity Type:** {opp.get('postingTypeCode', '')}")
    lines.append(f"- **Organization:** {organization}")
    lines.append(f"- **Posted:** {opp.get('postDateTime', '')}")
    closing_raw = str(opp.get("closeDateTime") or "")
    closing_text = format_closing(closing_raw, APC_SOURCE_TZ)
    time_left = describe_closing(parse_closing(closing_raw, APC_SOURCE_TZ))
    if time_left:
        closing_text += f" ({time_left})"
    lines.append(f"- **Closing:** {closing_text}")
    lines.append("")

    region = opp.get("regionOfDelivery") or ""
    if region:
        lines.append("## Region")
        lines.append(str(region))
        lines.append("")

    commodity_codes = data.get("commodityCodes") or opp.get("commodityCodes") or []
    if commodity_codes:
        lines.append("## Commodity Codes")
        for code in commodity_codes[:12]:
            if isinstance(code, dict):
                code_value = (
                    code.get("commodity")
                    or code.get("class")
                    or code.get("family")
                    or code.get("segment")
                    or code.get("code")
                    or code.get("value")
                    or ""
                )
                title_value = (
                    code.get("commodityTitle")
                    or code.get("classTitle")
                    or code.get("familyTitle")
                    or code.get("segmentTitle")
                    or code.get("title")
                    or code.get("description")
                    or ""
                )
                lines.append(f"- {code_value} {title_value}".strip())
            else:
                lines.append(f"- {code}")
        lines.append("")

    description = opp.get("projectDescription") or ""
    if description:
        lines.append("## Description")
        lines.append(str(description)[:3000])
        lines.append("")

    requirements = opp.get("additionalRequirements") or ""
    if requirements:
        lines.append("## Additional Requirements")
        lines.append(str(requirements)[:2000])
        lines.append("")

    submission = opp.get("submissionDetails") or ""
    question_submission = opp.get("questionSubmissionDetails") or ""
    email_submission = opp.get("emailSubmissionValue") if opp.get("useEmailSubmission") else ""
    if submission or question_submission or email_submission:
        lines.append("## Submission")
        if email_submission:
            lines.append(f"Email submission: {email_submission}")
        if submission:
            lines.append(str(submission)[:1500])
        if question_submission:
            lines.append(f"Questions: {str(question_submission)[:1000]}")
        lines.append("")

    manifest = apc_document_manifest(data)
    lines.extend(["## Procurement documents and addenda", ""])
    if manifest:
        for document in manifest:
            lines.append(
                f"- {document['name']} — ID `{document['document_id']}`, "
                f"{document['expected_bytes'] or 'unknown'} bytes, version {document['version']}, "
                f"amendment {document['amendment_number']} ({document['kind']})"
            )
        lines.append(APC_ACCESS_MESSAGE)
    else:
        lines.append("No procurement document metadata was returned; a notice is not a complete document package.")
    lines.append("")
    external_link = opp.get("externalOriginLink")
    lines.append("## Links")
    lines.append(f"- [View on Alberta Purchasing Connection]({public_url})")
    if external_link:
        lines.append(f"- [External posting]({external_link})")

    return "\n".join(lines)


def capability_terms(capability: str) -> list[str]:
    """Split a capability phrase into the significant terms worth matching.

    Profiles are written as natural phrases ("custom software development and
    systems integration"), but tender text never contains them verbatim. Match
    on the meaningful tokens instead, ignoring connective filler.
    """
    stop = {
        "and", "or", "the", "for", "with", "of", "in", "to", "a", "an",
        "our", "we", "custom", "services", "service", "solutions", "solution",
        "based", "other",
    }
    tokens = re.findall(r"[a-z0-9/+]{3,}", (capability or "").lower())
    return [t for t in tokens if t not in stop]


def capability_hit(capability: str, text: str) -> bool:
    """True when a capability phrase is meaningfully present in ``text``.

    Terms are matched on a five-character prefix so ordinary morphology lines
    up ("platforms" against "platform", "analytics" against "analysis"). A
    single-term capability must match; a multi-term one needs at least a third
    of its terms, which keeps "data platforms, analytics and AI/ML engineering"
    matching a data-analytics platform tender without letting a lone generic
    word drag in unrelated work.

    This raises the floor for phrase-shaped profiles. It is still a lexical
    heuristic: the calibrated relevance signal belongs upstream in the query
    planner and downstream in classification.
    """
    terms = capability_terms(capability)
    if not terms:
        return False
    words = set(re.findall(r"[a-z0-9/+]+", (text or "").lower()))
    hits = sum(1 for term in terms if _term_present(term, words))
    if len(terms) == 1:
        return hits == 1
    return hits * 3 >= len(terms)


def _term_present(term: str, words: set[str]) -> bool:
    if term in words:
        return True
    if len(term) < 5:
        return False
    prefix = term[:5]
    return any(len(word) >= 5 and word[:5] == prefix for word in words)


def score_alberta_opportunity(opp: dict, profile: dict) -> tuple[int, list[str]]:
    """Score an APC opportunity against the saved business profile."""
    score = 0
    reasons = []
    keywords = profile.get("capabilities", [])
    location = profile.get("location", "").lower()

    title = str(opp.get("title") or opp.get("shortTitle") or "").lower()
    desc = str(opp.get("projectDescription") or "").lower()
    commodity_titles = " ".join(str(v) for v in opp.get("commodityCodeTitles") or []).lower()
    regions = " ".join(str(v) for v in opp.get("regionOfDelivery") or []).lower()

    title_matches = [kw for kw in keywords if capability_hit(kw, title)]
    if title_matches:
        score += 10 * len(title_matches)
        reasons.append(f"title matches: {', '.join(title_matches[:3])}")

    desc_matches = [
        kw for kw in keywords
        if capability_hit(kw, desc) and not capability_hit(kw, title)
    ]
    if desc_matches:
        score += 5 * len(desc_matches)
        reasons.append(f"description matches: {', '.join(desc_matches[:3])}")

    commodity_matches = [kw for kw in keywords if capability_hit(kw, commodity_titles)]
    if commodity_matches:
        score += 8 * len(commodity_matches)
        reasons.append(f"commodity matches: {', '.join(commodity_matches[:3])}")

    if location:
        loc_parts = [p.strip().lower() for p in location.replace(",", " ").split()]
        for part in loc_parts:
            if len(part) > 3 and part in regions:
                score += 10
                reasons.append(f"delivers to {part}")
                break

    closing_date = alberta_closing(opp)
    if closing_date and not has_closed(closing_date):
        days_until = days_until_close(closing_date)
        if 0 < days_until <= 14:
            score += 5
            reasons.append(describe_days_until(days_until))

    return score, reasons


# ============== Business Profile ==============

# Industry keywords for matching (from pipeline config)
INDUSTRY_KEYWORDS = {
    "steel": ["steel", "stainless", "carbon steel", "structural steel", "metal fabrication",
              "welding", "iron", "metalwork", "rebar", "girder", "beam"],
    "lumber": ["lumber", "wood", "timber", "forestry", "plywood", "sawmill", "log",
               "pulp", "paper", "woodwork", "carpentry", "framing"],
    "aluminum": ["aluminum", "aluminium", "bauxite", "smelting", "extrusion"],
    "construction": ["construction", "building", "demolition", "renovation", "contractor",
                     "infrastructure", "excavation", "concrete", "masonry"],
}

# UNSPSC code prefixes by industry (from pipeline config)
INDUSTRY_UNSPSC = {
    "steel": ["111017", "301017", "111016", "232400", "251000", "221000", "301000"],
    "lumber": ["1112", "301515", "111215", "301524", "301521"],
    "aluminum": ["1111", "111106", "301116"],
    "construction": ["721", "301", "221", "251"],
}


def load_profile() -> dict:
    """Load the business profile.

    Signed-in hosted requests read the per-user or per-subscriber row.
    Anonymous callers on the hosted endpoint get an empty profile (no shared
    file). Local stdio still reads ``DATA_DIR/profile.json``.
    """
    from procurement_core import storage

    if storage.tenant_active():
        return storage.get_json_field("profile", {}) or {}
    if not storage.allow_anonymous_file_persist():
        return {}

    profile_path = DATA_DIR / "profile.json"
    if not profile_path.exists():
        return {}
    with profile_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict) -> bool:
    """Save the business profile. Returns True when something was persisted."""
    from procurement_core import storage

    if storage.tenant_active():
        return storage.set_json_field("profile", profile)
    if not storage.allow_anonymous_file_persist():
        return False

    profile_path = DATA_DIR / "profile.json"
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    return True


NO_PROFILE_MESSAGE = (
    "No business profile available. Pass a `profile` argument with this call "
    "(company_name, location, description), or use `set_business_profile` "
    "first to save one."
)


def resolve_profile(args: dict) -> dict:
    """Return the profile to use: an inline `profile` argument wins over the saved one.

    Anonymous callers on the shared hosted endpoint have no tenant row, so an
    inline per-request profile is the only way they can describe their
    business without overwriting each other's saved file.
    """
    inline = args.get("profile")
    if isinstance(inline, dict) and inline:
        description = str(inline.get("description") or "")
        capabilities = [str(kw) for kw in (inline.get("capabilities") or []) if str(kw).strip()]
        if not capabilities:
            capabilities = extract_keywords(description)
        industries = [str(ind) for ind in (inline.get("industries") or []) if str(ind).strip()]
        if not industries:
            industries = infer_industries(capabilities, description)
        return {
            "company_name": str(inline.get("company_name") or "Your Business"),
            "location": str(inline.get("location") or ""),
            "description": description,
            "capabilities": capabilities,
            "industries": industries,
        }
    return load_profile()


def extract_keywords(description: str) -> list[str]:
    """Extract relevant keywords from business description."""
    if not description:
        return []

    desc_lower = description.lower()
    found = []

    # Check for industry keywords
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower and kw not in found:
                found.append(kw)

    # Also extract significant words (nouns likely to appear in contracts)
    words = re.findall(r'\b[a-z]{4,}\b', desc_lower)
    for word in words:
        if word not in found and word not in ["that", "this", "with", "from", "have", "been", "will", "your", "they", "their", "about", "which", "would", "could", "should", "these", "those", "other", "some", "into", "also", "make", "made"]:
            found.append(word)

    return found[:20]  # Limit to 20 keywords


def infer_industries(keywords: list[str], description: str = "") -> list[str]:
    """Infer which industries match based on keywords."""
    industries = set()
    text = " ".join(keywords) + " " + description.lower()

    for industry, kw_list in INDUSTRY_KEYWORDS.items():
        for kw in kw_list:
            if kw in text:
                industries.add(industry)
                break

    return list(industries)


def score_contract(contract: dict, profile: dict) -> tuple[int, list[str]]:
    """Score a contract against a business profile. Returns (score, reasons)."""
    score = 0
    reasons = []

    keywords = profile.get("capabilities", [])
    industries = profile.get("industries", [])
    location = profile.get("location", "").lower()

    title = get_field(contract, "title-titre-eng", "title-titre-fra").lower()
    desc = get_field(contract, "tenderDescription-descriptionAppelOffres-eng").lower()
    regions = f"{get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng')} {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}".lower()
    unspsc = get_field(contract, "unspsc", "")

    # Keyword matches in title (high value)
    title_matches = [kw for kw in keywords if kw.lower() in title]
    if title_matches:
        score += 10 * len(title_matches)
        reasons.append(f"title matches: {', '.join(title_matches[:3])}")

    # Keyword matches in description
    desc_matches = [kw for kw in keywords if kw.lower() in desc and kw.lower() not in title]
    if desc_matches:
        score += 5 * len(desc_matches)
        reasons.append(f"description matches: {', '.join(desc_matches[:3])}")

    # UNSPSC code matches
    for industry in industries:
        prefixes = INDUSTRY_UNSPSC.get(industry, [])
        for prefix in prefixes:
            if prefix in unspsc:
                score += 15
                reasons.append(f"UNSPSC code matches {industry}")
                break

    # Region match
    if location:
        # Extract province/city from location
        loc_parts = [p.strip().lower() for p in location.replace(",", " ").split()]
        for part in loc_parts:
            if len(part) > 3 and part in regions:
                score += 10
                reasons.append(f"delivers to {part}")
                break

    # Closing soon bonus (urgency)
    closing_date = canadabuys_closing(contract)
    if closing_date and not has_closed(closing_date):
        days_until = days_until_close(closing_date)
        if 0 < days_until <= 14:
            score += 5
            reasons.append(describe_days_until(days_until))

    return score, reasons


def render_contract_markdown(contract: dict) -> str:
    """Render a contract as markdown."""
    title = get_field(contract, "title-titre-eng", "title-titre-fra", "Title")
    if not title:
        title = "Untitled Contract"

    lines = [f"# {title}", ""]

    lines.append("## Overview")
    lines.append(f"- **Reference:** {get_field(contract, 'referenceNumber-numeroReference', 'Reference Number')}")
    lines.append(f"- **Solicitation:** {get_field(contract, 'solicitationNumber-numeroSollicitation', 'Solicitation Number')}")
    lines.append(f"- **Status:** {get_field(contract, 'tenderStatus-appelOffresStatut-eng', 'Status')}")
    closing_raw = get_field(contract, 'tenderClosingDate-appelOffresDateCloture', 'Closing Date')
    closing_text = format_closing(closing_raw, CANADABUYS_SOURCE_TZ)
    time_left = describe_closing(parse_closing(closing_raw, CANADABUYS_SOURCE_TZ))
    if time_left:
        closing_text += f" — {time_left}"
    lines.append(f"- **Closing Date:** {closing_text}")
    lines.append(f"- **Entity:** {get_field(contract, 'contractingEntityName-nomEntitContractante-eng', 'Organization')}")
    lines.append("")

    lines.append("## Regions")
    lines.append(f"- **Opportunity:** {get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng', 'Regions')}")
    lines.append(f"- **Delivery:** {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}")
    lines.append("")

    desc = get_field(contract, "tenderDescription-descriptionAppelOffres-eng", "Description")
    if desc:
        lines.append("## Description")
        lines.append(desc[:2000])
        lines.append("")

    notice_url = get_field(contract, "noticeURL-URLavis-eng", "URL")
    if notice_url:
        lines.append("## Links")
        lines.append(f"- [View on CanadaBuys]({notice_url})")

    return "\n".join(lines)


def find_contract_by_reference(reference: str, contracts: list[dict]) -> dict | None:
    """Find a contract by reference or solicitation number."""
    needle = reference.lower().strip()
    if not needle:
        return None

    for contract in contracts:
        ref = get_field(contract, "referenceNumber-numeroReference").lower()
        sol = get_field(contract, "solicitationNumber-numeroSollicitation").lower()
        if needle in ref or needle in sol:
            return contract
    return None


# ============== Unified Opportunity Helpers ==============


def include_source(source: str, candidate: str) -> bool:
    """Return true if a unified tool should include a source."""
    raw = (source or "all").strip().lower()
    aliases = {
        "all": {"all", "both", ""},
        "federal": {"federal", "canadabuys", "canada", "national"},
        "alberta": {"alberta", "apc"},
    }
    return raw in aliases["all"] or raw in aliases[candidate]


def is_alberta_reference(reference: str) -> bool:
    """Return true if the reference looks like an APC reference."""
    return bool(re.search(r"^AB-\d{4}-\d+", reference.strip(), flags=re.IGNORECASE))


def load_contracts_for_unified() -> tuple[list[dict], list[str]]:
    """Load CanadaBuys contracts, refreshing once when no cache exists."""
    fixture_rows = fixtures.load_canadabuys_rows()
    if fixture_rows is not None:
        return fixture_rows, []

    warnings = []
    contracts = load_contracts()
    if contracts:
        return contracts, warnings

    try:
        contracts = fetch_all_contracts()
        save_contracts(contracts)
        warnings.append("CanadaBuys cache was empty, so it was refreshed from open data.")
    except Exception as exc:
        warnings.append(f"CanadaBuys data unavailable: {exc}")
        contracts = []
    return contracts, warnings


def normalize_canadabuys_contract(contract: dict) -> dict[str, Any]:
    """Normalize a CanadaBuys row to the shared opportunity shape."""
    return {
        "source": "CanadaBuys",
        "source_key": "federal",
        "reference": get_field(contract, "referenceNumber-numeroReference"),
        "solicitation": get_field(contract, "solicitationNumber-numeroSollicitation"),
        "title": get_field(contract, "title-titre-eng", "title-titre-fra") or "Untitled federal opportunity",
        "buyer": get_field(contract, "contractingEntityName-nomEntitContractante-eng"),
        "status": get_field(contract, "tenderStatus-appelOffresStatut-eng"),
        "category": get_field(contract, "procurementCategory-categorieApprovisionnement"),
        "posted": get_field(contract, "publicationDate-datePublication"),
        "closing": get_field(contract, "tenderClosingDate-appelOffresDateCloture"),
        "region": get_field(contract, "regionsOfDelivery-regionsLivraison-eng", "regionsOfOpportunity-regionAppelOffres-eng"),
        "description": get_field(contract, "tenderDescription-descriptionAppelOffres-eng"),
        "url": get_field(contract, "noticeURL-URLavis-eng"),
        "raw": contract,
    }


def normalize_alberta_opportunity(opp: dict) -> dict[str, Any]:
    """Normalize an APC search result to the shared opportunity shape."""
    ref = opp.get("referenceNumber", "")
    url = ""
    if ref:
        try:
            year, draft_id = parse_alberta_reference(ref)
            url = apc_posting_url(ref, ALBERTA_APC_APP_BASE)
        except ValueError:
            url = ALBERTA_APC_APP_BASE

    region = opp.get("regionOfDelivery") or []
    if isinstance(region, list):
        region_text = ", ".join(str(item) for item in region)
    else:
        region_text = str(region)

    return {
        "source": "Alberta Purchasing Connection",
        "source_key": "alberta",
        "reference": ref,
        "solicitation": opp.get("solicitationNumber", ""),
        "title": opp.get("title") or opp.get("shortTitle") or "Untitled Alberta opportunity",
        "buyer": opp.get("contractingOrganization", ""),
        "status": opp.get("statusCode", ""),
        "category": ALBERTA_CATEGORY_LABELS.get(opp.get("categoryCode"), opp.get("categoryCode", "")),
        "posted": opp.get("postDateTime", ""),
        "closing": opp.get("closeDateTime", ""),
        "region": region_text,
        "description": opp.get("projectDescription", ""),
        "url": opp.get("externalOriginLink") or url,
        "raw": opp,
    }


def opportunity_date(opportunity: dict, field: str) -> datetime:
    """Parse a normalized opportunity date for sorting.

    Closing times are read in their source's time zone. Other fields keep
    the older UTC reading, which only affects relative ordering.
    """
    raw = str(opportunity.get(field) or "")
    if field == "closing":
        parsed = opportunity_closing(opportunity)
    else:
        parsed = parse_date(raw)
        if parsed and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    if not parsed:
        return datetime.max.replace(tzinfo=timezone.utc)
    return parsed


def opportunity_text(opportunity: dict) -> str:
    """Return searchable text for a normalized opportunity."""
    return " ".join(
        str(opportunity.get(field, ""))
        for field in ("title", "buyer", "category", "region", "description", "solicitation", "reference")
    ).lower()


KEYWORD_STOPWORDS = frozenset({
    "and", "the", "for", "with", "from", "that", "this", "are", "was",
    "all", "any", "per",
})


def tokenize_keywords(keywords: str) -> list[str]:
    """Split a keyword phrase into lowercase search tokens.

    Tokens are alphanumeric runs; tokens shorter than 3 characters and
    stopwords are dropped. Order is preserved and duplicates removed.
    """
    tokens: list[str] = []
    for raw in re.split(r"[^a-z0-9]+", str(keywords or "").lower()):
        if len(raw) < 3 or raw in KEYWORD_STOPWORDS:
            continue
        if raw not in tokens:
            tokens.append(raw)
    return tokens


def token_in_text(token: str, text: str) -> bool:
    """Return True when a token appears in lowercase text.

    Word-boundary match so "ice" does not match "service"; a trailing
    plural "s" is tolerated so "signs" also matches "sign".
    """
    forms = [token]
    if token.endswith("s") and len(token) > 3:
        forms.append(token[:-1])
    return any(re.search(rf"\b{re.escape(form)}", text) for form in forms)


def token_coverage(text: str, tokens: list[str]) -> float:
    """Return the fraction of tokens present in text (1.0 when no tokens)."""
    if not tokens:
        return 1.0
    hits = sum(1 for token in tokens if token_in_text(token, text))
    return hits / len(tokens)


def alberta_opportunity_text(opp: dict) -> str:
    """Return lowercase searchable text for an APC search row."""
    parts = [
        str(opp.get("title") or ""),
        str(opp.get("shortTitle") or ""),
        str(opp.get("contractingOrganization") or ""),
        str(opp.get("projectDescription") or ""),
        " ".join(str(value) for value in opp.get("commodityCodeTitles") or []),
    ]
    return " ".join(parts).lower()


def alberta_posted_date(opp: dict) -> datetime:
    """Return the APC posting date, or datetime.min when unavailable."""
    parsed = parse_date(str(opp.get("postDateTime") or ""))
    if parsed is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def rank_by_token_coverage(
    rows: list[dict],
    keywords: str,
    text_fn: Any,
    date_fn: Any,
) -> tuple[list[dict], str]:
    """Filter and rank rows by AND-token coverage of the keyword phrase.

    Single-token (or empty) queries pass through unchanged in API order.
    Multi-token queries keep only rows with full token coverage, sorted by
    recency desc. When no row has full coverage, all rows are kept and
    ranked by (coverage desc, recency desc) and a fallback warning is
    returned so callers never return nothing when the API found rows.
    """
    tokens = tokenize_keywords(keywords)
    if len(tokens) <= 1:
        return list(rows), ""
    scored = [(token_coverage(text_fn(row), tokens), date_fn(row), row) for row in rows]
    full = [item for item in scored if item[0] >= 1.0]
    if full:
        full.sort(key=lambda item: item[1], reverse=True)
        return [item[2] for item in full], ""
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    warning = (
        f"Relevance fallback: no records matched all search tokens "
        f"({', '.join(tokens)}); showing best partial matches ranked by coverage."
    )
    return [item[2] for item in scored], warning


def federal_contract_matches(contract: dict, keywords: str, province: str, category: str) -> bool:
    """Apply simple unified filters to a CanadaBuys row."""
    normalized = normalize_canadabuys_contract(contract)
    text = opportunity_text(normalized)
    if keywords:
        tokens = tokenize_keywords(keywords)
        if len(tokens) <= 1:
            if keywords.lower() not in text:
                return False
        elif not all(token_in_text(token, text) for token in tokens):
            return False
    if province and province.lower() not in str(normalized.get("region", "")).lower():
        return False
    if category and category.lower() not in text:
        return False
    return True


def render_unified_opportunity_line(opportunity: dict, index: int, extra: str = "") -> str:
    """Render a normalized opportunity for unified listings."""
    title = str(opportunity.get("title") or "Untitled opportunity")[:90]
    buyer = str(opportunity.get("buyer") or "")[:70]
    closing_text = format_opportunity_closing(opportunity)
    closing = opportunity_closing(opportunity)
    if closing and has_closed(closing):
        closing_text += " — closed"
    output = (
        f"**{index}. {title}**\n"
        f"   Source: {opportunity.get('source')}\n"
        f"   Reference: `{opportunity.get('reference', '')}`\n"
        f"   Buyer: {buyer}\n"
        f"   Category: {opportunity.get('category', '')}\n"
        f"   Closing: {closing_text}\n"
    )
    if extra:
        output += f"   {extra}\n"
    return output


def collect_unified_search(args: dict) -> tuple[list[dict], list[str]]:
    """Collect normalized search results across requested sources."""
    source = args.get("source", "all")
    keywords = args.get("keywords", "")
    category = args.get("category", "")
    province = args.get("province", "")
    limit = clamp_int(args.get("limit"), default=20, minimum=1, maximum=50)
    warnings = []
    opportunities = []

    if include_source(source, "federal"):
        contracts, federal_warnings = load_contracts_for_unified()
        warnings.extend(federal_warnings)
        for contract in contracts:
            if federal_contract_matches(contract, keywords, province, category):
                opportunities.append(normalize_canadabuys_contract(contract))
                if len([o for o in opportunities if o["source_key"] == "federal"]) >= limit:
                    break

    if include_source(source, "alberta"):
        if province and "alberta" not in province.lower():
            warnings.append("Alberta APC was skipped because the province filter is not Alberta.")
        else:
            apc_category = normalize_alberta_category(category) if category else ""
            if category and apc_category not in ALBERTA_CATEGORY_LABELS:
                apc_category = ""
            try:
                alberta_rows, alberta_warnings = collect_alberta_candidates(
                    keywords, category=apc_category,
                )
                warnings.extend(alberta_warnings)
                opportunities.extend(normalize_alberta_opportunity(opp) for opp in alberta_rows[:limit])
            except RuntimeError as exc:
                warnings.append(f"Alberta APC unavailable: {exc}")

    if not keywords:
        opportunities.sort(key=lambda item: opportunity_date(item, "posted"), reverse=True)
    return opportunities[:limit], warnings


def collect_unified_deadlines(args: dict) -> tuple[list[dict], list[str]]:
    """Collect normalized closing-soon opportunities across requested sources."""
    source = args.get("source", "all")
    days = clamp_int(args.get("days"), default=30, minimum=1, maximum=365)
    limit = clamp_int(args.get("limit"), default=20, minimum=1, maximum=50)
    category = args.get("category", "")
    province = args.get("province", "")
    now = datetime.now(timezone.utc)
    today = alberta_today(now)
    warnings = []
    opportunities = []

    if include_source(source, "federal"):
        contracts, federal_warnings = load_contracts_for_unified()
        warnings.extend(federal_warnings)
        for contract in contracts:
            if not federal_contract_matches(contract, "", province, category):
                continue
            closing = canadabuys_closing(contract)
            if not closing or has_closed(closing, now):
                continue
            if days_until_close(closing, now) <= days:
                opportunities.append(normalize_canadabuys_contract(contract))

    if include_source(source, "alberta"):
        if province and "alberta" not in province.lower():
            warnings.append("Alberta APC was skipped because the province filter is not Alberta.")
        else:
            apc_category = normalize_alberta_category(category) if category else ""
            if category and apc_category not in ALBERTA_CATEGORY_LABELS:
                apc_category = ""
            try:
                data = search_alberta_api(
                    status="OPEN",
                    category=apc_category,
                    limit=limit,
                    sort_field="CloseDateTime",
                    sort_direction="asc",
                    close_start=today.strftime("%Y-%m-%d"),
                    close_end=(today + timedelta(days=days)).strftime("%Y-%m-%d"),
                )
                for opp in data.get("values", []):
                    closing = alberta_closing(opp)
                    if closing and has_closed(closing, now):
                        continue
                    opportunities.append(normalize_alberta_opportunity(opp))
            except RuntimeError as exc:
                warnings.append(f"Alberta APC unavailable: {exc}")

    opportunities.sort(key=lambda item: opportunity_date(item, "closing"))
    return opportunities[:limit], warnings


def collect_unified_matches(profile: dict, days: int, limit: int) -> tuple[list[tuple[int, int, dict, list[str]]], list[str]]:
    """Collect scored opportunity matches across federal and Alberta sources."""
    now = datetime.now(timezone.utc)
    warnings = []
    scored: list[tuple[int, int, dict, list[str]]] = []

    contracts, federal_warnings = load_contracts_for_unified()
    warnings.extend(federal_warnings)
    for contract in contracts:
        closing = canadabuys_closing(contract)
        if not closing or has_closed(closing, now):
            continue
        days_until = days_until_close(closing, now)
        if days_until > days:
            continue
        score, reasons = score_contract(contract, profile)
        if score > 0:
            scored.append((score, days_until, normalize_canadabuys_contract(contract), reasons))

    alberta_matches, alberta_warnings = collect_alberta_matches(profile, days)
    warnings.extend(alberta_warnings)
    scored.extend((score, days_until, normalize_alberta_opportunity(opp), reasons)
                  for score, days_until, opp, reasons in alberta_matches)

    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[:limit], warnings

# ============== Tool Dispatch ==============

TOOL_NAMES = (
    "get_server_guide",
    "search_contracts",
    "get_contract_details",
    "list_upcoming_deadlines",
    "summarize_contracts",
    "refresh_data",
    "set_business_profile",
    "find_opportunities",
    "get_my_profile",
    "search_opportunities",
    "get_opportunity_details",
    "list_deadlines",
    "find_matching_opportunities",
    "daily_bid_brief",
    "search_alberta_opportunities",
    "get_alberta_opportunity_details",
    "list_alberta_deadlines",
    "summarize_alberta_opportunities",
    "find_alberta_opportunities",
    "process_bid_room",
    "classify_tender",
    "check_cohere_status",
    "analyze_contract_with_cohere",
    # Extension tools (procurement_core/extensions.py)
    "watch_opportunity",
    "list_watchlist",
    "unwatch_opportunity",
    "bid_no_bid_scorecard",
)


async def get_server_guide(args: dict) -> str:
    """Agent-readable operating contract without credentials or upstream calls."""
    from procurement_core.agent_contract import workflow_contract
    return json.dumps(workflow_contract(), ensure_ascii=False, indent=2)


async def call_tool_text(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Run a procurement tool and return plain text without any MCP dependency."""
    args = arguments or {}
    handlers = {tool_name: globals()[tool_name] for tool_name in TOOL_NAMES}
    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"

    # Handlers are async-signatured but internally synchronous: they block on
    # urlopen to CanadaBuys/Alberta APC/Cohere for up to 120s. Run each call
    # in a worker thread so one slow fetch cannot freeze the event loop (and
    # with it every concurrent request, including /health). asyncio.to_thread
    # copies contextvars, so the storage tenant binding propagates.
    def _run_in_thread() -> str:
        return asyncio.run(handler(args))

    try:
        if name in {"process_bid_room", "classify_tender"}:
            return await handler(args)  # These handlers own their complete deadline.
        return await asyncio.to_thread(_run_in_thread)
    except Exception as exc:
        return f"Error: {exc}"


def _opportunity_record(opportunity: dict) -> dict[str, Any]:
    """Return a JSON-safe normalized opportunity record for structured output.

    ``closing`` is the value exactly as the source published it; ``closes_at``
    is the same moment as ISO 8601 in Alberta time with its UTC offset.
    """
    closing = opportunity_closing(opportunity)
    return {
        "title": str(opportunity.get("title") or ""),
        "source": str(opportunity.get("source") or ""),
        "reference": str(opportunity.get("reference") or ""),
        "buyer": str(opportunity.get("buyer") or ""),
        "category": str(opportunity.get("category") or ""),
        "closing": str(opportunity.get("closing") or ""),
        "closes_at": closing.astimezone(ALBERTA_TZ).isoformat() if closing else "",
        "region": str(opportunity.get("region") or ""),
        "solicitation": str(opportunity.get("solicitation") or ""),
    }


def _search_structured(opportunities: list[dict], warnings: list[str]) -> dict[str, Any]:
    """Build the machine-readable payload for search/deadline listings."""
    return {
        "kind": "opportunities",
        "count": len(opportunities),
        "warnings": list(warnings),
        "opportunities": [_opportunity_record(o) for o in opportunities],
    }


def _matches_structured(
    scored: list[tuple[int, int, dict, list[str]]], warnings: list[str], limit: int
) -> dict[str, Any]:
    """Build the machine-readable payload for ranked matches."""
    matches = [
        {
            **_opportunity_record(opportunity),
            "score": score,
            "days_until": None if days_until == 9999 else days_until,
            "reasons": list(reasons),
        }
        for (score, days_until, opportunity, reasons) in scored[:limit]
    ]
    return {"kind": "matches", "count": len(matches), "warnings": list(warnings[:5]), "matches": matches}


def _render_search_markdown(opportunities: list[dict], warnings: list[str]) -> str:
    """Render the unified search listing (single source for the handler + MCP)."""
    if not opportunities:
        output = "No opportunities found matching criteria."
        if warnings:
            output += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        return output

    output = "# Opportunities\n\n"
    output += f"Showing {len(opportunities)} combined results from CanadaBuys and Alberta Purchasing Connection.\n\n"
    for i, opportunity in enumerate(opportunities, 1):
        output += render_unified_opportunity_line(opportunity, i) + "\n"

    if warnings:
        output += "## Warnings\n"
        for warning in warnings:
            output += f"- {warning}\n"

    output += "\nUse `get_opportunity_details` with a reference number for full details."
    return output


def _render_deadlines_markdown(opportunities: list[dict], warnings: list[str], days: int) -> str:
    """Render the closing-soon listing (single source for the handler + MCP)."""
    if not opportunities:
        output = f"No opportunities closing within {days} days."
        if warnings:
            output += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        return output

    output = f"# Opportunities Closing Within {days} Days\n\n"
    for i, opportunity in enumerate(opportunities, 1):
        time_left = describe_closing(opportunity_closing(opportunity))
        extra = time_left[:1].upper() + time_left[1:] if time_left else ""
        output += render_unified_opportunity_line(opportunity, i, extra) + "\n"

    if warnings:
        output += "## Warnings\n"
        for warning in warnings:
            output += f"- {warning}\n"

    return output


def _render_matches_markdown(
    scored: list[tuple[int, int, dict, list[str]]],
    warnings: list[str],
    profile: dict,
    days: int,
    limit: int,
) -> str:
    """Render the ranked matches listing (single source for the handler + MCP)."""
    if not scored:
        output = f"No matching opportunities found in the next {days} days."
        if warnings:
            output += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings[:5])
        return output

    company = profile.get("company_name", "Your Business")
    output = f"# Matching Opportunities for {company}\n\n"
    output += f"Found **{len(scored)}** ranked opportunities across CanadaBuys and Alberta APC.\n\n"

    for i, (score, days_until, opportunity, reasons) in enumerate(scored[:limit], 1):
        extra = f"Match Score: {score}"
        if days_until != 9999:
            extra += f" | {describe_days_until(days_until).capitalize()}"
        output += render_unified_opportunity_line(opportunity, i, extra)
        output += f"   Why it matches: {'; '.join(reasons)}\n\n"

    if warnings:
        output += "## Warnings\n"
        for warning in warnings[:5]:
            output += f"- {warning}\n"

    return output


STRUCTURED_TOOLS = frozenset({"search_opportunities", "list_deadlines", "find_matching_opportunities"})

TENDER_REQUIREMENTS_SCHEMA = "wa.tender_requirements.v1"
CLASSIFY_JSON_NOTE = (
    f"The full result follows as JSON (schema {TENDER_REQUIREMENTS_SCHEMA}). If the WorkspaceAlberta "
    "procurement skill is available, use its requirements-board template to build the artifact from that "
    "JSON; otherwise, offer the user an interactive requirements board grouped by connector and lead time, "
    "counted back from `tender.closes_at`."
)


def mcp_text_blocks(name: str, text: str, structured: dict[str, Any] | None) -> list[str]:
    """Text content blocks for an MCP tool result.

    Some clients show the model only text content, never ``structuredContent``. The MCP
    spec says a tool that returns structured content SHOULD also return it serialized in a
    text block, so ``classify_tender`` sends its markdown followed by the same object as
    compact JSON. Every other tool keeps its single text block.
    """
    if name != "classify_tender" or structured is None:
        return [text]
    data = json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
    if structured.get("schema") == TENDER_REQUIREMENTS_SCHEMA:
        return [f"{text}\n\n{CLASSIFY_JSON_NOTE}",
                f"classify_tender JSON (schema {TENDER_REQUIREMENTS_SCHEMA}):\n{data}"]
    return [text, f"classify_tender JSON (upload link; no requirements yet):\n{data}"]


async def call_tool_text_and_structured(
    name: str, arguments: dict[str, Any] | None = None
) -> tuple[str, dict[str, Any] | None]:
    """Run a tool and return (markdown, structured) in a single pass.

    The primary search/match tools also produce a machine-readable
    ``structured`` payload for MCP ``structured_content``; every other tool
    returns ``(text, None)``. Collecting once keeps the markdown and the
    structured payload consistent and avoids a second upstream fetch.
    """
    args = arguments or {}
    handlers = {tool_name: globals()[tool_name] for tool_name in TOOL_NAMES}
    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}", None

    if name == "classify_tender":
        # Markdown for the conversation; the artifact itself (or the upload link) as structured
        # content. mcp_text_blocks repeats the structured content as a JSON text block.
        try:
            envelope = await classify_tender_artifact_bounded(args)
        except Exception as exc:
            return f"Error: {exc}", None
        if "artifact" in envelope:
            return envelope["markdown"], envelope["artifact"]
        return envelope["markdown"], {key: value for key, value in envelope.items() if key != "markdown"}

    if name not in STRUCTURED_TOOLS:
        return await call_tool_text(name, args), None

    def _run() -> tuple[str, dict[str, Any] | None]:
        if name == "search_opportunities":
            opportunities, warnings = collect_unified_search(args)
            return _render_search_markdown(opportunities, warnings), _search_structured(opportunities, warnings)
        if name == "list_deadlines":
            days = clamp_int(args.get("days"), default=30, minimum=1, maximum=365)
            opportunities, warnings = collect_unified_deadlines(args)
            return _render_deadlines_markdown(opportunities, warnings, days), _search_structured(opportunities, warnings)
        # find_matching_opportunities
        profile = resolve_profile(args)
        if not profile:
            return NO_PROFILE_MESSAGE, None
        days = clamp_int(args.get("days"), default=60, minimum=1, maximum=365)
        limit = clamp_int(args.get("limit"), default=15, minimum=1, maximum=30)
        scored, warnings = collect_unified_matches(profile, days, limit)
        return (
            _render_matches_markdown(scored, warnings, profile, days, limit),
            _matches_structured(scored, warnings, limit),
        )

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        return f"Error: {exc}", None


async def search_contracts(args: dict) -> str:
    """Search contracts."""
    contracts = load_contracts()
    if not contracts:
        return "No data available. Run 'refresh_data' first."

    keywords = args.get("keywords", "").lower()
    province = args.get("province", "").lower()
    limit = args.get("limit", 10)

    results = []
    for contract in contracts:
        # Keyword filter
        if keywords:
            text = f"{get_field(contract, 'title-titre-eng')} {get_field(contract, 'tenderDescription-descriptionAppelOffres-eng')}".lower()
            if keywords not in text:
                continue

        # Province filter
        if province:
            regions = f"{get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng')} {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}".lower()
            if province not in regions:
                continue

        results.append(contract)
        if len(results) >= limit:
            break

    if not results:
        return "No contracts found matching criteria."

    output = f"Found {len(results)} contracts:\n\n"
    for i, c in enumerate(results, 1):
        title = get_field(c, "title-titre-eng", "title-titre-fra")[:60]
        output += f"**{i}. {title}**\n"
        output += f"   Reference: {get_field(c, 'referenceNumber-numeroReference')}\n"
        output += f"   Closing: {format_closing(get_field(c, 'tenderClosingDate-appelOffresDateCloture'), CANADABUYS_SOURCE_TZ)}\n"
        output += f"   Entity: {get_field(c, 'contractingEntityName-nomEntitContractante-eng')}\n\n"

    return output


async def get_contract_details(args: dict) -> str:
    """Get contract details."""
    reference = args.get("reference", "").lower()
    if not reference:
        return "Please provide a reference number."

    contracts = load_contracts()
    contract = find_contract_by_reference(reference, contracts)
    if contract:
        return render_contract_markdown(contract)

    return f"Contract not found: {reference}"


async def list_upcoming_deadlines(args: dict) -> str:
    """List upcoming deadlines."""
    days = args.get("days", 30)
    province = args.get("province", "").lower()

    contracts = load_contracts()
    if not contracts:
        return "No data available. Run 'refresh_data' first."

    now = datetime.now(timezone.utc)
    upcoming = []

    for contract in contracts:
        if province:
            regions = f"{get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng')} {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}".lower()
            if province not in regions:
                continue

        closing_date = canadabuys_closing(contract)

        if closing_date and not has_closed(closing_date, now):
            days_until = days_until_close(closing_date, now)
            if days_until <= days:
                upcoming.append((closing_date, days_until, contract))

    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return f"No contracts closing within {days} days."

    output = f"Contracts closing within {days} days:\n\n"
    for _closing, days_until, c in upcoming[:20]:
        title = get_field(c, "title-titre-eng")[:50]
        closing_text = format_closing(get_field(c, "tenderClosingDate-appelOffresDateCloture"), CANADABUYS_SOURCE_TZ)
        output += f"**{title}**\n"
        output += f"   Closing: {closing_text} ({describe_days_until(days_until)})\n"
        output += f"   Reference: {get_field(c, 'referenceNumber-numeroReference')}\n\n"

    return output


async def summarize_contracts(args: dict) -> str:
    """Summarize available contracts."""
    contracts = load_contracts()
    if not contracts:
        return "No data available. Run 'refresh_data' first."

    output = f"# CanadaBuys Contract Summary\n\n"
    output += f"**Total Contracts:** {len(contracts)}\n\n"

    # Sample some titles
    output += "## Sample Opportunities\n"
    for c in contracts[:5]:
        title = get_field(c, "title-titre-eng")[:60]
        output += f"- {title}\n"

    summary_path = DATA_DIR / "latest.json"
    if summary_path.exists():
        with summary_path.open("r") as f:
            summary = json.load(f)
            output += f"\n## Data Info\n"
            output += f"- Last Updated: {summary.get('generated_at_utc', 'Unknown')}\n"

    return output


async def refresh_data(args: dict) -> str:
    """Refresh data from CanadaBuys."""
    try:
        contracts = fetch_all_contracts()
        save_contracts(contracts)

        return f"Data refreshed!\n\n**Total Contracts:** {len(contracts)}"
    except Exception as e:
        return f"Error: {str(e)}"


# ============== Business Profile Handlers ==============

async def set_business_profile(args: dict) -> str:
    """Save business profile for smart matching."""
    description = args.get("description", "")
    if not description:
        return "Please describe your business."

    # Extract keywords and infer industries
    capabilities = extract_keywords(description)
    industries = infer_industries(capabilities, description)

    profile = {
        "company_name": args.get("company_name", "My Business"),
        "location": args.get("location", ""),
        "description": description,
        "capabilities": capabilities,
        "industries": industries,
    }

    persisted = save_profile(profile)

    output = "# Profile Saved!\n\n"
    output += f"**Company:** {profile['company_name']}\n"
    if profile['location']:
        output += f"**Location:** {profile['location']}\n"
    output += f"\n**Detected Industries:** {', '.join(industries) if industries else 'General'}\n"
    output += f"**Keywords I'll search for:** {', '.join(capabilities[:10])}\n"
    if not persisted:
        output += (
            "\nThis hosted session is anonymous, so the profile was **not stored**. "
            "Sign in (or send a `wa_live_` key) to keep it, or pass a `profile` "
            "argument on later calls.\n"
        )
    output += "\nUse `find_opportunities` to see matching contracts!"

    return output


async def find_opportunities(args: dict) -> str:
    """Find contracts matching an inline or saved business profile."""
    profile = resolve_profile(args)
    if not profile:
        return NO_PROFILE_MESSAGE

    contracts = load_contracts()
    if not contracts:
        return "No contract data available. Run `refresh_data` first."

    days = args.get("days", 60)
    limit = args.get("limit", 15)
    now = datetime.now(timezone.utc)

    # Score all contracts
    scored = []
    for contract in contracts:
        # Check if closing date is within range
        closing_date = canadabuys_closing(contract)

        if closing_date:
            if has_closed(closing_date, now):
                continue  # Skip expired
            days_until = days_until_close(closing_date, now)

            if days_until > days:
                continue  # Skip too far out

            score, reasons = score_contract(contract, profile)
            if score > 0:
                scored.append((score, days_until, contract, reasons))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    if not scored:
        return f"No matching opportunities found in the next {days} days.\n\nTry:\n- Updating your profile with more detail\n- Increasing the days parameter\n- Running `refresh_data` to get latest contracts"

    company = profile.get("company_name", "Your Business")
    output = f"# Opportunities for {company}\n\n"
    output += f"Found **{len(scored)}** matching contracts (showing top {min(limit, len(scored))})\n\n"

    for i, (score, days_until, contract, reasons) in enumerate(scored[:limit], 1):
        title = get_field(contract, "title-titre-eng", "title-titre-fra")[:70]
        ref = get_field(contract, "referenceNumber-numeroReference")
        entity = get_field(contract, "contractingEntityName-nomEntitContractante-eng")[:40]

        output += f"### {i}. {title}\n"
        output += f"**Match Score:** {score} | **Closing:** {format_closing(get_field(contract, 'tenderClosingDate-appelOffresDateCloture'), CANADABUYS_SOURCE_TZ)} ({describe_days_until(days_until)})\n"
        output += f"**Why it matches:** {'; '.join(reasons)}\n"
        output += f"**Entity:** {entity}\n"
        output += f"**Reference:** `{ref}`\n\n"

    output += "---\n*Use `get_contract_details` with a reference number to see full details.*"

    return output


async def get_my_profile(args: dict) -> str:
    """Return current business profile."""
    profile = load_profile()
    if not profile:
        return "No business profile set yet.\n\nUse `set_business_profile` to tell me about your business!"

    output = "# Your Business Profile\n\n"
    output += f"**Company:** {profile.get('company_name', 'Not set')}\n"
    output += f"**Location:** {profile.get('location', 'Not set')}\n\n"
    output += f"**Description:**\n{profile.get('description', 'Not set')}\n\n"
    output += f"**Industries:** {', '.join(profile.get('industries', [])) or 'None detected'}\n"
    output += f"**Keywords:** {', '.join(profile.get('capabilities', [])[:15])}\n"

    return output


# ============== Unified Procurement Handlers ==============


async def search_opportunities(args: dict) -> str:
    """Search across federal and Alberta opportunity sources."""
    opportunities, warnings = collect_unified_search(args)
    return _render_search_markdown(opportunities, warnings)


async def get_opportunity_details(args: dict) -> str:
    """Get details from the right source based on reference number."""
    reference = args.get("reference", "")
    if not reference:
        return "Please provide a reference number."

    if is_alberta_reference(reference):
        return await get_alberta_opportunity_details({"reference": reference})

    contracts, warnings = load_contracts_for_unified()
    contract = find_contract_by_reference(reference, contracts)
    if contract:
        output = render_contract_markdown(contract)
        if warnings:
            output += "\n\n## Warnings\n" + "\n".join(f"- {warning}" for warning in warnings)
        return output

    output = f"Opportunity not found: {reference}"
    if warnings:
        output += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
    return output


async def list_deadlines(args: dict) -> str:
    """List closing-soon opportunities across sources."""
    days = clamp_int(args.get("days"), default=30, minimum=1, maximum=365)
    opportunities, warnings = collect_unified_deadlines(args)
    return _render_deadlines_markdown(opportunities, warnings, days)


async def find_matching_opportunities(args: dict) -> str:
    """Rank opportunities from both sources against an inline or saved profile."""
    profile = resolve_profile(args)
    if not profile:
        return NO_PROFILE_MESSAGE

    days = clamp_int(args.get("days"), default=60, minimum=1, maximum=365)
    limit = clamp_int(args.get("limit"), default=15, minimum=1, maximum=30)
    scored, warnings = collect_unified_matches(profile, days, limit)
    return _render_matches_markdown(scored, warnings, profile, days, limit)


async def daily_bid_brief(args: dict) -> str:
    """Generate a free daily bid brief from both opportunity sources."""
    profile = resolve_profile(args)
    if not profile:
        return NO_PROFILE_MESSAGE

    days = clamp_int(args.get("days"), default=14, minimum=1, maximum=60)
    limit = clamp_int(args.get("limit"), default=5, minimum=1, maximum=10)
    warnings = []

    contracts, federal_warnings = load_contracts_for_unified()
    warnings.extend(federal_warnings)
    federal_count = len(contracts)
    alberta_count: Any = "Unknown"
    try:
        alberta_count = search_alberta_api(status="OPEN", limit=1).get("totalCount", "Unknown")
    except RuntimeError as exc:
        warnings.append(f"Alberta APC summary unavailable: {exc}")

    matches, match_warnings = collect_unified_matches(profile, days, limit)
    warnings.extend(match_warnings)
    deadlines, deadline_warnings = collect_unified_deadlines({"days": days, "limit": limit, "source": "all"})
    warnings.extend(deadline_warnings)

    company = profile.get("company_name", "Your Business")
    output = f"# Daily Bid Brief for {company}\n\n"
    output += "Free community brief. Build the habit first; pricing can wait until people rely on it.\n\n"
    output += "## Market Snapshot\n"
    output += f"- **Federal CanadaBuys open notices:** {federal_count}\n"
    output += f"- **Alberta APC open opportunities:** {alberta_count}\n"
    output += f"- **Lookahead window:** {days} days\n\n"

    output += "## Best Fits\n"
    if matches:
        for i, (score, days_until, opportunity, reasons) in enumerate(matches[:limit], 1):
            extra = f"Score {score}"
            if days_until != 9999:
                extra += f" | {describe_days_until(days_until)}"
            output += render_unified_opportunity_line(opportunity, i, extra)
            output += f"   Reason: {'; '.join(reasons)}\n\n"
    else:
        output += "No profile-matched opportunities found in this lookahead window.\n\n"

    output += "## Closing Soon\n"
    if deadlines:
        for i, opportunity in enumerate(deadlines[:limit], 1):
            time_left = describe_closing(opportunity_closing(opportunity))
            extra = time_left.capitalize() if time_left else ""
            output += render_unified_opportunity_line(opportunity, i, extra) + "\n"
    else:
        output += "No upcoming deadlines found.\n\n"

    output += "## Suggested Action\n"
    if matches:
        output += "Open the top one or two matches, check mandatory requirements and documents, then make a bid/no-bid call.\n"
    else:
        output += "Broaden the profile keywords or extend the lookahead window.\n"

    if warnings:
        output += "\n## Warnings\n"
        seen = []
        for warning in warnings:
            if warning not in seen:
                seen.append(warning)
                output += f"- {warning}\n"
            if len(seen) >= 5:
                break

    return output


def process_bid_room_artifact(args: dict, *, deadline: float | None = None, cancelled=None) -> dict[str, Any]:
    """Process a bid room in E2B and return a JSON-ready artifact envelope."""
    from procurement_core.e2b_bid_room import (
        build_apc_bid_room_payload,
        build_canadabuys_bid_room_payload,
        render_bid_room_markdown,
        run_live_bid_room_process,
        BID_ROOM_WORK_SECONDS,
        remaining_bid_room_seconds,
        BidRoomTimeout, BID_ROOM_TIMEOUT_MESSAGE,
    )

    deadline = deadline if deadline is not None else time.monotonic() + BID_ROOM_WORK_SECONDS
    remaining_bid_room_seconds(deadline)

    reference = str(args.get("reference") or "").strip()
    if not reference:
        raise ValueError("Please provide a reference number.")
    if args.get("apc_document_urls") is not None and not is_alberta_reference(reference):
        raise ValueError("apc_document_urls applies only to an Alberta APC reference.")

    profile = resolve_profile(args) or {}
    business_context = str(args.get("business_context") or "").strip()
    max_attachments = clamp_int(args.get("max_attachments"), default=5, minimum=0, maximum=5)
    # Older REST callers may send these fields; they cannot extend the budget
    # or leave a paid sandbox alive. They are no longer in the MCP schema.
    warnings: list[str] = []

    upload_token = str(args.get("upload_token") or "").strip()
    if upload_token and not is_alberta_reference(reference):
        raise ValueError("upload_token applies only to an Alberta APC reference.")

    if is_alberta_reference(reference):
        try:
            details = get_alberta_api_details(reference)
        except (RuntimeError, ValueError) as exc:
            raise ValueError(f"Alberta opportunity not available: {exc}") from exc
        if upload_token:
            return _process_uploaded_bid_room(
                reference, upload_token, details, profile,
                business_context=business_context, max_attachments=max_attachments,
                deadline=deadline, cancelled=cancelled,
            )
        payload = build_apc_bid_room_payload(
            details,
            profile,
            business_context=business_context,
            max_attachments=max_attachments,
            apc_document_urls=args.get("apc_document_urls"),
        )
    else:
        contracts, federal_warnings = load_contracts_for_unified()
        warnings.extend(federal_warnings)
        contract = find_contract_by_reference(reference, contracts)
        if not contract:
            raise ValueError(f"Opportunity not found: {reference}")
        payload = build_canadabuys_bid_room_payload(
            contract,
            profile,
            business_context=business_context,
            max_attachments=max_attachments,
        )

    remaining_bid_room_seconds(deadline, reserve=5)
    if cancelled is not None and cancelled.is_set():
        raise BidRoomTimeout(BID_ROOM_TIMEOUT_MESSAGE)
    if is_alberta_reference(reference) and max_attachments > 0 and not any(
        item.get("kind") in {"apc_document", "apc_addendum"} for item in payload.get("attachments", [])
    ):
        from procurement_core import bid_room_uploads

        if bid_room_uploads.uploads_available():
            return _bid_room_upload_request(reference, payload)
        raise ValueError(f"No readable APC procurement files were resolved. No sandbox was started. {APC_ACCESS_MESSAGE}")
    result = run_live_bid_room_process(
        payload,
        deadline=deadline,
    )
    if warnings:
        result.artifact.setdefault("warnings", []).extend(warnings)
        from procurement_core.document_coverage import document_coverage
        result.artifact["coverage"] = document_coverage(result.artifact["documents"], result.artifact["warnings"])
    return {
        "sandbox_id": result.sandbox_id,
        "sandbox_killed": result.killed,
        "artifact": result.artifact,
        "markdown": render_bid_room_markdown(result),
    }


def _bid_room_upload_request(reference: str, payload: dict[str, Any], *, tool: str = "process_bid_room") -> dict[str, Any]:
    """APC files need the user's own sign-in: hand back a private upload link.

    Shared by ``process_bid_room`` and ``classify_tender``: one upload serves both tools,
    because the token is bound to the reference and the tenant, not to a tool.
    """
    from procurement_core import bid_room_uploads, storage

    token = bid_room_uploads.create_upload_token(reference, storage.current_tenant())
    url = bid_room_uploads.upload_page_url(token)
    listed = payload.get("document_manifest") or []
    hours = bid_room_uploads.TOKEN_TTL_SECONDS // 3600
    if tool == "process_bid_room":
        retention = "Uploaded files are deleted after processing."
    else:
        retention = (
            f"`{tool}` does not delete the uploaded files, so `process_bid_room` can use the same "
            "`upload_token` afterwards; `process_bid_room` deletes them after processing."
        )
    heading = "Bid room" if tool == "process_bid_room" else "Tender requirements"
    lines = [
        f"# {heading}: upload the APC documents for {reference}",
        "",
        "Alberta Purchasing Connection only releases tender documents to a signed-in supplier "
        "account, so WorkspaceAlberta does not download them for you.",
        "",
        f"1. Open the posting on APC with your own supplier account: {payload.get('opportunity', {}).get('url', '')}",
        "2. Under **Document downloads**, choose **Download All** (or download each file, including every addendum). "
        "APC adds your account to that posting's Interested Suppliers list when you do.",
        f"3. Upload the files here: {url}",
        f"4. Then run `{tool}` again with `reference` = `{reference}` and `upload_token` = `{token}`.",
        "",
        f"The link is private to your account and expires in {hours} hours. {retention}",
    ]
    if listed:
        lines += ["", "APC lists these documents for this posting:"]
        lines += [f"- {item.get('name')}" + (f" (addendum {item.get('amendment_number')})" if item.get("kind") == "apc_addendum" else "") for item in listed]
    return {
        "upload_required": True,
        "upload_url": url,
        "upload_token": token,
        "expected_documents": [item.get("name") for item in listed],
        "markdown": "\n".join(lines),
    }


def _process_uploaded_bid_room(
    reference: str,
    upload_token: str,
    details: dict[str, Any],
    profile: dict[str, Any],
    *,
    business_context: str,
    max_attachments: int,
    deadline: float,
    cancelled=None,
) -> dict[str, Any]:
    from procurement_core import bid_room_uploads, storage
    from procurement_core.apc_documents import apc_document_manifest
    from procurement_core.e2b_bid_room import (
        BID_ROOM_TIMEOUT_MESSAGE, BidRoomTimeout, remaining_bid_room_seconds,
        render_bid_room_markdown, run_live_bid_room_process,
    )
    from procurement_core.local_bid_room import build_local_bid_room_payload

    claims = bid_room_uploads.verify_upload_token(
        upload_token, reference=reference, tenant=storage.current_tenant() or "",
    )
    download = bid_room_uploads.load_uploaded_files(claims, apc_manifest=apc_document_manifest(details))
    download["provenance"] = "user_upload"
    if max_attachments and not any(item["status"] == "verified" for item in download["files"]):
        problems = "; ".join(f"{item['name']}: {item['error'] or item['status']}" for item in download["files"])
        raise ValueError(f"None of the uploaded files can be processed ({problems}). No sandbox was started.")
    payload, uploads = build_local_bid_room_payload(
        download, profile,
        business_context=business_context,
        max_attachments=max_attachments,
        details=details,
    )
    remaining_bid_room_seconds(deadline, reserve=5)
    if cancelled is not None and cancelled.is_set():
        raise BidRoomTimeout(BID_ROOM_TIMEOUT_MESSAGE)
    result = run_live_bid_room_process(payload, uploads=uploads, deadline=deadline)
    bid_room_uploads.delete_session(claims)
    return {
        "sandbox_id": result.sandbox_id,
        "sandbox_killed": result.killed,
        "artifact": result.artifact,
        "markdown": render_bid_room_markdown(result),
    }


async def process_bid_room_artifact_bounded(args: dict) -> dict[str, Any]:
    """Bound every public adapter, including slow host-side source lookups.

    A source lookup already in a thread may finish after cancellation; the
    shared deadline prevents that worker from subsequently starting E2B work.
    Running sandboxes have command limits, bounded cleanup and a short expiry.
    """
    from procurement_core.e2b_bid_room import (
        BID_ROOM_CALL_SECONDS, BID_ROOM_WORK_SECONDS,
        BID_ROOM_TIMEOUT_MESSAGE, BidRoomTimeout,
    )
    from threading import Event
    cancelled = Event()
    deadline = time.monotonic() + BID_ROOM_WORK_SECONDS
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(process_bid_room_artifact, args, deadline=deadline, cancelled=cancelled),
            timeout=BID_ROOM_CALL_SECONDS,
        )
    except TimeoutError as exc:
        raise BidRoomTimeout(BID_ROOM_TIMEOUT_MESSAGE) from exc
    finally:
        cancelled.set()


async def process_bid_room(args: dict) -> str:
    """Process a tender package in E2B and analyze it with Cohere inside the sandbox."""
    try:
        return (await process_bid_room_artifact_bounded(args))["markdown"]
    except (RuntimeError, ValueError) as exc:
        return f"Error: Bid room processing is not available: {exc}"


# ============== Tender requirement classification (TypeSafe Jev) ==============

CLASSIFY_CALL_SECONDS = 140
CLASSIFY_WORK_SECONDS = 120  # Leave time to finish the response inside the call limit.
CLASSIFY_MAX_FILES = 5  # CanadaBuys PDF/ZIP attachments downloaded per call
CLASSIFY_MAX_URLS = 10  # attachment URLs looked at (Word/Excel files are skipped without download)
CLASSIFY_MIN_SECONDS_TO_CLASSIFY = 45  # Stop downloading when less than this is left.
CLASSIFY_NOT_CONFIGURED_MESSAGE = "Requirement classification is not configured on this server."
CLASSIFY_TIMEOUT_MESSAGE = (
    "Requirement classification reached its time limit; no requirement list is available. "
    "Do not treat this response as a completed review."
)


class ClassifierNotConfigured(ValueError):
    """TYPESAFE_API_KEY is not set: nothing was downloaded or sent anywhere."""


def _typesafe_api_key() -> str:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise ClassifierNotConfigured(CLASSIFY_NOT_CONFIGURED_MESSAGE)
    return key


def _download_public_document(url: str, timeout: float) -> bytes:
    """Download one public HTTPS document with the bid room's URL and size checks.

    Every URL and every redirect target must be a public HTTPS address
    (``apc_documents.public_document_url`` with DNS resolution); the body is capped at
    the bid room's per-file limit.
    """
    from urllib.request import HTTPRedirectHandler, build_opener

    from procurement_core.apc_documents import public_document_url
    from procurement_core.e2b_bid_room import MAX_FILE_BYTES

    class PublicRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            public_document_url(newurl, resolve=True)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    public_document_url(url, resolve=True)
    request = Request(url, headers={
        "User-Agent": "WorkspaceAlberta/1.0 (+https://elbowsupknivesout.warreandvavasour.com)",
        "Accept": "application/pdf,application/zip,*/*",
    })
    limit_mb = MAX_FILE_BYTES // (1024 * 1024)
    with build_opener(PublicRedirects()).open(request, timeout=timeout) as response:
        length = str(response.headers.get("Content-Length") or "")
        if length.isdigit() and int(length) > MAX_FILE_BYTES:
            raise ValueError(f"larger than the {limit_mb} MB limit")
        data = response.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"larger than the {limit_mb} MB limit")
    return data


def _classify_canadabuys_files(
    reference: str, deadline: float, cancelled=None,
) -> tuple[list[tuple[str, bytes]], list[str], dict[str, Any]]:
    """Public first-party CanadaBuys attachments, PDFs only (PDFs inside ZIPs included).

    Also returns the CanadaBuys row, so the result can describe the tender without
    another lookup.
    """
    import http.client
    from urllib.parse import urlparse

    from procurement_core import bid_room_uploads
    from procurement_core.e2b_bid_room import MAX_FILE_BYTES, _name_from_url, resolve_canadabuys_attachment_urls

    contracts, warnings = load_contracts_for_unified()
    contract = find_contract_by_reference(reference, contracts)
    if not contract:
        raise ValueError(f"Opportunity not found: {reference}")
    urls = resolve_canadabuys_attachment_urls(contract, max_attachments=CLASSIFY_MAX_URLS)
    if not urls:
        raise ValueError(
            f"No tender attachments are published for {reference} in the CanadaBuys data or on its "
            "official detail page, so there is nothing to classify. Nothing was sent to the classifier."
        )
    warnings = list(warnings)
    files: list[tuple[str, bytes]] = []
    downloads = 0
    for index, url in enumerate(urls, 1):
        name = _name_from_url(url, f"canadabuys-attachment-{index}")
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix and suffix not in {".pdf", ".zip"}:
            warnings.append(f"{name}: skipped, only PDF files are classified.")
            continue
        if downloads >= CLASSIFY_MAX_FILES:
            warnings.append(f"{name}: not downloaded, at most {CLASSIFY_MAX_FILES} attachments are read per call.")
            continue
        if cancelled is not None and cancelled.is_set():
            raise RuntimeError(CLASSIFY_TIMEOUT_MESSAGE)
        remaining = deadline - time.monotonic() - CLASSIFY_MIN_SECONDS_TO_CLASSIFY
        if remaining < 3:
            warnings.append(f"Time limit: {name} and later attachments were not downloaded.")
            break
        downloads += 1
        try:
            data = _download_public_document(url, timeout=min(30.0, remaining))
        except (ValueError, OSError, http.client.HTTPException) as exc:
            warnings.append(f"{name}: could not be downloaded ({exc}).")
            continue
        expanded: list[tuple[str, bytes]] = []
        bid_room_uploads._expand(name, data, expanded, warnings)  # same ZIP rules as uploads
        for member_name, content in expanded:
            if not content.startswith(b"%PDF-"):
                warnings.append(f"{member_name}: skipped, only PDF files are classified.")
            elif len(content) > MAX_FILE_BYTES:
                warnings.append(f"{member_name}: skipped, larger than the {MAX_FILE_BYTES // (1024 * 1024)} MB limit.")
            else:
                files.append((member_name, content))
    if not files:
        raise ValueError(
            f"No PDF tender documents could be downloaded for {reference}. "
            + " ".join(warnings[-5:])
        )
    return files, warnings, contract


def _classify_uploaded_files(
    reference: str, upload_token: str, details: dict[str, Any],
) -> tuple[list[tuple[str, bytes]], list[str]]:
    """The user's own APC uploads, verified exactly as ``process_bid_room`` does.

    The uploads are not deleted: ``process_bid_room`` may run on the same token next.
    """
    from procurement_core import bid_room_uploads, storage
    from procurement_core.apc_documents import apc_document_manifest

    claims = bid_room_uploads.verify_upload_token(
        upload_token, reference=reference, tenant=storage.current_tenant() or "",
    )
    download = bid_room_uploads.load_uploaded_files(claims, apc_manifest=apc_document_manifest(details))
    warnings = list(download["warnings"])
    files: list[tuple[str, bytes]] = []
    for item in download["files"]:
        if item["status"] != "verified":
            warnings.append(f"{item['name']}: skipped ({item['error'] or item['status']}).")
        elif Path(item["name"]).suffix.lower() != ".pdf":
            warnings.append(f"{item['name']}: skipped, only PDF files are classified.")
        else:
            files.append((item["name"], item["data"]))
    if not files:
        problems = "; ".join(f"{item['name']}: {item['error'] or item['status']}" for item in download["files"])
        raise ValueError(
            f"None of the uploaded files is a PDF that can be classified ({problems}). "
            "Nothing was sent to the classifier."
        )
    return files, warnings


APC_CLOSING_TIMEZONE = "America/Edmonton (APC reports Alberta local time without a UTC offset)"
CANADABUYS_CLOSING_TIMEZONE = "UTC-05:00 when no offset is given (CanadaBuys open data uses a fixed offset)"


def _reported(value: Any) -> str | None:
    """A source value exactly as reported, or None when the source left it empty."""
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def _tender_closing(raw: Any, source_tz: tzinfo, timezone_note: str) -> dict[str, Any]:
    """``closing`` as the source reported it; ``closes_at`` the same moment in Alberta time.

    Same convention as the search tools' structured records.
    """
    closing = _reported(raw)
    parsed = parse_closing(closing, source_tz) if closing else None
    return {
        "closing": closing,
        "closing_timezone": timezone_note if closing else None,
        "closes_at": parsed.astimezone(ALBERTA_TZ).isoformat() if parsed else None,
    }


def _apc_tender(reference: str, details: dict[str, Any]) -> dict[str, Any]:
    """The tender as described by the APC details already fetched for the token check."""
    opp = details.get("opportunity") or {}
    return {
        "reference": reference,
        "source": "apc",
        "title": _reported(opp.get("title") or opp.get("shortTitle")),
        "buyer": _reported(opp.get("contractingOrganization")),
        **_tender_closing(opp.get("closeDateTime"), APC_SOURCE_TZ, APC_CLOSING_TIMEZONE),
        "posting_url": apc_posting_url(reference, ALBERTA_APC_APP_BASE),
    }


def _canadabuys_tender(reference: str, contract: dict[str, Any]) -> dict[str, Any]:
    """The tender as described by the CanadaBuys row used to find its attachments."""
    return {
        "reference": _reported(get_field(contract, "referenceNumber-numeroReference")) or reference,
        "source": "canadabuys",
        "title": _reported(get_field(contract, "title-titre-eng", "title-titre-fra")),
        "buyer": _reported(get_field(contract, "contractingEntityName-nomEntitContractante-eng")),
        **_tender_closing(get_field(contract, "tenderClosingDate-appelOffresDateCloture"),
                          CANADABUYS_SOURCE_TZ, CANADABUYS_CLOSING_TIMEZONE),
        "posting_url": _reported(get_field(contract, "noticeURL-URLavis-eng")),
    }


def classify_tender_artifact(args: dict, *, deadline: float | None = None, cancelled=None) -> dict[str, Any]:
    """Classify a tender package into bidder requirements; return markdown + artifact.

    The artifact follows ``TENDER_REQUIREMENTS_SCHEMA``: its ``tender`` object comes from the
    APC details or CanadaBuys row this call already fetched, with no extra lookup.
    For an APC reference without ``upload_token`` this returns the same private upload
    link as ``process_bid_room``. Raises :class:`ClassifierNotConfigured` before any
    download when ``TYPESAFE_API_KEY`` is not set.
    """
    from procurement_core.requirements import classify_documents, render_markdown
    from procurement_core.requirements.jev import AuthError

    deadline = deadline if deadline is not None else time.monotonic() + CLASSIFY_WORK_SECONDS
    reference = str(args.get("reference") or "").strip()
    if not reference:
        raise ValueError("Please provide a reference number.")
    upload_token = str(args.get("upload_token") or "").strip()
    if upload_token and not is_alberta_reference(reference):
        raise ValueError("upload_token applies only to an Alberta APC reference.")
    api_key = _typesafe_api_key()

    if is_alberta_reference(reference):
        try:
            details = get_alberta_api_details(reference)
        except (RuntimeError, ValueError) as exc:
            raise ValueError(f"Alberta opportunity not available: {exc}") from exc
        if not upload_token:
            from procurement_core import bid_room_uploads
            from procurement_core.e2b_bid_room import build_apc_bid_room_payload

            if not bid_room_uploads.uploads_available():
                raise ValueError(
                    "APC releases tender documents only to a signed-in supplier account, and private "
                    "document uploads are not available on this server, so there is nothing to classify."
                )
            payload = build_apc_bid_room_payload(details, {}, max_attachments=0)
            return _bid_room_upload_request(reference, payload, tool="classify_tender")
        files, warnings = _classify_uploaded_files(reference, upload_token, details)
        source = "uploaded by the user from APC"
        tender = _apc_tender(reference, details)
    else:
        files, warnings, contract = _classify_canadabuys_files(reference, deadline, cancelled)
        source = "CanadaBuys public attachments"
        tender = _canadabuys_tender(reference, contract)

    if cancelled is not None and cancelled.is_set():
        raise RuntimeError(CLASSIFY_TIMEOUT_MESSAGE)
    try:
        result = classify_documents(files, deadline=deadline, api_key=api_key, stop=cancelled)
    except AuthError:
        raise RuntimeError(
            "The classifier (TypeSafe AI) refused this server's credentials; requirement classification "
            "is unavailable. Nothing else was changed."
        ) from None
    result = {"schema": TENDER_REQUIREMENTS_SCHEMA, "reference": reference, "source": source,
              "tender": tender, **result, "warnings": [*warnings, *result["warnings"]]}
    return {"artifact": result, "markdown": render_markdown(result, reference=reference, source=source)}


async def classify_tender_artifact_bounded(args: dict) -> dict[str, Any]:
    """Bound the whole call, source lookups and downloads included (as process_bid_room)."""
    from threading import Event

    cancelled = Event()
    deadline = time.monotonic() + CLASSIFY_WORK_SECONDS
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(classify_tender_artifact, args, deadline=deadline, cancelled=cancelled),
            timeout=CLASSIFY_CALL_SECONDS,
        )
    except TimeoutError as exc:
        raise RuntimeError(CLASSIFY_TIMEOUT_MESSAGE) from exc
    finally:
        cancelled.set()


async def classify_tender(args: dict) -> str:
    """List the bidder requirements in a tender package (TypeSafe Jev classification)."""
    try:
        return (await classify_tender_artifact_bounded(args))["markdown"]
    except (RuntimeError, ValueError) as exc:
        return f"Error: {exc}"


# ============== Alberta Purchasing Connection Handlers ==============


async def search_alberta_opportunities(args: dict) -> str:
    """Search Alberta Purchasing Connection opportunities."""
    keywords = args.get("keywords", "")
    category = args.get("category", "")
    status = args.get("status", "OPEN")
    limit = clamp_int(args.get("limit"), default=10, minimum=1, maximum=50)
    rows, warnings = collect_alberta_candidates(keywords, category=category, status=status)
    output = "# Alberta Opportunities\n\n"
    output += f"Showing {min(limit, len(rows))} of {len(rows)} retrieved matching APC records.\n\n"
    if not rows:
        output += "No Alberta opportunities found matching criteria.\n\n"

    for i, opp in enumerate(rows[:limit], 1):
        output += render_alberta_opportunity_line(opp, i) + "\n"

    if warnings:
        output += "## Warnings\n" + "\n".join(f"- {warning}" for warning in warnings) + "\n\n"

    output += "Use `get_alberta_opportunity_details` with an `AB-YYYY-NNNNN` reference for full details."
    return output


async def get_alberta_opportunity_details(args: dict) -> str:
    """Get APC opportunity details by reference."""
    reference = args.get("reference", "")
    if not reference:
        return "Please provide an Alberta APC reference number."

    try:
        data = get_alberta_api_details(reference)
    except (RuntimeError, ValueError) as exc:
        return f"Alberta opportunity not available: {exc}"

    return render_alberta_details_markdown(data)


async def list_alberta_deadlines(args: dict) -> str:
    """List open APC opportunities closing soon."""
    days = clamp_int(args.get("days"), default=30, minimum=1, maximum=365)
    limit = clamp_int(args.get("limit"), default=20, minimum=1, maximum=50)
    category = args.get("category", "")
    now = datetime.now(timezone.utc)
    today = alberta_today(now)
    close_start = today.strftime("%Y-%m-%d")
    close_end = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        data = search_alberta_api(
            status="OPEN",
            category=category,
            limit=limit,
            sort_field="CloseDateTime",
            sort_direction="asc",
            close_start=close_start,
            close_end=close_end,
        )
    except RuntimeError as exc:
        return f"Alberta deadline search failed: {exc}"

    rows = []
    for opp in data.get("values", []):
        closing = alberta_closing(opp)
        if closing and has_closed(closing, now):
            continue
        rows.append(opp)
    if not rows:
        return f"No Alberta opportunities closing within {days} days."

    output = f"# Alberta Opportunities Closing Within {days} Days\n\n"
    for i, opp in enumerate(rows[:limit], 1):
        time_left = describe_closing(alberta_closing(opp), now)
        output += render_alberta_opportunity_line(opp, i)
        if time_left:
            output += f"   {time_left.capitalize()}\n"
        output += "\n"
    return output


async def summarize_alberta_opportunities(args: dict) -> str:
    """Summarize open APC opportunities."""
    try:
        total_data = search_alberta_api(status="OPEN", limit=1)
        category_counts = {}
        for label, code in (("Services", "SRV"), ("Goods", "GD"), ("Construction", "CNST")):
            category_data = search_alberta_api(status="OPEN", category=code, limit=1)
            category_counts[label] = category_data.get("totalCount", 0)
    except RuntimeError as exc:
        return f"Alberta APC summary failed: {exc}"

    output = "# Alberta Purchasing Connection Summary\n\n"
    output += f"**Open Opportunities:** {total_data.get('totalCount', 'Unknown')}\n\n"
    output += "## By Category\n"
    for label, count in category_counts.items():
        output += f"- **{label}:** {count}\n"
    output += "\nAPC includes Government of Alberta and Alberta public-sector buyers such as municipalities, school boards, health entities, and post-secondary institutions."

    return output


async def find_alberta_opportunities(args: dict) -> str:
    """Find APC opportunities matching an inline or saved business profile."""
    profile = resolve_profile(args)
    if not profile:
        return NO_PROFILE_MESSAGE

    days = clamp_int(args.get("days"), default=60, minimum=1, maximum=365)
    limit = clamp_int(args.get("limit"), default=15, minimum=1, maximum=30)
    scored, errors = collect_alberta_matches(profile, days)

    if not scored:
        message = f"No matching Alberta opportunities found in the next {days} days."
        if errors:
            message += f"\n\nAPC search warnings: {'; '.join(errors[:2])}"
        return message

    company = profile.get("company_name", "Your Business")
    output = f"# Alberta Opportunities for {company}\n\n"
    output += f"Found **{len(scored)}** matching APC opportunities (showing top {min(limit, len(scored))}).\n\n"

    for i, (score, days_until, opp, reasons) in enumerate(scored[:limit], 1):
        title = str(opp.get("title") or opp.get("shortTitle") or "Untitled opportunity")[:90]
        ref = opp.get("referenceNumber", "")
        org = str(opp.get("contractingOrganization") or "")[:60]
        output += f"### {i}. {title}\n"
        output += f"**Match Score:** {score}"
        if days_until != 9999:
            output += f" | **Closing:** {format_closing(str(opp.get('closeDateTime') or ''), APC_SOURCE_TZ)} ({describe_days_until(days_until)})"
        output += "\n"
        output += f"**Why it matches:** {'; '.join(reasons)}\n"
        output += f"**Organization:** {org}\n"
        output += f"**Reference:** `{ref}`\n\n"

    if errors:
        output += "## Warnings\n" + "\n".join(f"- {warning}" for warning in errors) + "\n\n"

    output += "---\nUse `get_alberta_opportunity_details` with a reference number to inspect the posting."
    return output


async def check_cohere_status(args: dict) -> str:
    """Return non-secret status for the optional Cohere integration."""
    cohere_token, cohere_env_name = get_cohere_api_key()
    hf_token, hf_env_name = get_hf_token()

    output = "# Cohere Command A+ Status\n\n"
    output += f"**Preferred route:** {'Cohere API' if cohere_token else 'Hugging Face Inference Providers'}\n"
    output += f"**Cohere model:** `{COHERE_MODEL}`\n"
    output += f"**Cohere endpoint:** `{COHERE_CHAT_COMPLETIONS_URL}`\n"
    output += f"**Cohere key configured:** {'yes, via `' + cohere_env_name + '`' if cohere_token else 'no'}\n\n"
    if os.environ.get("COHERE_API_KEY", "").strip() and os.environ.get("COHERE_PROD_API_KEY", "").strip():
        output += "**Cohere failover:** `COHERE_API_KEY` first, then `COHERE_PROD_API_KEY` on rate-limit, quota, or credit failures.\n\n"
    output += f"**HF model route:** `{COHERE_HF_MODEL}`\n"
    output += f"**HF endpoint:** `{HF_CHAT_COMPLETIONS_URL}`\n"
    output += f"**HF token configured:** {'yes, via `' + hf_env_name + '`' if hf_token else 'no'}\n\n"
    output += "This status check does not call the model or reveal any token value."
    if not cohere_token and not hf_token:
        output += "\n\nSet `COHERE_API_KEY`, `COHERE_PROD_API_KEY`, `HF_TOKEN`, or `HUGGINGFACEHUB_API_TOKEN` to enable live analysis."
    elif hf_token and not cohere_token:
        output += "\n\nHF tokens must include the `Make calls to Inference Providers` permission."

    return output


async def analyze_contract_with_cohere(args: dict) -> str:
    """Use Cohere Command A+ to analyze a tender notice from either source."""
    reference = args.get("reference", "")
    if not reference:
        return "Please provide a reference number."

    if is_alberta_reference(reference):
        source_name = "Alberta Purchasing Connection"
        source_ref = reference.strip()
        try:
            alberta_data = get_alberta_api_details(reference)
        except (RuntimeError, ValueError) as exc:
            return f"Alberta opportunity not available: {exc}"
        contract_markdown = render_alberta_details_markdown(alberta_data)
    else:
        source_name = "CanadaBuys"
        contracts = load_contracts()
        if not contracts:
            return "No contract data available. Run `refresh_data` first."

        contract = find_contract_by_reference(reference, contracts)
        if not contract:
            return f"Contract not found: {reference}"
        source_ref = get_field(contract, "referenceNumber-numeroReference")
        contract_markdown = render_contract_markdown(contract)

    business_context = args.get("business_context", "").strip()
    if not business_context:
        profile = resolve_profile(args)
        if profile:
            company = profile.get("company_name", "The business")
            location = profile.get("location", "")
            description = profile.get("description", "")
            business_context = f"{company}. Location: {location}. Capabilities: {description}".strip()
        else:
            business_context = "No saved business profile or extra business context was provided."

    question = args.get("question", "").strip()
    if not question:
        question = "Should this business pursue this opportunity, and what should they check next?"

    max_tokens = clamp_int(args.get("max_tokens"), default=1200, minimum=400, maximum=2000)
    if len(contract_markdown) > MAX_CONTRACT_PROMPT_CHARS:
        contract_markdown = contract_markdown[:MAX_CONTRACT_PROMPT_CHARS] + "\n\n[Contract text truncated for model call.]"

    messages = [
        {
            "role": "system",
            "content": (
                "You help Canadian businesses review Canadian public tender notices "
                "(CanadaBuys federal or Alberta Purchasing Connection). "
                "Be practical, concise, and careful. Do not invent requirements. "
                "If the notice text is missing key details, say what the user should inspect on the source portal."
            ),
        },
        {
            "role": "user",
            "content": (
                "Review this tender for a business owner.\n\n"
                "Return these sections:\n"
                "1. Fit\n"
                "2. Why it may be worth a look\n"
                "3. Bid risks or missing details\n"
                "4. Next actions\n\n"
                f"Business context:\n{business_context}\n\n"
                f"Question:\n{question}\n\n"
                f"Tender notice:\n{contract_markdown}"
            ),
        },
    ]

    try:
        analysis, provider, model = call_cohere_chat(messages, max_tokens=max_tokens)
    except RuntimeError as exc:
        return f"Cohere analysis is not available: {exc}"

    output = "# Cohere Tender Analysis\n\n"
    output += f"**Source:** {source_name}\n"
    output += f"**Provider:** {provider}\n"
    output += f"**Model:** `{model}`\n"
    output += f"**Reference:** `{source_ref}`\n\n"
    output += analysis
    output += (
        f"\n\n---\nVerify requirements, amendments, and attachments on {source_name} "
        "before making a bid decision."
    )

    return output


# ============== Extension Tool Bindings ==============
# Imported last so `call_tool_text` dispatch (which resolves handlers from
# this module's globals) can find the extension handlers by name. The
# extensions module imports service helpers lazily, so no circular import.

from procurement_core.extensions import (  # noqa: E402
    bid_no_bid_scorecard,
    list_watchlist,
    unwatch_opportunity,
    watch_opportunity,
)
