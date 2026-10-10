"""Tender PDFs -> bidder requirements: split, L0, page layer, L1, merge.

:func:`classify_documents` is the runtime entry point behind the ``classify_tender`` tool.
Every step after the split is a Jev classification (see :mod:`.jev`); there is no LLM and
no free-text extraction. Routing per requirement (answer source, lead time, connector,
question) comes from the tag library, not from the model.

Bounds:

- PDFs only (callers expand ZIPs first). Each PDF is split in a separate OS process
  (:mod:`.child`) with CPU, memory and wall-clock limits, two files at a time; a file that
  fails, times out or has no text layer is skipped with a warning;
- at most ``max_pages`` pages and ``max_units`` units in total, with a warning when a cap
  cuts the package short;
- a wall-clock ``deadline``: L0 and the page layer run together and stop early enough to
  leave time for L1; whatever is not classified when time runs out is reported, and the
  result is labelled ``partial`` instead of being thrown away;
- bounded concurrency (``ThreadPoolExecutor``, default 16 workers).

The API key is only handed to :func:`.jev.call_jev`; it never appears in the result.
"""

from __future__ import annotations

import collections
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any

from procurement_core.requirements import child, jev, tags
from procurement_core.requirements.extract import looks_scanned  # pure function; no PDF parsing here

MAX_PAGES = 800
MAX_UNITS = 8000
DEFAULT_CONCURRENCY = 16
EVIDENCE_CHARS = 240
MAX_EVIDENCE = 5
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 4
MERGE_RESERVE_SECONDS = 2.0
MIN_L1_SECONDS = 10.0  # L0 + pages stop at least this long before the deadline, for L1
LEAD_ORDER = {"minutes": 0, "days": 1, "weeks": 2}
PDF_SIGNATURE = b"%PDF-"
PARALLEL_FILES = 2  # PDFs parsed at the same time (each in its own child process)

class ClassificationError(RuntimeError):
    """The classifier gave no usable answer (for example every call failed)."""


class NoTextError(ValueError):
    """The documents have no classifiable text (not PDFs, unreadable, or scanned)."""


def _run_calls(
    jobs: list[tuple[Any, dict]],
    api_key: str,
    *,
    concurrency: int,
    cutoff: float,
    stop: threading.Event,
) -> tuple[dict[Any, tuple[dict | None, str]], int]:
    """Send each job's payload to Jev with bounded concurrency until ``cutoff``.

    Returns ``(results by key, number of jobs not run)``. A job counts as not run when it
    was never started, was still in flight at the cutoff, or gave up before sending a
    request. Jobs not started by the cutoff are cancelled; every request and retry wait
    is itself bounded by the cutoff, so in-flight calls end shortly after it.
    """
    results: dict[Any, tuple[dict | None, str]] = {}
    if not jobs:
        return results, 0

    def work(payload: dict) -> tuple[dict | None, str, int]:
        return jev.call_jev(payload, api_key, MAX_RETRIES, REQUEST_TIMEOUT, deadline=cutoff, stop=stop)

    pool = ThreadPoolExecutor(max_workers=max(1, concurrency), thread_name_prefix="jev")
    try:
        futures = {pool.submit(work, payload): key for key, payload in jobs}
        pending = set(futures)
        while pending and not stop.is_set():
            remaining = cutoff - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            for future in done:
                key = futures[future]
                try:
                    body, error, attempts = future.result()
                except jev.AuthError:
                    stop.set()
                    raise
                except Exception as exc:  # unexpected: count it as a failed call, keep going
                    body, error, attempts = None, type(exc).__name__, 1
                if attempts == 0:
                    continue  # never sent: time limit or stop
                results[key] = (body, error)
        return results, len(jobs) - len(results)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _extract(name: str, data: bytes, max_pages: int, deadline: float) -> tuple[str, Any]:
    """Split one PDF in a child process. Returns ``("ok", (units, stats))`` or ``(status, None)``."""
    remaining = deadline - time.monotonic()
    if remaining < 1:
        return "time", None
    try:
        return "ok", child.extract_in_child(data, max_pages=max_pages,
                                            timeout=min(child.FILE_TIMEOUT_SECONDS, remaining))
    except child.WorkerTimeout:
        return "slow", None
    except (child.WorkerFailed, OSError):
        return "failed", None


