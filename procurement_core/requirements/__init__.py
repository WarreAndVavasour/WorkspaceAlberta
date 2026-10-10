"""Bidder-requirement classification for tender PDFs (the ``classify_tender`` tool).

Modules:

- ``tags``     — tag library: response types, sub-tags, routing per tag, document parts;
- ``extract``  — PDF text blocks -> units (PyMuPDF; in-process, for the research scripts);
- ``child`` / ``extract_worker`` — the hosted path: ``extract`` run in a separate OS process
  with CPU, memory, file-size and wall-clock limits and no secrets in its environment;
- ``jev``      — TypeSafe Jev questions and a stdlib HTTP client with retries;
- ``pipeline`` — :func:`classify_documents` (split -> L0 -> pages -> L1 -> merge) and markdown.

The research scripts in ``pipelines/requirement_classifier/`` import ``tags``, ``extract`` and
the question definitions in ``jev`` from here, so the hosted tool and the evaluation runs
use one copy.
"""

from procurement_core.requirements.pipeline import (
    ClassificationError,
    NoTextError,
    classify_documents,
    render_markdown,
)

__all__ = ["ClassificationError", "NoTextError", "classify_documents", "render_markdown"]
