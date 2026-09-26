"""FastAPI routes for the workspaceAlberta OAuth 2.1 authorization server."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from procurement_core import oauth

_PAGE_STYLE = """
body { font-family: system-ui, sans-serif; max-width: 28rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.55; color: #1c1c1c; }
code { background: #f4f4f4; border-radius: 6px; padding: 0.1rem 0.35rem; }
input, button { font: inherit; width: 100%; box-sizing: border-box; padding: 0.6rem 0.7rem; margin: 0.35rem 0 0.9rem; }
button { background: #0b57d0; color: #fff; border: 0; border-radius: 8px; cursor: pointer; }
.sub { color: #555; }
.warn { background: #fff4cc; padding: 0.7rem 0.8rem; border-radius: 8px; }
.error { color: #9b1c1c; }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{title}</title><style>{_PAGE_STYLE}</style></head><body>"
        f"{body}</body></html>"
    )


def _hidden_params(params: dict[str, str]) -> str:
    parts = []
    for key, value in params.items():
        escaped = (
            str(value)
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
        )
        parts.append(f'<input type="hidden" name="{key}" value="{escaped}">')
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
    host = oauth.consent_hostname(params.get("redirect_uri", ""))
    error_html = f'<p class="error">{error}</p>' if error else ""
    notice_html = f'<p class="warn">{notice}</p>' if notice else ""
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


def _code_form(login_id: str, email: str, *, dev_code: str = "", error: str = "") -> str:
    hint = ""
    if dev_code:
        hint = (
            f'<p class="warn">Developer mode: your code is '
            f'<code data-otp="{dev_code}">{dev_code}</code>.</p>'
        )
    error_html = f'<p class="error">{error}</p>' if error else ""
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
    consent_id = login_result["consent_id"]
    return _page(
        "Approve workspaceAlberta access",
        f"""
<h1>Allow access?</h1>
<p><strong>{client_name}</strong> wants to use workspaceAlberta as <code>{user['email']}</code>.</p>
<p>We will send you back to <code>{host}</code>.</p>
<p class="sub">Pro tools stay locked unless this email has an active workspaceAlberta Pro subscription.</p>
<form method="post" action="/authorize/consent">
  <input type="hidden" name="consent_id" value="{consent_id}">
  <button type="submit" name="decision" value="approve">Allow</button>
  <button type="submit" name="decision" value="deny" style="background:#555;margin-top:0.4rem">Deny</button>
</form>
""",
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

    @app.get("/authorize", include_in_schema=False)
    async def authorize_get(request: Request) -> HTMLResponse | RedirectResponse:
        params = _params_from_request(request)
        try:
            checked = oauth.validate_authorize_params(params)
        except oauth.OAuthError as exc:
            target = _error_redirect(
                params.get("redirect_uri", ""),
                exc.error,
                exc.description,
                params.get("state", ""),
            )
            if target:
                return RedirectResponse(target, status_code=302)
            return HTMLResponse(_page("Authorization error", f"<p class='error'>{exc.description}</p>"), 400)
        return HTMLResponse(_email_form(checked))

    @app.post("/authorize", include_in_schema=False)
    async def authorize_start(request: Request) -> HTMLResponse | RedirectResponse:
        form = await _form_map(request)
        params = _params_from_form(form)
        try:
            checked = oauth.validate_authorize_params(params)
            started = oauth.start_login(form.get("email", ""), checked)
        except oauth.OAuthError as exc:
            try:
                checked = oauth.validate_authorize_params(params)
            except oauth.OAuthError:
                return HTMLResponse(_page("Authorization error", f"<p class='error'>{exc.description}</p>"), 400)
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
        form = await _form_map(request)
        try:
            result = oauth.verify_login(form.get("login_id", ""), form.get("code", ""))
        except oauth.OAuthError as exc:
            return HTMLResponse(
                _code_form(form.get("login_id", ""), "", error=exc.description),
                400,
            )
        return HTMLResponse(_consent_form(result))

    @app.post("/authorize/consent", include_in_schema=False)
    async def authorize_consent(request: Request) -> HTMLResponse | RedirectResponse:
        form = await _form_map(request)
        try:
            session = oauth.take_consent(form.get("consent_id", ""))
        except oauth.OAuthError as exc:
            return HTMLResponse(_page("Authorization error", f"<p class='error'>{exc.description}</p>"), 400)
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
            checked = oauth.validate_authorize_params(params)
        except oauth.OAuthError as exc:
            return HTMLResponse(_page("Authorization error", f"<p class='error'>{exc.description}</p>"), 400)
        code = oauth.issue_authorization_code(session["user"], checked)
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
            tokens = oauth.issue_tokens(form)
        except oauth.OAuthError as exc:
            return _oauth_error_response(exc)
        return JSONResponse(tokens, headers={"Cache-Control": "no-store"})

    @app.post("/register", include_in_schema=False)
    async def register_endpoint(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise oauth.OAuthError(400, "invalid_client_metadata", "JSON object required.")
            created = oauth.register_client(payload)
        except oauth.OAuthError as exc:
            return _oauth_error_response(exc)
        return JSONResponse(created, status_code=201)
