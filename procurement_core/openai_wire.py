"""MCP 2.x context middleware for OpenAI's non-core tool declarations."""
from copy import deepcopy

from procurement_core import oauth

# Virtual tools injected by PostHog MCP Analytics (collect_feedback / report_missing).
# They are public (no sign-in required) and carry no server-owned _meta or title until here.
POSTHOG_VIRTUAL_TOOL_TITLES = {
    "send_feedback": "Send agent feedback",
    "get_more_tools": "Request missing tools",
}
POSTHOG_VIRTUAL_TOOLS = frozenset(POSTHOG_VIRTUAL_TOOL_TITLES)


def _public_security_schemes() -> list[dict]:
    return [{"type": "noauth"}, {"type": "oauth2", "scopes": [oauth.SCOPE_PRO]}]


async def preserve_auth_metadata(ctx, call_next):
    """Restore trusted extensions after SDK protocol-version projection.

    Core fields and protocol envelopes remain SDK-validated. Only tools/list
    receives the auth declarations already present in the server-owned _meta
    (plus public declarations and titles for PostHog MCP Analytics virtual tools).
    Other methods, errors, identity checks and middleware remain unchanged.
    """
    result = await call_next(ctx)
    if ctx.method != "tools/list":
        return result
    if not isinstance(result, dict):
        raise TypeError("Expected the MCP middleware's serialized tools/list result")
    tools = []
    for tool in result.get("tools", []):
        name = tool.get("name")
        meta = tool.get("_meta")
        schemes = meta.get("securitySchemes") if isinstance(meta, dict) else None
        if name in POSTHOG_VIRTUAL_TOOL_TITLES:
            title = (tool.get("title") or "").strip() or POSTHOG_VIRTUAL_TOOL_TITLES[name]
            raw_annotations = tool.get("annotations")
            annotations = {
                **(raw_annotations if isinstance(raw_annotations, dict) else {}),
                "title": title,
            }
            if not isinstance(schemes, list) or not schemes:
                schemes = _public_security_schemes()
            meta = {**(meta if isinstance(meta, dict) else {}), "securitySchemes": deepcopy(schemes)}
            tool = {**tool, "title": title, "annotations": annotations, "_meta": meta}
        if not isinstance(schemes, list) or not schemes:
            raise ValueError("Server tool is missing its authentication declaration")
        tools.append({**tool, "securitySchemes": deepcopy(schemes)})
    return {**result, "tools": tools}
