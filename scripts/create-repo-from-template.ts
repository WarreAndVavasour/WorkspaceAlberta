#!/usr/bin/env ts-node
/**
 * Create a new GitHub repository from tool selection
 *
 * This script creates a new GitHub repository with generated workspace configuration files
 * based on the selected MCP tools from the catalog.
 *
 * Usage:
 *   npx ts-node scripts/create-repo-from-template.ts \
 *     --username <github-username> \
 *     --repo <repo-name> \
 *     --tools <tool-id-1,tool-id-2,...> \
 *     [--dry-run] \
 *     [--private]
 *
 * Environment variables:
 *   GITHUB_TOKEN - Required. Fine-grained GitHub PAT with repo:write permissions
 */

import { Octokit } from "@octokit/rest";
import path from "path";
import {
  loadCatalog,
  selectTools,
  buildMcpJson,
  buildEnvExample,
  buildIntegrationsMd,
  Tool,
} from "../generator/generator";

interface RepoOptions {
  username: string;
  repoName: string;
  toolIds: string[];
  dryRun?: boolean;
  template?: string;
  isPrivate?: boolean;
}

interface GeneratedContent {
  path: string;
  content: string;
}

/**
 * Parse command line arguments
 */
function parseArgs(): RepoOptions {
  const args = process.argv.slice(2);
  const options: Partial<RepoOptions> = {
    dryRun: false,
    isPrivate: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    switch (arg) {
      case "--username":
        options.username = args[++i];
        break;
      case "--repo":
        options.repoName = args[++i];
        break;
      case "--tools":
        options.toolIds = args[++i].split(",").map((id) => id.trim());
        break;
      case "--dry-run":
        options.dryRun = true;
        break;
      case "--template":
        options.template = args[++i];
        break;
      case "--private":
        options.isPrivate = true;
        break;
      case "--help":
      case "-h":
        printUsage();
        process.exit(0);
      default:
        console.error(`Unknown argument: ${arg}`);
        printUsage();
        process.exit(1);
    }
  }

  // Validate required options
  if (
    !options.username ||
    !options.repoName ||
    !options.toolIds ||
    options.toolIds.length === 0
  ) {
    console.error("Error: Missing required arguments");
    printUsage();
    process.exit(1);
  }

  return options as RepoOptions;
}

function printUsage(): void {
  console.log(`
Usage: npx ts-node scripts/create-repo-from-template.ts [options]

Required:
  --username <username>      GitHub username or organization
  --repo <repo-name>         Name for the new repository
  --tools <tool-ids>         Comma-separated list of tool IDs from catalog

Optional:
  --dry-run                  Print intended actions without creating repo
  --template <repo>          Template repository (format: owner/repo)
  --private                  Create private repository (default: public)
  --help, -h                 Show this help message

Environment Variables:
  GITHUB_TOKEN               Required. GitHub Personal Access Token with repo permissions

Examples:
  # Dry run to preview
  npx ts-node scripts/create-repo-from-template.ts \\
    --username mycompany \\
    --repo sales-workspace \\
    --tools google_drive,slack,github,stripe \\
    --dry-run

  # Create public repository
  npx ts-node scripts/create-repo-from-template.ts \\
    --username mycompany \\
    --repo sales-workspace \\
    --tools google_drive,slack,github,stripe

  # Create private repository
  npx ts-node scripts/create-repo-from-template.ts \\
    --username mycompany \\
    --repo sales-workspace \\
    --tools google_drive,slack,github \\
    --private
`);
}

/**
 * Generate README.md content
 */
function generateReadme(repoName: string, selectedTools: Tool[]): string {
  const toolList = selectedTools
    .map((t) => `- **${t.display_name}** (${t.category}): ${t.description}`)
    .join("\n");

  return `# ${repoName}

This workspace is configured with MCP (Model Context Protocol) servers for the following integrations:

${toolList}

## Setup

1. Clone this repository:
   \`\`\`bash
   git clone https://github.com/<username>/${repoName}.git
   cd ${repoName}
   \`\`\`

2. Copy the environment template and fill in your credentials:
   \`\`\`bash
   cp env/.env.example env/.env
   \`\`\`

3. Edit \`env/.env\` and add your API keys and credentials for each service.

4. Open the workspace in Cursor:
   \`\`\`bash
   cursor .
   \`\`\`

The MCP servers will automatically connect using the configuration in \`.cursor/mcp.json\`.

## Documentation

- See [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) for detailed integration information
- Refer to each service's documentation for obtaining API credentials

## Project Structure

\`\`\`
.
├── .cursor/
│   └── mcp.json          # MCP server configuration
├── env/
│   └── .env.example      # Environment variables template
├── docs/
│   └── INTEGRATIONS.md   # Integration details
└── README.md             # This file
\`\`\`

---

Generated with [WorkspaceAlberta](https://github.com/HarleyCoops/WorkspaceAlberta)
`;
}

