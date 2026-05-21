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
        default=120,
        help="Command timeout in seconds. Default: 120.",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Leave the sandbox running after the smoke test.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON artifact.",
    )
    args = parser.parse_args()

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
