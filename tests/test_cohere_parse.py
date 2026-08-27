"""Unit tests for Cohere Parse helpers. HTTP is mocked — no live credits."""

from __future__ import annotations

import json
import unittest
from urllib.error import HTTPError, URLError
from io import BytesIO

from procurement_core.cohere_parse import (
    EXTRACT_FALLBACK,
    PARSE_MODEL_DEFAULT,
    PARSE_URL,
    build_parse_request,
    call_cohere_parse,
    markdown_from_parse_response,
    parse_kind,
    run_parse_or_fallback,
    summarize_extract_methods,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class CohereParseTest(unittest.TestCase):
    def test_parse_kind_routes_images_and_pdfs_only(self) -> None:
        self.assertEqual(parse_kind("drawing.png"), "image")
        self.assertEqual(parse_kind("scan.JPG"), "image")
        self.assertEqual(parse_kind("page.bin", "image/jpeg"), "image")
        self.assertEqual(parse_kind("specs.pdf"), "pdf")
        self.assertEqual(parse_kind("notice", "application/pdf"), "pdf")
        self.assertEqual(parse_kind("scope.docx"), "")
        self.assertEqual(parse_kind("prices.xlsx"), "")
        self.assertEqual(parse_kind("bundle.zip"), "")

    def test_build_parse_request_uses_official_image_url_only(self) -> None:
        body = build_parse_request(b"fake-image", "image/png", PARSE_MODEL_DEFAULT)
        self.assertEqual(body["model"], "parse-v5.0")
        self.assertEqual(body["output_format"], "markdown")
        self.assertEqual(body["document"]["type"], "image_url")
        self.assertTrue(body["document"]["image_url"].startswith("data:image/png;base64,"))
        self.assertNotIn("file", body["document"])
        self.assertNotIn("pdf", json.dumps(body["document"]))

    def test_markdown_from_parse_response_joins_pages(self) -> None:
        markdown = markdown_from_parse_response({
            "pages": [
                {"type": "markdown", "index": 0, "markdown": {"content": "# Page one\nA table"}},
                {"type": "markdown", "index": 1, "markdown": {"content": "## Page two"}},
            ]
        })
        self.assertIn("# Page one", markdown)
        self.assertIn("## Page two", markdown)

    def test_call_cohere_parse_posts_to_official_endpoint(self) -> None:
        captured: dict = {}

        def opener(request, timeout=None):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["auth"] = request.get_header("Authorization")
            captured["body"] = json.loads(request.data)
            return _FakeResponse({
                "id": "parse-1",
                "pages": [{"type": "markdown", "index": 0, "markdown": {"content": "Steel spec"}}],
            })

        result = call_cohere_parse(
            b"png-bytes",
            "image/png",
            "test-key",
            opener=opener,
        )
        self.assertEqual(captured["url"], PARSE_URL)
        self.assertEqual(captured["auth"], "Bearer test-key")
        self.assertEqual(captured["body"]["document"]["type"], "image_url")
        self.assertEqual(captured["body"]["model"], "parse-v5.0")
        self.assertEqual(result["pages"][0]["markdown"]["content"], "Steel spec")

    def test_call_cohere_parse_maps_http_and_timeout_errors(self) -> None:
        def http_opener(request, timeout=None):
            raise HTTPError(PARSE_URL, 400, "bad", hdrs=None, fp=BytesIO(b'{"message":"no"}'))

        with self.assertRaises(RuntimeError) as http_exc:
            call_cohere_parse(b"x", "image/png", "test-key", opener=http_opener)
        self.assertIn("parse_http_400", str(http_exc.exception))

        def timeout_opener(request, timeout=None):
            raise URLError("timed out")

        with self.assertRaises(RuntimeError) as timeout_exc:
            call_cohere_parse(b"x", "image/png", "test-key", opener=timeout_opener)
        self.assertEqual(str(timeout_exc.exception), "parse_timeout")

    def test_run_parse_or_fallback_prefers_parse_then_keeps_extractor(self) -> None:
        text, method, error = run_parse_or_fallback(
            "image",
            True,
            "test-key",
            lambda: "# Parsed table",
            lambda: "plain extract",
        )
        self.assertEqual(text, "# Parsed table")
        self.assertEqual(method, "parse-v5.0")
        self.assertEqual(error, "")

        text, method, error = run_parse_or_fallback(
            "pdf",
            True,
            "test-key",
            lambda: (_ for _ in ()).throw(RuntimeError("parse_http_503: down")),
            lambda: "pdfminer text",
        )
        self.assertEqual(text, "pdfminer text")
        self.assertEqual(method, EXTRACT_FALLBACK)
        self.assertIn("parse_http_503", error)

        text, method, error = run_parse_or_fallback(
            "image",
            True,
            "",
            lambda: self.fail("Parse must not run without a key"),
            lambda: "fallback after unset",
        )
        self.assertEqual(method, EXTRACT_FALLBACK)
        self.assertEqual(error, "parse_unset")

        text, method, error = run_parse_or_fallback(
            "",
            True,
            "test-key",
            lambda: self.fail("Parse must not run for DOCX"),
            lambda: "docx extract",
        )
        self.assertEqual(text, "docx extract")
        self.assertEqual(error, "unsupported_mime")

    def test_summarize_extract_methods_lists_parse_vs_fallback(self) -> None:
        summary = summarize_extract_methods([
            {"name": "notice.txt", "extract_method": "inline"},
            {"name": "specs.pdf", "extract_method": "parse-v5.0"},
            {"name": "prices.xlsx", "extract_method": "fallback"},
        ])
        self.assertEqual(summary["model"], "parse-v5.0")
        self.assertEqual(summary["files_used_parse"], ["specs.pdf"])
        self.assertEqual(summary["files_used_fallback"], ["prices.xlsx"])


if __name__ == "__main__":
    unittest.main()
