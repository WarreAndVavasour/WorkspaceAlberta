# Getting Started with WorkspaceAlberta

Welcome! This guide will help you set up your customized Cursor workspace.

## Prerequisites

- [Cursor IDE](https://cursor.sh) installed
- Git installed
- API keys for services you want to use

## Step 1: Clone the Repository

```bash
git clone https://github.com/HarleyCoops/WorkspaceAlberta.git
cd WorkspaceAlberta
```

## Step 2: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` in a text editor and add your API keys

## Step 3: Open in Cursor

1. Open Cursor IDE
2. File > Open Folder > Select WorkspaceAlberta
3. Cursor will automatically load the workspace settings

## Step 4: Verify Setup

- Check that MCP servers are connected (look for green indicators)
- Try a simple command to test integrations

## Troubleshooting

### MCP servers not connecting
- Verify your API keys are correct in `.env`
- Restart Cursor after adding keys
- Check the MCP server logs for errors

### Missing features
- Ensure you're using the latest version of Cursor
- Some features require specific API access levels

## Need Help?

Open an issue on GitHub or check the main documentation.
