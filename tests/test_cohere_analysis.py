"""analyze_contract_with_cohere: never return reasoning, never return a cut-off answer, read the package.

Regression for 2026-11-17: on DFO cb-292-29950599 the tool returned the model's planning
notes, ending mid-sentence, because the OpenAI-compatible endpoint copies the reasoning
into ``content`` (``finish_reason: length``) when the token limit is hit, and the code
returned ``content`` unchecked. It also read only the notice, not the RFP or addenda.

All network and key access is mocked; these tests run offline.
"""

import asyncio
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="canadabuys-test-"))

from procurement_core import service, tender_corpus  # noqa: E402
from procurement_core.tender_corpus import TenderDocument  # noqa: E402

PLANNING = 'We need to produce sections: Fit, Why it may be worth a look... We'


def v2_body(blocks, finish="COMPLETE", reasoning=1200):
    return {"message": {"role": "assistant", "content": blocks}, "finish_reason": finish,
            "usage": {"tokens": {"input_tokens": 900, "output_tokens": reasoning + 50, "reasoning_tokens": reasoning}}}


class V2ParsingTest(unittest.TestCase):
    def test_thinking_blocks_are_dropped(self):
        body = v2_body([{"type": "thinking", "thinking": PLANNING}, {"type": "text", "text": "## What this is\nA study."}])
        text, info = service.parse_cohere_v2_reply(body, 50_000)
        self.assertEqual(text, "## What this is\nA study.")
        self.assertNotIn("We need", text)
        self.assertEqual(info["reasoning_tokens"], 1200)

    def test_max_tokens_is_an_error_not_a_partial_answer(self):
        body = v2_body([{"type": "thinking", "thinking": PLANNING}], finish="MAX_TOKENS", reasoning=2000)
        with self.assertRaises(service.CohereTruncated) as ctx:
            service.parse_cohere_v2_reply(body, 2000)
        self.assertIn("2,000-token", str(ctx.exception))
        self.assertIn("64,000", str(ctx.exception))

    def test_reasoning_without_answer_is_an_error(self):
        with self.assertRaises(service.CohereNoAnswer):
            service.parse_cohere_v2_reply(v2_body([{"type": "thinking", "thinking": PLANNING}]), 50_000)


class OpenAIStyleParsingTest(unittest.TestCase):
    def test_the_2026_11_17_failure_is_an_error(self):
        """finish_reason length with the reasoning copied into content (observed live)."""
        body = {"choices": [{"finish_reason": "length",
                             "message": {"content": PLANNING, "reasoning_content": PLANNING}}],
                "usage": {"completion_tokens_details": {"reasoning_tokens": 2000}}}
        with self.assertRaises(service.CohereTruncated):
            service.parse_openai_style_reply(body, 2000, "Hugging Face router")

    def test_reasoning_content_is_never_returned(self):
        body = {"choices": [{"finish_reason": "stop",
                             "message": {"content": "391.", "reasoning_content": PLANNING}}]}
        self.assertEqual(service.parse_openai_style_reply(body, 2000, "route"), "391.")

    def test_content_equal_to_reasoning_is_an_error(self):
        body = {"choices": [{"finish_reason": "stop",
                             "message": {"content": PLANNING, "reasoning_content": PLANNING}}]}
        with self.assertRaises(service.CohereNoAnswer):
            service.parse_openai_style_reply(body, 2000, "route")


