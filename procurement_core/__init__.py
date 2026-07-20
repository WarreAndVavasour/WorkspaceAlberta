"""Shared procurement intelligence core for WorkspaceAlberta.

Package layout:

- ``service``       — all tool logic and dispatch (``call_tool_text``); pure
                      Python, no MCP dependency. ``TOOL_NAMES`` is the
                      canonical list of public tools.
- ``e2b_bid_room``  — isolated E2B sandbox processing for tender attachment
                      packages plus in-sandbox Cohere Command A+ review.

Adapters in ``mcp-servers/canadabuys/`` (stdio and StreamableHTTP/REST) are
thin shells over this package. Import from here when embedding the core in
other services:

    from procurement_core import TOOL_NAMES, call_tool_text
"""

from .service import TOOL_NAMES, call_tool_text

__all__ = ["TOOL_NAMES", "call_tool_text"]
