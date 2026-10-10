# /// script
# requires-python = ">=3.10"
# dependencies = ["requests>=2.28"]
# ///
"""L1 tagging with Jev, then merge into one requirement per tag.

Input units must pass two gates:
- L0 unit gate (jev_classify.py): response type is not "none" and in_bid >= 0.5
  (attendance and submission rules exempt);
- page gate (jev_pages.py): the page is a bid part, or it says what to submit with the bid.

L1 asks one Jev question per unit: ``sub_tag``, a Choice over the sub-tags of its L0 response
type (procurement_core.requirements.tags.SUB_TAGS) plus "not_a_bid_requirement". The canonical tag is
"<response_type>.<sub_tag>".

Merge: one requirement per canonical tag across the whole document. Routing (answer source,
lead time, connector, question) comes from tags.routing(), not from the model.

    python jev_l1.py                 # writes jev_l1.jsonl and requirements.json in the tender folder
    python jev_l1.py --no-page-gate  # skip the page gate
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

from procurement_core.requirements import jev, tags  # noqa: E402

# The L1 question is shared with the hosted classify_tender tool.
PROMPT_VERSION = jev.L1_PROMPT_VERSION
LEAD_ORDER = {"minutes": 0, "days": 1, "weeks": 2}
questions_for = jev.l1_questions


def merge(rows: list[dict], units: dict[int, dict]) -> list[dict]:
    by_tag: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r.get("tag"):
            by_tag[r["tag"]].append(r)
    reqs = []
    for tag, rs in by_tag.items():
        rs.sort(key=lambda r: r["unit_index"])
        best = max(rs, key=lambda r: (r["mandatory"], r.get("sub_prob") or 0))
        reqs.append({
            "tag": tag,
            **tags.routing(tag),
            "mandatory": any(r["mandatory"] for r in rs),
            "pages": sorted({r["page"] for r in rs}),
            "unit_indices": [r["unit_index"] for r in rs],
            "evidence": [{"page": r["page"], "unit_index": r["unit_index"], "text": units[r["unit_index"]]["text"][:240],
                          "sub_prob": r.get("sub_prob"), "mandatory": r["mandatory"]} for r in rs],
            "headline": units[best["unit_index"]]["text"][:200],
        })
    # Order for a work plan: mandatory first, then longest lead time, then first page.
    reqs.sort(key=lambda q: (not q["mandatory"], -LEAD_ORDER[q["lead_time"]], q["pages"][0]))
    for i, q in enumerate(reqs, 1):
        q["requirement_id"] = f"R{i:02d}"
    return reqs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--units", type=Path, default=TENDER / "units.jsonl")
    ap.add_argument("--l0", type=Path, default=TENDER / "jev_labels_v2.jsonl")
    ap.add_argument("--pages", type=Path, default=TENDER / "jev_pages.jsonl")
    ap.add_argument("--out", type=Path, default=TENDER / "jev_l1.jsonl")
    ap.add_argument("--model", default=jc.DEFAULT_MODEL)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--no-page-gate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    units = {u["unit_index"]: u for u in jc.read_jsonl(args.units)}
    l0 = [r for r in jc.read_jsonl(args.l0) if r.get("requires_response")]
    print(f"L0 gated units: {len(l0)}")
    if not args.no_page_gate:
        gate = {r["page"]: r.get("page_gate") for r in jc.read_jsonl(args.pages)}
        l0 = [r for r in l0 if gate.get(r["page"])]
        print(f"after page gate: {len(l0)}")
    payloads = {r["unit_index"]: {"model": args.model, "state": jc.build_state(units[r["unit_index"]]),
                                  "questions": questions_for(r["label"])} for r in l0}
    if args.dry_run:
        print(json.dumps(next(iter(payloads.values())), indent=2, ensure_ascii=False)[:2500])
        return 0
    key = jc.read_api_key()
    if not key:
        print("ABORT: no TYPESAFE_API_KEY / JEV_API_KEY", file=sys.stderr)
        return 2
    by_idx = {r["unit_index"]: r for r in l0}
    t0 = time.monotonic()

    def work(idx: int) -> dict:
        body, err, _ = jc.call_jev(payloads[idx], key, 6, 60.0)
        base = by_idx[idx]
        row = {"unit_index": idx, "page": base["page"], "l0_label": base["label"],
               "mandatory": bool(base.get("mandatory")), "in_bid_prob": base.get("in_bid_prob"),
               "prompt_version": PROMPT_VERSION, "error": err or None}
        if body:
            row.update(**jev.parse_l1(body, base["label"]),
                       input_tokens=(body.get("usage") or {}).get("input_tokens"))
        return row

    with ThreadPoolExecutor(args.concurrency) as pool:
        rows = [f.result() for f in as_completed([pool.submit(work, i) for i in payloads])]
    rows.sort(key=lambda r: r["unit_index"])
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    ok = [r for r in rows if not r["error"]]
    reqs = merge(ok, units)
    (args.out.with_name("requirements.json")).write_text(json.dumps(reqs, indent=2, ensure_ascii=False), encoding="utf-8")
    tokens = sum(r.get("input_tokens") or 0 for r in ok)
    summary = {
        "units_sent": len(rows), "errors": len(rows) - len(ok),
        "rejected_by_l1": sum(1 for r in ok if r.get("sub_tag") == tags.NOT_A_REQUIREMENT[0]),
        "requirements": len(reqs), "mandatory_requirements": sum(1 for q in reqs if q["mandatory"]),
        "other_share": round(sum(1 for q in reqs if ".other_" in q["tag"]) / max(1, len(reqs)), 3),
        "connectors": dict(collections.Counter(q["connector"] for q in reqs).most_common()),
        "lead_time": dict(collections.Counter(q["lead_time"] for q in reqs).most_common()),
        "input_tokens": tokens, "cost_usd": round(tokens / 1e6 * jc.PRICE_PER_MTOK, 4),
        "wall_s": round(time.monotonic() - t0, 1),
    }
    args.out.with_name("jev_l1_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
