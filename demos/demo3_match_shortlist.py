#!/usr/bin/env python3
"""Demo 3 - Profile-matched shortlist pipeline.

Asks the workspacealberta MCP to rank live opportunities against the
carpenter's business profile, then geo-filters to the Rocky Mountain House
drive ring and writes a shortlist a human can act on.

Run:  python3 demos/demo3_match_shortlist.py
Output: demos/output/shortlist-YYYY-MM-DD.md (+ copy in /data/tasks/from-zcode/)
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wa_mcp import mcp_call, mcp_initialize, filter_local  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
SHARED = Path("/data/tasks/from-zcode")

PROFILE = {
    "company_name": "Rocky Mountain Carpentry",
    "location": "Rocky Mountain House, Alberta",
    "description": (
        "Carpentry contractor serving Clearwater County and Nordegg: framing, "
        "finishing, custom woodwork, renovations, design/build small commercial "
        "and residential projects."
    ),
    "capabilities": ["carpentry", "framing", "finishing", "renovation",
                     "custom woodwork", "design/build", "residential",
                     "construction"],
    "industries": ["construction", "lumber"],
}


def main() -> None:
    mcp_initialize()
    ranked = mcp_call("find_matching_opportunities",
                      {"profile": PROFILE, "days": 45, "limit": 20})

    today = datetime.date.today().isoformat()
    local = filter_local(ranked)
    doc = (
        f"# Carpenter Shortlist — Rocky Mountain House ring — {today}\n\n"
        f"_Pipeline demo 3: profile-matched ranking (workspacealberta MCP) "
        f"→ geo-filter to the one-hour drive ring._\n\n"
        f"## Matched in the drive ring: {len(local)}\n\n"
        + ("\n".join(f"- {line}" for line in local) if local
           else "_None closing within 45 days right now — the ring is quiet; "
                "widen with the full ranked list below._")
        + "\n\n## Full ranked list (all Alberta/Canada)\n\n" + ranked
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"shortlist-{today}.md").write_text(doc)
    SHARED.mkdir(parents=True, exist_ok=True)
    (SHARED / f"SHORTLIST-{today}.md").write_text(doc)

    print(f"ranked opportunities: {ranked.count('Match Score')} | "
          f"in drive ring: {len(local)}")
    for line in local[:8]:
        print(f"  {line[:130]}")
    print(f"written: demos/output/shortlist-{today}.md + shared copy")


if __name__ == "__main__":
    main()
