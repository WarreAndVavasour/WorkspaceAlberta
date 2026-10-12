"""Per-tool-call meter for paid upstream APIs (TypeSafe, Cohere, Hugging Face, E2B).

The hosted adapter opens a :class:`Meter` around each tool call with :func:`metering`.
Upstream clients call :func:`record` after each request they send; the totals end up on
the ``mcp_tool_call`` log line (see :mod:`.telemetry`), so Cloud Logging shows what every
call cost, not only how long it took.

The meter lives in a :class:`contextvars.ContextVar`. ``asyncio.to_thread`` copies the
context, so work started that way records into the caller's meter. A plain
``ThreadPoolExecutor`` does not: submit through :func:`bind` (as the Jev pipeline does) so
worker threads record into the same meter. With no meter open, :func:`record` is a no-op,
which keeps the stdio server, scripts and tests unaffected.

Only counts are kept: request counts, token counts, sandbox seconds. Never prompts,
documents, keys or responses.
"""

from __future__ import annotations

import contextlib
import contextvars
import threading
from typing import Any, Callable, Iterator

# USD per million input tokens; TypeSafe bills input only (docs.typesafe.ai/models).
# Kept in step with requirements.jev.PRICE_PER_MTOK. Other providers are logged as raw
# counts because their price depends on the plan and model in use.
TYPESAFE_USD_PER_MTOK = 0.042

_current: contextvars.ContextVar["Meter | None"] = contextvars.ContextVar("wa_usage_meter", default=None)


class Meter:
    """Thread-safe counters for one tool call."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, dict[str, float]] = {}

    def add(self, provider: str, **counts: float) -> None:
        with self._lock:
            bucket = self._counts.setdefault(provider, {})
            for name, value in counts.items():
                if value:
                    bucket[name] = bucket.get(name, 0) + value

    def snapshot(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {provider: dict(bucket) for provider, bucket in self._counts.items() if bucket}

    def log_fields(self) -> dict[str, Any]:
        """Flat fields for the structured log line; empty when nothing was used."""
        counts = {
            provider: {name: int(v) if float(v).is_integer() else round(v, 1) for name, v in bucket.items()}
            for provider, bucket in self.snapshot().items()
        }
        if not counts:
            return {}
        fields: dict[str, Any] = {"upstream": counts}
        typesafe_tokens = counts.get("typesafe", {}).get("input_tokens", 0)
        if typesafe_tokens:
            fields["typesafe_est_usd"] = round(typesafe_tokens / 1e6 * TYPESAFE_USD_PER_MTOK, 6)
        return fields


def current() -> Meter | None:
    return _current.get()


@contextlib.contextmanager
def metering() -> Iterator[Meter]:
    """Open a fresh meter for the duration of one tool call."""
    meter = Meter()
    token = _current.set(meter)
    try:
        yield meter
    finally:
        _current.reset(token)


def record(provider: str, **counts: float) -> None:
    """Add counts to the open meter, if any. Never raises."""
    meter = _current.get()
    if meter is None:
        return
    try:
        meter.add(provider, **{k: float(v or 0) for k, v in counts.items()})
    except Exception:
        pass


def bind(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap ``fn`` so it runs in a copy of the current context (for executor threads)."""
    ctx = contextvars.copy_context()

    def run(*args: Any, **kwargs: Any) -> Any:
        return ctx.run(fn, *args, **kwargs)

    return run


def openai_style_tokens(body: Any) -> dict[str, int]:
    """``usage.prompt_tokens`` / ``completion_tokens`` from an OpenAI-compatible body."""
    try:
        usage = (body or {}).get("usage") or {}
        return {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        }
    except (AttributeError, TypeError, ValueError):
        return {"input_tokens": 0, "output_tokens": 0}
