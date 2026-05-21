import json
import unittest

from procurement_core.e2b_bid_room import (
    build_apc_bid_room_payload,
    build_canadabuys_bid_room_payload,
    build_sample_payload,
    build_sandbox_command,
    collect_canadabuys_attachment_urls,
    parse_artifact,
    validate_bid_room_artifact,
    validate_cohere_analysis,
)


class E2BBidRoomTest(unittest.TestCase):
    def test_sample_payload_and_artifact_parser(self) -> None:
        payload = build_sample_payload()
        self.assertEqual(payload["profile"]["company_name"], "Edmonton Steel Works")
        self.assertEqual(len(payload["documents"]), 3)
        self.assertEqual(payload["cohere"]["response_format"]["type"], "json_object")
        self.assertEqual(
            payload["cohere"]["response_format"]["schema"]["required"][0],
            "bid_recommendation",
        )

        command = build_sandbox_command(payload)
        self.assertIn("workspacealberta-e2b-bid-room-v1", command)
        self.assertIn("python3 - <<'PY'", command)

        artifact = {
            "processor": "workspacealberta-e2b-bid-room-v1",
            "opportunity": {},
            "profile": {},
            "documents": [],
            "evidence": {},
        }
        parsed = parse_artifact("logs before\n" + json.dumps(artifact) + "\nlogs after")
        self.assertEqual(parsed["processor"], "workspacealberta-e2b-bid-room-v1")
        self.assertEqual(validate_bid_room_artifact(parsed)["documents"], [])

    def test_canadabuys_attachment_extraction_and_payload(self) -> None:
        contract = {
            "referenceNumber-numeroReference": "TEST-FED-001",
            "title-titre-eng": "Steel package",
            "attachment_urls": "https://example.com/a.pdf;https://example.com/b.zip",
            "attachment-piecesJointes-eng": "https://example.com/a.pdf,https://example.com/c.docx",
        }
        urls = collect_canadabuys_attachment_urls(contract)
        self.assertEqual(urls, [
            "https://example.com/a.pdf",
            "https://example.com/b.zip",
            "https://example.com/c.docx",
        ])

        payload = build_canadabuys_bid_room_payload(
            contract,
            {"company_name": "Test Co", "capabilities": ["steel"]},
        )
        self.assertEqual(payload["opportunity"]["reference"], "TEST-FED-001")
        self.assertEqual(len(payload["attachments"]), 3)

    def test_apc_payload_uses_metadata_and_external_link(self) -> None:
        payload = build_apc_bid_room_payload(
            {
                "opportunity": {
                    "referenceNumber": "AB-2026-00001",
                    "title": "Steel Refurbishment Work",
                    "projectDescription": "Mandatory site visit required.",
                    "externalOriginLink": "https://example.com/tender",
                    "regionOfDelivery": ["Alberta"],
                }
            },
            {"company_name": "Test Co", "capabilities": ["steel"]},
        )
        self.assertEqual(payload["opportunity"]["reference"], "AB-2026-00001")
        self.assertEqual(payload["attachments"][0]["kind"], "apc_external_page")
        self.assertIn("Mandatory site visit", payload["documents"][0]["text"])

    def test_cohere_analysis_validation(self) -> None:
        analysis = validate_cohere_analysis({
            "bid_recommendation": "maybe",
            "fit_score": "88",
            "requirements": "Submit signed form.",
            "risks": [],
            "missing_information": [],
            "deadlines": [],
            "questions_to_ask": [],
            "next_actions": [],
        })
        self.assertEqual(analysis["fit_score"], 88)
        self.assertEqual(analysis["requirements"], ["Submit signed form."])

    def test_bid_room_artifact_requires_tool_trace_with_cohere(self) -> None:
        artifact = {
            "processor": "workspacealberta-e2b-bid-room-v1",
            "opportunity": {},
            "profile": {},
            "documents": [],
            "evidence": {},
            "cohere_analysis": {
                "bid_recommendation": "maybe",
                "fit_score": 50,
                "requirements": [],
                "risks": [],
                "missing_information": [],
                "deadlines": [],
                "questions_to_ask": [],
                "next_actions": [],
            },
            "cohere_tool_calls": [{
                "id": "search_extracted_documents_1",
                "name": "search_extracted_documents",
                "arguments": {"query": "requirements"},
                "result_count": 2,
            }],
        }
        validated = validate_bid_room_artifact(artifact, require_cohere=True)
        self.assertEqual(validated["cohere_tool_calls"][0]["result_count"], 2)


if __name__ == "__main__":
    unittest.main()
