"""MCP Tool definitions for the procurement adapters."""

import os

from mcp.types import Tool

# Tools that read/write the single file-backed profile; hidden in public mode
# because every anonymous caller would share the same file.
PROFILE_STORAGE_TOOLS = frozenset({"set_business_profile", "get_my_profile"})

# Inline per-request profile, so shared public deployments never need saved state.
PROFILE_ARG_SCHEMA = {
    "type": "object",
    "description": (
        "Inline business profile used for this call only. Overrides any saved "
        "profile. On the shared public endpoint this is the way to describe "
        "your business."
    ),
    "properties": {
        "company_name": {"type": "string", "description": "Company name"},
        "location": {"type": "string", "description": "Where the business is located, e.g. 'Edmonton, Alberta'"},
        "description": {"type": "string", "description": "What the business does: products, services, capabilities"},
        "capabilities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional explicit capability keywords; derived from description when omitted",
        },
        "industries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional industries such as steel, lumber, aluminum, construction",
        },
    },
}


def is_public_mode() -> bool:
    """True when this deployment serves many anonymous users at once."""
    return os.environ.get("WORKSPACEALBERTA_PUBLIC_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def get_mcp_tools(public_mode: bool | None = None) -> list[Tool]:
    """List available tools, hiding shared-state profile tools in public mode."""
    tools = _all_tools()
    if public_mode is None:
        public_mode = is_public_mode()
    if public_mode:
        tools = [tool for tool in tools if tool.name not in PROFILE_STORAGE_TOOLS]
    return tools


def _all_tools() -> list[Tool]:
    """Full tool catalogue."""
    return [
        Tool(
            name="search_contracts",
            description="Search Canadian federal government contracts. Filter by keywords, province, or status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords (e.g., 'steel', 'construction', 'IT services')"
                    },
                    "province": {
                        "type": "string",
                        "description": "Filter by province (e.g., 'Alberta', 'Ontario', 'Quebec')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 10)",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="get_contract_details",
            description="Get full details of a contract by reference or solicitation number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference or solicitation number"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_upcoming_deadlines",
            description="List contracts with upcoming closing deadlines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Show contracts closing within N days (default 30)",
                        "default": 30
                    },
                    "province": {
                        "type": "string",
                        "description": "Filter by province"
                    }
                }
            }
        ),
        Tool(
            name="summarize_contracts",
            description="Get a summary of available contracts.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="refresh_data",
            description="Refresh contract data from CanadaBuys.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # ===== Business Profile Tools =====
        Tool(
            name="set_business_profile",
            description="Tell me about your business. I'll save your profile and use it to find matching government contracts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Your company name"
                    },
                    "location": {
                        "type": "string",
                        "description": "Where you're located (e.g., 'Edmonton, Alberta')"
                    },
                    "description": {
                        "type": "string",
                        "description": "What does your business do? Describe your products, services, and capabilities."
                    }
                },
                "required": ["description"]
            }
        ),
        Tool(
            name="find_opportunities",
            description="Find government contracts that match your business profile. Returns scored and ranked opportunities with explanations of why each one fits your capabilities. Pass an inline `profile` to describe the business per call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Only show contracts closing within N days (default: 60)",
                        "default": 60
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum opportunities to return (default: 15)",
                        "default": 15
                    },
                    "profile": PROFILE_ARG_SCHEMA
                }
            }
        ),
        Tool(
            name="get_my_profile",
            description="View your current business profile that's being used to match contracts.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # ===== Unified Procurement Tools =====
        Tool(
            name="search_opportunities",
            description="Search CanadaBuys and Alberta Purchasing Connection together.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search words or phrase"
                    },
                    "source": {
                        "type": "string",
                        "description": "all, federal, or alberta",
                        "default": "all"
                    },
                    "province": {
                        "type": "string",
                        "description": "Optional province or delivery region filter"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category such as services, goods, construction, steel, lumber"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum combined results (default 20, max 50)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="get_opportunity_details",
            description="Get details for a federal CanadaBuys or Alberta APC opportunity by reference number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference number, such as AB-2026-03908 or a CanadaBuys reference"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_deadlines",
            description="List CanadaBuys and Alberta APC opportunities closing soon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Show opportunities closing within N days (default 30)",
                        "default": 30
                    },
                    "source": {
                        "type": "string",
                        "description": "all, federal, or alberta",
                        "default": "all"
                    },
                    "province": {
                        "type": "string",
                        "description": "Optional province or delivery region filter"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum combined results (default 20, max 50)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="find_matching_opportunities",
            description="Rank CanadaBuys and Alberta APC opportunities against a business profile. Pass an inline `profile` to describe the business per call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Only show opportunities closing within N days (default 60)",
                        "default": 60
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum opportunities to return (default 15, max 30)",
                        "default": 15
                    },
                    "profile": PROFILE_ARG_SCHEMA
                }
            }
        ),
        Tool(
            name="daily_bid_brief",
            description="Generate a free daily bid brief from CanadaBuys and Alberta APC for a business profile. Pass an inline `profile` to describe the business per call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Look ahead this many days for matches and deadlines (default 14)",
                        "default": 14
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items per section (default 5, max 10)",
                        "default": 5
                    },
                    "profile": PROFILE_ARG_SCHEMA
                }
            }
        ),
        # ===== Alberta Purchasing Connection Tools =====
        Tool(
            name="search_alberta_opportunities",
            description="Search Alberta Purchasing Connection opportunities from Alberta public-sector buyers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search words or phrase"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category: services, goods, or construction"
                    },
                    "status": {
                        "type": "string",
                        "description": "APC status code (default OPEN)",
                        "default": "OPEN"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 10, max 50)",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="get_alberta_opportunity_details",
            description="Get full Alberta Purchasing Connection details by reference number, such as AB-2026-03908.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "APC reference number"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_alberta_deadlines",
            description="List open Alberta Purchasing Connection opportunities closing soon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Show opportunities closing within N days (default 30)",
                        "default": 30
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category: services, goods, or construction"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 20, max 50)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="summarize_alberta_opportunities",
            description="Summarize current open Alberta Purchasing Connection opportunities by category.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="find_alberta_opportunities",
            description="Find Alberta Purchasing Connection opportunities that match your business profile. Pass an inline `profile` to describe the business per call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Only show opportunities closing within N days (default: 60)",
                        "default": 60
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum opportunities to return (default: 15)",
                        "default": 15
                    },
                    "profile": PROFILE_ARG_SCHEMA
                }
            }
        ),
        Tool(
            name="process_bid_room",
            description="Use an E2B sandbox to process tender attachments and call Cohere Command A+ inside the sandbox for bid-room analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "CanadaBuys or Alberta APC reference number"
                    },
                    "business_context": {
                        "type": "string",
                        "description": "Optional company capabilities or bid context. If omitted, the saved business profile is used."
                    },
                    "max_attachments": {
                        "type": "integer",
                        "description": "Maximum direct attachments to process (default 5, max 5)",
                        "default": 5
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "E2B sandbox timeout in seconds (default 900)",
                        "default": 900
                    },
                    "command_timeout_seconds": {
                        "type": "integer",
                        "description": "Sandbox command timeout in seconds (default 420)",
                        "default": 420
                    },
                    "profile": PROFILE_ARG_SCHEMA
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="check_cohere_status",
            description="Check whether the optional Cohere Command A+ model integration is configured. Does not call the model.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="analyze_contract_with_cohere",
            description="Use Cohere Command A+ to review a CanadaBuys tender and explain fit, risks, and next steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference or solicitation number for the tender to analyze"
                    },
                    "business_context": {
                        "type": "string",
                        "description": "Optional company capabilities or bid context. If omitted, the saved business profile is used."
                    },
                    "question": {
                        "type": "string",
                        "description": "Optional specific question to ask about the tender"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum model response tokens (default 1200, max 2000)",
                        "default": 1200
                    },
                    "profile": PROFILE_ARG_SCHEMA
                },
                "required": ["reference"]
            }
        )
    ]
