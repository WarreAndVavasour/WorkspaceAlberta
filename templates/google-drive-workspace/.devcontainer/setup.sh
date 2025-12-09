#!/bin/bash
# Post-create setup script for Google Drive workspace

echo "Setting up Google Drive workspace..."

# Install dependencies
npm install

# Create credentials directory
mkdir -p .credentials

# Check if secrets are available
if [ -z "$GOOGLE_CLIENT_ID" ] || [ -z "$GOOGLE_CLIENT_SECRET" ]; then
    echo ""
    echo "============================================"
    echo "  IMPORTANT: Google credentials not found!"
    echo "============================================"
    echo ""
    echo "Please add your Google OAuth credentials:"
    echo "  1. Go to: https://github.com/settings/codespaces"
    echo "  2. Add secret: GOOGLE_CLIENT_ID"
    echo "  3. Add secret: GOOGLE_CLIENT_SECRET"
    echo "  4. Rebuild this Codespace"
    echo ""
    echo "See SETUP-GUIDE.md for detailed instructions."
    echo ""
else
    echo ""
    echo "[OK] Google credentials found!"
    echo ""
    echo "Run 'npm run setup' to complete Google Drive authorization."
    echo ""
fi

echo "Setup script complete."
