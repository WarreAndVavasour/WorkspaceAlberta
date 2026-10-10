# /// script
# requires-python = ">=3.10"
# dependencies = ["requests>=2.28"]
# ///
"""Page-level layer: classify each page of a tender package with Jev.

One request per page, built from that page's units (no extra PDF parsing), two questions:
- ``document_part``: Choice over procurement_core.requirements.tags.DOCUMENT_PARTS (instructions, bid forms,
  contract terms, contract schedule, specifications, drawings, reference report, cover).
- ``bid_content``: Noul, does this page tell the bidder what to prepare or submit WITH its bid?

page_gate = part is a bid part (cover, instructions, forms) or bid_content >= 0.5.
The second test keeps pages such as a contract schedule that says "submit a Construction
Execution Plan with your Proposal".

    python jev_pages.py            # writes jev_pages.jsonl next to units.jsonl
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TENDER = Path(os.environ.get("REQ_TENDER_DIR", REPO / "drive-downloads/tenders/AB-2026-06600"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jc = _load("jev_classify")  # also puts the repo root on sys.path

from procurement_core.requirements import jev, tags  # noqa: E402,F401

# Questions, gate and page state are shared with the hosted classify_tender tool.
PROMPT_VERSION = jev.PAGES_PROMPT_VERSION
BID_CONTENT_THRESHOLD = jev.BID_CONTENT_THRESHOLD
MAX_CHARS = jev.PAGE_MAX_CHARS
QUESTIONS = jev.PAGE_QUESTIONS
page_states = jev.page_states


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--units", type=Path, default=TENDER / "units.jsonl")
    ap.add_argument("--out", type=Path, default=TENDER / "jev_pages.jsonl")
    ap.add_argument("--model", default=jc.DEFAULT_MODEL)
    ap.add_argument("--concurrency", type=int, default=16)
    args = ap.parse_args()

    units = jc.read_jsonl(args.units)
    pages = max(u["page"] for u in units)
    states = page_states(units, pages)
    key = jc.read_api_key()
    if not key:
        print("ABORT: no TYPESAFE_API_KEY / JEV_API_KEY", file=sys.stderr)
        return 2
    t0 = time.monotonic()

    def work(p: int) -> dict:
        body, err, _ = jc.call_jev({"model": args.model, "state": states[p], "questions": QUESTIONS}, key, 6, 60.0)
        row = {"page": p, "prompt_version": PROMPT_VERSION, "error": err or None}
        if body:
            row.update(**jev.parse_page(body), input_tokens=(body.get("usage") or {}).get("input_tokens"))
        return row

    with ThreadPoolExecutor(args.concurrency) as pool:
        rows = [f.result() for f in as_completed([pool.submit(work, p) for p in states])]
    rows.sort(key=lambda r: r["page"])
    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    ok = [r for r in rows if not r["error"]]
    tokens = sum(r.get("input_tokens") or 0 for r in ok)
    # contiguous runs of the same part, for a quick read of the package structure
    runs = []
    for r in ok:
        if runs and runs[-1][0] == r["part"] and runs[-1][2] == r["page"] - 1:
            runs[-1][2] = r["page"]
        else:
            runs.append([r["part"], r["page"], r["page"]])
    summary = {
        "pages": len(rows), "errors": len(rows) - len(ok),
        "parts": dict(collections.Counter(r["part"] for r in ok).most_common()),
        "pages_passing_gate": sum(1 for r in ok if r["page_gate"]),
        "runs": [f"{a}-{b} {p}" if a != b else f"{a} {p}" for p, a, b in runs],
        "input_tokens": tokens, "cost_usd": round(tokens / 1e6 * jc.PRICE_PER_MTOK, 4),
        "wall_s": round(time.monotonic() - t0, 1),
    }
    args.out.with_name("jev_pages_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
