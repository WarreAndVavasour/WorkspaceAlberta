#!/bin/bash
# WorkspaceAlberta - Post-Create Setup Script
# This runs after the Codespace container is created

set -e

echo "==========================================="
echo "  WorkspaceAlberta Workspace Setup"
echo "==========================================="

# Install Node.js MCP dependencies globally
echo "[1/4] Installing MCP server dependencies..."
npm install -g @modelcontextprotocol/sdk 2>/dev/null || true

# Install any project-specific dependencies
if [ -f "package.json" ]; then
    echo "[2/4] Installing project dependencies..."
    npm install
else
    echo "[2/4] No package.json found, skipping npm install"
fi

# Install Python dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "[3/4] Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "[3/4] No requirements.txt found, skipping pip install"
fi

# Verify MCP configuration exists
echo "[4/4] Verifying MCP configuration..."
if [ -f ".vscode/mcp.json" ]; then
    echo "  - MCP configuration found at .vscode/mcp.json"
    echo "  - Your MCP servers will be available in VS Code"
else
    echo "  - No MCP configuration found (this is okay for basic workspaces)"
fi

# Display configured secrets status
echo ""
echo "==========================================="
echo "  Environment Status"
echo "==========================================="

check_secret() {
    if [ -n "${!1}" ]; then
        echo "  [OK] $1 is configured"
    else
        echo "  [--] $1 not set (add in Codespaces secrets)"
    fi
}

# Check common secrets
check_secret "ANTHROPIC_API_KEY"
check_secret "STRIPE_API_KEY"
check_secret "GOOGLE_CLIENT_ID"
check_secret "GITHUB_TOKEN"

echo ""
echo "==========================================="
echo "  Setup Complete!"
echo "==========================================="
echo ""
echo "Next steps:"
echo "  1. Open docs/WELCOME.md for your personalized guide"
echo "  2. Add any missing API keys in Codespaces secrets"
echo "  3. Start working on your business problem!"
echo ""
