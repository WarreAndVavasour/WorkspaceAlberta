"""MCP 2.x context middleware for OpenAI's non-core tool declarations."""
from copy import deepcopy


async def preserve_auth_metadata(ctx, call_next):
    """Restore trusted extensions after SDK protocol-version projection.

    Core fields and protocol envelopes remain SDK-validated. Only tools/list
    receives the auth declarations already present in the server-owned _meta.
    Other methods, errors, identity checks and middleware remain unchanged.
    """
    result = await call_next(ctx)
    if ctx.method != "tools/list":
        return result
    if not isinstance(result, dict):
        raise TypeError("Expected the MCP middleware's serialized tools/list result")
    tools = []
    for tool in result.get("tools", []):
        schemes = tool.get("_meta", {}).get("securitySchemes")
        if not isinstance(schemes, list) or not schemes:
            raise ValueError("Server tool is missing its authentication declaration")
        tools.append({**tool, "securitySchemes": deepcopy(schemes)})
    return {**result, "tools": tools}
