"""FastAPI routes for the workspaceAlberta OAuth 2.1 authorization server."""

from __future__ import annotations

import asyncio
import secrets
from html import escape
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from procurement_core import oauth, google_login
from procurement_core.auth_pages import CONSENT, auth_page

_PAGE_STYLE = """
body { font-family: system-ui, sans-serif; max-width: 28rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.55; color: #1c1c1c; }
code { background: #f4f4f4; border-radius: 6px; padding: 0.1rem 0.35rem; }
input, button { font: inherit; width: 100%; box-sizing: border-box; padding: 0.6rem 0.7rem; margin: 0.35rem 0 0.9rem; }
button { background: #0b57d0; color: #fff; border: 0; border-radius: 8px; cursor: pointer; }
.google-signin { background: transparent; width: auto; padding: 0; line-height: 0; }
.google-signin img { width: auto; height: 40px; }
.google-signin:focus-visible { outline: 2px solid #0b57d0; outline-offset: 3px; }
.sub { color: #555; }
.warn { background: #fff4cc; padding: 0.7rem 0.8rem; border-radius: 8px; }
.error { color: #9b1c1c; }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{escape(title)}</title><style>{_PAGE_STYLE}</style></head><body>"
        f"{body}</body></html>"
    )


def _hidden_params(params: dict[str, str]) -> str:
    parts = []
    for key, value in params.items():
        parts.append(f'<input type="hidden" name="{escape(str(key))}" value="{escape(str(value))}">')
    return "\n".join(parts)


def _authorize_param_names() -> tuple[str, ...]:
    return (
        "response_type",
        "client_id",
        "redirect_uri",
        "code_challenge",
        "code_challenge_method",
        "state",
        "resource",
        "scope",
    )


def _params_from_request(request: Request) -> dict[str, str]:
    source = request.query_params if request.method == "GET" else None
    # POST uses the form; caller passes a mapping.
    if source is None:
        return {}
    return {key: source.get(key, "") for key in _authorize_param_names()}


def _params_from_form(form: dict[str, str]) -> dict[str, str]:
    return {key: form.get(key, "") for key in _authorize_param_names()}


def _error_redirect(redirect_uri: str, error: str, description: str, state: str) -> str | None:
    if not oauth.redirect_uri_allowed(redirect_uri):
        return None
    parsed = urlparse(redirect_uri)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["error"] = error
    query["error_description"] = description
    if state:
        query["state"] = state
    return urlunparse(parsed._replace(query=urlencode(query)))


def _email_form(params: dict[str, str], *, error: str = "", notice: str = "") -> str:
    host = escape(oauth.consent_hostname(params.get("redirect_uri", "")))
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    notice_html = f'<p class="warn">{escape(notice)}</p>' if notice else ""
    return _page(
        "Sign in to workspaceAlberta",
        f"""
<h1>workspaceAlberta</h1>
<p class="sub">Sign in to unlock Pro tools for Claude and other MCP clients.</p>
<p>After you approve, we send you back to <code>{host}</code>.</p>
{error_html}{notice_html}
<form method="post" action="/authorize">
  {_hidden_params(params)}
  <label>Email <input type="email" name="email" required autocomplete="username"></label>
  <button type="submit">Email me a sign-in code</button>
</form>
<p class="sub">Pro tools also still accept a legacy <code>wa_live_</code> subscriber key.</p>
""",
    )


def _google_form(params: dict[str, str]) -> str:
    host = escape(oauth.consent_hostname(params.get("redirect_uri", "")))
    return auth_page("Sign in to workspaceAlberta", f"""
<div class="signin-body">
<h1>Your next<br>possibility awaits.</h1>
<p class="intro">Connect your procurement tools. Sign in with your Gmail or Google Workspace account, then review access for <strong>{host}</strong>.</p>
<form method="post" action="/authorize/google">
  {_hidden_params(params)}
  <button type="submit" class="google-signin" aria-label="Sign in with Google"><img src="/assets/google-signin.png" alt="Sign in with Google"></button>
</form>
<p class="subscription-note">Use the same email as your Pro subscription. Signing in does not start a subscription or charge you.</p>
</div>
""", step="01", step_label="Connect your workspace")


def _code_form(login_id: str, email: str, *, dev_code: str = "", error: str = "") -> str:
    login_id, email, dev_code = escape(login_id), escape(email), escape(dev_code)
    hint = ""
    if dev_code:
        hint = (
            f'<p class="warn">Developer mode: your code is '
            f'<code data-otp="{dev_code}">{dev_code}</code>.</p>'
        )
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    return _page(
        "Enter your workspaceAlberta code",
        f"""
