"""OAuth2 token management for OPERA Cloud.

Confirmed against rest-api-specs/property/v1/oauth.json (operationId
``getToken``):

- Request: ``POST {base_url}/oauth/v1/tokens`` with an HTTP Basic header of
  base64(``ClientID:ClientSecret``), required header ``x-app-key``, and an
  ``application/x-www-form-urlencoded`` body.
- Form fields: ``grant_type`` (enum: ``password`` | ``client_credentials``);
  ``username`` + ``password`` for the password grant; ``scope`` for the
  client_credentials grant.
- Response (``OAuth2TokenResponse``): ``access_token`` (required),
  ``expires_in`` (seconds, typically 3600), ``token_type`` (``Bearer``),
  ``oracle_tk_context``.

Tokens are cached in memory and refreshed once they are within
``EXPIRY_SKEW_SECONDS`` of expiring.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Settings

EXPIRY_SKEW_SECONDS = 60
DEFAULT_TIMEOUT_SECONDS = 30


class AuthError(Exception):
    """Raised when an OAuth token cannot be obtained or parsed."""


class TokenManager:
    """Fetches and caches an OPERA Cloud OAuth2 access token."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def token(self) -> str:
        """Return a valid access token, fetching a new one when needed."""
        if self._access_token and time.time() < self._expires_at - EXPIRY_SKEW_SECONDS:
            return self._access_token
        self._fetch()
        assert self._access_token is not None
        return self._access_token

    def _fetch(self) -> None:
        """Request a fresh token from the OPERA identity server."""
        s = self._settings
        if not s.base_url or not s.app_key or not s.client_id or not s.client_secret:
            raise AuthError(
                "missing required settings: base_url, app_key, client_id, client_secret"
            )

        form: dict[str, str] = {"grant_type": s.grant_type}
        if s.grant_type == "password":
            form["username"] = s.username
            form["password"] = s.password
        elif s.grant_type == "client_credentials":
            form["scope"] = "urn:opc:hgbu:ws:__myscopes__"

        basic = base64.b64encode(f"{s.client_id}:{s.client_secret}".encode()).decode()
        request = Request(
            url=f"{s.base_url}{s.token_path}",
            data=urlencode(form).encode(),
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "x-app-key": s.app_key,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as resp:
                payload: dict[str, Any] = json.loads(resp.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise AuthError(f"token request failed: HTTP {exc.code}: {detail}") from exc
        except (URLError, json.JSONDecodeError) as exc:
            raise AuthError(f"token request failed: {exc}") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise AuthError("token response missing 'access_token'")
        expires_in = int(payload.get("expires_in", 3600))

        self._access_token = str(access_token)
        self._expires_at = time.time() + expires_in
