import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "mcp-servers" / "canadabuys"
TEST_DATA_DIR = tempfile.TemporaryDirectory()

os.environ["CANADABUYS_DATA_DIR"] = TEST_DATA_DIR.name
os.environ.setdefault("WA_OAUTH_STORE", "memory")
os.environ.setdefault("WA_OAUTH_SIGNING_KEY", "test-oauth-signing-key")
sys.path.insert(0, str(SERVER_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from server_http import app  # noqa: E402


class ProcurementHttpAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_apc_missing_document_access_is_rest_and_mcp_error_before_e2b(self):
        details = json.loads((ROOT / "tests/fixtures/procurement/apc_re9256.json").read_text())
        with patch("server_http.check_tool_access", return_value=None), patch(
            "procurement_core.service.get_alberta_api_details", return_value=details
        ), patch("procurement_core.service.resolve_profile", return_value={}), patch(
            "procurement_core.e2b_bid_room.run_live_bid_room_process"
        ) as run:
            response = self.client.post("/bid-room/process", json={"reference": "AB-2026-06584"})
            self.assertEqual(response.status_code, 400)
            self.assertIn("No sandbox was started", response.json()["detail"])
            response = self.client.post("/mcp", headers={"Accept": "application/json"}, json={
                "jsonrpc": "2.0", "id": 21, "method": "tools/call",
                "params": {"name": "process_bid_room", "arguments": {"reference": "AB-2026-06584"}},
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["result"]["isError"])
            self.assertIn("No sandbox was started", response.json()["result"]["content"][0]["text"])
            run.assert_not_called()

    def test_mcp_public_copy_argument_routes_actual_pdf_content_to_processor(self):
        from tests.test_apc_documents import COPY_URL, DOCUMENT_ID, LocalAPCPDFProcessingTest
        from procurement_core.e2b_bid_room import BidRoomSandboxResult
        helper = LocalAPCPDFProcessingTest()
        helper.setUp()
        pdf = helper.pdf_bytes("Supplier must provide control panel certification MCP-PDF-BODY.")

        def local_processor(payload, **kwargs):
            artifact, requests, namespace = helper.process(payload, {"re9256.pdf": pdf})
            self.assertEqual(requests, [COPY_URL])
            self.assertIn("MCP-PDF-BODY", namespace["evidence_bundle"]["evidence"]["text_for_model"])
            return BidRoomSandboxResult("local-only", True, artifact, "", "")

        with patch("server_http.check_tool_access", return_value=None), patch(
            "procurement_core.service.get_alberta_api_details", return_value=helper.details
        ), patch("procurement_core.service.resolve_profile", return_value={}), patch(
            "procurement_core.e2b_bid_room.run_live_bid_room_process", side_effect=local_processor
        ) as run:
            response = self.client.post("/mcp", headers={"Accept": "application/json"}, json={
                "jsonrpc": "2.0", "id": 22, "method": "tools/call", "params": {
                    "name": "process_bid_room", "arguments": {"reference": "AB-2026-06584",
                    "apc_document_urls": {DOCUMENT_ID: COPY_URL}},
                },
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["result"]["isError"])
            self.assertIn("1 of 1 procurement files extracted", response.json()["result"]["content"][0]["text"])
            self.assertIn(f"{len(pdf)} bytes", response.json()["result"]["content"][0]["text"])
            run.assert_called_once()

    def test_health_tools_openapi_and_generic_tool(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        health_body = health.json()
        self.assertEqual(health_body["status"], "ok")
        self.assertEqual(health_body["mcp"], {"streamable_http": "/mcp"})

        old_sse = self.client.get("/sse")
        self.assertEqual(old_sse.status_code, 404)

        # Stateless mode has no server-push stream; GET must fail fast, not hang.
        mcp_probe = self.client.get("/mcp", headers={"Accept": "text/event-stream"})
        self.assertEqual(mcp_probe.status_code, 405)

        tools = self.client.get("/tools")
        self.assertEqual(tools.status_code, 200)
        tool_names = {tool["name"] for tool in tools.json()["tools"]}
        self.assertIn("search_opportunities", tool_names)
        self.assertIn("daily_bid_brief", tool_names)
        self.assertIn("process_bid_room", tool_names)
        self.assertIn("classify_tender", tool_names)

        openapi = self.client.get("/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/search", openapi.json()["paths"])
        self.assertIn("/bid-room/process", openapi.json()["paths"])
        self.assertIn("/bid-room/classify", openapi.json()["paths"])

        missing_reference = self.client.post("/bid-room/process", json={})
        self.assertEqual(missing_reference.status_code, 400)
        self.assertIn("reference", missing_reference.json()["detail"].lower())

        missing_reference = self.client.post("/bid-room/classify", json={})
        self.assertEqual(missing_reference.status_code, 400)
        self.assertIn("reference", missing_reference.json()["detail"].lower())
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            not_configured = self.client.post("/bid-room/classify", json={"reference": "AB-2026-06584"})
        self.assertEqual(not_configured.status_code, 503)
        self.assertEqual(not_configured.json()["detail"], "Requirement classification is not configured on this server.")

        cohere_status = self.client.post("/tools/check_cohere_status", json={})
        self.assertEqual(cohere_status.status_code, 200)
        self.assertIn(
            "This status check does not call the model",
            cohere_status.json()["content"],
        )

    def test_landing_page(self) -> None:
        landing = self.client.get("/")
        self.assertEqual(landing.status_code, 200)
        self.assertIn("text/html", landing.headers["content-type"])
        self.assertIn("/mcp", landing.text)
        self.assertIn("mcpServers", landing.text)

    def test_extended_card_still_validates_legacy_keys(self) -> None:
        with patch("server_http.validate_key", return_value={"status": "active"}) as validate:
            response = self.client.get(
                "/agent/authenticatedExtendedCard",
                headers={"Authorization": "Bearer wa_live_test"},
            )
        validate.assert_called_once_with("wa_live_test")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])

    def test_cors_preflight(self) -> None:
        preflight = self.client.options(
            "/mcp",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization,mcp-session-id",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers["access-control-allow-origin"], "*")

    def test_mcp_stateless_json_only_accept(self) -> None:
        initialize = self.client.post(
            "/mcp",
            headers={"Accept": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        self.assertEqual(initialize.status_code, 200)
        self.assertEqual(initialize.json()["result"]["serverInfo"]["name"], "canadabuys")

        # Stateless: a fresh request with no mcp-session-id header still works.
        tools = self.client.post(
            "/mcp",
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        self.assertEqual(tools.status_code, 200)
        tool_names = {tool["name"] for tool in tools.json()["result"]["tools"]}
        self.assertIn("search_opportunities", tool_names)

    def test_discovery_endpoints(self) -> None:
        # A2A agent card at every location crawlers have probed.
        for path in (
            "/.well-known/agent.json",
            "/.well-known/agent-card.json",
            "/agents/.well-known/agent-card.json",
            "/mcp/.well-known/agent-card.json",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            card = response.json()
            self.assertEqual(card["name"], "WorkspaceAlberta Procurement")
            self.assertTrue(card["url"].endswith("/mcp"), path)
            skill_ids = {skill["id"] for skill in card["skills"]}
            self.assertIn("search_opportunities", skill_ids)
            self.assertIn("daily_bid_brief", skill_ids)

        # Extended card is spec-correct: 401 + challenge without a key.
        extended = self.client.get("/agent/authenticatedExtendedCard")
        self.assertEqual(extended.status_code, 401)
        self.assertEqual(extended.headers["www-authenticate"], "Bearer")

        # RFC 9728 protected-resource metadata.
        prm = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(prm.status_code, 200)
        self.assertTrue(prm.json()["resource"].endswith("/mcp"))
        self.assertEqual(prm.json()["bearer_methods_supported"], ["header"])

        # RFC 8414 auth-server metadata for the in-process OAuth 2.1 server.
        as_meta = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(as_meta.status_code, 200)
        self.assertIn("issuer", as_meta.json())
        self.assertIn("authorization_code", as_meta.json()["grant_types_supported"])
        self.assertEqual(as_meta.json()["code_challenge_methods_supported"], ["S256"])

        # MCP discovery mirrors the registry entry.
        mcp_meta = self.client.get("/.well-known/mcp.json")
        self.assertEqual(mcp_meta.status_code, 200)
        self.assertEqual(mcp_meta.json()["name"], "io.github.HarleyCoops/workspace-alberta")
        self.assertTrue(mcp_meta.json()["remotes"][0]["url"].endswith("/mcp"))


class InlineProfileTest(unittest.TestCase):
    def test_inline_profile_resolves(self) -> None:
        from procurement_core.service import resolve_profile

        profile = resolve_profile(
            {
                "profile": {
                    "company_name": "Test Fab",
                    "location": "Edmonton, Alberta",
                    "description": "structural steel fabrication and welding",
                }
            }
        )
        self.assertEqual(profile["company_name"], "Test Fab")
        self.assertIn("steel", profile["industries"])
        self.assertTrue(profile["capabilities"])

    def test_profile_arg_declared_on_matching_tools(self) -> None:
        from mcp_tools import get_mcp_tools

        by_name = {tool.name: tool for tool in get_mcp_tools()}
        for name in (
            "find_opportunities",
            "find_matching_opportunities",
            "daily_bid_brief",
            "find_business_fit",
            "search_opportunities",
            "find_alberta_opportunities",
            "process_bid_room",
            "analyze_contract_with_cohere",
        ):
            self.assertIn("profile", by_name[name].input_schema["properties"], name)


if __name__ == "__main__":
    unittest.main()


class FirstRunQaPagesTest(unittest.TestCase):
    """Regression tests for the October 2026 first-run QA pass."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        import server_http

        self.client = TestClient(server_http.app)

    def test_landing_shows_one_public_url_and_paths_to_try_and_pricing(self) -> None:
        html = self.client.get("/").text
        self.assertIn("https://elbowsupknivesout.warreandvavasour.com/mcp", html)
        self.assertNotIn("run.app", html)
        self.assertIn('href="/try"', html)
        self.assertIn('href="/pricing"', html)
        self.assertNotIn('href="/me"', html)
        self.assertIn('lang="fr"', html)

    def test_pricing_has_price_checkout_and_terms(self) -> None:
        html = self.client.get("/pricing").text
        self.assertIn("C$85", html)
        self.assertIn("buy.stripe.com", html)
        self.assertIn('id="terms"', html)
        self.assertEqual(self.client.get("/terms", follow_redirects=False).status_code, 302)

    def test_me_in_browser_is_a_page_not_json(self) -> None:
        response = self.client.get("/me", headers={"accept": "text/html"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sign-in happens inside your AI app", response.text)
        self.assertEqual(self.client.get("/me", headers={"accept": "application/json"}).status_code, 401)

    def test_browser_404_is_html_and_api_404_is_json(self) -> None:
        html = self.client.get("/no-such-page", headers={"accept": "text/html"})
        self.assertEqual(html.status_code, 404)
        self.assertIn("Page not found", html.text)
        api = self.client.get("/no-such-page", headers={"accept": "application/json"})
        self.assertEqual(api.json(), {"detail": "Not Found"})

    def test_rest_rejects_unknown_fields_and_wrong_types(self) -> None:
        unknown = self.client.post("/search", json={"query": "concrete"})
        self.assertEqual(unknown.status_code, 422)
        self.assertIn("keywords", str(unknown.json()))
        wrong = self.client.post("/search", json={"keywords": ["x"]})
        self.assertEqual(wrong.status_code, 422)
        negative = self.client.post("/deadlines", json={"days": -30})
        self.assertEqual(negative.status_code, 422)
        too_long = self.client.post("/search", json={"keywords": "x" * 5000})
        self.assertEqual(too_long.status_code, 422)

    def test_docs_show_real_search_fields_and_hide_internal_routes(self) -> None:
        schema = self.client.get("/openapi.json").json()
        body = schema["paths"]["/search"]["post"]["requestBody"]["content"]["application/json"]
        self.assertIn("keywords", body["schema"]["properties"])
        self.assertEqual(body["example"]["keywords"], "concrete")
        self.assertNotIn("/stripe/webhook", schema["paths"])
        self.assertNotIn("/requirements-board-template", schema["paths"])

    def test_try_search_requires_a_word(self) -> None:
        response = self.client.post("/try/search", json={"keywords": "  "})
        self.assertEqual(response.status_code, 422)
        self.assertIn("message", response.json())

    def test_authorize_unknown_client_never_redirects(self) -> None:
        response = self.client.get(
            "/authorize",
            params={"response_type": "code", "client_id": "wa_cli_unknown", "redirect_uri": "http://127.0.0.1:9/x",
                    "code_challenge": "a" * 43, "code_challenge_method": "S256", "state": "s"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("This sign-in link did not work", response.text)

    def test_terms_supports_head(self) -> None:
        self.assertEqual(self.client.head("/terms", follow_redirects=False).status_code, 302)

    def test_canadabuys_record_without_notice_url_gets_notice_page(self) -> None:
        from procurement_core.service import _opportunity_record

        record = _opportunity_record({"reference": "cb-922-97825427", "source": "CanadaBuys"})
        self.assertEqual(record["url"], "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-922-97825427")
