# Codex / OpenClaw Setup

This repository is set up to be Codex-first.

## What is already in the repo

- `AGENTS.md` is the primary instruction file for Codex-style agents.
- `.cursor/mcp.json` includes:
  - `buildcanada`
  - `openaiDeveloperDocs`
- `opencode.json` includes:
  - the local Build Canada MCP
  - the OpenAI Docs MCP
  - project instructions
  - a `procurement` primary agent
  - a `review` subagent
  - a `smoke` command

## Codex CLI / IDE extension

Add the OpenAI Docs MCP globally:

```bash
codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp
codex mcp list
```

## Local validation

Install the dependency:

```bash
python -m pip install -r requirements.txt
```

Run the smoke test:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

## Repo-specific workflow

- Use `buildcanada` for CanadaBuys procurement work.
- Use `openaiDeveloperDocs` when the question is about OpenAI, Codex, MCP, models, or tool wiring.
- Keep user-facing brand language in `README.md` intact unless a rewrite is explicitly requested.
