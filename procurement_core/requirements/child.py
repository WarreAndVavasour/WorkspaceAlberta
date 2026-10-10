"""Run the PDF splitter in a separate OS process with CPU, memory and time limits.

Untrusted tender PDFs are parsed by MuPDF (C code). The service process never does that
on request input; :func:`extract_in_child` starts :mod:`.extract_worker` with

- ``sys.executable -I -B``: isolated mode (no ``PYTHON*`` variables, no user site, no
  current directory on ``sys.path``) and no bytecode writes;
- a minimal environment (:func:`child_env`): no API keys or other secrets;
- ``start_new_session=True``: the child leads its own process group, so a timeout kills
  everything it started;
- limits the child sets on itself before reading input: address space
  (``MEMORY_LIMIT_BYTES``), CPU time (matched to the wall-clock timeout), file size 0,
  no core dumps;
- a wall-clock timeout in the parent: ``min(FILE_TIMEOUT_SECONDS, time left)``.

This is process isolation inside the same container, not a sandbox VM: the child shares
the container's filesystem and network namespace.

The child's stderr is never returned to callers; only its length and the exit code are
logged.
"""

from __future__ import annotations

import json
import logging
import math
import os
import signal
import subprocess
import sys
from pathlib import Path

WORKER = Path(__file__).with_name("extract_worker.py")
FILE_TIMEOUT_SECONDS = 60.0
MEMORY_LIMIT_BYTES = 1536 * 1024 * 1024  # 1.5 GB address space per child
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE")

log = logging.getLogger(__name__)


class WorkerTimeout(Exception):
    """The child did not finish in time and was killed."""


class WorkerFailed(Exception):
    """The child exited with an error or returned output that is not a result."""


def child_env() -> dict[str, str]:
    """PATH and locale only. ``-I`` ignores PYTHONPATH and friends anyway."""
    return {name: os.environ[name] for name in ENV_ALLOWLIST if os.environ.get(name)}


def worker_command(max_pages: int, timeout: float) -> list[str]:
    cpu_seconds = max(1, math.ceil(timeout))
    return [sys.executable, "-I", "-B", str(WORKER), str(int(max_pages)), str(cpu_seconds), str(MEMORY_LIMIT_BYTES)]


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.communicate(timeout=5)
    except Exception:
        proc.kill()


def extract_in_child(
    data: bytes,
    *,
    max_pages: int,
    timeout: float,
    command: list[str] | None = None,
) -> tuple[list[dict], dict]:
    """Return ``(units, stats)`` from :mod:`.extract_worker`, or raise.

    Raises :class:`WorkerTimeout` (child killed) or :class:`WorkerFailed` (non-zero exit,
    oversized or malformed output). ``command`` replaces the worker command (tests).
    """
    timeout = max(0.1, float(timeout))
    proc = subprocess.Popen(
        command or worker_command(max_pages, timeout),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=child_env(), cwd=os.path.abspath(os.sep), close_fds=True, start_new_session=True,
    )
    try:
        out, err = proc.communicate(input=bytes(data), timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        log.warning("pdf worker killed after %.1f s timeout", timeout)
        raise WorkerTimeout() from None
    except BaseException:
        _kill_group(proc)
        raise
    if proc.returncode != 0:
        log.warning("pdf worker exit %s, stderr %d bytes", proc.returncode, len(err or b""))
        raise WorkerFailed(f"exit {proc.returncode}")
    if len(out) > MAX_OUTPUT_BYTES:
        log.warning("pdf worker output too large: %d bytes", len(out))
        raise WorkerFailed("output too large")
    try:
        payload = json.loads(out)
        units, stats = payload["units"], payload["stats"]
        if not isinstance(units, list) or not isinstance(stats, dict):
            raise TypeError("wrong shape")
        for key in ("pages", "pages_without_text", "pages_in_file", "empty_pages"):
            stats[key]  # noqa: B018  (presence check)
        for unit in units:
            if not isinstance(unit, dict) or not isinstance(unit.get("text"), str) or not isinstance(unit.get("page"), int):
                raise TypeError("wrong unit shape")
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("pdf worker output unusable (%s), %d bytes", type(exc).__name__, len(out))
        raise WorkerFailed("bad output") from None
    return units, stats
