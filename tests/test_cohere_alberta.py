"""Tests for analyze_contract_with_cohere Alberta APC support (the "Cohere dead-end" fix).

Alberta references (AB-YYYY-NNNNN) must route to the APC detail API and reach
the Cohere call instead of dying in the federal CSV cache lookup. All network
and key access is monkeypatched out; these tests run fully offline.
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keep imports side-effect free (service.py creates DATA_DIR at import time).
os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="canadabuys-test-"))

from procurement_core import service  # noqa: E402


FAKE_ALBERTA_DETAILS = {
    "opportunity": {
        "title": "City of Edmonton - Snow Hauling Services",
        "referenceNumber": "AB-2026-04073",
        "solicitationNumber": "ED-12345",
        "statusCode": "OPEN",
        "categoryCode": "SRV",
        "solicitationTypeCode": "RFP",
        "postingTypeCode": "OPEN",
        "contractingOrganization": "City of Edmonton",
        "postDateTime": "2026-01-05",
        "closeDateTime": "2026-02-15",
        "projectDescription": "Snow hauling and removal services for downtown districts.",
    },
    "commodityCodes": [],
}

FAKE_FEDERAL_CONTRACT = {
    "referenceNumber-numeroReference": "WS3712345678",
    "title-titre-eng": "Janitorial Services - Federal Building",
    "tenderStatus-appelOffresStatut-eng": "Open",
    "tenderClosingDate-appelOffresDateCloture": "2026-03-01",
    "contractingEntityName-nomEntitContractante-eng": "Public Services and Procurement Canada",
    "tenderDescription-descriptionAppelOffres-eng": "Janitorial services for a federal building.",
}


def run_analyze(args):
    return asyncio.run(service.analyze_contract_with_cohere(args))


class AlbertaCoherePathTest(unittest.TestCase):
    def test_alberta_reference_reaches_cohere(self):
        """Alberta refs used to die at 'Contract not found'; they must reach Cohere."""
        with mock.patch.object(service, "get_alberta_api_details", return_value=FAKE_ALBERTA_DETAILS) as api, \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(
                 service,
                 "call_cohere_chat",
                 return_value=("Fit looks good.", "Cohere API", "command-a"),
             ) as chat:
            output = run_analyze({"reference": "AB-2026-04073"})

        api.assert_called_once_with("AB-2026-04073")
        chat.assert_called_once()
        self.assertIn("Alberta Purchasing Connection", output)
        self.assertIn("**Source:** Alberta Purchasing Connection", output)
        self.assertIn("**Reference:** `AB-2026-04073`", output)
        self.assertIn("Fit looks good.", output)
        self.assertIn("# Cohere Tender Analysis", output)
        self.assertNotIn("Contract not found", output)

    def test_alberta_reference_truncates_long_markdown(self):
        long_markdown = "y" * (service.MAX_CONTRACT_PROMPT_CHARS + 500)
        captured = {}

        def fake_chat(messages, max_tokens=1200):
            captured["user"] = messages[1]["content"]
            return ("ok", "Cohere API", "command-a")

        with mock.patch.object(service, "get_alberta_api_details", return_value=FAKE_ALBERTA_DETAILS), \
             mock.patch.object(service, "render_alberta_details_markdown", return_value=long_markdown), \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(service, "call_cohere_chat", side_effect=fake_chat):
            run_analyze({"reference": "AB-2026-04073"})

        self.assertIn("[Contract text truncated for model call.]", captured["user"])
        self.assertLessEqual(len(captured["user"]), service.MAX_CONTRACT_PROMPT_CHARS + 1000)

    def test_bad_alberta_reference_returns_not_available(self):
        with mock.patch.object(
            service,
            "get_alberta_api_details",
            side_effect=RuntimeError("HTTP 404: not found"),
        ), mock.patch.object(service, "call_cohere_chat") as chat:
            output = run_analyze({"reference": "AB-2026-99999"})

        chat.assert_not_called()
        self.assertIn("Alberta opportunity not available", output)
        self.assertIn("HTTP 404", output)

    def test_cohere_failure_returns_graceful_message(self):
        with mock.patch.object(service, "get_alberta_api_details", return_value=FAKE_ALBERTA_DETAILS), \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(
                 service,
                 "call_cohere_chat",
                 side_effect=RuntimeError("no API key configured"),
             ):
            output = run_analyze({"reference": "AB-2026-04073"})

        self.assertIn("Cohere analysis is not available", output)
        self.assertIn("no API key configured", output)


class FederalCoherePathTest(unittest.TestCase):
    def test_federal_reference_still_works(self):
        with mock.patch.object(service, "load_contracts", return_value=[FAKE_FEDERAL_CONTRACT]), \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(
                 service,
                 "call_cohere_chat",
                 return_value=("Federal fit analysis.", "Cohere API", "command-a"),
             ) as chat, \
             mock.patch.object(service, "get_alberta_api_details") as api:
            output = run_analyze({"reference": "WS3712345678"})

        api.assert_not_called()
        chat.assert_called_once()
        self.assertIn("**Source:** CanadaBuys", output)
        self.assertIn("**Reference:** `WS3712345678`", output)
        self.assertIn("Federal fit analysis.", output)
        self.assertIn("on CanadaBuys before making a bid decision", output)

    def test_federal_reference_not_found(self):
        with mock.patch.object(service, "load_contracts", return_value=[FAKE_FEDERAL_CONTRACT]), \
             mock.patch.object(service, "call_cohere_chat") as chat:
            output = run_analyze({"reference": "WS9999999999"})

        chat.assert_not_called()
        self.assertIn("Contract not found: WS9999999999", output)


if __name__ == "__main__":
    unittest.main()
