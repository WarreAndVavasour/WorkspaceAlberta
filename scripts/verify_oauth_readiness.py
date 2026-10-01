"""Check deployed OAuth discovery and MCP behavior without email or credentials.

Does not create clients, users, grants, subscriptions, or send login codes.
The tagged deployment can differ from the canonical --resource being checked.
This preflight does not certify email delivery or a completed customer sign-in.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify(base_url: str, resource: str, *, client_metadata_url: str | None = None) -> dict:
    base_url, resource = base_url.rstrip("/"), resource.rstrip("/")
    parts = urlsplit(resource)
    issuer = f"{parts.scheme}://{parts.netloc}"
    report = {"endpoint": base_url, "resource": resource,
              "checked_at": datetime.now(timezone.utc).isoformat(), "checks": [],
              "email_delivery": "not tested", "customer_sign_in": "not tested"}
    opener = build_opener(NoRedirects())

    def request(path, expected=200, *, payload=None, form=None, headers=None):
        merged = {"User-Agent": "WorkspaceAlberta-Acceptance/1.0", "Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            merged["Content-Type"] = "application/json"
        if form is not None:
            data = urlencode(form).encode()
            merged["Content-Type"] = "application/x-www-form-urlencoded"
        merged.update(headers or {})
        started = time.monotonic()
        req = Request(base_url + path, data=data, headers=merged)
        try:
            response = opener.open(req, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            status, response_headers = response.status, response.headers
            raw = response.read(1_000_001)
        assert status == expected, f"{path.split('?')[0]}: expected {expected}, got {status}"
        assert len(raw) <= 1_000_000, "Unexpectedly large response"
        body = json.loads(raw) if "json" in response_headers.get("Content-Type", "") else raw.decode()
        report["checks"].append({"path": path.split("?")[0], "method": req.get_method(),
                                  "status": status, "seconds": round(time.monotonic() - started, 3)})
        return body, response_headers

    def rpc(method, params=None, expected=200, headers=None):
        payload = {"jsonrpc": "2.0", "id": len(report["checks"]) + 1, "method": method}
        if params is not None:
            payload["params"] = params
        return request("/mcp", expected, payload=payload, headers=headers)

    health, _ = request("/health")
    assert health["status"] == "ok"
    prm, _ = request("/.well-known/oauth-protected-resource/mcp")
    root_prm, _ = request("/.well-known/oauth-protected-resource")
    assert prm == root_prm
    assert prm["resource"] == resource
    assert prm["authorization_servers"][0] == issuer
    metadata, _ = request("/.well-known/oauth-authorization-server")
    assert metadata["issuer"] == issuer
    for field, path in [("authorization_endpoint", "/authorize"), ("token_endpoint", "/token"),
                        ("registration_endpoint", "/register")]:
        assert metadata[field] == issuer + path
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert {"authorization_code", "refresh_token"} <= set(metadata["grant_types_supported"])
    assert "none" in metadata["token_endpoint_auth_methods_supported"]
    assert metadata["client_id_metadata_document_supported"] is True

    initialized, _ = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                        "clientInfo": {"name": "oauth-readiness", "version": "1"}})
    assert initialized["result"]["serverInfo"]["name"]
    listed, _ = rpc("tools/list")
    tools = listed["result"]["tools"]
    names = [tool["name"] for tool in tools]
    assert names and len(names) == len(set(names))
    for tool in tools:
        assert re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", tool["name"])
        assert tool.get("title", "").strip(), f"Missing title: {tool['name']}"
        annotations = tool.get("annotations", {})
        assert annotations.get("title") == tool["title"], f"Missing annotation title: {tool['name']}"
        assert any(isinstance(annotations.get(hint), bool) for hint in ("readOnlyHint", "destructiveHint"))
    report["tool_count"] = len(tools)
    report["tool_titles"] = {tool["name"]: tool["title"] for tool in tools}
    guide, _ = rpc("tools/call", {"name": "get_server_guide", "arguments": {}})
    assert guide["result"]["isError"] is False

    contract = json.loads(guide["result"]["content"][0]["text"])
    protected = {"list_watchlist"}
    declaration = contract.get("authentication", {})
    if declaration.get("partial_auth"):
        assert declaration["auth_type"] == "none"
        protected.update(declaration["sign_in_tools"])
        protected.update(declaration["pro_tools"])
        report["partial_auth"] = declaration

    for name in sorted(protected):
        for headers in [{}, {"Authorization": "Bearer oauth-readiness-invalid"}]:
            body, response_headers = rpc("tools/call", {"name": name, "arguments": {}},
                                         expected=401, headers=headers)
            assert body["error"] == "invalid_token"
            assert f'resource_metadata="{issuer}/.well-known/oauth-protected-resource/mcp"' in response_headers["WWW-Authenticate"]
    _, rest_headers = request("/tools/list_watchlist", 401, payload={})
    assert "resource_metadata=" in rest_headers["WWW-Authenticate"]
    for form, error in [({"grant_type": "invalid"}, "unsupported_grant_type"),
                        ({"grant_type": "refresh_token", "refresh_token": secrets.token_urlsafe(32)}, "invalid_grant")]:
        body, response_headers = request("/token", 400, form=form)
        assert body["error"] == error
        assert "no-store" in response_headers["Cache-Control"]
    rejected, _ = request("/register", 400, payload={"redirect_uris": ["https://example.invalid/callback"]})
    assert rejected["error"] == "invalid_redirect_uri"

    if client_metadata_url:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(secrets.token_bytes(32)).digest()).rstrip(b"=").decode()
        query = urlencode({"response_type": "code", "client_id": client_metadata_url,
                           "redirect_uri": "http://localhost:3118/callback", "resource": resource,
                           "code_challenge_method": "S256", "code_challenge": challenge,
                           "state": "readiness", "scope": "pro offline_access"})
        page, _ = request("/authorize?" + query)
        assert 'action="/authorize/google"' in page or 'type="email"' in page
        assert 'data-otp=' not in page
        report["client_metadata_authorization_page"] = "passed"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--client-metadata-url", help="Optional CIMD client with a localhost/callback redirect")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.url, args.resource, client_metadata_url=args.client_metadata_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Passed {len(result['checks'])} checks; {result['tool_count']} tools. Customer sign-in not tested.")
    print(f"Evidence: {args.output}")
