"""OpenAI interoperability without a second procurement backend.

Authorization, tenant isolation and subscription enforcement stay in oauth/identity.
"""
from __future__ import annotations
import asyncio
import os
import re
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from mcp.types import ListToolsResult, Tool
from pydantic import Field
from procurement_core import oauth
from procurement_core.auth import GateError, PRO_TOOLS, SIGN_IN_TOOLS, extract_bearer_key

STABLE_CALLBACK = "https://chatgpt.com/connector_platform_oauth_redirect"


class OpenAITool(Tool):
    """Explicit extension field: MCP 2.x otherwise discards unknown properties."""
    security_schemes: list[dict[str, Any]] = Field(alias="securitySchemes")


class OpenAIListToolsResult(ListToolsResult):
    """Retain the extension through nested Pydantic serialization."""
    tools: list[OpenAITool]


def openai_redirect_allowed(uri: str) -> bool:
    """Accept exact official callbacks, never a hostname wildcard."""
    if uri == STABLE_CALLBACK:
        return True
    configured = os.environ.get("WA_OPENAI_REDIRECT_URIS", "").split(",")
    return uri in {u.strip() for u in configured if re.fullmatch(
        r"https://chatgpt\.com/connector/oauth/[A-Za-z0-9_-]+", u.strip())}


def userinfo(authorization: str | None) -> dict[str, Any]:
    token = extract_bearer_key(authorization)
    if not token:
        raise GateError(401, "An OAuth access token is required.")
    try:
        claims = oauth.validate_access_token(token)
    except (ValueError, TypeError, UnicodeError, AttributeError):
        raise GateError(401, "Invalid OAuth access token.") from None
    if not {"openid", "email"}.issubset(str(claims.get("scope", "")).split()):
        raise GateError(403, "Reauthorize with openid and email scopes.")
    if claims.get("email_verified") is not True:
        raise GateError(403, "Reauthorize to provide a verified email.")
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise GateError(401, "The signed-in identity is missing.")
    user = oauth.get_store().get_user(user_id)
    if not user or user.get("email") != claims.get("email"):
        raise GateError(401, "The account changed or no longer exists; sign in again.")
    email = user.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise GateError(401, "The account has no verified email.")
    return {"sub": user_id, "email": email, "email_verified": True}


def annotate_tools(tools: list[Tool]) -> list[OpenAITool]:
    result = []
    for tool in tools:
        payload = tool.model_dump(by_alias=True, exclude_none=True)
        authenticated = {"type": "oauth2", "scopes": [oauth.SCOPE_PRO]}
        schemes = [authenticated] if tool.name in PRO_TOOLS | SIGN_IN_TOOLS else [{"type": "noauth"}, authenticated]
        payload["securitySchemes"] = schemes
        payload.setdefault("_meta", {})["securitySchemes"] = schemes
        if tool.name == "process_bid_room":
            payload["annotations"]["readOnlyHint"] = False
        result.append(OpenAITool.model_validate(payload))
    return result


def register_openai_routes(app: FastAPI) -> None:
    @app.get("/.well-known/openid-configuration", include_in_schema=False)
    async def discovery() -> JSONResponse:
        return JSONResponse(oauth.authorization_server_metadata())

    @app.get("/.well-known/openai-apps-challenge", include_in_schema=False)
    async def domain_challenge() -> PlainTextResponse:
        token = os.environ.get("WA_OPENAI_APPS_CHALLENGE", "")
        if not token:
            return PlainTextResponse("Not configured", status_code=404, headers={"Cache-Control": "no-store"})
        return PlainTextResponse(token, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @app.api_route("/userinfo", methods=["GET", "POST"], include_in_schema=False)
    async def userinfo_endpoint(request: Request) -> JSONResponse:
        headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
        try:
            claims = await asyncio.to_thread(userinfo, request.headers.get("authorization"))
        except GateError as exc:
            error = "insufficient_scope" if exc.status_code == 403 else "invalid_token"
            headers["WWW-Authenticate"] = oauth.www_authenticate_challenge(error=error, description=str(exc), scope="openid email")
            return JSONResponse({"error": error, "error_description": str(exc)}, status_code=exc.status_code, headers=headers)
        return JSONResponse(claims, headers=headers)
