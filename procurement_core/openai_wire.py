"""MCP 2.x context middleware for OpenAI's non-core tool declarations."""
from copy import deepcopy

from procurement_core import oauth

# Virtual tools injected by PostHog MCP Analytics (collect_feedback / report_missing).
# They are public (no sign-in required) and carry no server-owned _meta until here.
POSTHOG_VIRTUAL_TOOLS = frozenset({"send_feedback", "get_more_tools"})


def _public_security_schemes() -> list[dict]:
    return [{"type": "noauth"}, {"type": "oauth2", "scopes": [oauth.SCOPE_PRO]}]


async def preserve_auth_metadata(ctx, call_next):
    """Restore trusted extensions after SDK protocol-version projection.

    Core fields and protocol envelopes remain SDK-validated. Only tools/list
    receives the auth declarations already present in the server-owned _meta
    (plus public declarations for PostHog MCP Analytics virtual feedback tools).
    Other methods, errors, identity checks and middleware remain unchanged.
    """
    result = await call_next(ctx)
    if ctx.method != "tools/list":
        return result
    if not isinstance(result, dict):
        raise TypeError("Expected the MCP middleware's serialized tools/list result")
    tools = []
    for tool in result.get("tools", []):
        meta = tool.get("_meta")
        schemes = meta.get("securitySchemes") if isinstance(meta, dict) else None
        if (not isinstance(schemes, list) or not schemes) and tool.get("name") in POSTHOG_VIRTUAL_TOOLS:
            schemes = _public_security_schemes()
            meta = {**(meta if isinstance(meta, dict) else {}), "securitySchemes": deepcopy(schemes)}
            tool = {**tool, "_meta": meta}
        if not isinstance(schemes, list) or not schemes:
            raise ValueError("Server tool is missing its authentication declaration")
        tools.append({**tool, "securitySchemes": deepcopy(schemes)})
    return {**result, "tools": tools}
