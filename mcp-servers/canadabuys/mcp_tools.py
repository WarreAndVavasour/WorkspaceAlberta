"""MCP Tool definitions for the procurement adapters.

This module declares the public tool surface — names, descriptions, and JSON
input schemas — shared by both MCP adapters (stdio and StreamableHTTP) and
mirrored by the REST ``/tools`` endpoint. It contains no logic: every tool
name here must have a matching async handler in
``procurement_core.service`` and appear in ``service.TOOL_NAMES``, or calls
will fail at dispatch.

Tool groups, in declaration order:

- **Legacy CanadaBuys tools** (``search_contracts``, ``get_contract_details``,
  ``list_upcoming_deadlines``, ``summarize_contracts``, ``refresh_data``):
  federal-only tools kept for backwards compatibility.
- **Business profile tools** (``set_business_profile``,
  ``find_opportunities``, ``get_my_profile``): save and use the owner's
  capability profile for scoring.
- **Unified tools** (``search_opportunities``, ``get_opportunity_details``,
  ``list_deadlines``, ``find_matching_opportunities``, ``daily_bid_brief``):
  the primary surface — CanadaBuys and Alberta APC together.
- **Alberta APC tools** (``search_alberta_opportunities``, etc.):
  Alberta-only variants for targeted provincial work.
- **Sandbox & model tools** (``process_bid_room``, ``check_cohere_status``,
  ``analyze_contract_with_cohere``): E2B bid-room processing and optional
  Cohere Command A+ review.

When adding a tool: add the ``Tool`` entry here, implement the async handler
in ``procurement_core/service.py``, add the name to ``TOOL_NAMES``, and cover
it in ``tests/``. Keep descriptions user-facing and concrete — they are what
the calling model sees when choosing tools.
"""

from mcp.types import Tool


def get_mcp_tools() -> list[Tool]:
    """Return the full declared tool list in stable order."""
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
            description="Find government contracts that match your business profile. Returns scored and ranked opportunities with explanations of why each one fits your capabilities.",
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
                    }
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
            description="Rank CanadaBuys and Alberta APC opportunities against the saved business profile.",
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
                    }
                }
            }
        ),
        Tool(
            name="daily_bid_brief",
            description="Generate a free daily bid brief from CanadaBuys and Alberta APC for the saved business profile.",
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
                    }
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
            description="Find Alberta Purchasing Connection opportunities that match your saved business profile.",
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
                    }
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
                    }
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
                    }
                },
                "required": ["reference"]
            }
        ),
        # ===== Extension Tools (watchlist + scorecard) =====
        Tool(
            name="watch_opportunity",
            description="Add a CanadaBuys or Alberta APC opportunity to your persistent watchlist, with an optional note.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference number to track"
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional note, e.g. 'waiting on bonding quote'"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_watchlist",
            description="List watched opportunities sorted by closing date, with days remaining and notes.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="unwatch_opportunity",
            description="Remove an opportunity from the watchlist by reference number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference number to stop tracking"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="bid_no_bid_scorecard",
            description="Fast deterministic bid/no-bid checklist for one opportunity: profile fit, runway to closing, region match, and a go/caution/no-go verdict with reasons. No model call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "CanadaBuys or Alberta APC reference number"
                    }
                },
                "required": ["reference"]
            }
        )
    ]
