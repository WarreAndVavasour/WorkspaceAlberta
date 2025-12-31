# GitHub Repository Automation

Create new GitHub repositories with MCP workspace configurations automatically.

## Quick Start

```bash
# Install dependencies
npm install

# Set your GitHub token
export GITHUB_TOKEN=ghp_your_token_here

# Dry run to preview
npx ts-node scripts/create-repo-from-template.ts \
  --username mycompany \
  --repo sales-workspace \
  --tools google_drive,slack,github \
  --dry-run

# Create the repository
npx ts-node scripts/create-repo-from-template.ts \
  --username mycompany \
  --repo sales-workspace \
  --tools google_drive,slack,github
```

## Prerequisites

### 1. Install Dependencies

```bash
npm install
```

This installs:
- `@octokit/rest` - GitHub API client
- `minimist` - CLI argument parsing
- `ts-node` - TypeScript execution
- `typescript` - TypeScript compiler

### 2. Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Fine-grained tokens"**
3. Configure:
   - **Token name**: `workspace-alberta-automation`
   - **Expiration**: 90 days recommended
   - **Repository access**: Choose where you want to create workspaces
   - **Permissions**:
     - Contents: Read and write
     - Metadata: Read-only
4. Click **"Generate token"** and copy it immediately

### 3. Set Environment Variable

```bash
# Linux/macOS
export GITHUB_TOKEN=ghp_your_token_here

# Windows PowerShell
$env:GITHUB_TOKEN = "ghp_your_token_here"

# Windows CMD
set GITHUB_TOKEN=ghp_your_token_here
```

## Usage

```bash
npx ts-node scripts/create-repo-from-template.ts [options]
```

### Required Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--username` | GitHub username or organization | `mycompany` |
| `--repo` | Name for the new repository | `sales-workspace` |
| `--tools` | Comma-separated tool IDs from catalog | `google_drive,slack,github` |

### Optional Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--dry-run` | Preview without creating repo | `false` |
| `--private` | Create private repository | `false` (public) |
| `--template` | Template repository (owner/repo) | none |

## Examples

### Preview with Dry Run

```bash
npx ts-node scripts/create-repo-from-template.ts \
  --username mycompany \
  --repo sales-workspace \
  --tools google_drive,slack,github,stripe \
  --dry-run
```

### Create Public Repository

```bash
npx ts-node scripts/create-repo-from-template.ts \
  --username mycompany \
  --repo sales-workspace \
  --tools google_drive,slack,github,stripe
```

### Create Private Repository

```bash
npx ts-node scripts/create-repo-from-template.ts \
  --username mycompany \
  --repo client-workspace \
  --tools google_drive,notion,linear \
  --private
```

## Using the Generator CLI

You can also use the generator directly to create local workspace files:

```bash
# List all available tools
npx ts-node generator/generator.ts --list

# Generate workspace files locally
npx ts-node generator/generator.ts google_drive slack github

# Dry run to preview
npx ts-node generator/generator.ts --dry-run google_drive slack

# Generate with custom output directory and README
npx ts-node generator/generator.ts --out ./my-workspace --with-readme google_drive slack
```

## Common Tool Combinations

**Sales Team:**
```bash
--tools google_drive,gmail,slack,salesforce,hubspot,stripe
```

**Development Team:**
```bash
--tools github,gitlab,linear,jira,slack,sentry
```

**Marketing Team:**
```bash
--tools google_drive,google_analytics,mailchimp,hubspot,slack
```

**Finance Team:**
```bash
--tools google_drive,quickbooks,stripe,xero,slack
```

## Generated Repository Structure

```
.
├── .cursor/
│   └── mcp.json          # MCP server configuration
├── env/
│   └── .env.example      # Environment variables template
├── docs/
│   └── INTEGRATIONS.md   # Integration details
├── .gitignore
└── README.md
```

## Post-Creation Setup

1. Clone: `git clone https://github.com/<username>/<repo>.git`
2. Configure: `cp env/.env.example env/.env`
3. Add credentials to `env/.env`
4. Open: `cursor .`

## Troubleshooting

### GITHUB_TOKEN not set
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

### Unknown tool IDs
List available tools:
```bash
npx ts-node generator/generator.ts --list
```

### 401 Bad credentials
Token may be invalid or expired. Generate a new one.

### Repository already exists
Choose a different name or delete the existing repo first.

### Module not found errors
Run `npm install` to install dependencies.

## Security

- Never commit `.env` files (`.gitignore` prevents this)
- Use fine-grained tokens with minimal permissions
- Rotate tokens regularly
- Always `--dry-run` first to review

## Learning TypeScript

This codebase is a good learning opportunity:

- **generator/generator.ts** - Shows TypeScript basics:
  - Type definitions (`interface`, `type`)
  - Generics (`Map<string, Tool>`)
  - Module exports/imports
  - File system operations with Node.js

- **scripts/create-repo-from-template.ts** - Shows async/await:
  - Promise-based API calls
  - Error handling with try/catch
  - Working with external APIs (Octokit)
