#!/usr/bin/env python3
"""Run all 12 simulated businesses through the WA harness headless, in parallel.

Each business gets its own `dsh --profile headless` boot from /data/tasks (so
the file sandbox includes the shared workspace), calls the workspacealberta MCP
find_matching_opportunities tool, and writes /data/tasks/from-grok/HARNESS-<slug>.md.

Run:  python3 demos/harness_batch.py [--workers 4] [--timeout 420]
"""
import argparse
import concurrent.futures
import subprocess
import time
from pathlib import Path

DSH = str(Path.home() / ".local/bin/dsh")
PATCH = str(Path.home() / ".dsh/profiles/headless/wa-mcp.patch.yml")
CWD = "/data/tasks"
LOGDIR = Path(__file__).resolve().parent / "output" / "harness-batch"

BUSINESSES = [
    ("rocky-mountain-carpentry", "Rocky Mountain Carpentry", "Rocky Mountain House, Alberta",
     "Carpentry contractor: framing, finishing, custom woodwork, renovations, design/build residential and small commercial.",
     ["carpentry", "framing", "finishing", "renovation", "design/build"], ["construction", "lumber"]),
    ("battle-river-steel-works", "Battle River Steel Works", "Camrose, Alberta",
     "Structural steel fabrication and welding: beams, railings, platforms, shop drawings for commercial builds.",
     ["steel", "welding", "fabrication", "structural"], ["steel", "construction"]),
    ("peace-country-electrical", "Peace Country Electrical", "Grande Prairie, Alberta",
     "Electrical contractor: commercial fit-outs, industrial maintenance, solar installs, service calls.",
     ["electrical", "solar", "maintenance", "commercial"], ["electrical", "energy"]),
    ("badlands-excavation", "Badlands Excavation", "Drumheller, Alberta",
     "Excavation and earthworks: site prep, septic fields, trenching, aggregate hauling.",
     ["excavation", "earthworks", "septic", "aggregate"], ["construction"]),
    ("lethbridge-irrigation-supply", "Lethbridge Irrigation Supply", "Lethbridge, Alberta",
     "Irrigation systems supply and install for farms and municipalities: pivots, pumps, line work.",
     ["irrigation", "pumps", "agriculture", "installation"], ["agriculture"]),
    ("fort-mcmurray-outfitting", "Fort McMurray Outfitting", "Fort McMurray, Alberta",
     "Industrial camp catering and outfitting: workforce lodging, catering services, remote site support.",
     ["catering", "lodging", "camp", "remote site"], ["hospitality", "energy"]),
    ("kananaskis-guiding-co", "Kananaskis Guiding Co", "Canmore, Alberta",
     "Tourism operator: guided hiking, mountain safety services, backcountry logistics for groups.",
     ["tourism", "guiding", "safety", "backcountry"], ["tourism"]),
    ("veteran-haulage-ltd", "Veteran Haulage Ltd", "Red Deer, Alberta",
     "Trucking and logistics: flatbed, gravel, heavy equipment transport across central Alberta.",
     ["trucking", "logistics", "flatbed", "heavy equipment"], ["transport"]),
    ("cold-lake-marine-services", "Cold Lake Marine Services", "Cold Lake, Alberta",
     "Marine and dock services: dock installation, barge work, shoreline restoration.",
     ["marine", "dock", "barge", "shoreline"], ["construction", "tourism"]),
    ("medicine-hat-glazing", "Medicine Hat Glazing", "Medicine Hat, Alberta",
     "Glass and glazing contractor: storefront glazing, residential windows, curtain wall.",
     ["glazing", "glass", "windows", "storefront"], ["construction"]),
    ("athabasca-enviro-consulting", "Athabasca Enviro Consulting", "Athabasca, Alberta",
     "Environmental consulting: phase 1/2 site assessments, spill response, reclamation planning.",
     ["environmental", "assessment", "reclamation", "spill response"], ["environment"]),
    ("high-level-aviation", "High Level Aviation", "High Level, Alberta",
     "Charter and aerial work: forest fire spotting, cargo runs, pipeline patrol.",
     ["aviation", "charter", "aerial", "patrol"], ["transport", "forestry"]),
]


def task_text(slug, name, location, desc, caps, inds):
    caps_s = ", ".join(f"'{c}'" for c in caps)
    inds_s = ", ".join(f"'{i}'" for i in inds)
    return (
        f"Use the workspace_alberta MCP tool find_matching_opportunities with "
        f"days=30 and limit=5 for this business profile: company_name '{name}', "
        f"location '{location}', description '{desc}', "
        f"capabilities [{caps_s}], industries [{inds_s}]. "
        f"Write the full ranked result to /data/tasks/from-grok/HARNESS-{slug}.md "
        f"and state the top match score."
    )


def run_one(biz, timeout):
    slug, name = biz[0], biz[1]
    log = LOGDIR / f"{slug}.log"
    t0 = time.time()
    try:
        proc = subprocess.run(
            [DSH, "--profile", "headless", "--patch", PATCH, task_text(*biz)],
            cwd=CWD, capture_output=True, text=True, timeout=timeout,
        )
        elapsed = round(time.time() - t0, 1)
        log.write_text(proc.stdout[-4000:] + "\n--- stderr ---\n" + proc.stderr[-2000:])
        written = (Path(CWD) / "from-grok" / f"HARNESS-{slug}.md").exists()
        return {"slug": slug, "ok": proc.returncode == 0 and written,
                "rc": proc.returncode, "written": written, "secs": elapsed}
    except subprocess.TimeoutExpired:
        return {"slug": slug, "ok": False, "rc": "timeout",
                "written": False, "secs": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=420)
    args = ap.parse_args()
    LOGDIR.mkdir(parents=True, exist_ok=True)

    print(f"launching {len(BUSINESSES)} harness runs, {args.workers} at a time, "
          f"timeout {args.timeout}s each")
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, b, args.timeout): b[0] for b in BUSINESSES}
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            print(f"  [{r['slug']}] {'OK' if r['ok'] else 'FAIL'} "
                  f"rc={r['rc']} written={r['written']} {r['secs']}s", flush=True)

    print(f"\ndone in {time.time()-t0:.0f}s — logs in {LOGDIR}")
    files = sorted(Path(CWD, "from-grok").glob("HARNESS-*.md"))
    print(f"HARNESS-*.md files in shared workspace: {len(files)}")


if __name__ == "__main__":
    main()