def _cap_pages(units: list[dict], stats: dict, allowed: int) -> tuple[list[dict], dict]:
    """Keep only pages 1..allowed of a file that was split with a larger page cap."""
    kept = [u for u in units if u["page"] <= allowed]
    if kept:
        kept[-1]["next_text"] = ""  # as if the file ended there
    empty = [p for p in stats["empty_pages"] if p <= allowed]
    return kept, {**stats, "pages": allowed, "pages_without_text": len(empty), "empty_pages": empty,
                  "units": len(kept)}


def _split(files: list[tuple[str, bytes]], max_pages: int, max_units: int, warnings: list[str],
           deadline: float) -> tuple[list[dict], list[dict], collections.Counter]:
    """Split every PDF (in child processes, two at a time) within the page and unit caps.

    ``counts["truncated"]`` is set when a cap or the deadline cut the package short.
    """
    units: list[dict] = []
    documents: list[dict] = []
    counts: collections.Counter = collections.Counter()

    pdfs: list[tuple[int, str, bytes]] = []
    for doc_index, (name, data) in enumerate(files):
        if bytes(data[:5]) == PDF_SIGNATURE:
            pdfs.append((doc_index, name, data))
        else:
            warnings.append(f"{name}: skipped, not a PDF file (only PDFs are classified).")
            counts["files_skipped"] += 1

    with ThreadPoolExecutor(max_workers=PARALLEL_FILES, thread_name_prefix="pdf") as pool:
        futures = [pool.submit(_extract, name, data, max_pages, deadline) for _i, name, data in pdfs]
        outcomes = [future.result() for future in futures]  # each bounded by its own timeout

    pages_left = max_pages
    for (doc_index, name, _data), (status, value) in zip(pdfs, outcomes):
        if status == "time":
            warnings.append(f"Time limit reached while reading documents; {name} was not read.")
            counts["files_skipped"] += 1
            counts["truncated"] = 1
            continue
        if status == "slow":
            warnings.append(f"{name}: skipped, the PDF took too long to read.")
            counts["files_skipped"] += 1
            continue
        if status == "failed":
            warnings.append(f"{name}: skipped, the PDF could not be read.")
            counts["files_skipped"] += 1
            continue
        if pages_left <= 0:
            warnings.append(f"{name}: skipped, the {max_pages}-page limit was already reached.")
            counts["files_skipped"] += 1
            counts["truncated"] = 1
            continue
        doc_units, stats = value
        if stats["pages"] > pages_left:
            doc_units, stats = _cap_pages(doc_units, stats, pages_left)
        if stats["pages_in_file"] > stats["pages"]:
            warnings.append(
                f"{name}: only the first {stats['pages']} of {stats['pages_in_file']} pages were read "
                f"(limit {max_pages} pages per request)."
            )
            counts["truncated"] = 1
        if stats["pages"] and looks_scanned(stats):
            warnings.append(
                f"{name}: {stats['pages_without_text']} of {stats['pages']} pages have no text layer "
                "(scanned PDF?); those pages need OCR and were not classified."
            )
        pages_left -= stats["pages"]
        counts["pages"] += stats["pages"]
        counts["pages_without_text"] += stats["pages_without_text"]
        documents.append({"document": name, "pages": stats["pages"],
                          "pages_in_file": stats["pages_in_file"], "units": len(doc_units)})
        for unit in doc_units:
            unit["doc_name"] = name
            unit["doc_index"] = doc_index
            unit["doc_unit_index"] = unit.pop("unit_index")
        units.extend(doc_units)
        counts["files_read"] += 1
    if len(units) > max_units:
        warnings.append(
            f"The package has {len(units)} text units; only the first {max_units} were classified "
            "(limit per request). Requirements in later pages may be missing."
        )
        units = units[:max_units]
        counts["truncated"] = 1
    for i, unit in enumerate(units):
        unit["unit_index"] = i
    return units, documents, counts


