# /// script
# requires-python = ">=3.10"
# dependencies = ["requests>=2.28"]
# ///
"""Page-level layer: classify each page of a tender package with Jev.

One request per page, built from that page's units (no extra PDF parsing), two questions:
- ``document_part``: Choice over requirement_tags.DOCUMENT_PARTS (instructions, bid forms,
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
PROMPT_VERSION = "jev-pages-v1"
BID_CONTENT_THRESHOLD = 0.5
MAX_CHARS = 6000


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jc = _load("jev_classify")
tags = _load("requirement_tags")

QUESTIONS = {
    "document_part": {
        "type": "choice",
        "instructions": "`page_text` is one page of a public-sector tender package. Which part of the package is this page?",
        "criteria": dict(tags.DOCUMENT_PARTS),
    },
    "bid_content": {
        "type": "noul",
        "instructions": (
            "Does this page tell the bidder what it must prepare, fill in, sign or submit WITH ITS BID, "
            "before bids close? Pages about what the contractor must do or submit after award count as no."
        ),
        "criteria": {
            "true": "The page sets out content, forms or documents the bidder submits with its bid.",
            "false": "The page is about the process, the contract, the work, or anything due after award.",
        },
    },
}


def page_states(units: list[dict], pages: int) -> dict[int, dict]:
    by_page = collections.defaultdict(list)
    for u in sorted(units, key=lambda u: u["unit_index"]):
        by_page[u["page"]].append(u)
    out = {}
    for p in range(1, pages + 1):
        us = by_page.get(p, [])
        heads = list(dict.fromkeys(u["section"].split(" > ")[-1] for u in us if u.get("section")))[:8]
        text = "\n".join(u["text"] for u in us)[:MAX_CHARS]
        out[p] = {"document": us[0]["doc_name"] if us else "", "page": p, "headings": heads,
                  "page_text": text or "(no text extracted on this page)"}
    return out


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
            a = body["answers"]
            probs = {k: float(v) for k, v in a["document_part"]["probabilities"].items()}
            part = a["document_part"]["choice"]
            bc = float(a["bid_content"]["noul"])
            row.update(part=part, part_prob=probs.get(part), part_probabilities=probs, bid_content_prob=bc,
                       page_gate=part in tags.BID_PARTS or bc >= BID_CONTENT_THRESHOLD,
                       input_tokens=(body.get("usage") or {}).get("input_tokens"))
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
