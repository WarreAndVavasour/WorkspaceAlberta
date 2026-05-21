import json
import unittest

from procurement_core.e2b_bid_room import build_sample_payload, build_sandbox_command, parse_artifact


class E2BBidRoomTest(unittest.TestCase):
    def test_sample_payload_and_artifact_parser(self) -> None:
        payload = build_sample_payload()
        self.assertEqual(payload["profile"]["company_name"], "Edmonton Steel Works")
        self.assertEqual(len(payload["documents"]), 3)

        command = build_sandbox_command(payload)
        self.assertIn("workspacealberta-e2b-bid-room-smoke-v1", command)
        self.assertIn("python3 - <<'PY'", command)

        artifact = {
            "processor": "workspacealberta-e2b-bid-room-smoke-v1",
            "fit_score": 92,
        }
        parsed = parse_artifact("logs before\n" + json.dumps(artifact) + "\nlogs after")
        self.assertEqual(parsed["fit_score"], 92)


if __name__ == "__main__":
    unittest.main()