def merge(rows: list[dict], units: dict[int, dict]) -> list[dict]:
    """One requirement per canonical tag across the package, ordered for a work plan."""
    by_tag: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r.get("tag"):
            by_tag[r["tag"]].append(r)
    reqs = []
    for tag, rs in by_tag.items():
        rs.sort(key=lambda r: r["unit_index"])
        best = max(rs, key=lambda r: (r["mandatory"], r.get("sub_prob") or 0))
        locations = sorted({(units[r["unit_index"]]["doc_index"], units[r["unit_index"]]["doc_name"], r["page"]) for r in rs})
        reqs.append({
            "tag": tag,
            **tags.routing(tag),
            "mandatory": any(r["mandatory"] for r in rs),
            "pages": [{"document": name, "page": page} for _i, name, page in locations],
            "evidence": [
                {"document": units[r["unit_index"]]["doc_name"], "page": r["page"],
                 "text": units[r["unit_index"]]["text"][:EVIDENCE_CHARS], "mandatory": r["mandatory"]}
                for r in sorted(rs, key=lambda r: (not r["mandatory"], -(r.get("sub_prob") or 0), r["unit_index"]))[:MAX_EVIDENCE]
            ],
            "evidence_units": len(rs),
            "headline": units[best["unit_index"]]["text"][:200],
            "_first": (locations[0][0], locations[0][2]),
        })
    reqs.sort(key=lambda q: (not q["mandatory"], -LEAD_ORDER.get(q["lead_time"], 1), q["_first"]))
    for i, q in enumerate(reqs, 1):
        q.pop("_first")
        q["id"] = f"R{i:02d}"
    return [{"id": q.pop("id"), **q} for q in reqs]