/**
 * Generate .gitignore content
 */
function generateGitignore(): string {
  return `# Environment files
.env
env/.env

# Node modules
node_modules/

# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
`;
}

/**
 * Generate all file contents
 */
function generateFiles(repoName: string, selectedTools: Tool[]): GeneratedContent[] {
  const mcpJson = JSON.stringify(buildMcpJson(selectedTools), null, 2);
  const envExample = buildEnvExample(selectedTools);
  const integrationsMd = buildIntegrationsMd(selectedTools);
  const readme = generateReadme(repoName, selectedTools);
  const gitignore = generateGitignore();

  return [
    { path: ".cursor/mcp.json", content: mcpJson },
    { path: "env/.env.example", content: envExample },
    { path: "docs/INTEGRATIONS.md", content: integrationsMd },
    { path: "README.md", content: readme },
    { path: ".gitignore", content: gitignore },
  ];
}

/**
 * Dry run: print intended actions
 */
function dryRun(
  options: RepoOptions,
  selectedTools: Tool[],
  files: GeneratedContent[]
): void {
  console.log("=== DRY RUN MODE ===\n");
  console.log(`Would create repository: ${options.username}/${options.repoName}`);
  console.log(`Private: ${options.isPrivate}`);
  if (options.template) {
    console.log(`Using template: ${options.template}`);
  }
  console.log(`\nSelected tools (${selectedTools.length}):`);
  selectedTools.forEach((t) => {
    console.log(`  - ${t.id}: ${t.display_name} (${t.integration_status})`);
  });

  console.log(`\nWould create ${files.length} files:`);
  files.forEach((f) => {
    console.log(`  - ${f.path} (${f.content.length} bytes)`);
  });

  console.log("\nFile previews:");
  files.forEach((f) => {
    console.log(`\n--- ${f.path} ---`);
    const preview = f.content.split("\n").slice(0, 10).join("\n");
    console.log(preview);
    if (f.content.split("\n").length > 10) {
      console.log("... (truncated)");
    }
  });

  console.log("\n=== END DRY RUN ===");
}

/**
 * Create GitHub repository and commit files
 */
