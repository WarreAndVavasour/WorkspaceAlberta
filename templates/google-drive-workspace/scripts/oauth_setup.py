#!/usr/bin/env python3
"""
Google Drive OAuth Setup Wizard.

This script walks users through authorizing Google Drive access.
It starts a local server to handle the OAuth callback.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import Flow

TOKEN_PATH = Path(__file__).resolve().parent.parent / ".credentials" / "google-token.json"
REDIRECT_URI = "http://localhost:3000/callback"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

COLORS = {
    "reset": "\x1b[0m",
    "bright": "\x1b[1m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "red": "\x1b[31m",
    "cyan": "\x1b[36m",
}


def log(message: str, color: str = "") -> None:
    print(f"{color}{message}{COLORS['reset']}")


def check_secrets() -> tuple[str, str]:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        log("\n[ERROR] Missing Google credentials!", COLORS["red"])
        log("\nPlease add these secrets to your GitHub Codespaces settings:", COLORS["yellow"])
        log("  1. Go to: https://github.com/settings/codespaces")
        log("  2. Add GOOGLE_CLIENT_ID")
        log("  3. Add GOOGLE_CLIENT_SECRET")
        log("  4. Rebuild this Codespace")
        log("\nSee SETUP-GUIDE.md for detailed instructions.\n")
        raise SystemExit(1)

    return client_id, client_secret


class _CallbackServer(HTTPServer):
    code: Optional[str] = None
    error: Optional[str] = None
    event: threading.Event


class _CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]

        if error:
            self.server.error = error  # type: ignore[attr-defined]
            self._send_error_page(error)
            self.server.event.set()  # type: ignore[attr-defined]
            return

        if not code:
            self.server.error = "No authorization code received"  # type: ignore[attr-defined]
            self._send_error_page("No authorization code received")
            self.server.event.set()  # type: ignore[attr-defined]
            return

        self.server.code = code  # type: ignore[attr-defined]
        self._send_success_page()
        self.server.event.set()  # type: ignore[attr-defined]

    def _send_success_page(self) -> None:
        html = """
<html>
  <head>
    <style>
      body { font-family: system-ui; max-width: 600px; margin: 100px auto; text-align: center; }
      h1 { color: #10B981; }
      p { color: #6B7280; }
    </style>
  </head>
  <body>
    <h1>Authorization Successful!</h1>
    <p>You can close this window and return to your Codespace.</p>
    <p>Run <code>python scripts/test_connection.py</code> to verify the connection.</p>
  </body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_error_page(self, message: str) -> None:
        html = f"<h1>Error: {message}</h1>"
        self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def _build_flow(client_id: str, client_secret: str) -> Flow:
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)


def run_oauth_flow() -> None:
    log("\n========================================", COLORS["cyan"])
    log("  Google Drive OAuth Setup Wizard", COLORS["bright"])
    log("========================================\n", COLORS["cyan"])

    client_id, client_secret = check_secrets()
    log("[OK] Found Google credentials", COLORS["green"])

    if TOKEN_PATH.exists():
        log("[OK] Found existing authorization token", COLORS["green"])
        log("\nYou are already authorized! Run \"python scripts/test_connection.py\" to verify.\n")
        answer = input("Do you want to re-authorize? (y/N): ").strip().lower()
        if answer != "y":
            log("\nKeeping existing authorization.\n")
            return

    flow = _build_flow(client_id, client_secret)
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    log("\n[STEP 1] Opening browser for authorization...", COLORS["yellow"])
    log("\nIf the browser does not open, visit this URL:", COLORS["cyan"])
    log(auth_url)
    log("")

    server = _CallbackServer(("localhost", 3000), _CallbackHandler)
    server.event = threading.Event()

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log("[OK] Local callback server running on port 3000", COLORS["green"])

    try:
        webbrowser.open(auth_url)
    except Exception:
        log("Could not open browser automatically. Please visit the URL above.", COLORS["yellow"])

    server.event.wait()
    server.shutdown()
    thread.join()

    if server.error:
        log(f"\n[ERROR] Authorization failed: {server.error}", COLORS["red"])
        raise SystemExit(1)

    if not server.code:
        log("\n[ERROR] Authorization failed: No code received", COLORS["red"])
        raise SystemExit(1)

    try:
        log("[STEP 2] Received authorization code, exchanging for tokens...", COLORS["yellow"])
        flow.fetch_token(code=server.code)
        credentials = flow.credentials

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")

        log("\n[OK] Authorization successful!", COLORS["green"])
        log("[OK] Token saved to .credentials/google-token.json", COLORS["green"])
        log("\n========================================", COLORS["cyan"])
        log("  Setup Complete!", COLORS["bright"])
        log("========================================", COLORS["cyan"])
        log("\nNext steps:")
        log("  1. Run: python scripts/test_connection.py")
        log("  2. Open AI chat (Ctrl+Shift+I)")
        log("  3. Ask about your Google Drive files!\n")
    except Exception as exc:
        log(f"\n[ERROR] Authorization failed: {exc}", COLORS["red"])
        raise SystemExit(1)


if __name__ == "__main__":
    run_oauth_flow()
