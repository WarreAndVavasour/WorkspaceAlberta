"""Local bid room: connector downloads -> verified uploads -> the real sandbox processor.

No E2B, Cohere or network: the embedded processor runs in-process against a
temporary work directory, exactly as tests.test_apc_documents does.
"""

import asyncio
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="local-bid-room-tests-"))

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-servers" / "canadabuys"))

from procurement_core import e2b_bid_room as bid  # noqa: E402
from procurement_core import local_bid_room as local  # noqa: E402
from tests.test_apc_documents import LocalAPCPDFProcessingTest  # noqa: E402

REFERENCE = "AB-2026-06523"
pdf_bytes = LocalAPCPDFProcessingTest.pdf_bytes


def write_download(home: Path, files: dict[str, bytes], *, complete=True, reference=REFERENCE,
                   path_prefix="/media/old-mount/apc"):
    """Mimic the harness connector's folder layout and manifest receipt."""
    folder = home / "opportunities" / reference
    folder.mkdir(parents=True)
    documents = []
    for title, data in files.items():
        digest = hashlib.sha256(data).hexdigest()
        name = f"{title}-{digest[:16]}.pdf"
        (folder / name).write_bytes(data)
        documents.append({
            "title": title,
            # Absolute path from a different mount: the loader must use only the file name.
            "path": f"{path_prefix}/opportunities/{reference}/{name}",
            "sha256": digest, "bytes": len(data),
            "source": f"https://purchasing.alberta.ca/posting/{reference}",
            "retrieved_at": "2026-10-02T15:00:00+00:00",
        })
    (folder / "manifest.json").write_text(json.dumps({
        "reference": reference, "complete": complete,
        "expected_documents": len(documents), "documents": documents,
    }))
    (home / "browser-profile").mkdir(exist_ok=True)
    (home / "browser-profile" / "Cookies").write_text("SECRET-SESSION")
    return folder


def run_processor(payload, uploads, work: Path):
    """Place uploads where the sandbox would have them, then exec the real processor."""
    for sandbox_path, data in uploads:
        relative = Path(sandbox_path).relative_to("/tmp/workspacealberta-bid-room")
        target = work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    payload["cohere"]["enabled"] = False
    payload["parse"]["enabled"] = False
    script = bid.build_sandbox_command(payload).split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    script = script.replace('Path("/tmp/workspacealberta-bid-room")', f"Path({str(work)!r})")

    def no_network(*args, **kwargs):
        raise AssertionError("Local bid room must not fetch anything")

    script = script.replace("\ndocuments = []\n", "\nurlopen = _no_network\ndocuments = []\n", 1)
    output = io.StringIO()
    namespace = {"_no_network": no_network}
    with patch.dict(os.environ, {"CANADABUYS_LOAD_ENV_FILE": "0"}, clear=True), patch(
        "subprocess.check_call", side_effect=AssertionError("No installs")
    ), redirect_stdout(output):
        exec(compile(script, "actual-sandbox-processor", "exec"), namespace)
    artifact = bid.validate_bid_room_artifact(
        bid.parse_artifact(output.getvalue()), expected_documents=payload["document_manifest"])
    return artifact, namespace


class LoadLocalDownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verifies_files_using_only_their_names_inside_the_folder(self):
        write_download(self.home, {"RFP": pdf_bytes("Scope FIXTURE-RFP"), "Addendum_1": pdf_bytes("FIXTURE-ADD")})
        download = local.load_local_download(REFERENCE, self.home)
        self.assertTrue(download["complete"])
        self.assertEqual([item["status"] for item in download["files"]], ["verified", "verified"])
        for item in download["files"]:
            self.assertEqual(item["path"].parent, (self.home / "opportunities" / REFERENCE).resolve())

    def test_rejects_changed_missing_traversal_and_fake_files(self):
        folder = write_download(self.home, {
            "Changed": pdf_bytes("one"), "Missing": pdf_bytes("two"),
            "Fake": pdf_bytes("three"), "Escape": pdf_bytes("four"),
        })
        manifest = json.loads((folder / "manifest.json").read_text())
        by_title = {entry["title"]: entry for entry in manifest["documents"]}
        changed = folder / Path(by_title["Changed"]["path"]).name
        changed.write_bytes(changed.read_bytes().replace(b"one", b"0ne"))
        (folder / Path(by_title["Missing"]["path"]).name).unlink()
        fake = folder / Path(by_title["Fake"]["path"]).name
        login_page = b"<html>Sign in</html>"
        fake.write_bytes(login_page)
        by_title["Fake"].update(sha256=hashlib.sha256(login_page).hexdigest(), bytes=len(login_page))
        (self.home / "outside.pdf").write_bytes(b"%PDF-outside")
        by_title["Escape"]["path"] = "../../outside.pdf"
        (folder / "manifest.json").write_text(json.dumps(manifest))

        statuses = {item["title"]: item["status"] for item in local.load_local_download(REFERENCE, self.home)["files"]}
        self.assertEqual(statuses["Changed"], "hash_mismatch")
        self.assertEqual(statuses["Missing"], "missing")
        self.assertEqual(statuses["Fake"], "bad_signature")
        self.assertEqual(statuses["Escape"], "missing")  # name only; never resolved outside the folder

    def test_reference_and_manifest_mismatches_fail_before_any_work(self):
        with self.assertRaises(local.LocalBidRoomError):
            local.load_local_download("../../etc", self.home)
        with self.assertRaisesRegex(local.LocalBidRoomError, "No local download"):
            local.load_local_download(REFERENCE, self.home)
        folder = write_download(self.home, {"RFP": pdf_bytes("x")})
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest["reference"] = "AB-2026-00001"
        (folder / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(local.LocalBidRoomError, "not AB-2026-06523"):
            local.load_local_download(REFERENCE, self.home)

    def test_no_verified_files_starts_no_sandbox(self):
        folder = write_download(self.home, {"RFP": pdf_bytes("x")})
        for path in folder.glob("*.pdf"):
            path.unlink()
        with patch.object(bid, "run_live_bid_room_process") as run:
            with self.assertRaisesRegex(local.LocalBidRoomError, "No sandbox was started"):
                local.process_local_bid_room_artifact({"reference": REFERENCE, "fetch_notice": False,
                                                       "profile": {}}, home=self.home)
        run.assert_not_called()


class LocalPayloadAndProcessorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "apc"
        self.work = Path(self.tmp.name) / "sandbox"

    def tearDown(self):
        self.tmp.cleanup()

    def test_downloaded_pdf_text_reaches_evidence_with_complete_coverage(self):
        rfp = pdf_bytes("Supplier must provide a cost estimate FIXTURE-RFP. Closing date: 2026-10-22.")
        addendum = pdf_bytes("Supplier must attend site visit FIXTURE-ADDENDUM.")
        write_download(self.home, {"RFP": rfp, "Addendum_1": addendum})
        download = local.load_local_download(REFERENCE, self.home)
        details = json.loads((ROOT / "tests" / "fixtures" / "procurement" / "apc_re9256.json").read_text())
        details["opportunity"]["referenceNumber"] = REFERENCE
        details["opportunity"]["addendaDocuments"] = [{"id": "a1", "filename": "Addendum.pdf"}]
        payload, uploads = local.build_local_bid_room_payload(
            download, {}, business_context="Estimators", details=details)
        self.assertEqual(payload["warnings"], [])

        self.assertEqual(len(uploads), 2)
        self.assertTrue(all(path.startswith(local.SANDBOX_LOCAL_DIR + "/") for path, _ in uploads))
        self.assertEqual({data for _, data in uploads}, {rfp, addendum})
        self.assertEqual([item["url"] for item in payload["attachments"]], ["", ""])
        self.assertNotIn(b"SECRET-SESSION", b"".join(data for _, data in uploads))
        self.assertNotIn("SECRET-SESSION", json.dumps(payload))

        artifact, namespace = run_processor(payload, uploads, self.work)
        tender = [item for item in artifact["documents"] if item.get("is_tender_document")]
        self.assertEqual([item["status"] for item in tender], ["extracted", "extracted"])
        self.assertEqual(tender[0]["sha256"], hashlib.sha256(rfp).hexdigest())
        text = namespace["evidence_bundle"]["evidence"]["text_for_model"]
        self.assertIn("FIXTURE-RFP", text)
        self.assertIn("FIXTURE-ADDENDUM", text)
        self.assertTrue(artifact["coverage"]["complete"], artifact["coverage"])
        self.assertEqual(artifact["opportunity"]["provenance"], "local_apc_download")

        # Without APC's public notice nothing confirms the download is current: partial, not complete.
        offline, offline_uploads = local.build_local_bid_room_payload(download, {})
        offline_artifact, _ = run_processor(offline, offline_uploads, self.work / "offline")
        self.assertEqual(offline_artifact["coverage"]["status"], "partial")

    def test_bytes_altered_in_transit_and_limits_make_coverage_partial(self):
        files = {f"Doc_{index}": pdf_bytes(f"FIXTURE-{index}") for index in range(7)}
        write_download(self.home, files, complete=False)
        download = local.load_local_download(REFERENCE, self.home)
        payload, uploads = local.build_local_bid_room_payload(download, {})
        self.assertEqual(len(uploads), 5)
        self.assertEqual([item["status"] for item in payload["document_manifest"]].count("not_selected"), 2)
        self.assertTrue(any("not marked complete" in warning for warning in payload["warnings"]))
        tampered = list(uploads)
        tampered[0] = (tampered[0][0], tampered[0][1] + b"%tampered")
        artifact, _ = run_processor(payload, tampered, self.work)
        statuses = [item["status"] for item in artifact["documents"] if item.get("is_tender_document")]
        self.assertIn("local_file_rejected", statuses)
        self.assertEqual(artifact["coverage"]["status"], "partial")
        self.assertFalse(artifact["coverage"]["complete"])

    def test_public_notice_is_merged_and_document_count_drift_is_warned(self):
        write_download(self.home, {"RFP": pdf_bytes("FIXTURE-RFP")})
        details = json.loads((ROOT / "tests" / "fixtures" / "procurement" / "apc_re9256.json").read_text())
        details["opportunity"]["referenceNumber"] = REFERENCE
        details["opportunity"]["addendaDocuments"] = [{"id": "a1", "filename": "Addendum.pdf"}]
        download = local.load_local_download(REFERENCE, self.home)
        payload, _ = local.build_local_bid_room_payload(download, {}, details=details)
        self.assertEqual(payload["documents"][0]["source"], "apc_details")
        self.assertEqual(payload["opportunity"]["reference"], REFERENCE)
        self.assertTrue(any("public metadata lists 2" in warning for warning in payload["warnings"]))


class RunnerUploadTest(unittest.TestCase):
    def test_uploads_are_written_before_the_processor_command(self):
        events = []

        class FakeFiles:
            def write(self, path, data):
                events.append(("write", path, data))

        class FakeCommands:
            def run(self, command, **kwargs):
                events.append(("run",))
                artifact = {"processor": "x", "opportunity": {}, "profile": {}, "documents": [],
                            "evidence": {}, "cohere_analysis": None, "cohere_tool_calls": None}

                class Result:
                    stdout = json.dumps(artifact)
                    stderr = ""
                return Result()

        class FakeSandbox:
            sandbox_id = "sbx-test"
            files = FakeFiles()
            commands = FakeCommands()

            @classmethod
            def create(cls, **kwargs):
                return cls()

            def kill(self, **kwargs):
                events.append(("kill",))
                return True

        fake_module = type(sys)("e2b")
        fake_module.Sandbox = FakeSandbox
        fake_exceptions = type(sys)("e2b.exceptions")
        fake_exceptions.TimeoutException = TimeoutError
        payload = bid.build_sample_payload(cohere_enabled=False)
        with patch.dict(sys.modules, {"e2b": fake_module, "e2b.exceptions": fake_exceptions}), patch.dict(
            os.environ, {"E2B_API_KEY": "test", "CANADABUYS_LOAD_ENV_FILE": "0"}
        ), patch.object(bid, "load_local_env"):
            result = bid._run_e2b_payload(payload, uploads=[("/tmp/workspacealberta-bid-room/local/a.pdf", b"%PDF-1")])
        self.assertEqual(events[0], ("write", "/tmp/workspacealberta-bid-room/local/a.pdf", b"%PDF-1"))
        self.assertEqual(events[1], ("run",))
        self.assertEqual(events[-1], ("kill",))
        self.assertTrue(result.killed)


class AdapterBoundaryTest(unittest.TestCase):
    def test_tool_is_stdio_only(self):
        from mcp_tools import get_mcp_tools
        from procurement_core.service import TOOL_NAMES
        import server as stdio_server

        self.assertNotIn("process_local_bid_room", {tool.name for tool in get_mcp_tools()})
        self.assertNotIn("process_local_bid_room", TOOL_NAMES)
        listed = asyncio.run(stdio_server.handle_list_tools(None, None))
        self.assertIn("process_local_bid_room", {tool.name for tool in listed.tools})
        schema = stdio_server.LOCAL_BID_ROOM_TOOL.input_schema
        self.assertEqual(set(schema["properties"]), {"reference", "business_context", "max_attachments"})
        self.assertFalse(schema["additionalProperties"])

    def test_stdio_call_reports_missing_download_as_error(self):
        import server as stdio_server
        from mcp.types import CallToolRequestParams

        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"WA_APC_HOME": home}):
            result = asyncio.run(stdio_server.handle_call_tool(None, CallToolRequestParams(
                name="process_local_bid_room", arguments={"reference": REFERENCE})))
        self.assertTrue(result.is_error)
        self.assertIn("No local download", result.content[0].text)


if __name__ == "__main__":
    unittest.main()
