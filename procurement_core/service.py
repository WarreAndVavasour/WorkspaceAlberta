#!/usr/bin/env python3
"""
Procurement Core Service

Pure Python procurement logic for CanadaBuys, Alberta Purchasing Connection,
business-profile matching, daily bid briefs, and optional Cohere analysis.

Configuration:
    CANADABUYS_DATA_DIR - Where to cache data (default: ~/.canadabuys/)
"""

import csv
import gzip
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def fetch_all_contracts() -> list[dict]:
    """Fetch all contracts from CanadaBuys."""
    request = Request(OPEN_TENDERS_URL, headers=REQUEST_HEADERS)

    with urlopen(request, timeout=120) as response:
        raw_data = response.read()

        # Decompress if gzipped
        if raw_data[:2] == b'\x1f\x8b':
            raw_data = gzip.decompress(raw_data)

        # Decode
        text_data = raw_data.decode("utf-8-sig")

        # Parse CSV - handle potential BOM and empty lines
        lines = [line for line in text_data.split('\n') if line.strip()]
        if not lines:
            return []

        reader = csv.DictReader(lines)
        return list(reader)


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


def read_json_request(request: Request, timeout: int = 120) -> dict:
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


def build_alberta_filter(
    *,
    status: str = "OPEN",
    category: str = "",
    close_start: str = "",
    close_end: str = "",
    post_start: str = "",
    post_end: str = "",
) -> dict[str, Any]:
    """Build the APC opportunity filter payload."""
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
        "unspsc": [],
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
) -> dict:
    """Search Alberta Purchasing Connection opportunities."""
    limit = clamp_int(limit, default=10, minimum=1, maximum=100)
    offset = clamp_int(offset, default=0, minimum=0, maximum=100)
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
    return read_json_request(request)


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
    close_date = opp.get("closeDateTime") or ""
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
    year, draft_id = parse_alberta_reference(ref) if ref else ("", "")
    public_url = f"{ALBERTA_APC_APP_BASE}/opportunity/{year}/{draft_id}" if ref else ALBERTA_APC_APP_BASE
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
    lines.append(f"- **Closing:** {opp.get('closeDateTime', '')}")
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
    if submission or question_submission:
        lines.append("## Submission")
        if submission:
            lines.append(str(submission)[:1500])
        if question_submission:
            lines.append(f"Questions: {str(question_submission)[:1000]}")
        lines.append("")

    external_link = opp.get("externalOriginLink")
    lines.append("## Links")
    lines.append(f"- [View on Alberta Purchasing Connection]({public_url})")
    if external_link:
        lines.append(f"- [External posting]({external_link})")

    return "\n".join(lines)


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

    title_matches = [kw for kw in keywords if kw.lower() in title]
    if title_matches:
        score += 10 * len(title_matches)
        reasons.append(f"title matches: {', '.join(title_matches[:3])}")

    desc_matches = [kw for kw in keywords if kw.lower() in desc and kw.lower() not in title]
    if desc_matches:
        score += 5 * len(desc_matches)
        reasons.append(f"description matches: {', '.join(desc_matches[:3])}")

    commodity_matches = [kw for kw in keywords if kw.lower() in commodity_titles]
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

    closing_date = parse_date(str(opp.get("closeDateTime") or ""))
    if closing_date:
        now = datetime.now(timezone.utc)
        if closing_date.tzinfo is None:
            closing_date = closing_date.replace(tzinfo=timezone.utc)
        days_until = (closing_date - now).days
        if 0 < days_until <= 14:
            score += 5
            reasons.append(f"closes in {days_until} days")

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
    """Load business profile from disk."""
    profile_path = DATA_DIR / "profile.json"
    if not profile_path.exists():
        return {}
    with profile_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_public_mode() -> bool:
    """True when this deployment serves many anonymous users at once."""
    return os.environ.get("WORKSPACEALBERTA_PUBLIC_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


# Tools that read or write the single file-backed profile. On a shared public
# endpoint every caller would see (and overwrite) the same file, so public
# mode hides them and callers pass a `profile` argument per request instead.
PROFILE_STORAGE_TOOL_NAMES = ("set_business_profile", "get_my_profile")

NO_PROFILE_MESSAGE = (
    "No business profile available. Pass a `profile` argument with this call "
    "(company_name, location, description), or use `set_business_profile` first "
    "on a private deployment."
)


def resolve_profile(args: dict) -> dict:
    """Return the profile to use: an inline `profile` argument wins over the saved file."""
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


def save_profile(profile: dict) -> None:
    """Save business profile to disk."""
    profile_path = DATA_DIR / "profile.json"
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


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
    closing_str = get_field(contract, "tenderClosingDate-appelOffresDateCloture")
    closing_date = parse_date(closing_str)
    if closing_date:
        now = datetime.now(timezone.utc)
        if closing_date.tzinfo is None:
            closing_date = closing_date.replace(tzinfo=timezone.utc)
        days_until = (closing_date - now).days
        if 0 < days_until <= 14:
            score += 5
            reasons.append(f"closes in {days_until} days")

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
    lines.append(f"- **Closing Date:** {get_field(contract, 'tenderClosingDate-appelOffresDateCloture', 'Closing Date')}")
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
            url = f"{ALBERTA_APC_APP_BASE}/opportunity/{year}/{draft_id}"
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
    """Parse a normalized opportunity date for sorting."""
    parsed = parse_date(str(opportunity.get(field) or ""))
    if not parsed:
        return datetime.max.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def opportunity_text(opportunity: dict) -> str:
    """Return searchable text for a normalized opportunity."""
    return " ".join(
        str(opportunity.get(field, ""))
        for field in ("title", "buyer", "category", "region", "description", "solicitation", "reference")
    ).lower()


def federal_contract_matches(contract: dict, keywords: str, province: str, category: str) -> bool:
    """Apply simple unified filters to a CanadaBuys row."""
    normalized = normalize_canadabuys_contract(contract)
    text = opportunity_text(normalized)
    if keywords and keywords.lower() not in text:
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
    output = (
        f"**{index}. {title}**\n"
        f"   Source: {opportunity.get('source')}\n"
        f"   Reference: `{opportunity.get('reference', '')}`\n"
        f"   Buyer: {buyer}\n"
        f"   Category: {opportunity.get('category', '')}\n"
        f"   Closing: {opportunity.get('closing', '')}\n"
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
                data = search_alberta_api(
                    query=keywords,
                    status="OPEN",
                    category=apc_category,
                    limit=limit,
                    sort_field="PostDateTime",
                    sort_direction="desc",
                )
                opportunities.extend(normalize_alberta_opportunity(opp) for opp in data.get("values", []))
            except RuntimeError as exc:
                warnings.append(f"Alberta APC unavailable: {exc}")

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
    close_end = now + timedelta(days=days)
    warnings = []
    opportunities = []

    if include_source(source, "federal"):
        contracts, federal_warnings = load_contracts_for_unified()
        warnings.extend(federal_warnings)
        for contract in contracts:
            if not federal_contract_matches(contract, "", province, category):
                continue
            closing = parse_date(get_field(contract, "tenderClosingDate-appelOffresDateCloture"))
            if not closing:
                continue
            if closing.tzinfo is None:
                closing = closing.replace(tzinfo=timezone.utc)
            if now <= closing <= close_end:
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
                    close_start=now.strftime("%Y-%m-%d"),
                    close_end=close_end.strftime("%Y-%m-%d"),
                )
                opportunities.extend(normalize_alberta_opportunity(opp) for opp in data.get("values", []))
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
        closing = parse_date(get_field(contract, "tenderClosingDate-appelOffresDateCloture"))
        if not closing:
            continue
        if closing.tzinfo is None:
            closing = closing.replace(tzinfo=timezone.utc)
        days_until = (closing - now).days
        if days_until < 0 or days_until > days:
            continue
        score, reasons = score_contract(contract, profile)
        if score > 0:
            scored.append((score, days_until, normalize_canadabuys_contract(contract), reasons))

    keywords = [kw for kw in profile.get("capabilities", []) if len(str(kw)) >= 4]
    found_alberta: dict[str, dict] = {}
    close_start = now.strftime("%Y-%m-%d")
    close_end = (now + timedelta(days=days)).strftime("%Y-%m-%d")
    for keyword in keywords[:8]:
        try:
            data = search_alberta_api(
                query=str(keyword),
                status="OPEN",
                limit=25,
                close_start=close_start,
                close_end=close_end,
            )
        except RuntimeError as exc:
            warnings.append(f"Alberta APC unavailable for `{keyword}`: {exc}")
            continue
        for opp in data.get("values", []):
            ref = opp.get("referenceNumber")
            if ref:
                found_alberta[ref] = opp

    for opp in found_alberta.values():
        score, reasons = score_alberta_opportunity(opp, profile)
        if score > 0:
            closing = parse_date(str(opp.get("closeDateTime") or ""))
            days_until = 9999
            if closing:
                if closing.tzinfo is None:
                    closing = closing.replace(tzinfo=timezone.utc)
                days_until = (closing - now).days
            scored.append((score, days_until, normalize_alberta_opportunity(opp), reasons))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[:limit], warnings

# ============== Tool Dispatch ==============

TOOL_NAMES = (
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
    "check_cohere_status",
    "analyze_contract_with_cohere",
)


async def call_tool_text(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Run a procurement tool and return plain text without any MCP dependency."""
    args = arguments or {}
    handlers = {tool_name: globals()[tool_name] for tool_name in TOOL_NAMES}
    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"

    if is_public_mode() and name in PROFILE_STORAGE_TOOL_NAMES:
        return (
            "This hosted endpoint is shared, so it does not store per-user business profiles. "
            "Pass a `profile` argument directly to `find_matching_opportunities`, "
            "`daily_bid_brief`, `find_opportunities`, or `find_alberta_opportunities` instead."
        )

    try:
        return await handler(args)
    except Exception as exc:
        return f"Error: {exc}"


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
        output += f"   Closing: {get_field(c, 'tenderClosingDate-appelOffresDateCloture')}\n"
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

        closing_str = get_field(contract, "tenderClosingDate-appelOffresDateCloture")
        closing_date = parse_date(closing_str)

        if closing_date:
            if closing_date.tzinfo is None:
                closing_date = closing_date.replace(tzinfo=timezone.utc)

            if closing_date > now:
                days_until = (closing_date - now).days
                if days_until <= days:
                    upcoming.append((days_until, contract))

    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return f"No contracts closing within {days} days."

    output = f"Contracts closing within {days} days:\n\n"
    for days_until, c in upcoming[:20]:
        title = get_field(c, "title-titre-eng")[:50]
        output += f"**{title}**\n"
        output += f"   Closes in: {days_until} days\n"
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

    save_profile(profile)

    output = "# Profile Saved!\n\n"
    output += f"**Company:** {profile['company_name']}\n"
    if profile['location']:
        output += f"**Location:** {profile['location']}\n"
    output += f"\n**Detected Industries:** {', '.join(industries) if industries else 'General'}\n"
    output += f"**Keywords I'll search for:** {', '.join(capabilities[:10])}\n"
    output += "\nUse `find_opportunities` to see matching contracts!"

    return output


async def find_opportunities(args: dict) -> str:
    """Find contracts matching business profile."""
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
        closing_str = get_field(contract, "tenderClosingDate-appelOffresDateCloture")
        closing_date = parse_date(closing_str)

        if closing_date:
            if closing_date.tzinfo is None:
                closing_date = closing_date.replace(tzinfo=timezone.utc)
            days_until = (closing_date - now).days

            if days_until < 0 or days_until > days:
                continue  # Skip expired or too far out

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
        output += f"**Match Score:** {score} | **Closes in:** {days_until} days\n"
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
    if not opportunities:
        output = f"No opportunities closing within {days} days."
        if warnings:
            output += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        return output

    now = datetime.now(timezone.utc)
    output = f"# Opportunities Closing Within {days} Days\n\n"
    for i, opportunity in enumerate(opportunities, 1):
        closing = opportunity_date(opportunity, "closing")
        days_until = ""
        if closing != datetime.max.replace(tzinfo=timezone.utc):
            days_until = f"Closes in {(closing - now).days} days"
        output += render_unified_opportunity_line(opportunity, i, days_until) + "\n"

    if warnings:
        output += "## Warnings\n"
        for warning in warnings:
            output += f"- {warning}\n"

    return output


async def find_matching_opportunities(args: dict) -> str:
    """Rank opportunities from both sources against an inline or saved profile."""
    profile = resolve_profile(args)
    if not profile:
        return NO_PROFILE_MESSAGE

    days = clamp_int(args.get("days"), default=60, minimum=1, maximum=365)
    limit = clamp_int(args.get("limit"), default=15, minimum=1, maximum=30)
    scored, warnings = collect_unified_matches(profile, days, limit)

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
            extra += f" | Closes in {days_until} days"
        output += render_unified_opportunity_line(opportunity, i, extra)
        output += f"   Why it matches: {'; '.join(reasons)}\n\n"

    if warnings:
        output += "## Warnings\n"
        for warning in warnings[:5]:
            output += f"- {warning}\n"

    return output


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
                extra += f" | closes in {days_until} days"
            output += render_unified_opportunity_line(opportunity, i, extra)
            output += f"   Reason: {'; '.join(reasons)}\n\n"
    else:
        output += "No profile-matched opportunities found in this lookahead window.\n\n"

    output += "## Closing Soon\n"
    if deadlines:
        now = datetime.now(timezone.utc)
        for i, opportunity in enumerate(deadlines[:limit], 1):
            closing = opportunity_date(opportunity, "closing")
            extra = ""
            if closing != datetime.max.replace(tzinfo=timezone.utc):
                extra = f"Closes in {(closing - now).days} days"
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


def process_bid_room_artifact(args: dict) -> dict[str, Any]:
    """Process a bid room in E2B and return a JSON-ready artifact envelope."""
    from procurement_core.e2b_bid_room import (
        build_apc_bid_room_payload,
        build_canadabuys_bid_room_payload,
        render_bid_room_markdown,
        run_live_bid_room_process,
    )

    reference = str(args.get("reference") or "").strip()
    if not reference:
        raise ValueError("Please provide a reference number.")

    profile = resolve_profile(args) or {}
    business_context = str(args.get("business_context") or "").strip()
    max_attachments = clamp_int(args.get("max_attachments"), default=5, minimum=0, maximum=5)
    timeout_seconds = clamp_int(args.get("timeout_seconds"), default=900, minimum=60, maximum=86400)
    command_timeout_seconds = clamp_int(args.get("command_timeout_seconds"), default=420, minimum=120, maximum=3600)
    keep_alive = bool(args.get("keep_alive", False))
    warnings: list[str] = []

    if is_alberta_reference(reference):
        try:
            details = get_alberta_api_details(reference)
        except (RuntimeError, ValueError) as exc:
            raise ValueError(f"Alberta opportunity not available: {exc}") from exc
        payload = build_apc_bid_room_payload(
            details,
            profile,
            business_context=business_context,
            max_attachments=max_attachments,
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

    result = run_live_bid_room_process(
        payload,
        timeout_seconds=timeout_seconds,
        command_timeout_seconds=command_timeout_seconds,
        keep_alive=keep_alive,
    )
    if warnings:
        result.artifact.setdefault("warnings", []).extend(warnings)
    return {
        "sandbox_id": result.sandbox_id,
        "sandbox_killed": result.killed,
        "artifact": result.artifact,
        "markdown": render_bid_room_markdown(result),
    }


async def process_bid_room(args: dict) -> str:
    """Process a tender package in E2B and analyze it with Cohere inside the sandbox."""
    try:
        return process_bid_room_artifact(args)["markdown"]
    except (RuntimeError, ValueError) as exc:
        return f"Bid room processing is not available: {exc}"


# ============== Alberta Purchasing Connection Handlers ==============


async def search_alberta_opportunities(args: dict) -> str:
    """Search Alberta Purchasing Connection opportunities."""
    keywords = args.get("keywords", "")
    category = args.get("category", "")
    status = args.get("status", "OPEN")
    limit = clamp_int(args.get("limit"), default=10, minimum=1, maximum=50)

    try:
        data = search_alberta_api(
            query=keywords,
            status=status,
            category=category,
            limit=limit,
            sort_field="PostDateTime",
            sort_direction="desc",
        )
    except RuntimeError as exc:
        return f"Alberta APC search failed: {exc}"

    rows = data.get("values", [])
    if not rows:
        return "No Alberta opportunities found matching criteria."

    output = "# Alberta Opportunities\n\n"
    total = data.get("totalCount")
    if total is not None:
        output += f"Showing {len(rows)} of {total} matching APC records.\n\n"
    else:
        output += f"Found {len(rows)} matching APC records.\n\n"

    for i, opp in enumerate(rows[:limit], 1):
        output += render_alberta_opportunity_line(opp, i) + "\n"

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
    close_start = now.strftime("%Y-%m-%d")
    close_end = (now + timedelta(days=days)).strftime("%Y-%m-%d")

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

    rows = data.get("values", [])
    if not rows:
        return f"No Alberta opportunities closing within {days} days."

    output = f"# Alberta Opportunities Closing Within {days} Days\n\n"
    for i, opp in enumerate(rows[:limit], 1):
        output += render_alberta_opportunity_line(opp, i) + "\n"
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

    keywords = [kw for kw in profile.get("capabilities", []) if len(str(kw)) >= 4]
    if not keywords:
        return "Your profile does not have enough keywords yet. Update it with more detail, then try again."

    days = clamp_int(args.get("days"), default=60, minimum=1, maximum=365)
    limit = clamp_int(args.get("limit"), default=15, minimum=1, maximum=30)
    now = datetime.now(timezone.utc)
    close_start = now.strftime("%Y-%m-%d")
    close_end = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    found: dict[str, dict] = {}
    errors = []
    for keyword in keywords[:8]:
        try:
            data = search_alberta_api(
                query=str(keyword),
                status="OPEN",
                limit=25,
                close_start=close_start,
                close_end=close_end,
            )
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        for opp in data.get("values", []):
            ref = opp.get("referenceNumber")
            if ref:
                found[ref] = opp

    scored = []
    for opp in found.values():
        score, reasons = score_alberta_opportunity(opp, profile)
        if score > 0:
            closing = parse_date(str(opp.get("closeDateTime") or ""))
            days_until = 9999
            if closing:
                if closing.tzinfo is None:
                    closing = closing.replace(tzinfo=timezone.utc)
                days_until = (closing - now).days
            scored.append((score, days_until, opp, reasons))

    scored.sort(key=lambda item: (-item[0], item[1]))

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
            output += f" | **Closes in:** {days_until} days"
        output += "\n"
        output += f"**Why it matches:** {'; '.join(reasons)}\n"
        output += f"**Organization:** {org}\n"
        output += f"**Reference:** `{ref}`\n\n"

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
    """Use Cohere Command A+ to analyze a cached tender notice."""
    reference = args.get("reference", "")
    if not reference:
        return "Please provide a reference number."

    contracts = load_contracts()
    if not contracts:
        return "No contract data available. Run `refresh_data` first."

    contract = find_contract_by_reference(reference, contracts)
    if not contract:
        return f"Contract not found: {reference}"

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
    contract_markdown = render_contract_markdown(contract)
    if len(contract_markdown) > MAX_CONTRACT_PROMPT_CHARS:
        contract_markdown = contract_markdown[:MAX_CONTRACT_PROMPT_CHARS] + "\n\n[Contract text truncated for model call.]"

    messages = [
        {
            "role": "system",
            "content": (
                "You help Canadian businesses review CanadaBuys tender notices. "
                "Be practical, concise, and careful. Do not invent requirements. "
                "If the notice text is missing key details, say what the user should inspect on CanadaBuys."
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
    output += f"**Provider:** {provider}\n"
    output += f"**Model:** `{model}`\n"
    output += f"**Reference:** `{get_field(contract, 'referenceNumber-numeroReference')}`\n\n"
    output += analysis
    output += "\n\n---\nVerify requirements, amendments, and attachments on CanadaBuys before making a bid decision."

    return output