async function createRepository(
  octokit: Octokit,
  options: RepoOptions,
  selectedTools: Tool[],
  files: GeneratedContent[]
): Promise<string> {
  console.log(`Creating repository: ${options.username}/${options.repoName}...`);

  try {
    // Step 1: Create repository
    let createResponse;
    if (options.template) {
      // Create from template
      const [templateOwner, templateRepo] = options.template.split("/");
      createResponse = await octokit.repos.createUsingTemplate({
        template_owner: templateOwner,
        template_repo: templateRepo,
        owner: options.username,
        name: options.repoName,
        private: options.isPrivate,
        description: `Cursor workspace with MCP integrations: ${options.toolIds.join(", ")}`,
      });
    } else {
      // Create blank repository
      createResponse = await octokit.repos.createForAuthenticatedUser({
        name: options.repoName,
        private: options.isPrivate,
        description: `Cursor workspace with MCP integrations: ${options.toolIds.join(", ")}`,
        auto_init: true, // Create with README to have a main branch
      });
    }

    const repoUrl = createResponse.data.html_url;
    console.log(`✓ Repository created: ${repoUrl}`);

    // Wait a moment for initialization
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // Step 2: Get the default branch
    const { data: repoData } = await octokit.repos.get({
      owner: options.username,
      repo: options.repoName,
    });
    const defaultBranch = repoData.default_branch;

    // Step 3: Get the latest commit SHA
    const { data: refData } = await octokit.git.getRef({
      owner: options.username,
      repo: options.repoName,
      ref: `heads/${defaultBranch}`,
    });
    const latestCommitSha = refData.object.sha;

    // Step 4: Get the tree for the latest commit
    const { data: commitData } = await octokit.git.getCommit({
      owner: options.username,
      repo: options.repoName,
      commit_sha: latestCommitSha,
    });
    const baseTreeSha = commitData.tree.sha;

    // Step 5: Create blobs for all files
    console.log("Creating file blobs...");
    const blobs = await Promise.all(
      files.map(async (file) => {
        const { data: blob } = await octokit.git.createBlob({
          owner: options.username,
          repo: options.repoName,
          content: Buffer.from(file.content).toString("base64"),
          encoding: "base64",
        });
        return {
          path: file.path,
          mode: "100644" as const,
          type: "blob" as const,
          sha: blob.sha,
        };
      })
    );
    console.log(`✓ Created ${blobs.length} file blobs`);

    // Step 6: Create a new tree with all files
    console.log("Creating tree...");
    const { data: newTree } = await octokit.git.createTree({
      owner: options.username,
      repo: options.repoName,
      base_tree: baseTreeSha,
      tree: blobs,
    });
    console.log(`✓ Tree created`);

    // Step 7: Create a commit
    console.log("Creating commit...");
    const { data: newCommit } = await octokit.git.createCommit({
      owner: options.username,
      repo: options.repoName,
      message: `Initialize workspace with ${selectedTools.length} MCP integrations\n\nTools: ${options.toolIds.join(", ")}`,
      tree: newTree.sha,
      parents: [latestCommitSha],
    });
    console.log(`✓ Commit created: ${newCommit.sha.substring(0, 7)}`);

    // Step 8: Update the reference
    console.log("Updating branch...");
    await octokit.git.updateRef({
      owner: options.username,
      repo: options.repoName,
      ref: `heads/${defaultBranch}`,
      sha: newCommit.sha,
    });
    console.log(`✓ Branch ${defaultBranch} updated`);

    console.log(`\n✅ Repository successfully created and configured!`);
    console.log(`   URL: ${repoUrl}`);
    console.log(`\nNext steps:`);
    console.log(`  1. git clone ${repoUrl}`);
    console.log(`  2. cd ${options.repoName}`);
    console.log(`  3. cp env/.env.example env/.env`);
    console.log(`  4. Edit env/.env with your credentials`);
    console.log(`  5. cursor .`);

    return repoUrl;
  } catch (error: any) {
    console.error("\n❌ Error creating repository:");
    if (error.response) {
      console.error(`  Status: ${error.response.status}`);
      console.error(`  Message: ${error.response.data.message || error.message}`);
    } else {
      console.error(`  ${error.message}`);
    }
    throw error;
  }
}

/**
 * Main execution
 */
async function main(): Promise<void> {
  try {
    // Parse arguments
    const options = parseArgs();

    // Check for GitHub token
    const githubToken = process.env.GITHUB_TOKEN;
    if (!githubToken && !options.dryRun) {
      console.error("Error: GITHUB_TOKEN environment variable is required");
      console.error("\nTo create a token:");
      console.error("  1. Go to https://github.com/settings/tokens");
      console.error("  2. Click 'Generate new token (fine-grained)'");
      console.error("  3. Grant 'Contents' and 'Metadata' repository permissions");
      console.error("  4. Export it: export GITHUB_TOKEN=your_token_here");
      process.exit(1);
    }

    // Load catalog and select tools
    console.log("Loading catalog...");
    const catalogPath = path.join(__dirname, "..", "generator", "catalog.json");
    const catalog = loadCatalog(catalogPath);
    console.log(`✓ Loaded ${catalog.length} tools from catalog`);

    console.log(`\nSelecting tools: ${options.toolIds.join(", ")}...`);
    const selectedTools = selectTools(catalog, options.toolIds);
    console.log(`✓ Selected ${selectedTools.length} tools`);

    // Generate files
    console.log("\nGenerating workspace files...");
    const files = generateFiles(options.repoName, selectedTools);
    console.log(`✓ Generated ${files.length} files`);

    // Dry run or execute
    if (options.dryRun) {
      dryRun(options, selectedTools, files);
    } else {
      const octokit = new Octokit({ auth: githubToken });
      await createRepository(octokit, options, selectedTools, files);
    }
  } catch (error: any) {
    console.error("\n❌ Fatal error:", error.message);
    process.exit(1);
  }
}

// Run if executed directly
if (require.main === module) {
  main();
}
