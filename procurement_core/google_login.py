"""Google OpenID Connect sign-in upstream of the client-neutral MCP issuer.

Google credentials never become MCP tokens. Only the stable Google subject and
verified Google-hosted email are retained; provider tokens are discarded.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlparse

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from procurement_core import oauth

BROWSER_COOKIE = "__Host-wa_oauth_browser"
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def callback_url() -> str:
    value = os.environ.get("WA_GOOGLE_REDIRECT_URI", "").strip() or oauth.public_origin() + "/oauth/google/callback"
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/oauth/google/callback":
        raise oauth.OAuthError(503, "temporarily_unavailable", "Google callback configuration is invalid.")
    return value


def configuration() -> tuple[str, str]:
    client_id = os.environ.get("WA_GOOGLE_CLIENT_ID", "").strip()
    secret = os.environ.get("WA_GOOGLE_CLIENT_SECRET", "").strip()
    if oauth.login_provider() != "google" or not client_id or not secret:
        raise oauth.OAuthError(503, "temporarily_unavailable", "Google sign-in is not configured.")
    return client_id, secret


def start(params: dict[str, str], browser_secret: str) -> str:
    client_id, _ = configuration()
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    oauth.get_store().put_google_state({
        "state_hash": oauth._hash_secret(state),
        "browser_hash": oauth._hash_secret(browser_secret),
        "nonce": nonce,
        "code_verifier": verifier,
        "authorize_params": params,
        "expires_at": oauth._iso(oauth._utc_now() + timedelta(seconds=oauth.LOGIN_TTL_SECONDS)),
    })
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": callback_url(),
        "response_type": "code", "scope": "openid email",
        "state": state, "nonce": nonce, "prompt": "select_account",
        "code_challenge": oauth._b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
        "code_challenge_method": "S256",
    })


def exchange_and_verify(code: str, verifier: str) -> dict:
    client_id, secret = configuration()
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(TOKEN_URL, data={
                "code": code, "client_id": client_id, "client_secret": secret,
                "redirect_uri": callback_url(), "grant_type": "authorization_code",
                "code_verifier": verifier,
            }, timeout=5, allow_redirects=False)
            if response.status_code != 200:
                raise ValueError("Google rejected the authorization code")
            encoded_token = response.json().get("id_token")
            if not isinstance(encoded_token, str) or not encoded_token:
                raise ValueError("Google returned no ID token")
            transport = Request(session=session)
            # Google's library verifies signature, audience, issuer, iat and exp.
            # Bound certificate fetching to the same short network timeout.
            def bounded_request(url, method="GET", **kwargs):
                kwargs["timeout"] = 5
                return transport(url, method=method, **kwargs)
            return id_token.verify_oauth2_token(encoded_token, bounded_request, client_id)
    except (ValueError, requests.RequestException, GoogleAuthError) as exc:
        # Provider response bodies may contain credentials; never reflect/log them.
        raise oauth.OAuthError(400, "access_denied", "Google sign-in could not be verified. Start again.") from exc


def finish(state: str, code: str, browser_secret: str, error: str = "") -> dict:
    configuration()
    if not state or not browser_secret or len(state) > 256 or len(browser_secret) > 256:
        raise oauth.OAuthError(400, "invalid_request", "Sign-in session missing. Start again.")
    row = oauth.get_store().take_google_state(oauth._hash_secret(state), oauth._hash_secret(browser_secret))
    if not row or oauth._parse_iso(row["expires_at"]) < oauth._utc_now():
        raise oauth.OAuthError(400, "invalid_request", "Sign-in session expired or already used. Start again.")
    if error or not code:
        raise oauth.OAuthError(400, "access_denied", "Google sign-in was cancelled. Start again when ready.")
    claims = exchange_and_verify(code, row["code_verifier"])
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(nonce, row["nonce"]):
        raise oauth.OAuthError(400, "access_denied", "Google sign-in session did not match. Start again.")
    email = oauth.normalize_email(str(claims.get("email") or ""))
    subject = claims.get("sub")
    if claims.get("email_verified") is not True or not isinstance(subject, str) or not subject or len(subject) > 255:
        raise oauth.OAuthError(400, "access_denied", "A verified Google identity is required.")
    # Billing currently links by email. Google is authoritative for Gmail and
    # Workspace addresses, but not for third-party addresses added to an account.
    if not email.endswith("@gmail.com") and not claims.get("hd"):
        raise oauth.OAuthError(400, "access_denied", "Use a Gmail or Google Workspace account so we can verify ownership of your subscription email.")
    if "@" not in email or len(email) > 320:
        raise oauth.OAuthError(400, "access_denied", "A verified email is required.")
    user = oauth.get_store().google_user(subject, email)
    return oauth.create_consent(user, {**row["authorize_params"], "browser_hash": row["browser_hash"]})
