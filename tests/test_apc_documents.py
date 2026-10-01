import copy
import hashlib
import http.server
import io
import json
import os
import socket
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="apc-docs-tests-"))

from procurement_core import e2b_bid_room as bid, service
from procurement_core.apc_documents import apc_document_manifest, public_document_url, resolve_apc_documents

FIXTURE = Path(__file__).parent / "fixtures" / "procurement" / "apc_re9256.json"
DOCUMENT_ID = "f245a5f8-d095-4e7c-8872-ddcc900dc24c"
COPY_URL = "https://copies.example.test/re9256.pdf"


class APCDocumentTest(unittest.TestCase):
    def setUp(self):
        self.details = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_real_metadata_lists_pdf_and_correct_posting_and_submission(self):
        markdown = service.render_alberta_details_markdown(self.details)
        self.assertIn("https://purchasing.alberta.ca/posting/AB-2026-06584", markdown)
        self.assertNotIn("/opportunity/2026/6584", markdown)
        self.assertIn(DOCUMENT_ID, markdown)
        self.assertIn("422592 bytes", markdown)
        self.assertIn("requisitions@specialareas.ab.ca", markdown)
        self.assertIn("supplier registration/notifications", markdown)
        row = service.normalize_alberta_opportunity(self.details["opportunity"])
        self.assertEqual(row["url"], "https://purchasing.alberta.ca/posting/AB-2026-06584")

    def test_real_metadata_blocks_before_paid_work_without_a_public_copy(self):
        payload = bid.build_apc_bid_room_payload(self.details, {})
        self.assertEqual(payload["attachments"], [])
        self.assertEqual(payload["document_manifest"][0]["status"], "access_required")
        self.assertEqual(payload["document_manifest"][0]["document_id"], DOCUMENT_ID)
        with patch.object(service, "get_alberta_api_details", return_value=self.details), patch.object(
            service, "resolve_profile", return_value={}
        ), patch.object(bid, "run_live_bid_room_process") as run:
            with self.assertRaisesRegex(ValueError, "No sandbox was started"):
                service.process_bid_room_artifact({"reference": "AB-2026-06584"})
        run.assert_not_called()

    def test_addenda_versions_deleted_files_and_limits_remain_visible(self):
        old = copy.deepcopy(self.details["opportunity"]["documents"][0])
        old["version"] = -1
        deleted = dict(old, id="deleted", deletedOnUtc="2026-09-30")
        self.details["opportunity"]["documents"].extend([old, deleted])
        self.details["opportunity"]["addendaDocuments"] = [{
            "id": "addendum-1", "filename": "Addendum-1.pdf", "version": 1,
            "amendmentNumber": 1, "mimeType": "application/pdf",
        }]
        manifest, attachments = resolve_apc_documents(self.details, {
            DOCUMENT_ID: COPY_URL, "addendum-1": "https://copies.example.test/addendum.pdf",
        }, max_attachments=1)
        self.assertEqual(len(manifest), 2)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["version"], 0)
        self.assertEqual(manifest[1]["kind"], "apc_addendum")
        self.assertEqual(manifest[1]["status"], "not_selected")
        self.assertEqual(manifest[1]["amendment_number"], 1)

    def test_no_nda_or_authenticated_download_bypass(self):
        self.details["opportunity"]["isNdaRequiredForDocumentsAccess"] = True
        manifest, attachments = resolve_apc_documents(self.details, {DOCUMENT_ID: COPY_URL})
        self.assertEqual(attachments, [])
        self.assertEqual(manifest[0]["status"], "access_required")
        for url in [
            "https://purchasing.alberta.ca/api/documents/download", "http://copies.example.test/a.pdf",
            "https://user:password@copies.example.test/a.pdf", "https://127.0.0.1/a.pdf",
            "https://copies.example.test/a.pdf?access_token=credential",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                public_document_url(url)
        with self.assertRaisesRegex(ValueError, "not present"):
            resolve_apc_documents(self.details, {"other-tender-id": COPY_URL})
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(ValueError, "public addresses"):
                public_document_url(COPY_URL, resolve=True)

    def test_metadata_public_urls_are_resolved_but_apc_downloads_stay_gated(self):
        document = self.details["opportunity"]["documents"][0]
        document["downloadUrl"] = COPY_URL
        self.assertEqual(resolve_apc_documents(self.details)[1][0]["url"], COPY_URL)
        document["downloadUrl"] = "https://purchasing.alberta.ca/api/document/download"
        self.assertEqual(resolve_apc_documents(self.details)[0][0]["status"], "access_required")

    def test_validator_cannot_accept_forged_complete_coverage_or_omitted_files(self):
        payload = bid.build_apc_bid_room_payload(self.details, {}, apc_document_urls={DOCUMENT_ID: COPY_URL})
        artifact = {"processor": "test", "opportunity": {}, "profile": {}, "documents": [],
                    "evidence": {}, "coverage": {"complete": True, "status": "complete"}}
        checked = bid.validate_bid_room_artifact(artifact, expected_documents=payload["document_manifest"])
        self.assertFalse(checked["coverage"]["complete"])
        self.assertEqual(checked["documents"][0]["status"], "not_returned")
        self.assertTrue(checked["warnings"])


class LocalAPCPDFProcessingTest(unittest.TestCase):
    """Real embedded processor and PDF bytes; only transport maps to loopback."""

    setUp = APCDocumentTest.setUp

    @staticmethod
    def pdf_bytes(text):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 700 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def process(self, payload, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in files.items():
                (root / name).write_bytes(data)

            class Handler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=directory, **kwargs)

                def log_message(self, *args):
                    pass

            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            requests = []
            original_getaddrinfo = socket.getaddrinfo

            def local_dns(host, *args, **kwargs):
                if host == "copies.example.test":
                    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
                if host not in {"127.0.0.1", "localhost", "::1"}:
                    raise AssertionError("External DNS prohibited")
                return original_getaddrinfo(host, *args, **kwargs)

            def local_open(request, timeout=90):
                url = request.full_url
                if not url.startswith("https://copies.example.test/"):
                    raise AssertionError(f"External/provider request prohibited: {url}")
                requests.append(url)
                return urlopen(Request(f"http://127.0.0.1:{server.server_port}/" + url.rsplit("/", 1)[1]), timeout=timeout)

            class Opener:
                open = staticmethod(local_open)

            payload["cohere"]["enabled"] = False
            payload["parse"]["enabled"] = False
            script = bid.build_sandbox_command(payload).split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
            script = script.replace('Path("/tmp/workspacealberta-bid-room")', f"Path({str(root / 'work')!r})")
            script = script.replace("\ndocuments = []\n", "\nurlopen = _fixture_open\nbuild_opener = lambda *handlers: _fixture_opener\ndocuments = []\n", 1)
            output = io.StringIO()
            namespace = {"_fixture_open": local_open, "_fixture_opener": Opener()}
            try:
                with patch.dict(os.environ, {"CANADABUYS_LOAD_ENV_FILE": "0"}, clear=True), patch(
                    "subprocess.check_call", side_effect=AssertionError("Dependency/network installation prohibited")
                ), patch("socket.getaddrinfo", side_effect=local_dns
                ), redirect_stdout(output):
                    exec(compile(script, "actual-sandbox-processor", "exec"), namespace)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            artifact = bid.validate_bid_room_artifact(bid.parse_artifact(output.getvalue()),
                                                       expected_documents=payload["document_manifest"])
            return artifact, requests, namespace

    def test_pdf_and_addendum_content_reach_real_extractor_and_evidence(self):
        base = self.pdf_bytes("Supplier must provide disconnect permit FIXTURE-BASE. Closing date: 2026-10-14.")
        addendum = self.pdf_bytes("Supplier must provide commissioning report FIXTURE-ADDENDUM.")
        self.details["opportunity"]["addendaDocuments"] = [{
            "id": "addendum-1", "filename": "addendum.pdf", "amendmentNumber": 1, "mimeType": "application/pdf",
        }]
        payload = bid.build_apc_bid_room_payload(self.details, {}, apc_document_urls={
            DOCUMENT_ID: COPY_URL, "addendum-1": "https://copies.example.test/addendum.pdf",
        })
        artifact, requests, namespace = self.process(payload, {"re9256.pdf": base, "addendum.pdf": addendum})
        self.assertEqual(len(requests), 2)
        self.assertIsNone(artifact["cohere_analysis"])
        extracted = [item for item in artifact["documents"] if item.get("is_tender_document")]
        self.assertEqual([item["status"] for item in extracted], ["extracted", "extracted"])
        self.assertEqual(extracted[0]["sha256"], hashlib.sha256(base).hexdigest())
        self.assertEqual(extracted[0]["bytes"], len(base))
        evidence_text = json.dumps(artifact["evidence"])
        self.assertIn("disconnect permit", evidence_text)
        self.assertIn("commissioning report", evidence_text)
        self.assertIn("FIXTURE-BASE", namespace["evidence_bundle"]["evidence"]["text_for_model"])
        self.assertIn("FIXTURE-ADDENDUM", namespace["evidence_bundle"]["evidence"]["text_for_model"])
        self.assertTrue(artifact["coverage"]["complete"])
        with self.assertRaises(ValueError):
            namespace["PublicDocumentRedirects"]().redirect_request(
                Request(COPY_URL), None, 302, "Found", {}, "https://purchasing.alberta.ca/api/download")

    def test_download_failure_empty_pdf_login_page_and_invalid_pdf_are_incomplete(self):
        for name, content, expected_status in [
            ("missing.pdf", None, "download_failed"),
            ("empty.pdf", self.pdf_bytes(""), "empty"),
            ("login.pdf", b"<html>Sign in</html>", "unexpected_content"),
            ("invalid.pdf", b"%PDF-not-a-valid-file", "extract_failed"),
        ]:
            with self.subTest(name=name):
                payload = bid.build_apc_bid_room_payload(self.details, {}, apc_document_urls={
                    DOCUMENT_ID: "https://copies.example.test/" + name,
                })
                artifact, _requests, _namespace = self.process(payload, {name: content} if content is not None else {})
                record = next(item for item in artifact["documents"] if item.get("document_id") == DOCUMENT_ID)
                self.assertEqual(record["status"], expected_status)
                self.assertFalse(artifact["coverage"]["complete"])
                self.assertTrue(artifact["warnings"])
                markdown = bid.render_bid_room_markdown(bid.BidRoomSandboxResult("local-only", True, artifact, "", ""))
                self.assertIn("not a complete document review", markdown)

    def test_notice_only_and_capped_addendum_cannot_claim_complete_coverage(self):
        payload = bid.build_apc_bid_room_payload(self.details, {}, max_attachments=0)
        artifact, requests, _namespace = self.process(payload, {})
        self.assertEqual(requests, [])
        self.assertEqual(artifact["coverage"]["status"], "notice_only")
        self.assertFalse(artifact["coverage"]["complete"])
        self.details["opportunity"]["addendaDocuments"] = [{"id": "addendum-1", "filename": "addendum.pdf"}]
        payload = bid.build_apc_bid_room_payload(self.details, {}, max_attachments=1,
            apc_document_urls={DOCUMENT_ID: COPY_URL, "addendum-1": "https://copies.example.test/addendum.pdf"})
        artifact, _requests, _namespace = self.process(payload, {"re9256.pdf": self.pdf_bytes("Supplier must provide a permit.")})
        self.assertEqual(artifact["coverage"]["status"], "partial")
        self.assertEqual(artifact["coverage"]["expected_documents"], 2)
        self.assertIn("not_selected", json.dumps(artifact["coverage"]["issues"]))

    def test_text_and_model_limits_make_coverage_partial(self):
        pdf = self.pdf_bytes("Supplier must provide a permit. " + "X" * 24010)
        payload = bid.build_apc_bid_room_payload(self.details, {}, apc_document_urls={DOCUMENT_ID: COPY_URL})
        payload["limits"]["max_cohere_chars"] = 100
        artifact, _requests, _namespace = self.process(payload, {"re9256.pdf": pdf})
        record = next(item for item in artifact["documents"] if item.get("document_id") == DOCUMENT_ID)
        self.assertTrue(record["truncated"])
        self.assertEqual(artifact["coverage"]["status"], "partial")
        self.assertIn("model text limit", " ".join(artifact["warnings"]))


if __name__ == "__main__":
    unittest.main()
