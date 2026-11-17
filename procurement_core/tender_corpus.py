"""Every document in a tender package, as page-marked text a reasoning model can read.

Used by ``analyze_contract_with_cohere``. The same files ``classify_tender`` reads are
gathered here (CanadaBuys public attachments, or the user's own APC uploads), split in
the same isolated child processes, and assembled into one text with document and page
markers so the model can cite "RFP p.54".

Nothing here assumes a tender format. The assembly only decides *order* and *budget*:

1. the notice (always);
2. amendments, addenda and Q&A (they override the original text);
3. the remaining documents in the package's main language, largest first;
4. documents in the other official language (usually translations), last.

Whatever does not fit the model's input budget is listed in the inventory as not read,
with the page range, so the analysis can say what it did not see. Documents that could
not be read at all (not a PDF, scanned, failed, behind a login) are listed too: the
inventory is the whole package, not just what was read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

AMENDMENT_PATTERN = re.compile(
    r"addend|amend|modif|q\s*&\s*a|questions?\s+(and|&)\s+answers?|questions?\s+et\s+r[ée]ponses?|"
    r"clarification|bulletin|erratum",
    re.IGNORECASE,
)
REFERENCE_PATTERN = re.compile(
    r"\b(Annex(?:e)?|Appendix|Appendice|Schedule|Attachment|Exhibit|Form|Formulaire|Pi[èe]ce\s+jointe)"
    r"\s+([A-Z0-9][A-Za-z0-9\-\.]{0,6}(?:\s*[-–:]\s*[A-Z][\w’'\-]+(?:\s+[A-Z][\w’'\-]+){0,5})?)"
)
EN_WORDS = (" the ", " and ", " of ", " to ", " must ", " shall ", " will ", " with ")
FR_WORDS = (" le ", " la ", " les ", " des ", " et ", " du ", " doit ", " pour ", " une ")
NOTICE_CHAR_CAP = 12_000


@dataclass
class TenderDocument:
    name: str
    pages: list[str] = field(default_factory=list)  # page text, index 0 = page 1
    language: str = "unknown"
    role: str = "document"  # "amendment" or "document"
    status: str = "read"  # read | partial | not_read | skipped
    pages_read: int = 0
    note: str = ""

    @property
    def chars(self) -> int:
        return sum(len(p) for p in self.pages)


def detect_language(text: str) -> str:
    """'en', 'fr' or 'unknown', from common function words. Good enough to pair translations."""
    sample = f" {text[:20000].lower()} "
    en = sum(sample.count(w) for w in EN_WORDS)
    fr = sum(sample.count(w) for w in FR_WORDS)
    if en + fr < 20:
        return "unknown"
    return "fr" if fr > en * 1.2 else "en" if en > fr * 1.2 else "unknown"


def document_role(name: str, first_page: str) -> str:
    head = f"{name}\n{first_page[:1500]}"
    return "amendment" if AMENDMENT_PATTERN.search(head) else "document"


def referenced_documents(docs: list[TenderDocument], limit: int = 40) -> list[str]:
    """Annexes, appendices, schedules, forms and attachments the tender text names."""
    seen: dict[str, None] = {}
    for doc in docs:
        for page in doc.pages:
            for match in REFERENCE_PATTERN.finditer(page):
                label = re.sub(r"\s+", " ", f"{match.group(1)} {match.group(2)}").strip(" .:-–")
                seen.setdefault(label, None)
                if len(seen) >= limit:
                    return list(seen)
    return list(seen)


def pages_from_units(units: list[dict], documents: list[dict]) -> list[TenderDocument]:
    """Group split units back into page text per document (units come from requirements.pipeline)."""
    docs: list[TenderDocument] = []
    by_doc: dict[int, TenderDocument] = {}
    for meta in documents:
        doc = TenderDocument(name=meta["document"], pages=[""] * int(meta.get("pages") or 0))
        if int(meta.get("pages_in_file") or 0) > int(meta.get("pages") or 0):
            doc.note = f"file has {meta['pages_in_file']} pages; only the first {meta['pages']} were split"
        by_doc[meta["doc"]] = doc
        docs.append(doc)
    for unit in units:
        doc = by_doc.get(unit.get("doc"))
        if doc is None:
            continue
        index = int(unit.get("page") or 1) - 1
        while index >= len(doc.pages):
            doc.pages.append("")
        text = str(unit.get("text") or "").strip()
        if text:
            doc.pages[index] = f"{doc.pages[index]}\n{text}" if doc.pages[index] else text
    for doc in docs:
        joined = "\n".join(doc.pages)
        doc.language = detect_language(joined)
        doc.role = document_role(doc.name, doc.pages[0] if doc.pages else "")
    return docs


def reading_order(docs: list[TenderDocument]) -> list[TenderDocument]:
    """Amendments first, then the main language largest first, then the other language."""
    totals: dict[str, int] = {}
    for doc in docs:
        totals[doc.language] = totals.get(doc.language, 0) + doc.chars
    known = {k: v for k, v in totals.items() if k != "unknown"}
    primary = max(known, key=known.get) if known else "unknown"

    def key(doc: TenderDocument) -> tuple:
        other_language = doc.language not in (primary, "unknown")
        return (other_language, doc.role != "amendment", -doc.chars)

    return sorted(docs, key=key)


def assemble(
    notice_markdown: str,
    docs: list[TenderDocument],
    *,
    char_budget: int,
    skipped: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build the model text and the full inventory within ``char_budget`` characters."""
    notice = notice_markdown.strip()
    if len(notice) > NOTICE_CHAR_CAP:
        notice = notice[:NOTICE_CHAR_CAP] + "\n[Notice text cut at the notice cap.]"
    parts = [f"=== NOTICE (the published tender notice) ===\n{notice}"]
    used = len(parts[0])
    ordered = reading_order(docs)
    for number, doc in enumerate(ordered, 1):
        header = f"\n\n=== DOCUMENT {number}: {doc.name} ({len(doc.pages)} pages, language: {doc.language}, role: {doc.role}) ==="
        if used + len(header) + 200 > char_budget:
            doc.status, doc.pages_read = "not_read", 0
            continue
        body: list[str] = [header]
        used += len(header)
        read = 0
        for page_number, text in enumerate(doc.pages, 1):
            block = f"\n--- {doc.name} p.{page_number} ---\n{text if text.strip() else '[no text on this page: image or scan]'}"
            if used + len(block) > char_budget:
                break
            body.append(block)
            used += len(block)
            read += 1
        doc.pages_read = read
        doc.status = "read" if read == len(doc.pages) else ("partial" if read else "not_read")
        if read:
            parts.append("".join(body))
        else:
            used -= len(header)

    inventory = [
        {"document": d.name, "pages": len(d.pages), "pages_read": d.pages_read, "language": d.language,
         "role": d.role, "status": d.status, "note": d.note}
        for d in ordered
    ]
    for name, reason in skipped or []:
        inventory.append({"document": name, "pages": None, "pages_read": 0, "language": "unknown",
                          "role": "document", "status": "skipped", "note": reason})
    return {
        "text": "".join(parts),
        "chars": used,
        "inventory": inventory,
        "referenced": referenced_documents(docs),
        "complete": all(item["status"] == "read" for item in inventory),
    }


def inventory_markdown(inventory: list[dict]) -> str:
    rows = ["| Document | Pages | Read | Language | Role | Status |", "|---|---|---|---|---|---|"]
    for item in inventory:
        pages = item["pages"] if item["pages"] is not None else "?"
        status = item["status"] + (f" ({item['note']})" if item.get("note") else "")
        rows.append(f"| {item['document']} | {pages} | {item['pages_read']} | {item['language']} | {item['role']} | {status} |")
    return "\n".join(rows)
