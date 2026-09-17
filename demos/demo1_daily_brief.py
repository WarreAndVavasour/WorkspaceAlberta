#!/usr/bin/env python3
"""Demo 1 - Daily Bid Brief pipeline.

workspacealberta MCP (daily_bid_brief) -> markdown brief -> shared /data/tasks
workspace where RaspberryPiBot and every other platform client can read it.

Run:  python3 demos/demo1_daily_brief.py
Output: demos/output/daily-brief-YYYY-MM-DD.md (+ copy in /data/tasks/from-zcode/)
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wa_mcp import mcp_call, mcp_initialize, filter_local  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
SHARED = Path("/data/tasks/from-zcode")


def main() -> None:
    mcp_initialize()
    brief = mcp_call("daily_bid_brief", {"days": 30})

    today = datetime.date.today().isoformat()
    header = (
        f"# WorkspaceAlberta Daily Bid Brief — {today}\n\n"
        f"_Pipeline demo 1: workspacealberta MCP → shared workspace. "
        f"Generated keyless via the public MCP endpoint._\n\n"
    )
    local_hits = filter_local(brief)
    if local_hits:
        header += (
            "## Inside the Rocky Mountain House drive ring\n\n"
            + "\n".join(f"- {line}" for line in local_hits[:15])
            + "\n\n---\n\n"
        )

    (OUT.mkdir(parents=True, exist_ok=True))
    (OUT / f"daily-brief-{today}.md").write_text(header + brief)
    SHARED.mkdir(parents=True, exist_ok=True)
    (SHARED / f"DAILY-BRIEF-{today}.md").write_text(header + brief)

    print(f"brief: {len(brief)} chars")
    print(f"local-ring hits: {len(local_hits)}")
    for line in local_hits[:5]:
        print(f"  {line[:120]}")
    print(f"written: demos/output/daily-brief-{today}.md")
    print(f"shared:  /data/tasks/from-zcode/DAILY-BRIEF-{today}.md")


if __name__ == "__main__":
    main()
