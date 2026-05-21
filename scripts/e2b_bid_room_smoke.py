#!/usr/bin/env python3
"""Run a live E2B bid-room smoke test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core.e2b_bid_room import run_live_bid_room_smoke  # noqa: E402
from procurement_core.service import process_bid_room_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a live E2B sandbox and process a sample bid package."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Sandbox timeout in seconds. Default: 900.",
    )
    parser.add_argument(
        "--command-timeout",
        type=int,
        default=420,
        help="Command timeout in seconds. Default: 420.",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Leave the sandbox running after the smoke test.",
    )
    parser.add_argument(
        "--reference",
        help="CanadaBuys or Alberta APC reference to process with real attachments and Cohere.",
    )
    parser.add_argument(
        "--business-context",
        default="",
        help="Optional business context for reference-based processing.",
    )
    parser.add_argument(
        "--max-attachments",
        type=int,
        default=5,
        help="Maximum attachments to process for a real reference. Default: 5.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON artifact.",
    )
    args = parser.parse_args()

    if args.reference:
        envelope = process_bid_room_artifact({
            "reference": args.reference,
            "business_context": args.business_context,
            "max_attachments": args.max_attachments,
            "timeout_seconds": args.timeout,
            "command_timeout_seconds": args.command_timeout,
            "keep_alive": args.keep_alive,
        })
        if args.json:
            print(json.dumps(envelope, indent=2))
        else:
            print(envelope["markdown"])
        return 0

    result = run_live_bid_room_smoke(
        timeout_seconds=args.timeout,
        command_timeout_seconds=args.command_timeout,
        keep_alive=args.keep_alive,
    )
    artifact = result.artifact

    if args.json:
        print(json.dumps({
            "sandbox_id": result.sandbox_id,
            "killed": result.killed,
            "artifact": artifact,
        }, indent=2))
        return 0

    print("# E2B Bid Room Smoke")
    print(f"Sandbox: {result.sandbox_id}")
    print(f"Sandbox killed: {str(result.killed).lower()}")
    print(f"Processor: {artifact.get('processor')}")
    print(f"Documents processed: {len(artifact.get('documents', []))}")
    print(f"Fit score: {artifact.get('fit_score')}")
    print(f"Matched terms: {', '.join(artifact.get('matched_terms', []))}")
    print(f"Requirements found: {len(artifact.get('requirements', []))}")
    print(f"Deadlines found: {len(artifact.get('deadlines', []))}")
    print("\nNext actions:")
    for action in artifact.get("next_actions", []):
        print(f"- {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
