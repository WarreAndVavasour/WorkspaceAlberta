# WorkspaceAlberta: a working connection for agents

Connect to `https://elbowsupknivesout.warreandvavasour.com/mcp` using StreamableHTTP, initialize, discover the current tool schemas, and call `get_server_guide`. Both local stdio and hosted MCP supply the same operating instructions during initialization. REST clients can call `POST /tools/get_server_guide` with `{}`.

The MCP server is the procurement specialist. The [harness](https://github.com/HarleyCoops/workspacealberta-harness) carries the working session; [setup](https://github.com/HarleyCoops/workspaceAlbertaSetup) installs the physical workspace. The [terminal support offer](terminal-offer.md) explains the human relationship around them.

## From an owner's question to a useful handoff

1. Establish the business's actual trade, location, capabilities and constraints. Use an inline profile for anonymous hosted matching; save business details only when asked.
2. Prefer `search_opportunities`, `find_matching_opportunities`, `list_deadlines` and `daily_bid_brief` across CanadaBuys and Alberta APC. Read warnings and stale-data indicators.
3. Use `get_opportunity_details` for shortlisted references. Check source documents and amendments. Never invent a closing timezone or assume a mandatory qualification.
4. Use Cohere analysis when authorized and available. `process_bid_room` sends packages to E2B and evidence to Cohere. `check_cohere_status` only reports configuration; it does not test live inference.
5. Hand back the reference, source URL, reported deadline, reasons for fit, unresolved requirements, artifact locations, owner and next action. Keep model judgments distinct from source facts. People decide whether to bid and authorize external actions.

The server does not submit bids, email buyers, run general company systems or execute A2A tasks. Its agent cards are discovery metadata; clients must use the documented MCP/REST interfaces, not `message/send` or `tasks/get`.

## Cohere integration

The harness deployment patch connects directly to this MCP endpoint and selects Cohere through its compatibility API. The bid-room processor uses Cohere's native V2 API with read-only evidence tools. These are different routes; improvements must be verified on the route they affect.

For a native V2 bridge, map discovered MCP tool names, descriptions and `inputSchema` to Cohere function definitions. Preserve assistant tool calls and their IDs, execute only known authorized tools, and return a document result with the matching `tool_call_id` for every call, including failures. Validate generated arguments locally. Bound turns, calls, output size and time; report exhaustion instead of implying completion. Use `strict_tools` only with compatible schemas and a supported route, and retain local validation even when it is enabled. Do not silently retry a schema rejection in a weaker mode.

Schema annotations describe side effects; they do not grant permission. Do not expose an unrestricted dispatcher or subscriber credentials as model arguments. Unknown tool names, malformed JSON and denied access are failures to surface, not reasons to guess another business action.

References: [Cohere V2 tool-use messages](https://docs.cohere.com/docs/tool-use-overview), [Cohere parameter constraints](https://docs.cohere.com/docs/tool-use-parameter-types), and [OpenAI MCP initialization instructions](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). These guided the connection documentation; live model behavior still requires provider testing.
