# E2B Bid Room Build Plan

WorkspaceAlberta should keep the deployed MCP/REST endpoint as the always-on product surface. E2B is the isolated compute layer behind it.

For the full business-owner and tool-call map, see [`bid-room-operating-diagram.md`](bid-room-operating-diagram.md).

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

For a real opportunity plus Cohere review:

```bash
python scripts/e2b_bid_room_smoke.py --reference cb-576-54577723 --max-attachments 1 --json
```

This path injects only `COHERE_API_KEY` into the sandbox. It does not pass the Cohere prod key, Hugging Face token, OpenAI key, or other repo secrets.

### Slice 2: Tender Package Processor

Inputs:

- opportunity reference
- downloaded tender documents
- company profile

Sandbox work:

- create an isolated workspace
- download direct public tender attachments
- extract text and tables from PDF, HTML, TXT, DOCX, XLSX, and ZIP-contained supported files
- identify mandatory requirements
- identify deadlines and site meetings
- identify insurance, bonding, certification, safety, and submission requirements
- expose read-only evidence tools to Cohere inside the sandbox
- produce a JSON bid-room artifact

Output:

```json
{
  "reference": "AB-YYYY-NNNNN",
  "documents": [],
  "evidence": {
    "requirements": [],
    "deadlines": [],
    "matched_terms": []
  },
  "cohere_analysis": {
    "bid_recommendation": "maybe - short reason",
    "fit_score": 0,
    "requirements": [],
    "risks": [],
    "missing_information": [],
    "deadlines": [],
    "questions_to_ask": [],
    "next_actions": []
  },
  "cohere_tool_calls": []
}
```

### Slice 3: MCP Tool

Add `process_bid_room`, which accepts an opportunity reference and optional profile context, starts an E2B sandbox, processes the bid room, and returns the artifact summary.

Keep this separate from `search_opportunities`. Search should stay fast; bid-room processing can be a heavier job.

The REST equivalent is `POST /bid-room/process`.

### Slice 3A: Cohere Tool Loop

Cohere runs inside E2B through the native v2 Chat API. The model is allowed to think and use tools, but the tools are constrained to read-only evidence access:

- `search_extracted_documents(query, top_k)` searches snippets from extracted tender text
- `get_bid_evidence(section, top_k)` returns deterministic requirements, deadlines, matched terms, document summaries, opportunity metadata, or profile metadata

The sandbox executes requested tool calls locally, returns tool results to Cohere, then validates the final JSON. The host validates the same JSON again before returning it through MCP or REST.

Current v1 behavior is synchronous and bounded. If Cohere keeps asking for additional tool calls, the sandbox summarizes the bounded tool results into a final JSON-only synthesis request.

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
- Do keep all tender download, parsing, hashing, and extraction deterministic in Python.
- Do use Cohere for bid reasoning over extracted evidence and read-only evidence tools.
- Add auth and per-user profile storage before exposing profile-backed E2B jobs publicly.
- Keep raw tender attachments and user documents out of git.
- Shut sandboxes down by default unless a debugging run explicitly uses `--keep-alive`.
