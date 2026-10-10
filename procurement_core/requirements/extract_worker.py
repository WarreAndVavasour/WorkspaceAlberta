"""Child-process PDF splitter for the hosted classify_tender tool.

The service never parses request PDFs in its own process. It runs this file as::

    python -I -B extract_worker.py <max_pages> <cpu_seconds> <memory_bytes>

with the PDF bytes on stdin, a minimal environment (no secrets), a new session (its own
process group, so the parent can kill everything on timeout) and a wall-clock timeout.

Before reading any input this process sets its own resource limits (POSIX):
address space (``memory_bytes``), CPU time (``cpu_seconds``), file size 0 (it writes
no files) and no core dumps. The limits are set here, at the top of the child, rather
than in ``Popen(preexec_fn=...)``, because ``preexec_fn`` is not safe in a parent with
threads (the server runs tool calls in worker threads).

Output: one JSON object on stdout, ``{"units": [...], "stats": {...}}``, exit 0; or
``{"error": "<exception class>"}``, exit 2. Everything else MuPDF or Python prints goes
to stderr, which the parent never shows to users.

This file is run by path in isolated mode (``-I``), so it does not import the
``procurement_core`` package (whose import loads the service and its ``.env``); it loads
``extract.py`` from its own folder by file path.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def _set_limits(cpu_seconds: int, memory_bytes: int) -> None:
    try:
        import resource
    except ImportError:  # not POSIX: rely on the parent's wall-clock timeout
        return
    limits = (
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_AS, memory_bytes),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
    )
    for which, value in limits:
        try:
            resource.setrlimit(which, (value, value))
        except (ValueError, OSError):
            pass  # cannot lower below the current use or above the hard limit; others still apply


def main(argv: list[str]) -> int:
    max_pages, cpu_seconds, memory_bytes = (int(value) for value in argv[1:4])
    # Keep the real stdout for the JSON result; send any other output (MuPDF messages,
    # warnings) to stderr so it can never corrupt the result.
    result = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    sys.dont_write_bytecode = True

    spec = importlib.util.spec_from_file_location("wa_requirements_extract", Path(__file__).with_name("extract.py"))
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)

    _set_limits(cpu_seconds, memory_bytes)
    data = sys.stdin.buffer.read()
    try:
        units, stats = extract.extract_units(data, max_pages=max_pages)
    except Exception as exc:  # corrupt, encrypted, unsupported, out of memory
        result.write(json.dumps({"error": type(exc).__name__}).encode("utf-8"))
        result.close()
        return 2
    result.write(json.dumps({"units": units, "stats": stats}, ensure_ascii=False).encode("utf-8"))
    result.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
