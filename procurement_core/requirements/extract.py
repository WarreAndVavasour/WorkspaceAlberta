"""Split a tender PDF into text units (clauses, list items, paragraphs) with PyMuPDF.

Moved from ``pipelines/requirement_classifier/label_requirements.py`` so the hosted
``classify_tender`` tool and the research scripts share one implementation.

For each page: read text blocks, drop repeated running headers and footers, keep the
section-heading path, and split the text into units (numbered clauses, list items,
paragraphs; long paragraphs into sentence groups of at most ~700 characters).

PyMuPDF is imported inside :func:`extract_units` so importing this module stays cheap.
"""

from __future__ import annotations

import collections
import re
import statistics
from pathlib import Path

NUMBERED = re.compile(r"^\s*(?:(?:Section|Article|Part)\s+)?(\d+(?:\.\d+){0,5})[.)]?\s+\S")
LETTERED = re.compile(r"^\s*(?:\(?[a-z]{1,3}\)|[a-z]\.|[•\-–▪●○])\s+\S", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")
WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return WS.sub(" ", text).strip()


def repeated_lines(pages: list[list[str]], share: float = 0.3) -> set[str]:
    """Header/footer lines: same margin text (digits removed) on many pages."""
    if len(pages) < 4:
        return set()
    counts = collections.Counter()
    for blocks in pages:
        counts.update({re.sub(r"\d+", "#", b) for b in blocks if len(b) < 160})
    limit = max(3, int(len(pages) * share))
    return {text for text, n in counts.items() if n >= limit}


def is_heading(text: str, size: float, body_size: float) -> bool:
    if len(text) > 120 or text.endswith((".", ";", ",")):
        return False
    if size >= body_size + 1.5:
        return True
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return True
    return bool(NUMBERED.match(text)) and len(text.split()) <= 12


def split_long(text: str, limit: int = 700) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for sentence in SENTENCE_SPLIT.split(text):
        if current and len(current) + len(sentence) > limit:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def _open(source: Path | str | bytes | bytearray):
    import pymupdf

    if isinstance(source, (bytes, bytearray)):
        return pymupdf.open(stream=bytes(source), filetype="pdf")
    return pymupdf.open(source)


def extract_units(
    source: Path | str | bytes | bytearray,
    min_chars: int = 25,
    *,
    max_pages: int | None = None,
) -> tuple[list[dict], dict]:
    """Return ``(units, stats)`` for one PDF given as a path or as bytes.

    ``max_pages`` (default: no limit) reads only the first N pages; ``stats`` then also
    reports ``pages_in_file`` and ``empty_pages`` (page numbers with no text). Without it
    the output is exactly what the research pipeline has always produced.

    This parses the PDF in the calling process. The hosted service never calls it on
    request input directly; it runs :mod:`.extract_worker` in a child process instead.
    """
    doc = _open(source)
    try:
        page_count = doc.page_count
        raw_pages: list[list[tuple[str, float, bool]]] = []
        sizes: list[float] = []
        for page_index, page in enumerate(doc):
            if max_pages is not None and page_index >= max_pages:
                break
            blocks = []
            for block in page.get_text("dict")["blocks"]:
                spans = [s for line in block.get("lines", []) for s in line.get("spans", [])]
                text = normalize(" ".join(s["text"] for s in spans))
                if not text:
                    continue
                size = max((s["size"] for s in spans), default=0.0)
                sizes.extend(s["size"] for s in spans if s["text"].strip())
                y0, y1 = block["bbox"][1], block["bbox"][3]
                in_margin = y1 < page.rect.height * 0.06 or y0 > page.rect.height * 0.94
                blocks.append((text, size, in_margin))
            raw_pages.append(blocks)
    finally:
        doc.close()

    body_size = statistics.median(sizes) if sizes else 10.0
    noise = repeated_lines([[t for t, _, margin in blocks if margin] for blocks in raw_pages])
    headings: list[tuple[int, str]] = []  # (depth, text)
    units: list[dict] = []
    empty_pages = 0
    empty_page_numbers: list[int] = []

    for page_no, blocks in enumerate(raw_pages, 1):
        if not blocks:
            empty_pages += 1
            empty_page_numbers.append(page_no)
        for text, size, in_margin in blocks:
            if in_margin and re.sub(r"\d+", "#", text) in noise:
                continue
            if is_heading(text, size, body_size):
                match = NUMBERED.match(text)
                depth = match.group(1).count(".") + 1 if match else 1
                headings = [h for h in headings if h[0] < depth] + [(depth, text)]
                continue
            if len(text) < min_chars:
                continue
            for piece in split_long(text):
                units.append({
                    "page": page_no,
                    "section": " > ".join(h for _, h in headings)[-300:],
                    "kind": "numbered" if NUMBERED.match(piece) else "list_item" if LETTERED.match(piece) else "paragraph",
                    "text": piece,
                })

    for i, unit in enumerate(units):
        unit["unit_index"] = i
        unit["prev_text"] = units[i - 1]["text"][-300:] if i else ""
        unit["next_text"] = units[i + 1]["text"][:300] if i + 1 < len(units) else ""

    stats = {"pages": len(raw_pages), "pages_without_text": empty_pages, "units": len(units)}
    if max_pages is not None:
        stats["pages_in_file"] = page_count
        stats["empty_pages"] = empty_page_numbers
    return units, stats


def looks_scanned(stats: dict) -> bool:
    """More than half the pages have no text layer: the file needs OCR first."""
    return stats["pages_without_text"] > stats["pages"] / 2
