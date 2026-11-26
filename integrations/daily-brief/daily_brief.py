#!/usr/bin/env python3
"""Zero-dependency daily Canadian & Alberta government tender brief runner.

Uses only the Python standard library — no n8n, no Zapier, no pip installs,
and no API key required. Calls workspaceAlberta's public ``POST /brief``
endpoint and prints Markdown (or posts to a Slack/Teams/Discord webhook).

Examples:
    python daily_brief.py --company "Red Deer Steel" --location "Red Deer, Alberta" \
        --description "CWB structural steel fabrication and mobile welding" --days 30

    WEBHOOK_URL="https://hooks.slack.com/services/..." python daily_brief.py \
        --description "Commercial electrical contracting and switchgear" --location "Calgary, Alberta"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ENDPOINT = "https://elbowsupknivesout.warreandvavasour.com/brief"


def fetch_brief(
    *,
    company_name: str,
    location: str,
    description: str,
    days: int = 30,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: int = 60,
) -> str:
    payload = {
        "profile": {
            "company_name": company_name,
            "location": location,
            "description": description,
        },
        "days": max(1, min(int(days), 180)),
    }
    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "workspaceAlberta-DailyBrief/1.0",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    if isinstance(data, dict):
        return str(data.get("content") or data.get("text") or data.get("markdown") or json.dumps(data, indent=2))
    return str(data)


def post_webhook(webhook_url: str, text: str, timeout: int = 15) -> None:
    """Post a short Markdown summary to Slack, Microsoft Teams, or Discord."""
    trimmed = text if len(text) <= 3500 else text[:3450] + "\n\n...(truncated — open full brief locally)"
    body = json.dumps({"text": trimmed, "content": trimmed}).encode("utf-8")
    req = Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "workspaceAlberta-DailyBrief/1.0"},
    )
    with urlopen(req, timeout=timeout):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a daily Canadian & Alberta government tender brief (free, no auth).")
    parser.add_argument("--company", default=os.environ.get("WA_COMPANY_NAME", "My Shop"), help="Company or shop name")
    parser.add_argument("--location", default=os.environ.get("WA_LOCATION", "Alberta, Canada"), help="City and province")
    parser.add_argument(
        "--description",
        default=os.environ.get("WA_DESCRIPTION", "CWB structural steel fabrication, welding, and industrial metal supply"),
        help="Plain-language description of what your shop builds or delivers",
    )
    parser.add_argument("--days", type=int, default=int(os.environ.get("WA_DAYS", "30")), help="Lookahead window in days (default: 30)")
    parser.add_argument("--out", default="", help="Optional path to save the Markdown brief (e.g. briefs/today.md)")
    parser.add_argument("--webhook", default=os.environ.get("WEBHOOK_URL", ""), help="Optional Slack/Teams/Discord webhook URL")
    parser.add_argument("--endpoint", default=os.environ.get("WA_BRIEF_URL", DEFAULT_ENDPOINT), help="workspaceAlberta /brief URL")
    args = parser.parse_args(argv)

    try:
        markdown = fetch_brief(
            company_name=args.company,
            location=args.location,
            description=args.description,
            days=args.days,
            endpoint=args.endpoint,
        )
    except (HTTPError, URLError, OSError) as exc:
        print(f"Error fetching brief: {exc}", file=sys.stderr)
        return 1

    header = f"# Daily Government Tenders Brief — {date.today().isoformat()}\n\n"
    output = markdown if markdown.lstrip().startswith("#") else header + markdown

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Saved brief to {out_path}")
    else:
        print(output)

    if args.webhook:
        post_webhook(args.webhook, output)
        print("Posted brief to webhook.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
