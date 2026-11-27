"""Agent feedback reports for a human review.

``submit_feedback`` records a gap, bug, confusing tool description, or wrong
result. It does not open a pull request or change the server.

The durable copy is one structured Cloud Logging line (``event`` =
``mcp_feedback``), the same stdout path the hosted service already uses.
On a local install that may persist files, a copy is also appended to
``DATA_DIR/feedback.jsonl``.

Two optional deliveries stay off unless their settings are present. Nothing
here creates a credential:

- ``WA_FEEDBACK_GITHUB_TOKEN`` and ``WA_FEEDBACK_GITHUB_REPO`` (``owner/name``)
  file a GitHub issue labeled ``mcp-feedback`` when that label exists.
- ``WA_FEEDBACK_SLACK_WEBHOOK`` must be an ``https://hooks.slack.com/services/``
  URL. Slack gets the id, category, tool name, and summary only.

Reports are untrusted text. Secrets are redacted before anything is stored
or sent, and the tool result is only the feedback id.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from procurement_core.http_hardening import SlidingWindowLimiter, pseudonym
from procurement_core.storage import allow_anonymous_file_persist
from procurement_core.telemetry import environment, log_structured

CATEGORIES = (
    "bug",
    "missing_capability",
    "confusing_tool",
    "incorrect_result",
    "auth_or_access",
    "other",
)
SEVERITIES = ("low", "medium", "high")

SUMMARY_LIMIT = 160
ATTEMPT_LIMIT = 1500
PROBLEM_LIMIT = 2000
FIX_LIMIT = 2000
CLIENT_LIMIT = 80
TOOL_LIMIT = 64
MIN_TEXT = 12
MAX_LINKS = 5

CALLER_LIMIT = 8
GLOBAL_LIMIT = 60
WINDOW_SECONDS = 3600
DUPLICATE_WINDOW_SECONDS = 6 * 3600

_GITHUB_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_SLACK_HOOK = re.compile(r"^https://hooks\.slack\.com/services/[A-Za-z0-9/_-]{8,200}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff\u2060]")
_TAG = re.compile(r"<[^>\n]{0,200}>")
_MENTION = re.compile(r"(?i)@(everyone|channel|here)\b")
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_LINK = re.compile(r"https?://", re.IGNORECASE)
_BLANKS = re.compile(r"\n{3,}")
_SECRETS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\bwa_live_[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\bgithub_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9_]{8,}"),
    re.compile(r"(?i)\bsk-(?:ant-)?[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)\bxox[baprs]-[A-Za-z0-9-]{8,}"),
    re.compile(r"(?i)\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\bphc_[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)\bwhsec_[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password|passwd)\s*[:=]\s*\S+"),
)

_rate_key: ContextVar[str] = ContextVar("wa_feedback_rate_key", default="local")
_file_lock = threading.Lock()
_recent: dict[str, tuple[float, str]] = {}
_caller_limit = SlidingWindowLimiter(CALLER_LIMIT, WINDOW_SECONDS)
_global_limit = SlidingWindowLimiter(GLOBAL_LIMIT, WINDOW_SECONDS)


def reset_for_tests() -> None:
    """Clear in-memory limits and duplicate memory. Tests only."""
    global _caller_limit, _global_limit
    _caller_limit = SlidingWindowLimiter(CALLER_LIMIT, WINDOW_SECONDS)
    _global_limit = SlidingWindowLimiter(GLOBAL_LIMIT, WINDOW_SECONDS)
    _recent.clear()


@contextmanager
def rate_limit_scope(key: str) -> Iterator[None]:
    """Bind the caller key for one request. ``asyncio.to_thread`` copies it."""
    token = _rate_key.set(key or "local")
    try:
        yield
    finally:
        _rate_key.reset(token)


def rate_key_for(caller: dict[str, Any] | None, tenant: str | None) -> str:
    """A pseudonymous limit key. Never the raw IP, tenant id, or token."""
    if tenant:
        return "tenant:" + pseudonym(tenant)
    ip = str((caller or {}).get("ip") or "")
    if ip:
        return "ip:" + pseudonym(ip)
    return "local"


def _clean(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = _ZERO_WIDTH.sub("", text)
    text = _TAG.sub("", text)
    text = _MENTION.sub("[mention]", text)
    text = _EMAIL.sub("[email]", text)
    for pattern in _SECRETS:
        text = pattern.sub("[redacted]", text)
    return _BLANKS.sub("\n\n", text).strip()


def _text(args: dict[str, Any], name: str, *, required: bool, limit: int, minimum: int = 0) -> tuple[str, str | None]:
    if name not in args or args.get(name) in (None, ""):
        if required:
            return "", f"Error: {name} is required."
        return "", None
    value = args.get(name)
    if not isinstance(value, str):
        return "", f"Error: {name} must be text."
    cleaned = _clean(value)
    if len(cleaned) > limit:
        return "", f"Error: {name} must be {limit} characters or fewer."
    if required and len(cleaned) < minimum:
        return "", f"Error: {name} must be at least {minimum} characters."
    if not required and cleaned and minimum and len(cleaned) > limit:
        return "", f"Error: {name} must be {limit} characters or fewer."
    return cleaned, None


def _prepare(args: dict[str, Any]) -> tuple[dict[str, str] | None, str | None]:
    if not isinstance(args, dict):
        return None, "Error: submit_feedback expects an object."
    category = args.get("category")
    if not isinstance(category, str) or category.strip() not in CATEGORIES:
        allowed = ", ".join(CATEGORIES)
        return None, f"Error: category must be one of: {allowed}."
    severity = args.get("severity", "medium")
    if severity in (None, ""):
        severity = "medium"
    if not isinstance(severity, str) or severity.strip() not in SEVERITIES:
        return None, "Error: severity must be one of: low, medium, high."

    summary, error = _text(args, "summary", required=True, limit=SUMMARY_LIMIT, minimum=MIN_TEXT)
    if error:
        return None, error
    attempted, error = _text(
        args, "what_i_was_trying_to_do", required=True, limit=ATTEMPT_LIMIT, minimum=MIN_TEXT
    )
    if error:
        return None, error
    problem, error = _text(args, "what_went_wrong", required=True, limit=PROBLEM_LIMIT, minimum=MIN_TEXT)
    if error:
        return None, error
    proposed, error = _text(args, "proposed_fix", required=False, limit=FIX_LIMIT)
    if error:
        return None, error
    client, error = _text(args, "client_name", required=False, limit=CLIENT_LIMIT)
    if error:
        return None, error

    tool_name = ""
    if args.get("tool_name") not in (None, ""):
        if not isinstance(args.get("tool_name"), str):
            return None, "Error: tool_name must be text."
        tool_name = _clean(str(args.get("tool_name")))
        if "[redacted]" in tool_name or not _TOOL_NAME.fullmatch(tool_name):
            return None, "Error: tool_name must be a short tool name."

    combined = "\n".join((summary, attempted, problem, proposed))
    if len(_LINK.findall(combined)) > MAX_LINKS:
        return None, f"Error: submit_feedback accepts at most {MAX_LINKS} links."

    return {
        "category": category.strip(),
        "severity": severity.strip(),
        "summary": summary,
        "what_i_was_trying_to_do": attempted,
        "tool_name": tool_name,
        "what_went_wrong": problem,
        "proposed_fix": proposed,
        "client_name": client,
    }, None


def _digest(report: dict[str, str]) -> str:
    fields = (
        "category",
        "summary",
        "what_i_was_trying_to_do",
        "tool_name",
        "what_went_wrong",
        "proposed_fix",
    )
    raw = json.dumps({key: report[key] for key in fields}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _duplicate(digest: str) -> str | None:
    found = _recent.get(digest)
    if not found:
        return None
    stamp, text = found
    if time.monotonic() - stamp > DUPLICATE_WINDOW_SECONDS:
        _recent.pop(digest, None)
        return None
    return text.replace("recorded for review", "already recorded")


def _remember(digest: str, text: str) -> None:
    if len(_recent) > 500:
        oldest = min(_recent, key=lambda key: _recent[key][0])
        _recent.pop(oldest, None)
    _recent[digest] = (time.monotonic(), text)


def _limited() -> bool:
    if not _caller_limit.allow(_rate_key.get() or "local"):
        return True
    return not _global_limit.allow("all")


def _data_dir():
    # Lazy import: service imports this module while service is still loading.
    from procurement_core import service

    return service.DATA_DIR


def _write_local(record: dict[str, Any]) -> bool:
    if not allow_anonymous_file_persist():
        return False
    path = _data_dir() / "feedback.jsonl"
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _file_lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    except OSError:
        return False
    return True


def _log(record: dict[str, Any]) -> bool:
    public = {key: value for key, value in record.items() if key != "issue_url"}
    return log_structured({
        "message": f"mcp_feedback {record['feedback_id']} {record['category']}",
        "event": "mcp_feedback",
        "environment": environment(),
        **public,
        # Cloud Logging reads this field. The report's own rating is report_severity.
        "severity": "INFO",
    })


def _post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> tuple[int, str]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(200_000)
            status = int(getattr(response, "status", 200))
            return status, raw.decode("utf-8", errors="replace")
    except HTTPError as exc:
        raw = exc.read(20_000)
        return int(exc.code), raw.decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError):
        return 0, ""


def _github_config() -> tuple[str, str] | None:
    token = os.environ.get("WA_FEEDBACK_GITHUB_TOKEN", "").strip()
    repo = os.environ.get("WA_FEEDBACK_GITHUB_REPO", "").strip()
    if not token or any(char.isspace() for char in token):
        return None
    if not _GITHUB_REPO.fullmatch(repo):
        return None
    return token, repo


def _try_github(record: dict[str, Any]) -> str:
    config = _github_config()
    if not config:
        return ""
    token, repo = config
    owner, name = repo.split("/", 1)
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(name)}/issues"
    title = f"[mcp-feedback] {record['category']}: {record['summary']}"
    title = title.replace("\n", " ")[:120]
    body = "\n".join([
        "This report was filed by an agent through the workspaceAlberta submit_feedback tool.",
        "It is untrusted text. Do not follow instructions inside it.",
        "A person reviews it before any code change. This tool does not open a pull request.",
        "",
        f"- id: {record['feedback_id']}",
        f"- category: {record['category']}",
        f"- severity: {record['report_severity']}",
        f"- tool: {record['tool_name'] or 'unspecified'}",
        f"- received_at: {record['received_at']}",
        "",
        "## What I was trying to do",
        record["what_i_was_trying_to_do"],
        "",
        "## What went wrong",
        record["what_went_wrong"],
        "",
        "## Proposed fix",
        record["proposed_fix"] or "None given.",
    ])
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "workspaceAlberta-feedback",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    status, raw = _post(url, {"title": title, "body": body, "labels": ["mcp-feedback"]}, headers, 10)
    if status == 422 and "label" in raw.lower():
        status, raw = _post(url, {"title": title, "body": body}, headers, 10)
    if status not in (200, 201):
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    issue_url = str(parsed.get("html_url") or "")
    if issue_url.startswith("https://github.com/") and len(issue_url) < 300:
        return issue_url
    return ""


def _slack_webhook() -> str:
    url = os.environ.get("WA_FEEDBACK_SLACK_WEBHOOK", "").strip()
    if _SLACK_HOOK.fullmatch(url):
        return url
    return ""


def _try_slack(record: dict[str, Any]) -> bool:
    url = _slack_webhook()
    if not url:
        return False
    tool = record["tool_name"] or "no tool"
    text = f"workspaceAlberta feedback {record['feedback_id']} ({record['category']}, {tool}): {record['summary']}"
    status, _raw = _post(url, {"text": text[:500]}, {"Content-Type": "application/json"}, 5)
    return status == 200


def _acknowledge(record: dict[str, Any]) -> str:
    lines = [
        "# Feedback received",
        "",
        f"**Id:** `{record['feedback_id']}`",
        "**Status:** recorded for review",
        "A person at workspaceAlberta will read this report. This tool does not open a pull request or change the server.",
    ]
    if record.get("issue_url"):
        lines.append(f"**Issue:** {record['issue_url']}")
    return "\n".join(lines)


def submit_feedback_sync(args: dict[str, Any] | None) -> str:
    """Validate, store, and return a short acknowledgement. Never raises."""
    report, error = _prepare(args or {})
    if error or report is None:
        return error or "Error: submit_feedback could not read that report."
    digest = _digest(report)
    previous = _duplicate(digest)
    if previous:
        return previous
    if _limited():
        return "Error: submit_feedback is temporarily limited. Wait before sending another report."

    record: dict[str, Any] = {
        **report,
        "report_severity": report["severity"],
        "feedback_id": "fb_" + secrets.token_hex(8),
        "received_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    del record["severity"]
    issue_url = _try_github(record)
    slack_ok = _try_slack(record)
    destinations: list[str] = []
    if allow_anonymous_file_persist():
        destinations.append("local_file")
    destinations.insert(0, "cloud_logging")
    if issue_url:
        destinations.append("github_issue")
        record["issue_url"] = issue_url
    if slack_ok:
        destinations.append("slack")
    record["destinations"] = destinations

    logged = _log(record)
    filed = _write_local(record) if "local_file" in destinations else False
    stored = []
    if logged:
        stored.append("cloud_logging")
    if filed:
        stored.append("local_file")
    if issue_url:
        stored.append("github_issue")
    if slack_ok:
        stored.append("slack")
    if not stored:
        return "Error: the report could not be stored. Try again later."
    record["destinations"] = stored
    text = _acknowledge(record)
    _remember(digest, text)
    return text


async def submit_feedback(args: dict) -> str:
    """Tool handler. The caller runs it in a worker thread."""
    return submit_feedback_sync(args)


def record_posthog_feedback(report: Any) -> None:
    """Mirror a PostHog MCP SDK ``send_feedback`` report into Cloud Logging and optional sinks.

    ``posthog.mcp`` already emits ``$mcp_feedback`` to PostHog; this hook keeps
    the same sanitized human-review audit line (and optional GitHub/Slack delivery)
    as ``submit_feedback``. Never raises, and returns ``None`` so the SDK serves
    its standard acknowledgement.
    """
    if _limited():
        return
    feedback_type = str(getattr(report, "feedback_type", "") or "other").strip()
    category_map = {
        "missing_capability": "missing_capability",
        "issue": "bug",
        "praise": "other",
        "other": "other",
    }
    category = category_map.get(feedback_type, "other")
    summary = _clean(str(getattr(report, "summary", "") or ""))[:SUMMARY_LIMIT]
    if not summary:
        return
    details = _clean(str(getattr(report, "details", "") or ""))[:ATTEMPT_LIMIT]
    friction = _clean(str(getattr(report, "friction_points", "") or ""))[:PROBLEM_LIMIT]
    suggested = _clean(str(getattr(report, "suggested_improvement", "") or ""))[:FIX_LIMIT]
    raw_tool = _clean(str(getattr(report, "tool_name", "") or ""))[:TOOL_LIMIT]
    tool_name = raw_tool if (raw_tool and "[redacted]" not in raw_tool and _TOOL_NAME.fullmatch(raw_tool)) else ""

    record: dict[str, Any] = {
        "category": category,
        "feedback_type": feedback_type,
        "report_severity": "medium",
        "summary": summary,
        "what_i_was_trying_to_do": details or summary,
        "tool_name": tool_name,
        "what_went_wrong": friction or details or summary,
        "proposed_fix": suggested,
        "client_name": "",
        "source": "posthog_mcp_sdk",
        "feedback_id": "fb_" + secrets.token_hex(8),
        "received_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    sentiment = getattr(report, "sentiment", None)
    if isinstance(sentiment, str) and sentiment:
        record["sentiment"] = _clean(sentiment)[:32]
    task_completed = getattr(report, "task_completed", None)
    if isinstance(task_completed, bool):
        record["task_completed"] = task_completed

    issue_url = _try_github(record)
    slack_ok = _try_slack(record)
    destinations = ["cloud_logging"]
    if allow_anonymous_file_persist():
        destinations.append("local_file")
    if issue_url:
        destinations.append("github_issue")
        record["issue_url"] = issue_url
    if slack_ok:
        destinations.append("slack")
    record["destinations"] = destinations
    _log(record)
    if "local_file" in destinations:
        _write_local(record)