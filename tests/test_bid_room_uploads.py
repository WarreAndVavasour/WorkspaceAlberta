"""APC bring-your-own-documents uploads: tokens, storage, coverage, wiring."""

import io
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="bid-room-uploads-tests-"))

from fastapi.testclient import TestClient

from procurement_core import bid_room_uploads as up, e2b_bid_room as bid, service, storage

FIXTURE = Path(__file__).parent / "fixtures" / "procurement" / "apc_re9256.json"
PDF_NAME = "RE9256 - Contract Services Kirriemuir Hamlet Water Station Electrical Supply Installation.pdf"
PDF = b"%PDF-1.7\n" + b"x" * 200
REFERENCE = "AB-2026-06584"
TENANT = "user:1234"
ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-key",
    "WA_OAUTH_SIGNING_KEY": "k" * 40,
    "WA_PUBLIC_ORIGIN": "https://wa.example.test",
}


class FakeStorage:
    """In-memory stand-in for the Supabase Storage REST calls we make."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, path, *, payload=None, raw=False, timeout=30):
        from urllib.parse import unquote

        self.calls.append((method, path))
        if method == "POST" and path == "bucket":
            return {"name": up.BUCKET}
        if method == "POST" and path.startswith(f"object/upload/sign/{up.BUCKET}/"):
            key = unquote(path.split(f"object/upload/sign/{up.BUCKET}/", 1)[1])
            return {"url": f"/object/upload/sign/{up.BUCKET}/{key}?token=signed"}
        if method == "POST" and path == f"object/list/{up.BUCKET}":
            prefix = payload["prefix"]
            return [
                {"name": key[len(prefix):], "id": key, "metadata": {"size": len(data)}}
                for key, data in sorted(self.objects.items()) if key.startswith(prefix)
            ]
        if method == "GET" and path.startswith(f"object/authenticated/{up.BUCKET}/"):
            return self.objects[unquote(path.split(f"object/authenticated/{up.BUCKET}/", 1)[1])]
        if method == "DELETE" and path == f"object/{up.BUCKET}":
            for key in payload["prefixes"]:
                self.objects.pop(key, None)
            return []
        raise AssertionError(f"unexpected storage call {method} {path}")

    def put(self, claims, name, data):
        self.objects[f"{up.session_prefix(claims)}/{name}"] = data


class UploadTestCase(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.fake = FakeStorage()
        self.storage_patch = patch.object(up, "_storage_request", self.fake)
        self.storage_patch.start()
        up._bucket_ready = False
        self.details = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def tearDown(self):
        self.storage_patch.stop()
        self.env.stop()


class TokenTest(UploadTestCase):
    def test_round_trip_binds_reference_and_tenant(self):
        token = up.create_upload_token(REFERENCE, TENANT)
        claims = up.verify_upload_token(token, reference=REFERENCE, tenant=TENANT)
        self.assertEqual(claims["r"], REFERENCE)
        self.assertNotIn("1234", token)  # the tenant id is hashed, not embedded
        with self.assertRaisesRegex(up.UploadError, "not AB-2026-00001"):
            up.verify_upload_token(token, reference="AB-2026-00001")
        with self.assertRaisesRegex(up.UploadError, "different account"):
            up.verify_upload_token(token, tenant="user:other")

    def test_tampered_and_expired_tokens_are_rejected(self):
        token = up.create_upload_token(REFERENCE, TENANT)
        prefix, body, sig = token.split(".")
        with self.assertRaisesRegex(up.UploadError, "not valid"):
            up.verify_upload_token(f"{prefix}.{body}x.{sig}")
        old = up.create_upload_token(REFERENCE, TENANT, now=time.time() - up.TOKEN_TTL_SECONDS - 5)
        with self.assertRaisesRegex(up.UploadError, "expired"):
            up.verify_upload_token(old)

    def test_upload_requests_are_limited(self):
        with self.assertRaisesRegex(up.UploadError, "only PDF"):
            up.validate_upload_request("evil.exe", 10, [])
        with self.assertRaisesRegex(up.UploadError, "upload limit"):
            up.validate_upload_request("big.pdf", up.MAX_UPLOAD_BYTES + 1, [])
        with self.assertRaisesRegex(up.UploadError, "total limit"):
            up.validate_upload_request("a.pdf", 10, [{"bytes": up.MAX_SESSION_BYTES}])
        self.assertEqual(up.validate_upload_request("../../etc/Spec s.pdf", 10, []), "Spec s.pdf")


class LoadUploadsTest(UploadTestCase):
    def test_download_all_zip_is_expanded_and_checked_against_apc(self):
        from procurement_core.apc_documents import apc_document_manifest

        claims = up.verify_upload_token(up.create_upload_token(REFERENCE, TENANT))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(f"docs/{PDF_NAME}", PDF)
            archive.writestr("notes.pdf", b"not a pdf")
            archive.writestr("__MACOSX/._junk", b"junk")
        self.fake.put(claims, "AB-2026-06584.zip", buffer.getvalue())
        download = up.load_uploaded_files(claims, apc_manifest=apc_document_manifest(self.details))
        by_name = {item["name"]: item for item in download["files"]}
        self.assertEqual(by_name[PDF_NAME]["status"], "verified")
        self.assertEqual(by_name["notes.pdf"]["status"], "bad_signature")
        self.assertNotIn("._junk", by_name)
        self.assertTrue(download["complete"])
        self.assertEqual(download["expected_documents"], 1)

    def test_missing_apc_documents_are_reported(self):
        from procurement_core.apc_documents import apc_document_manifest

        claims = up.verify_upload_token(up.create_upload_token(REFERENCE, TENANT))
        self.fake.put(claims, "something-else.pdf", PDF)
        download = up.load_uploaded_files(claims, apc_manifest=apc_document_manifest(self.details))
        self.assertFalse(download["complete"])
        self.assertTrue(any("Not uploaded yet" in item for item in download["warnings"]))

    def test_empty_session_explains_next_step(self):
        claims = up.verify_upload_token(up.create_upload_token(REFERENCE, TENANT))
        with self.assertRaisesRegex(up.UploadError, "No documents have been uploaded"):
            up.load_uploaded_files(claims)


class ServiceWiringTest(UploadTestCase):
    def _run(self, args):
        token = storage.set_tenant(TENANT)
        try:
            with patch.object(service, "get_alberta_api_details", return_value=self.details), patch.object(
                service, "resolve_profile", return_value={}
            ):
                return service.process_bid_room_artifact(args)
        finally:
            storage.reset_tenant(token)

    def test_gated_apc_posting_returns_an_upload_link_not_an_error(self):
        with patch.object(bid, "run_live_bid_room_process") as run:
            result = self._run({"reference": REFERENCE})
        run.assert_not_called()
        self.assertTrue(result["upload_required"])
        self.assertTrue(result["upload_url"].startswith("https://wa.example.test/bid-room/upload/wabr1."))
        self.assertIn("upload_token", result["markdown"])
        self.assertIn(PDF_NAME, result["markdown"])
        self.assertFalse(result["markdown"].startswith("Error"))

    def test_uploaded_files_reach_the_sandbox_and_are_deleted(self):
        upload_token = up.create_upload_token(REFERENCE, TENANT)
        claims = up.verify_upload_token(upload_token)
        self.fake.put(claims, PDF_NAME, PDF)
        fake_result = bid.BidRoomSandboxResult(
            sandbox_id="sbx", killed=True,
            artifact={"documents": [], "warnings": [], "evidence": {}, "coverage": {}}, stdout="", stderr="",
        )
        with patch.object(bid, "run_live_bid_room_process", return_value=fake_result) as run, patch.object(
            bid, "render_bid_room_markdown", return_value="# review"
        ):
            result = self._run({"reference": REFERENCE, "upload_token": upload_token})
        payload = run.call_args.args[0]
        uploads = run.call_args.kwargs["uploads"]
        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0][1], PDF)
        self.assertEqual(payload["attachments"][0]["kind"], "apc_local_document")
        self.assertEqual(payload["opportunity"]["provenance"], "user_upload")
        self.assertEqual(result["markdown"], "# review")
        self.assertEqual(self.fake.objects, {})

    def test_token_from_another_account_is_refused(self):
        upload_token = up.create_upload_token(REFERENCE, "user:someone-else")
        with self.assertRaisesRegex(ValueError, "different account"):
            self._run({"reference": REFERENCE, "upload_token": upload_token})

    def test_without_storage_the_old_message_remains(self):
        with patch.dict(os.environ, {"SUPABASE_URL": ""}), patch.object(bid, "run_live_bid_room_process") as run:
            with self.assertRaisesRegex(ValueError, "No sandbox was started"):
                self._run({"reference": REFERENCE})
        run.assert_not_called()


class UploadPageTest(UploadTestCase):
    def setUp(self):
        super().setUp()
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
        from server_http import app

        self.client = TestClient(app)
        self.token = up.create_upload_token(REFERENCE, TENANT)

    def test_page_and_signing(self):
        with patch("procurement_core.bid_room_upload_http._expected_documents", return_value=[PDF_NAME]):
            page = self.client.get(f"/bid-room/upload/{self.token}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(REFERENCE, page.text)
        self.assertIn("no-store", page.headers["cache-control"])
        self.assertEqual(page.headers["referrer-policy"], "no-referrer")
        signed = self.client.post(f"/bid-room/upload/{self.token}/sign", json={"name": "Spec.pdf", "size": 100})
        self.assertEqual(signed.status_code, 200)
        self.assertTrue(signed.json()["upload_url"].startswith("https://example.supabase.co/storage/v1/object/upload/sign/"))
        refused = self.client.post(f"/bid-room/upload/{self.token}/sign", json={"name": "x.exe", "size": 100})
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(self.client.get(f"/bid-room/upload/{self.token}/files").json()["files"], [])

    def test_bad_link_is_404(self):
        self.assertEqual(self.client.get("/bid-room/upload/wabr1.nope.nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