<h1>Check your email</h1>
<p>We sent a 6-digit code to <code>{email}</code>.</p>
{hint}{error_html}
<form method="post" action="/authorize/verify">
  <input type="hidden" name="login_id" value="{login_id}">
  <label>Sign-in code <input name="code" inputmode="numeric" pattern="[0-9]{{6}}" maxlength="6" required></label>
  <button type="submit">Continue</button>
</form>
""",
    )


def _consent_form(login_result: dict[str, Any]) -> str:
    params = login_result["authorize_params"]
    user = login_result["user"]
    host = oauth.consent_hostname(params.get("redirect_uri", ""))
    client_name = params.get("client_name") or "This MCP client"
    if params.get("cimd") == "1":
        client_name = host
    client_name = escape(str(client_name))
    host = escape(host)
    email = escape(str(user["email"]))
    consent_id = escape(str(login_result["consent_id"]))
    return auth_page(
        "Approve workspaceAlberta access",
        CONSENT.substitute(client_name=client_name, email=email, host=host, consent_id=consent_id),
        step="02", step_label="Review access",
    )


def _oauth_error_response(exc: oauth.OAuthError) -> JSONResponse:
    return JSONResponse(
        exc.as_dict(),
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store"},
    )


async def _form_map(request: Request) -> dict[str, str]:
    form = await request.form()
    return {str(key): str(value) for key, value in form.items()}


def register_oauth_routes(app: FastAPI) -> None:
    """Attach RFC 8414 / RFC 7591 / authorization-code routes to *app*."""

    @app.middleware("http")
    async def protect_sign_in_pages(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/authorize", "/oauth/google/")):
            response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                     "X-Frame-Options": "DENY",
                                     # OAuth form responses legitimately redirect to Google
                                     # and the validated MCP callback (including loopback).
                                     "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"})
            if request.url.path == "/authorize/consent" and request.method == "POST":
                response.delete_cookie(google_login.BROWSER_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        return response

    @app.get("/authorize", include_in_schema=False, response_model=None)
    async def authorize_get(request: Request) -> HTMLResponse | RedirectResponse:
        params = _params_from_request(request)
        try:
            checked = await asyncio.to_thread(oauth.validate_authorize_params, params)
        except oauth.OAuthError as exc:
            target = _error_redirect(
                params.get("redirect_uri", ""),
                exc.error,
                exc.description,
                params.get("state", ""),
            )
            if target:
                return RedirectResponse(target, status_code=302)
            return HTMLResponse(_page("Authorization error", f"<p class='error'>{escape(exc.description)}</p>"), 400)
        return HTMLResponse(_google_form(checked) if oauth.login_provider() == "google" else _email_form(checked))

    @app.post("/authorize/google", include_in_schema=False, response_model=None)
    async def authorize_google(request: Request) -> HTMLResponse | RedirectResponse:
        form = await _form_map(request)
        try:
            checked = await asyncio.to_thread(oauth.validate_authorize_params, _params_from_form(form))
            browser_secret = secrets.token_urlsafe(32)
            target = await asyncio.to_thread(google_login.start, checked, browser_secret)
        except oauth.OAuthError as exc:
            return HTMLResponse(_page("Sign-in error", f"<p>{escape(exc.description)}</p>"), exc.status_code)
        response = RedirectResponse(target, status_code=303)
        response.set_cookie(google_login.BROWSER_COOKIE, browser_secret, max_age=oauth.LOGIN_TTL_SECONDS,
                            secure=True, httponly=True, samesite="lax", path="/")
        return response

    @app.get("/oauth/google/callback", include_in_schema=False)
    async def google_callback(request: Request) -> HTMLResponse:
        query = request.query_params
        try:
            result = await asyncio.to_thread(google_login.finish, query.get("state", ""), query.get("code", ""),
                                             request.cookies.get(google_login.BROWSER_COOKIE, ""), query.get("error", ""))
        except oauth.OAuthError as exc:
            return HTMLResponse(_page("Sign-in error", f"<p>{escape(exc.description)}</p>"), exc.status_code)
        return HTMLResponse(_consent_form(result))

    @app.post("/authorize", include_in_schema=False, response_model=None)
    async def authorize_start(request: Request) -> HTMLResponse | RedirectResponse:
        if oauth.login_provider() != "email":
            return HTMLResponse(_page("Sign in with Google", "<p>Reconnect from your MCP client to sign in with Google.</p>"), 404)
        form = await _form_map(request)
        params = _params_from_form(form)
        try:
            checked = await asyncio.to_thread(oauth.validate_authorize_params, params)
            started = await asyncio.to_thread(oauth.start_login, form.get("email", ""), checked)
        except oauth.OAuthError as exc:
            try:
                checked = await asyncio.to_thread(oauth.validate_authorize_params, params)
            except oauth.OAuthError:
                return HTMLResponse(_page("Authorization error", f"<p class='error'>{escape(exc.description)}</p>"), 400)
            return HTMLResponse(_email_form(checked, error=exc.description), 400)
        notice = ""
        if not started.get("delivered") and not started.get("dev_code"):
            notice = (
                "Email delivery is not configured on this server "
                "(set WA_SMTP_HOST or WA_OAUTH_DEV_SHOW_CODE). "
                "Ask Christian to set those env vars."
            )
        return HTMLResponse(
            _code_form(
                started["login_id"],
                started["email"],
                dev_code=started.get("dev_code", ""),
                error=notice,
            )
        )

    @app.post("/authorize/verify", include_in_schema=False)
    async def authorize_verify(request: Request) -> HTMLResponse:
        if oauth.login_provider() != "email":
            return HTMLResponse(_page("Sign in with Google", "<p>Email-code sign-in is disabled.</p>"), 404)
        form = await _form_map(request)
        try:
            result = await asyncio.to_thread(oauth.verify_login, form.get("login_id", ""), form.get("code", ""))
        except oauth.OAuthError as exc:
            return HTMLResponse(
                _code_form(form.get("login_id", ""), "", error=exc.description),
                400,
            )
        return HTMLResponse(_consent_form(result))

    @app.post("/authorize/consent", include_in_schema=False, response_model=None)
    async def authorize_consent(request: Request) -> HTMLResponse | RedirectResponse:
        form = await _form_map(request)
        try:
            session = await asyncio.to_thread(oauth.take_consent, form.get("consent_id", ""),
                                               request.cookies.get(google_login.BROWSER_COOKIE, ""))
        except oauth.OAuthError as exc:
            return HTMLResponse(_page("Authorization error", f"<p class='error'>{escape(exc.description)}</p>"), 400)
        params = session["authorize_params"]
        if form.get("decision") != "approve":
            target = _error_redirect(
                params.get("redirect_uri", ""),
                "access_denied",
                "The user denied the request.",
                params.get("state", ""),
            )
            if target:
                return RedirectResponse(target, status_code=302)
            return HTMLResponse(_page("Denied", "<p>Access denied.</p>"), 403)
        try:
            checked = await asyncio.to_thread(oauth.validate_authorize_params, params)
        except oauth.OAuthError as exc:
            return HTMLResponse(_page("Authorization error", f"<p class='error'>{escape(exc.description)}</p>"), 400)
        code = await asyncio.to_thread(oauth.issue_authorization_code, session["user"], checked)
        return RedirectResponse(oauth.authorization_redirect(checked, code), status_code=302)

    @app.post("/token", include_in_schema=False)
    async def token_endpoint(request: Request) -> JSONResponse:
        content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        if content_type not in {"application/x-www-form-urlencoded", "application/json"}:
            return JSONResponse(
                {"error": "invalid_request", "error_description": "Use application/x-www-form-urlencoded."},
                status_code=400,
                headers={"Cache-Control": "no-store"},
            )
        if content_type == "application/json":
            payload = await request.json()
            form = {str(key): str(value) for key, value in dict(payload or {}).items()}
        else:
            form = await _form_map(request)
        try:
            tokens = await asyncio.to_thread(oauth.issue_tokens, form)
        except oauth.OAuthError as exc:
            return _oauth_error_response(exc)
        return JSONResponse(tokens, headers={"Cache-Control": "no-store"})

    @app.post("/register", include_in_schema=False)
    async def register_endpoint(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise oauth.OAuthError(400, "invalid_client_metadata", "JSON object required.")
            created = await asyncio.to_thread(oauth.register_client, payload)
        except oauth.OAuthError as exc:
            return _oauth_error_response(exc)
        return JSONResponse(created, status_code=201)
