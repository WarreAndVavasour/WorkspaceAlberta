# E2B Bid Room Build Plan

WorkspaceAlberta should keep the deployed MCP/REST endpoint as the always-on product surface. E2B is the isolated compute layer behind it.

## Why E2B

The Professional tier changes the ceiling:

- 100 concurrent sandboxes for parallel tender processing
- 24 hour sessions for long bid-room jobs
- 20GB disk per sandbox for large tender packages
- 8 vCPU and 8GB RAM per sandbox for parsing, OCR, and enrichment

That is enough to process real bid packages without putting unknown files or user data inside the main web service.

## Build Slices

### Slice 1: Live Sandbox Smoke

Goal: prove the repo can create an E2B sandbox, run bid-room processing code inside it, return a structured artifact, and shut the sandbox down.

Command:

```bash
python scripts/e2b_bid_room_smoke.py
```

This uses `E2B_API_KEY` from the local environment or repo-root `.env`. It does not print the key.

### Slice 2: Tender Package Processor

Inputs:

- opportunity reference
- downloaded tender documents
- company profile

Sandbox work:

- create an isolated workspace
- write/upload tender files
- extract text and tables
- identify mandatory requirements
- identify deadlines and site meetings
- identify insurance, bonding, certification, safety, and submission requirements
- produce a JSON bid-room artifact

Output:

```json
{
  "reference": "AB-YYYY-NNNNN",
  "documents": [],
  "requirements": [],
  "deadlines": [],
  "risks": [],
  "fit_score": 0,
  "next_actions": []
}
```

### Slice 3: MCP Tool

Add a tool such as `process_bid_room` that accepts an opportunity reference and optional profile context, starts an E2B sandbox, processes the bid room, and returns the artifact summary.

Keep this separate from `search_opportunities`. Search should stay fast; bid-room processing can be a heavier job.

### Slice 4: Job Queue

For public users, bid-room processing should become asynchronous:

- create job
- return job id
- process in E2B
- store artifact
- allow polling or callback

This avoids tying user requests to long-running document parsing.

### Slice 5: Daily Enrichment Farm

Use concurrent E2B sandboxes to pre-process the highest-value daily opportunities. The daily brief can then include deeper readiness signals instead of only search results.

## Production Constraints

- Do not run the always-on MCP/REST endpoint inside E2B.
- Do use E2B for temporary, isolated, file-heavy tender work.
- Add auth and per-user profile storage before exposing profile-backed E2B jobs publicly.
- Keep raw tender attachments and user documents out of git.
- Shut sandboxes down by default unless a debugging run explicitly uses `--keep-alive`.