def classify_documents(
    files: list[tuple[str, bytes]],
    *,
    deadline: float,
    api_key: str,
    model: str = jev.DEFAULT_MODEL,
    concurrency: int = DEFAULT_CONCURRENCY,
    max_pages: int = MAX_PAGES,
    max_units: int = MAX_UNITS,
    stop: threading.Event | None = None,
) -> dict[str, Any]:
    """Classify tender PDFs into bidder requirements.

    ``files`` are ``(name, bytes)`` pairs; non-PDF bytes are skipped with a warning.
    ``deadline`` is a ``time.monotonic()`` value; ``stop`` an optional cancel event.
    Raises :class:`NoTextError` when the files hold no text to classify (nothing is sent),
    :class:`jev.AuthError` if the key is refused, and :class:`ClassificationError` when the
    classifier gave no usable answer at all.
    """
    started = time.monotonic()
    stop = stop or threading.Event()
    end = deadline - MERGE_RESERVE_SECONDS
    warnings: list[str] = []

    units, documents, counts = _split(files, max_pages, max_units, warnings, end)
    if not units:
        raise NoTextError(
            "No classifiable text was found in the PDF documents"
            + (": " + " ".join(warnings[:5]) if warnings else ".")
        )
    by_index = {u["unit_index"]: u for u in units}

    # L0 (per unit) and the page layer run together: they are independent of each other.
    units_by_page: dict[tuple[int, int], list[dict]] = collections.defaultdict(list)
    for u in units:
        units_by_page[(u["doc_index"], u["page"])].append(u)
    page_keys = sorted(units_by_page)
    jobs: list[tuple[Any, dict]] = [
        (("page", key), {"model": model, "state": jev.page_state(units_by_page[key], key[1]),
                         "questions": jev.PAGE_QUESTIONS})
        for key in page_keys
    ]
    jobs += [(("unit", u["unit_index"]), {"model": model, "state": jev.build_state(u), "questions": jev.QUESTIONS})
             for u in units]
    # Leave L1 a quarter of the remaining time (at least MIN_L1_SECONDS): it is ~5% of the calls.
    phase_a_cutoff = end - max(MIN_L1_SECONDS, 0.25 * max(0.0, end - time.monotonic()))
    results, _ = _run_calls(jobs, api_key, concurrency=concurrency, cutoff=phase_a_cutoff, stop=stop)

    tokens = 0
    errors: list[str] = []
    l0: dict[int, dict] = {}
    page_rows: dict[tuple[int, int], dict] = {}
    answered = collections.Counter()
    models: collections.Counter = collections.Counter()
    for (kind, key), (body, error) in results.items():
        answered[kind] += 1
        tokens += jev.input_tokens(body)
        if body is None:
            errors.append(error)
            continue
        try:
            row = jev.parse_page(body) if kind == "page" else jev.parse_l0(body)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            errors.append(f"unexpected response shape ({type(exc).__name__})")
            continue
        models[body.get("model") or model] += 1
        if kind == "page":
            page_rows[key] = row
        else:
            l0[key] = row
    units_not_run = len(units) - answered["unit"]
    pages_not_run = len(page_keys) - answered["page"]

    if not l0:
        raise ClassificationError(
            "The classifier returned no usable answers"
            + (f" ({errors[0][:200]})" if errors else " before the time limit") + "."
        )

    unit_gated = [i for i, r in sorted(l0.items()) if r.get("requires_response")]
    page_unknown = 0
    page_gated: list[int] = []
    for i in unit_gated:
        u = by_index[i]
        page = page_rows.get((u["doc_index"], u["page"]))
        if page is None:
            page_unknown += 1
            page_gated.append(i)  # fail open: keep the clause when its page was not classified
        elif page["page_gate"]:
            page_gated.append(i)

    # L1: sub-tag per gated unit, with the reject option last.
    l1_jobs = [(("l1", i), {"model": model, "state": jev.build_state(by_index[i]),
                            "questions": jev.l1_questions(l0[i]["label"])}) for i in page_gated]
    l1_results, l1_not_run = _run_calls(l1_jobs, api_key, concurrency=concurrency, cutoff=end, stop=stop)
    l1_rows: list[dict] = []
    rejected = 0
    for (_kind, i), (body, error) in sorted(l1_results.items()):
        tokens += jev.input_tokens(body)
        if body is None:
            errors.append(error)
            continue
        try:
            parsed = jev.parse_l1(body, l0[i]["label"])
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            errors.append(f"unexpected response shape ({type(exc).__name__})")
            continue
        models[body.get("model") or model] += 1
        if parsed["tag"] is None:
            rejected += 1
            continue
        l1_rows.append({"unit_index": i, "page": by_index[i]["page"], "mandatory": bool(l0[i].get("mandatory")),
                        **parsed})

    requirements = merge(l1_rows, by_index)

    partial = bool(counts["truncated"])
    if units_not_run or pages_not_run:
        partial = True
        warnings.append(
            f"Time limit reached: {units_not_run} of {len(units)} text units and {pages_not_run} of "
            f"{len(page_keys)} pages were not classified. Requirements in those parts may be missing."
        )
    if l1_not_run:
        partial = True
        warnings.append(
            f"Time limit reached: {l1_not_run} of {len(page_gated)} candidate clauses were not sub-tagged "
            "and are not in the list."
        )
    if stop.is_set() and not (units_not_run or pages_not_run or l1_not_run):
        partial = True
        warnings.append("The request was cancelled before classification finished.")
    if page_unknown:
        warnings.append(f"{page_unknown} candidate clauses are on pages that were not classified; they were kept.")
    if errors:
        partial = True
        samples = "; ".join(dict.fromkeys(e[:160] for e in errors))
        warnings.append(f"{len(errors)} classifier calls failed and were skipped (for example: {samples[:400]}).")

    return {
        "kind": "tender_requirements",
        "status": "partial" if partial else "complete",
        "requirements": requirements,
        "documents": documents,
        "counts": {
            "files": len(files),
            "files_read": counts["files_read"],
            "files_skipped": counts["files_skipped"],
            "pages": counts["pages"],
            "pages_without_text": counts["pages_without_text"],
            "units": len(units),
            "units_classified": len(l0),
            "units_gated": len(unit_gated),
            "pages_classified": len(page_rows),
            "pages_gated": sum(1 for r in page_rows.values() if r["page_gate"]),
            "units_after_page_gate": len(page_gated),
            "units_tagged": len(l1_rows),
            "rejected_by_l1": rejected,
            "requirements": len(requirements),
            "mandatory_requirements": sum(1 for q in requirements if q["mandatory"]),
            "other_tags": sum(1 for q in requirements if ".other_" in q["tag"]),
            "classifier_calls": len(results) + len(l1_results),
            "failed_calls": len(errors),
        },
        "cost": {
            "input_tokens": tokens,
            "usd": round(tokens / 1e6 * jev.PRICE_PER_MTOK, 4),
            "price_per_million_input_tokens_usd": jev.PRICE_PER_MTOK,
            "basis": "input tokens reported by the classifier",
        },
        "model": models.most_common(1)[0][0] if models else model,
        "prompt_versions": {"l0": jev.L0_PROMPT_VERSION, "pages": jev.PAGES_PROMPT_VERSION, "l1": jev.L1_PROMPT_VERSION},
        "limits": {"max_pages": max_pages, "max_units": max_units, "concurrency": concurrency},
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "warnings": warnings,
    }


