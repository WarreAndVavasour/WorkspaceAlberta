"""MCP-compliant OAuth 2.1 authorization server for the hosted endpoint.

workspaceAlberta keeps a single public Streamable HTTP resource
(``https://elbowsupknivesout.warreandvavasour.com/mcp``) and acts as its
own authorization server on the same Canadian origin (Cloud Run in Montréal,
state in the Toronto Supabase project).

This implementation owns the MCP authorization endpoints and consent flow;
Supabase PostgreSQL holds identity and OAuth state. Supabase Auth also offers
an OAuth server, but is not the token issuer used by this implementation.
Hosted sign-in uses Google OIDC when WA_LOGIN_PROVIDER=google. The optional
legacy email-code mode uses a separate SMTP provider.

Tokens are audience-bound to the canonical MCP resource. ``wa_live_``
subscriber keys remain a legacy Bearer path and are handled in
``procurement_core.auth`` / ``procurement_core.identity``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import secrets
import smtplib
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from procurement_core.auth import GateError, supabase_config


DEFAULT_PUBLIC_ORIGIN = "https://elbowsupknivesout.warreandvavasour.com"
DEFAULT_MCP_RESOURCE = f"{DEFAULT_PUBLIC_ORIGIN}/mcp"
ACCESS_PREFIX = "wa_at_"
REFRESH_PREFIX = "wa_rt_"
CLIENT_PREFIX = "wa_cli_"
SCOPE_PRO = "pro"
SCOPE_OFFLINE = "offline_access"
SUPPORTED_SCOPES = (SCOPE_PRO, SCOPE_OFFLINE)
CODE_TTL_SECONDS = 600
ACCESS_TTL_SECONDS = 900
REFRESH_TTL_SECONDS = 30 * 24 * 3600
LOGIN_TTL_SECONDS = 600
CIMD_CACHE_TTL_SECONDS = 300
MAX_OTP_ATTEMPTS = 5
CIMD_MAX_BYTES = 64 * 1024

CLAUDE_REDIRECTS = frozenset(
    {
        "https://claude.ai/api/mcp/auth_callback",
        "https://claude.com/api/mcp/auth_callback",
    }
)
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

FetchJson = Callable[[str], dict[str, Any]]


class OAuthError(Exception):
    """OAuth protocol error with an HTTP status and RFC 6749 error code."""

    def __init__(
        self,
        status_code: int,
        error: str,
        description: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error = error
        self.description = description
        self.extra = extra or {}
        super().__init__(description)

    def as_dict(self) -> dict[str, Any]:
        body = {"error": self.error, "error_description": self.description}
        body.update(self.extra)
        return body


# ---------------------------------------------------------------------------
# Public origin / resource
# ---------------------------------------------------------------------------


def public_origin() -> str:
    return (
        os.environ.get("WA_PUBLIC_ORIGIN", "").strip().rstrip("/")
        or DEFAULT_PUBLIC_ORIGIN
    )


def public_mcp_resource() -> str:
    return os.environ.get("WA_PUBLIC_MCP_URL", "").strip().rstrip("/") or DEFAULT_MCP_RESOURCE


def resource_metadata_url() -> str:
    return f"{public_origin()}/.well-known/oauth-protected-resource/mcp"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def login_provider() -> str:
    provider = os.environ.get("WA_LOGIN_PROVIDER", "email").strip().lower()
    if provider not in {"email", "google"}:
        raise RuntimeError("WA_LOGIN_PROVIDER must be email or google.")
    return provider


def validate_hosted_configuration() -> None:
    """Fail Cloud Run startup before a revision can serve unusable sign-in."""
    if not os.environ.get("K_SERVICE"):
        return
    provider = login_provider()
    required = ("WA_GOOGLE_CLIENT_ID", "WA_GOOGLE_CLIENT_SECRET") if provider == "google" else ("WA_SMTP_HOST", "WA_SMTP_FROM")
    missing = [name for name in ("WA_OAUTH_SIGNING_KEY", *required)
               if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Hosted OAuth requires: " + ", ".join(missing))
    if len(os.environ["WA_OAUTH_SIGNING_KEY"].strip()) < 32:
        raise RuntimeError("Hosted OAuth requires a random signing key of at least 32 characters.")
    if dev_show_code():
        raise RuntimeError("Hosted OAuth must not expose sign-in codes.")
    if os.environ.get("WA_OAUTH_STORE", "").strip().lower() == "memory" or not all(supabase_config()):
        raise RuntimeError("Hosted OAuth requires Supabase persistence.")
    if provider == "email" and os.environ.get("WA_SMTP_STARTTLS", "1").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("Hosted OAuth requires verified SMTP STARTTLS.")


def signing_key() -> bytes:
    raw = os.environ.get("WA_OAUTH_SIGNING_KEY", "").strip()
    if raw:
        return raw.encode("utf-8")
    # Process-local fallback so tests and a single-instance inspector work.
    # Multi-instance Cloud Run must set WA_OAUTH_SIGNING_KEY.
    existing = globals().get("_ephemeral_signing_key")
    if isinstance(existing, bytes):
        return existing
    generated = secrets.token_bytes(32)
    globals()["_ephemeral_signing_key"] = generated
    return generated


# ---------------------------------------------------------------------------
# Encoding / PKCE
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_pkce_s256(code_verifier: str, code_challenge: str) -> bool:
    if not code_verifier or not code_challenge:
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return hmac.compare_digest(_b64url(digest), code_challenge)


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Redirect URIs (Claude hosted apps + Claude Code loopback)
# ---------------------------------------------------------------------------


def _loopback_key(uri: str) -> tuple[str, str, str] | None:
    parsed = urlparse(uri)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or host not in LOOPBACK_HOSTS:
        return None
    path = parsed.path or "/"
    return (parsed.scheme, host, path)


def redirect_uri_allowed(uri: str) -> bool:
    """Return True when *uri* is a Claude callback or an RFC 8252 loopback."""
    if not uri:
        return False
    if uri in CLAUDE_REDIRECTS:
        return True
    return _loopback_key(uri) is not None


def redirect_uri_matches(requested: str, registered: list[str]) -> bool:
    """Exact match, plus port-agnostic loopback per RFC 8252 / Claude Code."""
    if requested in registered:
        return True
    requested_key = _loopback_key(requested)
    if requested_key is None:
        return False
    return any(_loopback_key(item) == requested_key for item in registered)


def consent_hostname(redirect_uri: str) -> str:
    return urlparse(redirect_uri).hostname or redirect_uri


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


class MemoryOAuthStore:
    """In-process store for tests and a single local inspector process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.clients: dict[str, dict[str, Any]] = {}
        self.codes: dict[str, dict[str, Any]] = {}
        self.refresh: dict[str, dict[str, Any]] = {}
        self.logins: dict[str, dict[str, Any]] = {}
        self.users: dict[str, dict[str, Any]] = {}
        self.google_states: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        with self._lock:
            self.clients.clear()
            self.codes.clear()
            self.refresh.clear()
            self.logins.clear()
            self.users.clear()
            self.google_states.clear()

    def put_google_state(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.google_states[row["state_hash"]] = dict(row)

    def take_google_state(self, state_hash: str, browser_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.google_states.get(state_hash)
            if not row or not hmac.compare_digest(row["browser_hash"], browser_hash):
                return None
            return dict(self.google_states.pop(state_hash))

    def google_user(self, subject: str, email: str) -> dict[str, Any]:
        with self._lock:
            matched = next((row for row in self.users.values() if row.get("google_subject") == subject), None)
            if any(row["email"] == email and row is not matched for row in self.users.values()):
                raise OAuthError(409, "access_denied", "This email already belongs to another sign-in. Contact support to link accounts.")
            if matched is None:
                matched = {"id": secrets.token_hex(16), "email": email, "google_subject": subject}
                self.users[matched["id"]] = matched
            matched["email"] = email
            return dict(matched)

    def put_client(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.clients[row["client_id"]] = dict(row)

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.clients.get(client_id)
            return dict(row) if row else None

    def put_code(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.codes[row["code_hash"]] = dict(row)

    def take_code(self, code_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.codes.pop(code_hash, None)
            return dict(row) if row else None

    def put_refresh(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.refresh[row["token_hash"]] = dict(row)

    def get_refresh(self, token_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.refresh.get(token_hash)
            return dict(row) if row else None

    def delete_refresh(self, token_hash: str) -> None:
        with self._lock:
            self.refresh.pop(token_hash, None)

    def take_refresh(self, token_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.refresh.pop(token_hash, None)
            return dict(row) if row and not row.get("revoked_at") else None

    def put_login(self, row: dict[str, Any]) -> None:
        with self._lock:
            self.logins[row["id"]] = dict(row)

    def get_login(self, login_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.logins.get(login_id)
            return dict(row) if row else None

    def update_login(self, login_id: str, fields: dict[str, Any]) -> None:
        with self._lock:
            if login_id in self.logins:
                self.logins[login_id].update(fields)

    def delete_login(self, login_id: str) -> None:
        with self._lock:
            self.logins.pop(login_id, None)

    def take_consent(self, consent_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.logins.get(consent_id)
            if not row or row.get("consumed_at") or row["code_hash"] != _hash_secret("consent"):
                return None
            return dict(self.logins.pop(consent_id))

    def verify_login(self, login_id: str, code_hash: str) -> dict[str, Any]:
        with self._lock:
            row = self.logins.get(login_id)
            error = _login_error(row, code_hash)
            if error:
                if error == "That code is incorrect.":
                    row["attempts"] = int(row.get("attempts") or 0) + 1
                return {"error": error}
            return {"row": dict(self.logins.pop(login_id))}

    def upsert_user(self, email: str) -> dict[str, Any]:
        email = normalize_email(email)
        with self._lock:
            for row in self.users.values():
                if row["email"] == email:
                    return dict(row)
            user_id = secrets.token_hex(16)
            row = {"id": user_id, "email": email}
            self.users[user_id] = row
            return dict(row)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.users.get(user_id)
            return dict(row) if row else None


class SupabaseOAuthStore:
    """Persist OAuth state in the Toronto Supabase project."""

    def put_google_state(self, row: dict[str, Any]) -> None:
        self._request("POST", "wa_oauth_google_states", [row], prefer="return=minimal")

    def take_google_state(self, state_hash: str, browser_hash: str) -> dict[str, Any] | None:
        return self._claim("wa_oauth_google_states", "state_hash", state_hash, "consumed_at",
                           browser_hash=f"eq.{browser_hash}")

    def google_user(self, subject: str, email: str) -> dict[str, Any]:
        result = self._request("POST", "rpc/wa_google_user", {"p_subject": subject, "p_email": email})
        if result.get("error"):
            raise OAuthError(409, "access_denied", "This email already belongs to another sign-in. Contact support to link accounts.")
        return result

    def clear(self) -> None:
        return None

    def _request(
        self,
        method: str,
        path_query: str,
        payload: Any = None,
        prefer: str = "return=representation",
    ) -> Any:
        url, service_key = supabase_config()
        if not (url and service_key):
            raise OAuthError(503, "temporarily_unavailable", "Supabase is not configured.")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{url}/rest/v1/{path_query}",
            data=data,
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Prefer": prefer,
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise OAuthError(502, "server_error", f"Supabase {method} failed: {detail}") from exc
        except URLError as exc:
            raise OAuthError(502, "server_error", f"Supabase unreachable: {exc.reason}") from exc
        return json.loads(body) if body else None

    def put_client(self, row: dict[str, Any]) -> None:
        self._request("POST", "wa_oauth_clients", [row], prefer="return=minimal")

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        params = urlencode({"client_id": f"eq.{client_id}", "select": "*", "limit": "1"})
        rows = self._request("GET", f"wa_oauth_clients?{params}") or []
        return rows[0] if rows else None

    def put_code(self, row: dict[str, Any]) -> None:
        self._request("POST", "wa_oauth_auth_codes", [row], prefer="return=minimal")

    def take_code(self, code_hash: str) -> dict[str, Any] | None:
        return self._claim("wa_oauth_auth_codes", "code_hash", code_hash, "consumed_at")

    def _claim(self, table: str, key: str, value: str, marker: str, **filters: str) -> dict[str, Any] | None:
        # A single UPDATE ... WHERE marker IS NULL RETURNING * is atomic across
        # processes and replicas. Only the winning request receives a row.
        params = urlencode({key: f"eq.{value}", marker: "is.null", **filters})
        rows = self._request("PATCH", f"{table}?{params}", {marker: _iso(_utc_now())}) or []
        if not rows:
            return None
        return rows[0]

    def put_refresh(self, row: dict[str, Any]) -> None:
        self._request("POST", "wa_oauth_refresh_tokens", [row], prefer="return=minimal")

    def get_refresh(self, token_hash: str) -> dict[str, Any] | None:
        params = urlencode({"token_hash": f"eq.{token_hash}", "select": "*", "limit": "1"})
        rows = self._request("GET", f"wa_oauth_refresh_tokens?{params}") or []
        return rows[0] if rows else None

    def delete_refresh(self, token_hash: str) -> None:
        params = urlencode({"token_hash": f"eq.{token_hash}"})
        self._request(
            "PATCH",
            f"wa_oauth_refresh_tokens?{params}",
            {"revoked_at": _iso(_utc_now())},
            prefer="return=minimal",
        )

    def take_refresh(self, token_hash: str) -> dict[str, Any] | None:
        return self._claim("wa_oauth_refresh_tokens", "token_hash", token_hash, "revoked_at")

    def put_login(self, row: dict[str, Any]) -> None:
        self._request("POST", "wa_oauth_login_challenges", [row], prefer="return=minimal")

    def get_login(self, login_id: str) -> dict[str, Any] | None:
        params = urlencode({"id": f"eq.{login_id}", "select": "*", "limit": "1"})
        rows = self._request("GET", f"wa_oauth_login_challenges?{params}") or []
        return rows[0] if rows else None

    def update_login(self, login_id: str, fields: dict[str, Any]) -> None:
        params = urlencode({"id": f"eq.{login_id}"})
        self._request("PATCH", f"wa_oauth_login_challenges?{params}", fields, prefer="return=minimal")

    def delete_login(self, login_id: str) -> None:
        params = urlencode({"id": f"eq.{login_id}"})
        self._request(
            "PATCH",
            f"wa_oauth_login_challenges?{params}",
            {"consumed_at": _iso(_utc_now())},
            prefer="return=minimal",
        )

    def take_consent(self, consent_id: str) -> dict[str, Any] | None:
        return self._claim(
            "wa_oauth_login_challenges", "id", consent_id, "consumed_at",
            code_hash=f"eq.{_hash_secret('consent')}",
        )

    def verify_login(self, login_id: str, code_hash: str) -> dict[str, Any]:
        return self._request("POST", "rpc/wa_oauth_verify_login", {
            "p_id": login_id, "p_code_hash": code_hash,
        })

    def upsert_user(self, email: str) -> dict[str, Any]:
        email = normalize_email(email)
        params = urlencode({"email": f"eq.{email}", "select": "id,email", "limit": "1"})
        rows = self._request("GET", f"wa_users?{params}") or []
        if rows:
            return rows[0]
        created = self._request("POST", "wa_users", [{"email": email}]) or []
        if created:
            return created[0]
        raise OAuthError(502, "server_error", "Could not create the workspaceAlberta user row.")

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        params = urlencode({"id": f"eq.{user_id}", "select": "id,email", "limit": "1"})
        rows = self._request("GET", f"wa_users?{params}") or []
        return rows[0] if rows else None


_memory_store = MemoryOAuthStore()
_store_override: MemoryOAuthStore | SupabaseOAuthStore | None = None


def get_store() -> MemoryOAuthStore | SupabaseOAuthStore:
    if _store_override is not None:
        return _store_override
    forced = os.environ.get("WA_OAUTH_STORE", "").strip().lower()
    if forced == "memory":
        return _memory_store
    if forced == "supabase":
        return SupabaseOAuthStore()
    url, key = supabase_config()
    if url and key:
        return SupabaseOAuthStore()
    return _memory_store


def use_store(store: MemoryOAuthStore | SupabaseOAuthStore | None) -> None:
    """Tests inject a store. Pass None to restore the default factory."""
    global _store_override
    _store_override = store


def reset_oauth_state() -> None:
    """Drop in-memory OAuth state and the CIMD cache (tests)."""
    _memory_store.clear()
    _cimd_cache.clear()
    globals().pop("_ephemeral_signing_key", None)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def protected_resource_metadata() -> dict[str, Any]:
    return {
        "resource": public_mcp_resource(),
        "authorization_servers": [public_origin()],
        "bearer_methods_supported": ["header"],
        "scopes_supported": [SCOPE_PRO],
        "resource_documentation": "https://github.com/WarreAndVavasour/WorkspaceAlberta",
    }


def authorization_server_metadata() -> dict[str, Any]:
    origin = public_origin()
    return {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/authorize",
        "token_endpoint": f"{origin}/token",
        "registration_endpoint": f"{origin}/register",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "client_id_metadata_document_supported": True,
        "scopes_supported": [SCOPE_PRO, SCOPE_OFFLINE],
        "service_documentation": "https://github.com/WarreAndVavasour/WorkspaceAlberta",
    }


def www_authenticate_challenge(
    *,
    error: str = "invalid_token",
    description: str = "Authentication required for this tool",
    scope: str = SCOPE_PRO,
) -> str:
    """RFC 9728 / RFC 6750 challenge that starts Claude lazy authentication."""
    return (
        f'Bearer error="{error}", '
        f'error_description="{description}", '
        f'resource_metadata="{resource_metadata_url()}", '
        f'scope="{scope}"'
    )


# ---------------------------------------------------------------------------
# Clients: DCR + CIMD
# ---------------------------------------------------------------------------


_cimd_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cimd_fetch: FetchJson | None = None


def set_cimd_fetch(fetch: FetchJson | None) -> None:
    global _cimd_fetch
    _cimd_fetch = fetch


def _public_addresses(hostname: str, port: int) -> list[tuple]:
    if not hostname or hostname.lower() in LOOPBACK_HOSTS:
        raise ValueError("Non-public host")
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Host could not be resolved") from None
    if not infos:
        raise ValueError("Host could not be resolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        addresses = [ip]
        if isinstance(ip, ipaddress.IPv6Address):
            addresses.extend(item for item in (ip.ipv4_mapped, ip.sixtofour) if item is not None)
            if ip.teredo:
                addresses.extend(ip.teredo)
            if ip in ipaddress.ip_network("64:ff9b::/96"):
                addresses.append(ipaddress.IPv4Address(int(ip) & 0xffffffff))
        if any(not address.is_global or address.is_multicast for address in addresses):
            raise ValueError("Non-public address")
    return infos


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect only to a previously checked address; retain TLS hostname checks."""

    def __init__(self, host: str, port: int, addresses: list[tuple]) -> None:
        super().__init__(host, port, timeout=5, context=ssl.create_default_context())
        self.addresses = addresses

    def connect(self) -> None:
        # No second DNS lookup, proxy, or automatic redirect can change the peer.
        deadline = time.monotonic() + self.timeout
        failure: OSError = TimeoutError("Metadata connection timed out")
        for family, socktype, proto, _, address in self.addresses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock = socket.socket(family, socktype, proto)
            try:
                sock.settimeout(remaining)
                sock.connect(address)
                sock.settimeout(max(0.001, deadline - time.monotonic()))
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except OSError as exc:
                sock.close()
                failure = exc
            except BaseException:
                sock.close()
                raise
        raise failure


def _default_cimd_fetch(url: str) -> dict[str, Any]:
    connection = None
    try:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.path or parsed.path == "/"
                or parsed.username is not None or parsed.password is not None or parsed.fragment
                or any(ord(char) < 33 for char in url)):
            raise ValueError("Invalid metadata URL")
        hostname = (parsed.hostname or "").encode("idna").decode("ascii")
        port = parsed.port or 443
        addresses = _public_addresses(hostname, port)
        connection = _PinnedHTTPSConnection(hostname, port, addresses)
        path = urlunparse(("", "", parsed.path, parsed.params, parsed.query, ""))
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        # Metadata URLs identify the client. Redirects are deliberately rejected.
        if response.status != 200:
            raise ValueError("Metadata must return HTTP 200 without redirects")
        raw = response.read(CIMD_MAX_BYTES + 1)
        if len(raw) > CIMD_MAX_BYTES:
            raise ValueError("Metadata is too large")
        body = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise OAuthError(400, "invalid_client", "Could not fetch valid public HTTPS client metadata.") from exc
    finally:
        if connection is not None:
            connection.close()
    if not isinstance(body, dict):
        raise OAuthError(400, "invalid_client", "Client metadata is not a JSON object.")
    return body


def _fetch_cimd(client_id: str) -> dict[str, Any]:
    now = time.time()
    cached = _cimd_cache.get(client_id)
    if cached and now - cached[0] < CIMD_CACHE_TTL_SECONDS:
        return dict(cached[1])
    fetch = _cimd_fetch or _default_cimd_fetch
    document = fetch(client_id)
    if document.get("client_id") != client_id:
        raise OAuthError(400, "invalid_client", "CIMD client_id does not match the document URL.")
    redirect_uris = document.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise OAuthError(400, "invalid_client", "CIMD is missing redirect_uris.")
    _cimd_cache[client_id] = (now, document)
    return dict(document)


def register_client(payload: dict[str, Any]) -> dict[str, Any]:
    """RFC 7591 Dynamic Client Registration."""
    redirect_uris = payload.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise OAuthError(400, "invalid_redirect_uri", "redirect_uris is required.")
    cleaned: list[str] = []
    for uri in redirect_uris:
        if not isinstance(uri, str) or not redirect_uri_allowed(uri):
            raise OAuthError(
                400,
                "invalid_redirect_uri",
                "redirect_uri is not a Claude callback or loopback URI.",
            )
        cleaned.append(uri)
    auth_method = str(payload.get("token_endpoint_auth_method") or "none")
    if auth_method not in {"none", "client_secret_post"}:
        auth_method = "none"
    client_id = CLIENT_PREFIX + secrets.token_urlsafe(16)
    issued_at = int(time.time())
    row = {
        "client_id": client_id,
        "client_name": str(payload.get("client_name") or "MCP client"),
        "redirect_uris": cleaned,
        "token_endpoint_auth_method": auth_method,
        "client_id_issued_at": issued_at,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    get_store().put_client(row)
    return {
        "client_id": client_id,
        "client_id_issued_at": issued_at,
        "client_name": row["client_name"],
        "redirect_uris": cleaned,
        "token_endpoint_auth_method": auth_method,
        "grant_types": row["grant_types"],
        "response_types": row["response_types"],
    }


def resolve_client(client_id: str) -> dict[str, Any]:
    if not client_id:
        raise OAuthError(400, "invalid_client", "client_id is required.")
    if client_id.startswith("https://"):
        document = _fetch_cimd(client_id)
        return {
            "client_id": client_id,
            "client_name": urlparse(client_id).hostname or client_id,
            "redirect_uris": list(document.get("redirect_uris") or []),
            "token_endpoint_auth_method": "none",
            "cimd": True,
        }
    row = get_store().get_client(client_id)
    if not row:
        raise OAuthError(400, "invalid_client", "Unknown client_id.")
    uris = row.get("redirect_uris") or []
    if isinstance(uris, str):
        uris = json.loads(uris)
    row = dict(row)
    row["redirect_uris"] = list(uris)
    row["cimd"] = False
    return row


# ---------------------------------------------------------------------------
# Login (email one-time code)
# ---------------------------------------------------------------------------


def dev_show_code() -> bool:
    return os.environ.get("WA_OAUTH_DEV_SHOW_CODE", "").lower() in {"1", "true", "yes"}


def send_login_code(email: str, code: str) -> bool:
    """Send the one-time code. Returns True when a delivery path ran."""
    if dev_show_code():
        return True
    host = os.environ.get("WA_SMTP_HOST", "").strip()
    if not host:
        return False

    port = int(os.environ.get("WA_SMTP_PORT", "587") or "587")
    user = os.environ.get("WA_SMTP_USER", "").strip()
    password = os.environ.get("WA_SMTP_PASSWORD", "").strip()
    sender = os.environ.get("WA_SMTP_FROM", "").strip() or user or "noreply@localhost"
    starttls = os.environ.get("WA_SMTP_STARTTLS", "1").lower() in {"1", "true", "yes"}
    message = EmailMessage()
    message["Subject"] = "Your workspaceAlberta sign-in code"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Your workspaceAlberta sign-in code is {code}.\n\n"
        "It expires in 10 minutes. If you did not request this, ignore the email.\n"
    )
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        if starttls:
            smtp.starttls(context=ssl.create_default_context())
        if user:
            smtp.login(user, password)
        smtp.send_message(message)
    return True


def start_login(email: str, authorize_params: dict[str, Any]) -> dict[str, Any]:
    email = normalize_email(email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise OAuthError(400, "invalid_request", "Enter a valid email address.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    login_id = secrets.token_urlsafe(24)
    row = {
        "id": login_id,
        "email": email,
        "code_hash": _hash_secret(code),
        "authorize_params": authorize_params,
        "expires_at": _iso(_utc_now() + timedelta(seconds=LOGIN_TTL_SECONDS)),
        "attempts": 0,
    }
    get_store().put_login(row)
    try:
        delivered = send_login_code(email, code)
    except (OSError, smtplib.SMTPException) as exc:
        raise OAuthError(503, "temporarily_unavailable", f"Could not send the sign-in email: {exc}") from exc
    result = {"login_id": login_id, "email": email, "delivered": delivered}
    if dev_show_code():
        result["dev_code"] = code
    return result


def _login_error(row: dict[str, Any] | None, code_hash: str) -> str:
    """Mirror the locked PostgreSQL verifier in migration 003 for local use."""
    if not row:
        return "Sign-in challenge not found."
    if row.get("consumed_at"):
        return "Sign-in challenge already used."
    if row["code_hash"] == _hash_secret("consent"):
        return "Sign-in challenge not found."
    if _parse_iso(row["expires_at"]) < _utc_now():
        return "Sign-in code expired. Start again."
    attempts = int(row.get("attempts") or 0)
    if attempts >= MAX_OTP_ATTEMPTS:
        return "Too many attempts. Start again."
    if not hmac.compare_digest(row["code_hash"], code_hash):
        return "That code is incorrect."
    return ""


def verify_login(login_id: str, code: str) -> dict[str, Any]:
    store = get_store()
    result = store.verify_login(login_id, _hash_secret(code.strip()))
    if result.get("error"):
        raise OAuthError(400, "invalid_request", result["error"])
    row = result["row"]
    params = row.get("authorize_params") or {}
    if isinstance(params, str):
        params = json.loads(params)
    user = store.upsert_user(row["email"])
    return create_consent(user, params)


def create_consent(user: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    store = get_store()
    consent_id = secrets.token_urlsafe(24)
    store.put_login(
        {
            "id": consent_id,
            "email": user["email"],
            "code_hash": _hash_secret("consent"),
            "authorize_params": {**params, "user_id": user["id"], "email": user["email"]},
            "expires_at": _iso(_utc_now() + timedelta(seconds=LOGIN_TTL_SECONDS)),
            "attempts": 0,
        }
    )
    return {"user": user, "authorize_params": params, "consent_id": consent_id}


def take_consent(consent_id: str, browser_secret: str = "") -> dict[str, Any]:
    store = get_store()
    row = store.take_consent(consent_id)
    if not row or row.get("code_hash") != _hash_secret("consent"):
        raise OAuthError(400, "invalid_request", "Consent session not found.")
    if _parse_iso(row["expires_at"]) < _utc_now():
        raise OAuthError(400, "invalid_request", "Consent session expired. Start again.")
    params = row.get("authorize_params") or {}
    if isinstance(params, str):
        params = json.loads(params)
    if params.get("browser_hash") and not hmac.compare_digest(params["browser_hash"], _hash_secret(browser_secret)):
        raise OAuthError(400, "invalid_request", "Sign-in browser changed. Start again.")
    user = {"id": params.get("user_id", ""), "email": params.get("email", "")}
    if not user["id"] or not user["email"]:
        raise OAuthError(400, "invalid_request", "Consent session is missing the signed-in user.")
    return {"user": user, "authorize_params": params}


# ---------------------------------------------------------------------------
# Authorization codes and tokens
# ---------------------------------------------------------------------------


def _resource_allowed(resource: str) -> bool:
    if not resource:
        return False
    allowed = {public_mcp_resource()}
    extra = os.environ.get("WA_OAUTH_EXTRA_RESOURCES", "")
    allowed.update(item.strip() for item in extra.split(",") if item.strip())
    return resource.rstrip("/") in {item.rstrip("/") for item in allowed}


def validate_authorize_params(params: dict[str, str]) -> dict[str, str]:
    if params.get("response_type") != "code":
        raise OAuthError(400, "unsupported_response_type", "Only response_type=code is supported.")
    if params.get("code_challenge_method", "S256") != "S256":
        raise OAuthError(400, "invalid_request", "code_challenge_method must be S256.")
    challenge = params.get("code_challenge", "")
    if len(challenge) < 43:
        raise OAuthError(400, "invalid_request", "code_challenge is required (PKCE S256).")
    client = resolve_client(params.get("client_id", ""))
    redirect_uri = params.get("redirect_uri", "")
    if not redirect_uri_allowed(redirect_uri) or not redirect_uri_matches(
        redirect_uri, list(client["redirect_uris"])
    ):
        raise OAuthError(400, "invalid_request", "redirect_uri is not registered for this client.")
    resource = params.get("resource") or public_mcp_resource()
    if not _resource_allowed(resource):
        raise OAuthError(400, "invalid_target", "resource is not this MCP server.")
    return {
        "response_type": "code",
        "client_id": client["client_id"],
        "client_name": client.get("client_name") or "MCP client",
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": params.get("state", ""),
        "resource": resource,
        "scope": params.get("scope") or SCOPE_PRO,
        "cimd": "1" if client.get("cimd") else "0",
    }


def issue_authorization_code(user: dict[str, Any], params: dict[str, str]) -> str:
    code = secrets.token_urlsafe(32)
    get_store().put_code(
        {
            "code_hash": _hash_secret(code),
            "client_id": params["client_id"],
            "redirect_uri": params["redirect_uri"],
            "code_challenge": params["code_challenge"],
            "resource": params["resource"],
            "user_email": user["email"],
            "user_id": user["id"],
            "scope": params.get("scope") or SCOPE_PRO,
            "expires_at": _iso(_utc_now() + timedelta(seconds=CODE_TTL_SECONDS)),
        }
    )
    return code


def authorization_redirect(params: dict[str, str], code: str) -> str:
    parsed = urlparse(params["redirect_uri"])
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["code"] = code
    if params.get("state"):
        query["state"] = params["state"]
    return urlunparse(parsed._replace(query=urlencode(query)))


def _mint_access_token(user: dict[str, Any], resource: str, scope: str) -> str:
    claims = {
        "sub": user["id"],
        "email": user["email"],
        "aud": resource,
        "iss": public_origin(),
        "iat": int(time.time()),
        "exp": int(time.time()) + ACCESS_TTL_SECONDS,
        "scope": scope,
    }
    payload = _b64url(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    sig = _b64url(hmac.new(signing_key(), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{ACCESS_PREFIX}{payload}.{sig}"


def validate_access_token(token: str) -> dict[str, Any]:
    """Validate a workspaceAlberta access token and return its claims."""
    if not token.startswith(ACCESS_PREFIX):
        raise GateError(401, "Not a workspaceAlberta OAuth access token.")
    body = token[len(ACCESS_PREFIX) :]
    if "." not in body:
        raise GateError(401, "Malformed access token.")
    payload_b64, sig = body.rsplit(".", 1)
    expected = _b64url(hmac.new(signing_key(), payload_b64.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise GateError(401, "Access token signature is invalid.")
    try:
        claims = json.loads(_b64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError) as exc:
        raise GateError(401, "Access token payload is invalid.") from exc
    if int(claims.get("exp") or 0) < int(time.time()):
        raise GateError(401, "Access token expired.")
    if claims.get("iss") != public_origin():
        raise GateError(401, "Access token issuer is invalid.")
    if str(claims.get("aud") or "").rstrip("/") != public_mcp_resource().rstrip("/"):
        raise GateError(401, "Access token is not audience-bound to this MCP server.")
    return claims


def _issue_refresh_token(user: dict[str, Any], client_id: str, resource: str, scope: str) -> str:
    token = REFRESH_PREFIX + secrets.token_urlsafe(32)
    get_store().put_refresh(
        {
            "token_hash": _hash_secret(token),
            "client_id": client_id,
            "user_email": user["email"],
            "user_id": user["id"],
            "resource": resource,
            "scope": scope,
            "expires_at": _iso(_utc_now() + timedelta(seconds=REFRESH_TTL_SECONDS)),
        }
    )
    return token


def _token_response(user: dict[str, Any], client_id: str, resource: str, scope: str) -> dict[str, Any]:
    access = _mint_access_token(user, resource, scope)
    refresh = _issue_refresh_token(user, client_id, resource, scope)
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL_SECONDS,
        "refresh_token": refresh,
        "scope": scope,
    }


def exchange_authorization_code(form: dict[str, str]) -> dict[str, Any]:
    if form.get("grant_type") != "authorization_code":
        raise OAuthError(400, "unsupported_grant_type", "grant_type must be authorization_code.")
    code = form.get("code", "")
    verifier = form.get("code_verifier", "")
    redirect_uri = form.get("redirect_uri", "")
    client_id = form.get("client_id", "")
    resource = form.get("resource") or public_mcp_resource()
    if not code or not verifier:
        raise OAuthError(400, "invalid_request", "code and code_verifier are required.")
    client = resolve_client(client_id)
    row = get_store().take_code(_hash_secret(code))
    if not row:
        raise OAuthError(400, "invalid_grant", "Authorization code is invalid or already used.")
    if _parse_iso(row["expires_at"]) < _utc_now():
        raise OAuthError(400, "invalid_grant", "Authorization code expired.")
    if row["client_id"] != client["client_id"] or row["redirect_uri"] != redirect_uri:
        raise OAuthError(400, "invalid_grant", "Authorization code does not match this client.")
    if not verify_pkce_s256(verifier, row["code_challenge"]):
        raise OAuthError(400, "invalid_grant", "PKCE verification failed.")
    if str(row.get("resource") or "").rstrip("/") != resource.rstrip("/"):
        raise OAuthError(400, "invalid_target", "resource does not match the authorization request.")
    user = {"id": row["user_id"], "email": row["user_email"]}
    scope = row.get("scope") or SCOPE_PRO
    if SCOPE_OFFLINE not in scope:
        scope = f"{scope} {SCOPE_OFFLINE}".strip()
    return _token_response(user, client["client_id"], resource, scope)


def exchange_refresh_token(form: dict[str, str]) -> dict[str, Any]:
    if form.get("grant_type") != "refresh_token":
        raise OAuthError(400, "unsupported_grant_type", "grant_type must be refresh_token.")
    token = form.get("refresh_token", "")
    client_id = form.get("client_id", "")
    if not token:
        raise OAuthError(400, "invalid_request", "refresh_token is required.")
    store = get_store()
    row = store.get_refresh(_hash_secret(token))
    if not row or row.get("revoked_at"):
        raise OAuthError(400, "invalid_grant", "Refresh token is invalid or revoked.")
    if _parse_iso(row["expires_at"]) < _utc_now():
        raise OAuthError(400, "invalid_grant", "Refresh token expired.")
    if client_id and row["client_id"] != client_id:
        raise OAuthError(400, "invalid_grant", "Refresh token does not match this client.")
    if not store.take_refresh(_hash_secret(token)):
        raise OAuthError(400, "invalid_grant", "Refresh token is invalid or revoked.")
    user = {"id": row["user_id"], "email": row["user_email"]}
    if login_provider() == "google":
        # Google Workspace addresses can change. Never renew the old email's
        # billing entitlement indefinitely from a refresh-token snapshot.
        current = store.get_user(row["user_id"])
        if not current:
            raise OAuthError(400, "invalid_grant", "The account no longer exists. Sign in again.")
        user = current
    resource = row.get("resource") or public_mcp_resource()
    scope = row.get("scope") or f"{SCOPE_PRO} {SCOPE_OFFLINE}"
    return _token_response(user, row["client_id"], resource, scope)


def issue_tokens(form: dict[str, str]) -> dict[str, Any]:
    grant = form.get("grant_type", "")
    if grant == "authorization_code":
        return exchange_authorization_code(form)
    if grant == "refresh_token":
        return exchange_refresh_token(form)
    raise OAuthError(400, "unsupported_grant_type", "Unsupported grant_type.")


def mcp_calls_pro_tool(body: Any, pro_tools: frozenset[str]) -> bool:
    """True when a JSON-RPC body (single or batch) calls a Pro tool."""
    messages = body if isinstance(body, list) else [body]
    for message in messages:
        if not isinstance(message, dict) or message.get("method") != "tools/call":
            continue
        params = message.get("params") or {}
        name = params.get("name") if isinstance(params, dict) else None
        if isinstance(name, str) and name in pro_tools:
            return True
    return False