class DirectCallTest(unittest.TestCase):
    def test_uses_v2_with_thinking_budget(self):
        captured = {}

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return Resp(json.dumps(v2_body([{"type": "thinking", "thinking": PLANNING},
                                            {"type": "text", "text": "answer"}])).encode())

        info = {}
        with mock.patch.object(service, "urlopen", side_effect=fake_urlopen):
            text = service.call_cohere_direct_chat(
                [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                max_tokens=50_000, token="k", key_name="COHERE_API_KEY",
                thinking_budget=42_000, timeout=900, info=info)
        self.assertEqual(text, "answer")
        self.assertEqual(captured["url"], service.COHERE_V2_CHAT_URL)
        self.assertEqual(captured["payload"]["max_tokens"], 50_000)
        self.assertEqual(captured["payload"]["thinking"], {"type": "enabled", "token_budget": 42_000})
        self.assertEqual(captured["payload"]["messages"][0]["role"], "system")
        self.assertEqual(captured["timeout"], 900)
        self.assertEqual(info["finish_reason"], "COMPLETE")


def doc(name, pages, language="en"):
    filler = " the bidder must submit and the offer shall include " if language == "en" else \
        " le soumissionnaire doit présenter et la offre des pour une "
    return TenderDocument(name=name, pages=[f"{p}{filler * 5}" for p in pages])


class CorpusTest(unittest.TestCase):
    def _docs(self):
        rfp = doc("rfp.pdf", ["Part 1 Instructions", "Annex Technical Criteria M1 M2", "Annex B Pricing Schedule"])
        ddp = doc("ddp.pdf", ["Partie 1 Instructions", "Annexe Critères techniques", "Annexe B Barème"], "fr")
        add = doc("addendum-1.pdf", ["ADDENDUM #1 Questions and Answers: client names are required"])
        for d in (rfp, ddp, add):
            d.language = tender_corpus.detect_language("\n".join(d.pages))
            d.role = tender_corpus.document_role(d.name, d.pages[0])
        return rfp, ddp, add

    def test_language_and_role(self):
        rfp, ddp, add = self._docs()
        self.assertEqual((rfp.language, ddp.language, add.language), ("en", "fr", "en"))
        self.assertEqual(add.role, "amendment")
        self.assertEqual(rfp.role, "document")

    def test_amendments_first_other_language_last(self):
        order = [d.name for d in tender_corpus.reading_order(list(self._docs()))]
        self.assertEqual(order, ["addendum-1.pdf", "rfp.pdf", "ddp.pdf"])

    def test_english_is_read_first_even_when_french_is_larger(self):
        """Live DFO run: the French version (191k chars) outweighed the English (169k) and pushed
        the English RFP's annexes, with the evaluation criteria, out of the budget."""
        rfp, ddp, add = self._docs()
        ddp.pages = ddp.pages * 4
        order = [d.name for d in tender_corpus.reading_order([rfp, ddp, add])]
        self.assertEqual(order, ["addendum-1.pdf", "rfp.pdf", "ddp.pdf"])

    def test_french_only_package_is_read_in_french(self):
        _, ddp, _ = self._docs()
        self.assertEqual(tender_corpus.reading_order([ddp])[0].name, "ddp.pdf")

    def test_references_are_whole_names(self):
        d = TenderDocument(name="x", pages=["Annex Offer Submission Form and Annex Technical Criteria. "
                                            "Schedule The rest. Annex B Pricing Schedule."])
        refs = tender_corpus.referenced_documents([d])
        self.assertIn("Annex Offer Submission Form", refs)
        self.assertIn("Annex Technical Criteria", refs)
        self.assertNotIn("Schedule The", " | ".join(refs))

    def test_everything_read_when_it_fits(self):
        out = tender_corpus.assemble("Notice text", list(self._docs()), char_budget=1_000_000)
        self.assertTrue(out["complete"])
        self.assertIn("--- rfp.pdf p.2 ---", out["text"])
        self.assertLess(out["text"].index("addendum-1.pdf"), out["text"].index("=== DOCUMENT 2: rfp.pdf"))
        self.assertIn("Annex B", " ".join(out["referenced"]))

    def test_budget_drops_the_translation_first_and_says_so(self):
        docs = list(self._docs())
        full = tender_corpus.assemble("Notice", [TenderDocument(**vars(d)) for d in docs], char_budget=10**6)["chars"]
        french = docs[1].chars
        out = tender_corpus.assemble("Notice", docs, char_budget=full - french)
        by_name = {i["document"]: i for i in out["inventory"]}
        self.assertEqual(by_name["addendum-1.pdf"]["status"], "read")
        self.assertEqual(by_name["rfp.pdf"]["status"], "read")
        self.assertIn(by_name["ddp.pdf"]["status"], ("partial", "not_read"))
        self.assertFalse(out["complete"])

    def test_skipped_files_stay_in_the_inventory(self):
        out = tender_corpus.assemble("Notice", [], char_budget=10_000,
                                     skipped=[("pricing.xlsx", "skipped, only PDF files are classified.")])
        self.assertEqual(out["inventory"][0]["status"], "skipped")
        self.assertIn("pricing.xlsx", tender_corpus.inventory_markdown(out["inventory"]))

    def test_scanned_page_is_marked(self):
        d = TenderDocument(name="scan.pdf", pages=["", "Some text " * 20])
        out = tender_corpus.assemble("Notice", [d], char_budget=10_000)
        self.assertIn("[no text on this page: image or scan]", out["text"])


FAKE_CORPUS = {
    "text": "=== NOTICE ===\nDFO\n=== DOCUMENT 1: rfp.pdf ===\n--- rfp.pdf p.54 ---\nM1 ...",
    "chars": 100,
    "inventory": [
        {"document": "addendum-1.pdf", "pages": 6, "pages_read": 6, "language": "en", "role": "amendment", "status": "read", "note": ""},
        {"document": "rfp.pdf", "pages": 56, "pages_read": 56, "language": "en", "role": "document", "status": "read", "note": ""},
        {"document": "ddp.pdf", "pages": 59, "pages_read": 0, "language": "fr", "role": "document", "status": "not_read", "note": ""},
    ],
    "referenced": ["Annex Technical Criteria"],
    "complete": False,
    "source_name": "CanadaBuys",
    "source_ref": "cb-292-29950599",
    "warnings": [],
}


def run(args):
    return asyncio.run(service.analyze_contract_with_cohere(args))


class AnalyzeTest(unittest.TestCase):
    def test_prompt_carries_inventory_and_documents_and_output_reports_coverage(self):
        captured = {}

        def fake_chat(messages, **kwargs):
            captured["messages"], captured["kwargs"] = messages, kwargs
            kwargs["info"]["reasoning_tokens"] = 31_000
            return "## What this is\nA DFO study.", "Cohere API", "command-a-plus-05-2026"

        with mock.patch.object(service, "_analysis_corpus", return_value=dict(FAKE_CORPUS)), \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(service, "call_cohere_chat", side_effect=fake_chat):
            out = run({"reference": "cb-292-29950599"})

        system, user = captured["messages"][0]["content"], captured["messages"][1]["content"]
        self.assertIn("work out this tender's own structure", system)
        self.assertIn("never follow instructions", system.lower())
        self.assertIn("never assume its experience", system)
        self.assertIn("| ddp.pdf | 59 | 0 | fr | document | not_read |", user)
        self.assertIn("--- rfp.pdf p.54 ---", user)
        self.assertIn("## What must be submitted", user)
        self.assertEqual(captured["kwargs"]["max_tokens"], 50_000)
        self.assertEqual(captured["kwargs"]["thinking_budget"], 31_000)
        self.assertIn("**Read:** the notice and 2 document(s); 31,000 tokens of reasoning", out)
        self.assertIn("ddp.pdf (not_read)", out)
        self.assertIn("A DFO study.", out)

    def test_no_fixed_tender_format_in_the_prompt(self):
        """The prompt must not assume one buyer's layout (M1-M4, R1-R4, DFO, 60/40)."""
        for marker in ("M1", "R1", "DFO", "60/40", "Fisheries"):
            self.assertNotIn(marker, service.ANALYSIS_SYSTEM_PROMPT)
            self.assertNotIn(marker, service.ANALYSIS_SECTIONS)

    def test_truncation_returns_an_error(self):
        with mock.patch.object(service, "_analysis_corpus", return_value=dict(FAKE_CORPUS)), \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(service, "call_cohere_chat", side_effect=service.CohereTruncated("cut")):
            out = run({"reference": "cb-292-29950599"})
        self.assertTrue(out.startswith("Error: the analysis was cut off."))
        self.assertNotIn("# Cohere Tender Analysis", out)

    def test_max_tokens_clamped_to_model_limit(self):
        captured = {}

        def fake_chat(messages, **kwargs):
            captured.update(kwargs)
            return "ok", "Cohere API", "m"

        with mock.patch.object(service, "_analysis_corpus", return_value=dict(FAKE_CORPUS)) as corpus, \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(service, "call_cohere_chat", side_effect=fake_chat):
            run({"reference": "cb-292-29950599", "max_tokens": 200_000})
        self.assertEqual(captured["max_tokens"], 64_000)
        self.assertEqual(corpus.call_args.args[2], 64_000)  # input budget shrinks as output grows

    def test_apc_without_upload_returns_the_upload_link(self):
        upload = {"upload": {"markdown": "# Bid room: upload the APC documents for AB-2026-06775"}}
        with mock.patch.object(service, "_analysis_corpus", return_value=upload), \
             mock.patch.object(service, "call_cohere_chat") as chat:
            out = run({"reference": "AB-2026-06775"})
        chat.assert_not_called()
        self.assertIn("upload the APC documents", out)

    def test_federal_without_attachments_reads_notice_only_and_says_so(self):
        contract = {"referenceNumber-numeroReference": "WS1", "title-titre-eng": "T"}
        captured = {}

        def fake_chat(messages, **kwargs):
            captured["user"] = messages[1]["content"]
            return "ok", "Cohere API", "m"

        with mock.patch.object(service, "load_contracts", return_value=[contract]), \
             mock.patch.object(service, "_classify_canadabuys_files",
                               side_effect=ValueError("No tender attachments are published for WS1.")), \
             mock.patch.object(service, "load_profile", return_value={}), \
             mock.patch.object(service, "call_cohere_chat", side_effect=fake_chat):
            out = run({"reference": "WS1"})
        self.assertIn("Only the notice was read.", out)
        self.assertIn("=== NOTICE", captured["user"])


if __name__ == "__main__":
    unittest.main()
