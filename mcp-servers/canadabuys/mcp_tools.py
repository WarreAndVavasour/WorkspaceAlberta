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
- **Sandbox & model tools** (``process_bid_room``, ``classify_tender``,
  ``check_cohere_status``, ``analyze_contract_with_cohere``): E2B bid-room
  processing, TypeSafe Jev requirement classification and optional Cohere
  Command A+ review.

When adding a tool: add the ``Tool`` entry here, implement the async handler
in ``procurement_core/service.py``, add the name to ``TOOL_NAMES``, and cover
it in ``tests/``. Keep descriptions user-facing and concrete — they are what
the calling model sees when choosing tools.
"""

from mcp.types import Tool, ToolAnnotations
from procurement_core.agent_contract import PERSISTENT_TOOLS
from procurement_core.auth import PRO_TOOLS, SIGN_IN_TOOLS

# Inline per-request profile: anonymous callers on the shared hosted endpoint
# have no tenant row, so this is how they describe their business without
# overwriting each other's saved file. Overrides the saved profile when passed.
PROFILE_ARG_SCHEMA = {
    "type": "object",
    "description": (
        "Inline business profile used for this call only. Overrides any saved "
        "profile. On the shared public endpoint without a subscriber key, "
        "this is the way to describe your business."
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
            "description": (
                "Optional sector labels for any business. Steel, lumber, aluminum, and "
                "construction still work. So do software, healthcare, energy, mining, "
                "training, or your own wording. Labels rank matches. They do not hide other contracts."
            ),
        },
    },
}


_OPPORTUNITY_RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "source": {"type": "string"},
        "reference": {"type": "string"},
        "buyer": {"type": "string"},
        "category": {"type": "string"},
        "closing": {"type": "string", "description": "Closing value exactly as the source published it"},
        "closes_at": {
            "type": "string",
            "description": "Closing time as ISO 8601 in Alberta time with UTC offset; empty when unknown",
        },
        "region": {"type": "string"},
        "solicitation": {"type": "string"},
        "unspsc": {"type": "string", "description": "UNSPSC code or codes from the source, when published"},
        "unspsc_description": {"type": "string"},
        "gsin": {"type": "string", "description": "GSIN code from CanadaBuys, when published"},
        "gsin_description": {"type": "string"},
        "trade_agreements": {"type": "string"},
        "procurement_method": {"type": "string"},
        "selection_criteria": {"type": "string"},
        "domestic_policies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Buy Canadian and domestic-preference flags read from the notice",
        },
    },
}

# Structured payload advertised on the tools that return structured_content.
OPPORTUNITIES_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string"},
        "count": {"type": "integer"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "opportunities": {"type": "array", "items": _OPPORTUNITY_RECORD_SCHEMA},
    },
}

MATCHES_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string"},
        "count": {"type": "integer"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    **_OPPORTUNITY_RECORD_SCHEMA["properties"],
                    "score": {"type": "integer"},
                    "days_until": {
                        "type": ["integer", "null"],
                        "description": "Calendar days to the closing date in Alberta time; 0 means it closes today",
                    },
                    "reasons": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def get_mcp_tools() -> list[Tool]:
    """Return the full declared tool list in stable order."""
    tools = [
        Tool(
            name="get_server_guide",
            title="Read the WorkspaceAlberta guide",
            description="Start here when connecting an agent: explains what workspaceAlberta does, the search-to-bid-review workflow, handoff fields, data boundaries and unsupported actions. No model or network call.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        Tool(
            name="search_contracts",
            title="Search federal contracts",
            description="Legacy: federal CanadaBuys only. Filter by keywords or province. Prefer search_opportunities for combined CanadaBuys and Alberta APC results.",
            input_schema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords for any sector, such as software, training, steel, healthcare, or logistics"
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
            title="Get federal contract details",
            description="Legacy: federal CanadaBuys details only, by reference or solicitation number. Prefer get_opportunity_details for federal or Alberta APC tenders.",
            input_schema={
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
            title="List federal contract deadlines",
            description="Legacy: federal CanadaBuys closing deadlines only. Prefer list_deadlines for combined CanadaBuys and Alberta APC results.",
            input_schema={
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
            title="Summarize federal contracts",
            description="Legacy: summarize federal CanadaBuys contracts only. For combined discovery use search_opportunities or daily_bid_brief; this summary excludes Alberta APC.",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="refresh_data",
            title="Refresh federal contract data",
            description="Refresh contract data from CanadaBuys.",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        # ===== Business Profile Tools =====
        Tool(
            name="set_business_profile",
            title="Save my business profile",
            description="Tell me about your business. I'll save your profile and use it to find matching government contracts.",
            input_schema={
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
            title="Find federal opportunities for my business",
            description="Legacy: rank federal CanadaBuys contracts only against your business profile. Prefer find_matching_opportunities for combined CanadaBuys and Alberta APC matches. Anonymous hosted callers must pass an inline profile.",
            input_schema={
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
            title="View my business profile",
            description="View your current business profile that's being used to match contracts.",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        # ===== Unified Procurement Tools =====
        Tool(
            name="search_opportunities",
            title="Search procurement opportunities",
            description=(
                "Search every open CanadaBuys and Alberta Purchasing Connection notice for any business. "
                "Results are not limited to steel, lumber, aluminum, or construction. "
                "Pass description or profile to rank by a TypeSafe Jev supply-fit classification "
                "(yes, partial, or no) after a commodity-code prefilter. Keyword-only searches stay lexical."
            ),
            output_schema=OPPORTUNITIES_OUTPUT_SCHEMA,
            input_schema={
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
                        "description": "Optional category or sector words. Federal search treats this as free text across the full notice, including UNSPSC and GSIN descriptions. Alberta maps services, goods, and construction to APC codes and still searches other words."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum combined results (default 20, max 50)",
                        "default": 20
                    },
                    "description": {
                        "type": "string",
                        "description": "What the business does, in plain language. When set, fit classification runs before keyword ranking."
                    },
                    "location": {
                        "type": "string",
                        "description": "Where the business works, such as Red Deer, Alberta."
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Optional company name."
                    },
                    "profile": PROFILE_ARG_SCHEMA
                }
            }
        ),
        Tool(
            name="get_opportunity_details",
            title="Get procurement opportunity details",
            description="Get details for any federal CanadaBuys or Alberta APC opportunity by reference number, including UNSPSC, GSIN, trade agreements, and Buy Canadian flags when the source published them.",
            input_schema={
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
            title="List procurement deadlines",
            description="List CanadaBuys and Alberta APC opportunities closing soon.",
            output_schema=OPPORTUNITIES_OUTPUT_SCHEMA,
            input_schema={
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
            title="Match procurement opportunities to my business",
            description=(
                "Rank CanadaBuys and Alberta APC opportunities for any business profile, in any sector. "
                "Pass an inline `profile` to describe the business per call. A description is classified with "
                "TypeSafe Jev (yes, partial, or no, and goods supply, services, training, or subcontract) "
                "after a commodity-code prefilter; keyword score and Buy Canadian bonuses break ties. "
                "Steel, lumber, aluminum, and construction remain valid labels."
            ),
            output_schema=MATCHES_OUTPUT_SCHEMA,
            input_schema={
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
            title="Get my daily bid brief",
            description=(
                "Generate a free daily bid brief from the full CanadaBuys and Alberta APC catalogues for any business. "
                "Pass an inline `profile` to describe the business per call. Best fits start with the same TypeSafe Jev "
                "supply classification as find_business_fit. Domestic-preference flags are included when a matched notice carries them."
            ),
            input_schema={
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
        Tool(
            name="find_business_fit",
            title="Find contracts for a business description",
            description=(
                "Rank open CanadaBuys and Alberta Purchasing Connection notices for a free-text business description. "
                "A commodity-code and term prefilter cuts the catalogues to a short candidate list, then TypeSafe Jev "
                "classifies each notice: could this business supply it (yes, partial, or no) and as which capability "
                "(goods supply, services, training, or subcontract). Yes and partial results are ordered by that "
                "verdict, then by the existing keyword score and Buy Canadian bonus. If Jev is not configured or "
                "rejects the key, keyword ranking is used and the result says so. The description and a short notice "
                "summary are sent to TypeSafe when classification runs. See /privacy. workspaceAlberta does not submit "
                "a bid or decide eligibility."
            ),
            output_schema=OPPORTUNITIES_OUTPUT_SCHEMA,
            input_schema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What the business does, in its own words. Example: a bakery in Red Deer that bakes at scale and teaches culinary skills."
                    },
                    "location": {
                        "type": "string",
                        "description": "Where the business works, such as Red Deer, Alberta."
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Optional company name for the heading."
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
                    "days": {
                        "type": "integer",
                        "description": "Only show notices closing within N days (default 120, max 365)",
                        "default": 120
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 15, max 50)",
                        "default": 15
                    },
                    "profile": PROFILE_ARG_SCHEMA
                },
                "required": ["description"]
            }
        ),
        # ===== Alberta Purchasing Connection Tools =====
        Tool(
            name="search_alberta_opportunities",
            title="Search Alberta procurement opportunities",
            description="Search Alberta Purchasing Connection opportunities from Alberta public-sector buyers.",
            input_schema={
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
            title="Get Alberta procurement opportunity details",
            description="Get full Alberta Purchasing Connection details by reference number, such as AB-2026-03908.",
            input_schema={
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
            title="List Alberta procurement deadlines",
            description="List open Alberta Purchasing Connection opportunities closing soon.",
            input_schema={
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
            title="Summarize Alberta procurement opportunities",
            description="Summarize current open Alberta Purchasing Connection opportunities by category.",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="find_alberta_opportunities",
            title="Find Alberta opportunities for my business",
            description="Find Alberta Purchasing Connection opportunities that match your business profile. Pass an inline `profile` to describe the business per call.",
            input_schema={
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
            title="Process bid documents",
            description="Process tender attachments in E2B: sends documents and business context to E2B, PDF page images/images and extracted evidence to Cohere Parse and Command A+. See /privacy for processing locations. For Alberta APC postings, the first call returns a private upload link: the user downloads the documents with their own APC supplier account and uploads them, then you call again with upload_token. Returns within 145 seconds including setup; large packages may time out. Retry with fewer attachments; a timeout is not a completed analysis.",
            input_schema={
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
                        "description": "Maximum procurement files to process (default 5, max 5). Use 0 explicitly for a notice-only review; missing/gated documents do not count as complete coverage.",
                        "default": 5,
                        "minimum": 0,
                        "maximum": 5
                    },
                    "apc_document_urls": {
                        "type": "object",
                        "description": "For APC only: map document IDs from get_opportunity_details to already authorized, publicly accessible HTTPS copies. This tool never signs in to APC, registers supplier interest, subscribes notifications, or accepts authenticated download URLs. Copies are sent to E2B and their contents to Cohere.",
                        "additionalProperties": {"type": "string", "format": "uri"},
                        "maxProperties": 5
                    },
                    "upload_token": {
                        "type": "string",
                        "description": "For APC only: the upload_token from an earlier process_bid_room result. APC releases documents only to the user's own signed-in supplier account, so the first call returns a private upload link; after the user uploads the files they downloaded from APC, call again with this token to process them."
                    },
                    "profile": PROFILE_ARG_SCHEMA
                },
                "required": ["reference"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="classify_tender",
            title="List the bidder requirements in a tender",
            description=(
                "List what a bidder must supply for one tender: splits the tender PDFs into clauses, "
                "classifies each clause and page with TypeSafe AI's Jev classifier, and groups the results "
                "into one requirement per kind (for example key personnel, mandatory site visit, bid bond), "
                "with a mandatory flag, the WorkspaceAlberta connector that would collect it, lead time, "
                "page numbers and short evidence quotes. Clause and page text is sent to TypeSafe AI "
                "(api.typesafe.ai) for classification; WorkspaceAlberta stores nothing beyond the existing "
                "private upload bucket for APC files. PDFs only (PDFs inside ZIPs are read); up to 800 pages "
                "and 8,000 clauses per call. CanadaBuys: reads the public tender attachments. Alberta APC: "
                "the first call returns a private upload link (the same upload flow as process_bid_room); the user downloads "
                "the documents with their own APC supplier account and uploads them, then you call again with "
                "upload_token. The link expires as before (2 hours). This tool does not delete the uploads, so "
                "process_bid_room can use the same upload_token afterwards. Returns markdown followed by the full "
                "result as JSON (schema wa.tender_requirements.v1, with tender closing time and posting link). "
                "Returns within 140 seconds; a "
                "result cut short by a limit is labelled partial. Results are classifier outputs: verify them "
                "against the official posting and amendments."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "CanadaBuys or Alberta APC reference number"
                    },
                    "upload_token": {
                        "type": "string",
                        "description": "For APC only: the upload_token from an earlier classify_tender or process_bid_room result, after the user has uploaded the documents they downloaded from APC."
                    }
                },
                "required": ["reference"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="check_cohere_status",
            title="Check Cohere analysis availability",
            description="Check whether the optional Cohere Command A+ model integration is configured. Does not call the model.",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="analyze_contract_with_cohere",
            title="Analyze a contract with Cohere",
            description="Use Cohere Command A+ to review a CanadaBuys tender and explain fit, risks, and next steps.",
            input_schema={
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
        ),
        Tool(
            name="match_industrial_support_programs",
            title="Match industrial and tariff support",
            description=(
                "Read-only catalog of industrial and tariff support for any Canadian business, "
                "including the October 2026 $8.72 billion federal-provincial package and national "
                "programs an Alberta firm can ask about: PrairiesCan Regional Tariff Response Initiative, "
                "the Strategic Response Fund, the Canada Strong Diversification Fund, BDC Pivot to Grow "
                "and its metals envelope, NRCan First and Last Mile Fund, the Critical Minerals Accelerator, "
                "and the PSPC Buy Canadian Policy Framework. Ontario-only streams are labeled so an Alberta "
                "firm can see they do not apply. workspaceAlberta does not apply for funding or decide eligibility."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What the business does. Any sector, in the business's own words.",
                    },
                    "industry": {
                        "type": "string",
                        "description": "Optional sector label, such as software, healthcare, steel, or critical minerals.",
                    },
                    "location": {
                        "type": "string",
                        "description": "Where the business is located, such as Edmonton, Alberta. Empty assumes Alberta.",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Optional company name for the heading.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum programs in the applies section (default 12, max 20).",
                        "default": 12,
                    },
                    "profile": PROFILE_ARG_SCHEMA,
                },
            },
        ),
        # ===== Extension Tools (watchlist + scorecard) =====
        Tool(
            name="watch_opportunity",
            title="Add an opportunity to my watchlist",
            description="Add a CanadaBuys or Alberta APC opportunity to your persistent watchlist, with an optional note.",
            input_schema={
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
            title="View my opportunity watchlist",
            description="List watched opportunities sorted by closing date, with days remaining and notes.",
            input_schema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="unwatch_opportunity",
            title="Remove an opportunity from my watchlist",
            description="Remove an opportunity from the watchlist by reference number.",
            input_schema={
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
            title="Assess whether to bid",
            description="Fast deterministic bid/no-bid checklist for one opportunity in any sector: profile fit, runway to closing, region match, Buy Canadian or other domestic-preference flags, and a go/caution/no-go verdict with reasons. No model call.",
            input_schema={
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
    for tool in tools:
        if tool.name in PRO_TOOLS:
            tool.description += " Hosted: sign-in and an active workspaceAlberta Pro subscription required."
        elif tool.name in SIGN_IN_TOOLS:
            tool.description += " Hosted: sign-in required; no paid subscription needed."
        if tool.name in {"search_alberta_opportunities", "find_alberta_opportunities", "find_matching_opportunities", "search_opportunities", "daily_bid_brief"}:
            tool.description += " When configured, search terms or business capabilities may be sent to Cohere to select commodity filters. See /privacy."
        if tool.name in {"search_opportunities", "find_matching_opportunities", "daily_bid_brief", "find_business_fit"}:
            tool.description += (
                " When a business description is present and TypeSafe is configured, notice text and that "
                "description are sent to TypeSafe for supply-fit classification. See /privacy."
            )
        persistent = tool.name in PERSISTENT_TOOLS
        tool.annotations = ToolAnnotations(
            title=tool.title,
            readOnlyHint=not persistent,
            destructiveHint=tool.name in {"set_business_profile", "unwatch_opportunity"},
            openWorldHint=tool.name not in {
                "get_server_guide", "get_my_profile", "check_cohere_status",
                "list_watchlist", "unwatch_opportunity", "set_business_profile",
                "match_industrial_support_programs",
            },
        )
    from procurement_core.openai_support import annotate_tools
    return annotate_tools(tools)
