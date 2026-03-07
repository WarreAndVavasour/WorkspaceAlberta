#!/bin/bash
# E2B Sandbox Setup Script for CanadaBuys Showcase

set -e

echo "Setting up CanadaBuys Showcase environment..."

# Refresh contract data on first run
echo "Fetching latest contracts from CanadaBuys..."
python /opt/mcp-servers/canadabuys/server.py --refresh 2>/dev/null || true

echo "Setup complete. CanadaBuys MCP server ready."
echo ""
echo "Available tools:"
echo "  - search_contracts: Search by keywords, province"
echo "  - get_contract_details: Full details by reference number"
echo "  - list_upcoming_deadlines: Contracts closing soon"
echo "  - set_business_profile: Save your business for smart matching"
echo "  - find_opportunities: Find contracts that match your profile"
