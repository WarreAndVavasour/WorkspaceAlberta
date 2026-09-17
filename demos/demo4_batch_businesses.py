#!/usr/bin/env python3
"""Aggressive batch pipeline: simulate N Alberta businesses against the live
workspacealberta MCP endpoint, concurrently, with full request/response traces.

Each simulated business runs the full funnel:
  initialize -> find_matching_opportunities -> geo-filter -> shortlist file

Every MCP round-trip is appended to demos/output/traces/batch-<ts>.jsonl so the
same trace schema can be diffed when this pipeline runs inside the WA harness.

Run:  python3 demos/demo4_batch_businesses.py [--workers 4] [--limit 10]
"""
import argparse
import concurrent.futures
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wa_mcp  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
SHARED = Path("/data/tasks/from-zcode")

BUSINESSES = [
    {"company_name": "Rocky Mountain Carpentry", "location": "Rocky Mountain House, Alberta",
     "description": "Carpentry contractor: framing, finishing, custom woodwork, renovations, design/build residential and small commercial.",
     "capabilities": ["carpentry", "framing", "finishing", "renovation", "design/build"], "industries": ["construction", "lumber"]},
    {"company_name": "Battle River Steel Works", "location": "Camrose, Alberta",
     "description": "Structural steel fabrication and welding: beams, railings, platforms, shop drawings for commercial builds.",
     "capabilities": ["steel", "welding", "fabrication", "structural"], "industries": ["steel", "construction"]},
    {"company_name": "Peace Country Electrical", "location": "Grande Prairie, Alberta",
     "description": "Electrical contractor: commercial fit-outs, industrial maintenance, solar installs, service calls.",
     "capabilities": ["electrical", "solar", "maintenance", "commercial"], "industries": ["electrical", "energy"]},
    {"company_name": "Badlands Excavation", "location": "Drumheller, Alberta",
     "description": "Excavation and earthworks: site prep, septic fields, trenching, aggregate hauling.",
     "capabilities": ["excavation", "earthworks", "septic", "aggregate"], "industries": ["construction"]},
    {"company_name": "Lethbridge Irrigation Supply", "location": "Lethbridge, Alberta",
     "description": "Irrigation systems supply and install for farms and municipalities: pivots, pumps, line work.",
     "capabilities": ["irrigation", "pumps", "agriculture", "installation"], "industries": ["agriculture"]},
    {"company_name": "Fort McMurray Outfitting", "location": "Fort McMurray, Alberta",
     "description": "Industrial camp catering and outfitting: workforce lodging, catering services, remote site support.",
     "capabilities": ["catering", "lodging", "camp", "remote site"], "industries": ["hospitality", "energy"]},
    {"company_name": "Kananaskis Guiding Co", "location": "Canmore, Alberta",
     "description": "Tourism operator: guided hiking, mountain safety services, backcountry logistics for groups.",
     "capabilities": ["tourism", "guiding", "safety", "backcountry"], "industries": ["tourism"]},
    {"company_name": "Veteran Haulage Ltd", "location": "Red Deer, Alberta",
     "description": "Trucking and logistics: flatbed, gravel, heavy equipment transport across central Alberta.",
     "capabilities": ["trucking", "logistics", "flatbed", "heavy equipment"], "industries": ["transport"]},
    {"company_name": "Cold Lake Marine Services", "location": "Cold Lake, Alberta",
     "description": "Marine and dock services: dock installation, barge work, shoreline restoration.",
     "capabilities": ["marine", "dock", "barge", "shoreline"], "industries": ["construction", "tourism"]},
    {"company_name": "Medicine Hat Glazing", "location": "Medicine Hat, Alberta",
     "description": "Glass and glazing contractor: storefront glazing, residential windows, curtain wall.",
     "capabilities": ["glazing", "glass", "windows", "storefront"], "industries": ["construction"]},
    {"company_name": "Athabasca Enviro Consulting", "location": "Athabasca, Alberta",
     "description": "Environmental consulting: phase 1/2 site assessments, spill response, reclamation planning.",
     "capabilities": ["environmental", "assessment", "reclamation", "spill response"], "industries": ["environment"]},
    {"company_name": "High Level Aviation", "location": "High Level, Alberta",
     "description": "Charter and aerial work: forest fire spotting, cargo runs, pipeline patrol.",
     "capabilities": ["aviation", "charter", "aerial", "patrol"], "industries": ["transport", "forestry"]},
]


def run_one(biz: dict, limit: int, trace_path: Path) -> dict:
    t0 = time.time()
    trace = {"business": biz["company_name"], "calls": []}

    def traced(tool, arguments):
        entry = {"tool": tool, "args": arguments, "ts": time.time()}
        try:
            text = wa_mcp.mcp_call(tool, arguments)
            entry["ok"] = True
            entry["chars"] = len(text)
            entry["elapsed_s"] = round(time.time() - entry["ts"], 2)
            trace["calls"].append(entry)
            return text
        except Exception as exc:  # trace the failure, keep going
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["elapsed_s"] = round(time.time() - entry["ts"], 2)
            trace["calls"].append(entry)
            raise

    try:
        ranked = traced("find_matching_opportunities",
                        {"profile": biz, "days": 30, "limit": limit})
        local = wa_mcp.filter_local(ranked)
        today = datetime.date.today().isoformat()
        slug = biz["company_name"].lower().replace(" ", "-")
        doc = (f"# {biz['company_name']} — matched opportunities — {today}\n\n"
               f"_Simulated business, live pipeline. {len(local)} in drive ring._\n\n"
               + ranked)
        (OUT / f"batch-{slug}.md").write_text(doc)
        result = {"business": biz["company_name"], "ok": True,
                  "chars": len(ranked), "ring_hits": len(local),
                  "elapsed_s": round(time.time() - t0, 2)}
    except Exception as exc:
        result = {"business": biz["company_name"], "ok": False,
                  "error": f"{type(exc).__name__}: {exc}",
                  "elapsed_s": round(time.time() - t0, 2)}

    trace["result"] = result
    with open(trace_path, "a") as fh:
        fh.write(json.dumps(trace) + "\n")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%H%M%S")
    trace_path = OUT / "traces" / f"batch-{stamp}.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"batch: {len(BUSINESSES)} simulated businesses, "
          f"{args.workers} workers, traces -> {trace_path}")
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda b: run_one(b, args.limit, trace_path),
                                BUSINESSES))

    ok = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    print(f"\n{'BUSINESS':34} {'OK':>3} {'RING':>4} {'CHARS':>6} {'SECS':>5}")
    for r in results:
        print(f"{r['business'][:34]:34} "
              f"{'✓' if r['ok'] else '✗':>3} "
              f"{str(r.get('ring_hits', '-')):>4} "
              f"{str(r.get('chars', '-')):>6} {r['elapsed_s']:>5}")
    print(f"\n{len(ok)}/{len(results)} succeeded in {time.time()-t0:.1f}s "
          f"({len(failed)} failed)")
    if failed:
        for r in failed:
            print(f"  FAIL {r['business']}: {r['error']}")


if __name__ == "__main__":
    main()