# --------------------------------------------------------------------------- markdown

def _locations(req: dict) -> str:
    by_doc: dict[str, list[int]] = collections.defaultdict(list)
    for loc in req["pages"]:
        by_doc[loc["document"]].append(loc["page"])
    parts = []
    for name, pages in by_doc.items():
        shown = ", ".join(str(p) for p in pages[:8]) + (" …" if len(pages) > 8 else "")
        parts.append(f"{name} p. {shown}" if len(by_doc) > 1 else f"p. {shown}")
    return "; ".join(parts)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render_markdown(result: dict, *, reference: str = "", source: str = "") -> str:
    """Requirements table (mandatory first), counts, cost and warnings."""
    counts = result["counts"]
    title = f"# Bidder requirements for {reference}" if reference else "# Bidder requirements"
    lines = [title, ""]
    if result["status"] != "complete":
        lines += ["**Partial result.** Some of the package was not classified; see Warnings below. "
                  "Do not treat this as a complete requirement list.", ""]
    docs = ", ".join(d["document"] for d in result["documents"]) or "none"
    lines += [
        f"Source documents{f' ({source})' if source else ''}: {docs}.",
        f"{counts['pages']} pages, {counts['units']} text units → {counts['units_gated']} candidate clauses → "
        f"{counts['units_after_page_gate']} after the page check → **{counts['requirements']} requirements** "
        f"({counts['mandatory_requirements']} mandatory).",
        "",
    ]
    for heading, mandatory in (("Mandatory", True), ("Other requirements", False)):
        rows = [q for q in result["requirements"] if q["mandatory"] is mandatory]
        if not rows:
            continue
        lines += [f"## {heading}", "", "| ID | Requirement | Collect with | Lead time | Pages | Evidence |",
                  "|---|---|---|---|---|---|"]
        for q in rows:
            evidence = q["evidence"][0]["text"] if q["evidence"] else ""
            lines.append(
                f"| {q['id']} | {_cell(q['question'])} (`{q['tag']}`) | {q['connector']} | {q['lead_time']} | "
                f"{_cell(_locations(q))} | {_cell(evidence[:160])} |"
            )
        lines.append("")
    if not result["requirements"]:
        lines += ["No bidder requirements were found by the classifier.", ""]
    cost = result["cost"]
    lines += [
        f"Classifier: TypeSafe Jev `{result['model']}`; {counts['classifier_calls']} calls, "
        f"{cost['input_tokens']:,} input tokens reported, about ${cost['usd']:.4f}; {result['elapsed_seconds']} s.",
        "",
    ]
    if result["warnings"]:
        lines += ["## Warnings", ""] + [f"- {_cell(w)}" for w in result["warnings"]] + [""]
    lines += [
        "---",
        "These are classifier outputs, not a reading of the tender. Verify every requirement, "
        "mandatory flag and date against the official posting and all amendments before bidding.",
    ]
    return "\n".join(lines)
