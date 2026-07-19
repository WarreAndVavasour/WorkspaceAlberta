#!/usr/bin/env python3
"""
Live MCP trace runner for the WorkspaceAlberta use-case experiment.

Connects to the deployed WorkspaceAlberta MCP server (StreamableHTTP),
lists real tool schemas, adapts each planned use-case step to the live
schema, executes steps sequentially, resolves <ref-from-previous-step>
placeholders from prior result text, and merges traces into
alberta-usecase-traces.json.

Usage:
  python run_traces.py                     # run all traces not yet in the dataset
  python run_traces.py --only uc-05,uc-15  # (re)run specific traces, merge into dataset
  python run_traces.py --list-tools-only   # fetch + print tool schemas, then exit
"""
import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

BASE = Path(__file__).resolve().parent
USECASES_PATH = BASE / "usecases.json"
DATASET_PATH = BASE / "alberta-usecase-traces.json"
SCHEMAS_PATH = BASE / "tool_schemas.json"
ENDPOINT = "https://workspacealberta-719334491060.northamerica-northeast1.run.app/mcp"
PER_CALL_TIMEOUT = 120  # seconds, per tool call

# Alias map: planned arg -> candidate real arg names (first match in schema wins)
ALIASES = {
    "keywords": ["query", "keyword", "search", "search_terms", "terms", "q"],
    "reference": ["reference_number", "ref", "opportunity_reference", "opportunity_id", "id"],
    "days": ["days_ahead", "within_days", "closing_within_days", "lookahead_days"],
    "limit": ["max_results", "top_k", "count", "n", "page_size"],
    "province": ["region", "prov", "province_filter"],
    "source": ["sources", "data_source"],
    "note": ["notes", "comment", "memo"],
    "company_name": ["name", "company"],
    "description": ["company_description", "profile", "summary"],
    "location": ["region", "city", "address"],
}

# Reference-number patterns, in priority order
REF_PATTERNS = [
    re.compile(r"\bAB-\d{4}-\d+\b"),
    re.compile(r"\bcb-\d[\w-]*", re.IGNORECASE),
    re.compile(r"\b[A-Z]{2,}-\d[\w-]*"),
    re.compile(r"\b[A-Za-z]{2,}-\d[\w-]*"),
]

PAYWALL_RE = re.compile(
    r"workspacealberta\s+pro|upgrade to (workspacealberta )?pro|"
    r"pro (subscription|feature|plan|tier|account)|requires (a )?pro|"
    r"pro (membership|access) (required|needed)|available (only )?(with|on|in) .*pro",
    re.IGNORECASE,
)
KNOWN_BUG_RE = re.compile(r"contract not found", re.IGNORECASE)


def load_usecases():
    return json.loads(USECASES_PATH.read_text(encoding="utf-8"))["use_cases"]


def adapt_arguments(schema_props, planned):
    """Map planned arguments onto the live tool schema. Returns (actual, notes)."""
    notes = []
    actual = {}
    for key, value in planned.items():
        if key in schema_props:
            actual[key] = value
            continue
        renamed = None
        for cand in ALIASES.get(key, []):
            if cand in schema_props:
                renamed = cand
                break
        if renamed:
            actual[renamed] = value
            notes.append(f"renamed '{key}' -> '{renamed}'")
        else:
            notes.append(f"dropped '{key}' (not in schema)")
    return actual, notes


def extract_ref(text):
    """First plausible opportunity reference in the text, by position."""
    best = None
    for pat in REF_PATTERNS:
        m = pat.search(text or "")
        if m and (best is None or m.start() < best.start()):
            best = m
    return best.group(0) if best else None


def classify(steps):
    texts = " ".join(s.get("result_text", "") for s in steps)
    if PAYWALL_RE.search(texts):
        return "paywall"
    if KNOWN_BUG_RE.search(texts):
        return "known-bug"
    if any(s.get("is_error") for s in steps):
        return "error"
    if any(s.get("skipped") for s in steps):
        return "error"
    if steps and all(s.get("result_text", "").strip() for s in steps):
        return "success"
    return "error"


def load_dataset():
    if DATASET_PATH.exists():
        return json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return None


def save_dataset(traces_by_id, usecases):
    ordered = [traces_by_id[uc["id"]] for uc in usecases if uc["id"] in traces_by_id]
    summary = {}
    for t in ordered:
        summary[t["actual_outcome"]] = summary.get(t["actual_outcome"], 0) + 1
    ds = {
        "experiment": "workspacealberta-mcp-alberta-usecase-traces",
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": ENDPOINT,
        "transport": "MCP StreamableHTTP (streamablehttp_client + ClientSession)",
        "method": (
            "Each of 22 scripted Alberta small-business prompts was executed live against the deployed "
            "WorkspaceAlberta MCP server: planned tool calls were adapted to the live list_tools schema, "
            "run sequentially with per-call 120s timeouts, and <ref-from-previous-step> placeholders were "
            "resolved from the first reference number found in the previous step's raw result text."
        ),
        "trace_count": len(ordered),
        "outcome_summary": summary,
        "traces": ordered,
    }
    DATASET_PATH.write_text(json.dumps(ds, indent=2, ensure_ascii=False), encoding="utf-8")
    return ds


async def call_tool(session, tool, args):
    """One tool call with timeout. Returns (result_text, is_error, latency_ms)."""
    t0 = time.monotonic()
    try:
        res = await asyncio.wait_for(session.call_tool(tool, args), timeout=PER_CALL_TIMEOUT)
        latency = int((time.monotonic() - t0) * 1000)
        parts = []
        for c in res.content:
            txt = getattr(c, "text", None)
            parts.append(txt if txt is not None else str(c))
        if not parts and getattr(res, "structuredContent", None) is not None:
            parts.append(json.dumps(res.structuredContent, ensure_ascii=False))
        return "\n".join(parts), bool(res.isError), latency
    except asyncio.TimeoutError:
        latency = int((time.monotonic() - t0) * 1000)
        return (
            f"TIMEOUT: call to '{tool}' exceeded {PER_CALL_TIMEOUT}s; no response received. "
            "Recorded as observed behavior.",
            True,
            latency,
        )
    except Exception as e:  # noqa: BLE001 - record everything as observed behavior
        latency = int((time.monotonic() - t0) * 1000)
        return f"EXCEPTION: {type(e).__name__}: {e}", True, latency


async def run_trace(session, schemas, uc):
    trace = {
        "id": uc["id"],
        "persona": uc["persona"],
        "prompt": uc["prompt"],
        "steps": [],
        "tools_used": [],
        "output": "",
        "expected_outcome": uc["expected_outcome"],
        "actual_outcome": None,
        "expectation_met": None,
    }
    if uc.get("notes"):
        trace["notes"] = uc["notes"]

    prev_text = ""
    for i, step in enumerate(uc["steps"], start=1):
        tool = step["tool"]
        planned = dict(step.get("arguments", {}))
        record = {
            "step": i,
            "thought": step["thought"],
            "tool": tool,
            "planned_arguments": planned,
        }

        # Resolve placeholder from previous step's result
        unresolved = False
        for k, v in list(planned.items()):
            if isinstance(v, str) and "<ref-from-previous-step>" in v:
                ref = extract_ref(prev_text)
                if ref:
                    planned[k] = v.replace("<ref-from-previous-step>", ref)
                else:
                    unresolved = True
                    record["skipped"] = True
                    record["reason"] = (
                        "could not resolve <ref-from-previous-step>: no plausible reference "
                        "number found in previous step result"
                    )
        if unresolved:
            record["arguments"] = {}
            record["result_text"] = ""
            record["is_error"] = False
            record["latency_ms"] = 0
            trace["steps"].append(record)
            prev_text = ""
            print(f"    step {i}: {tool} SKIPPED ({record['reason']})")
            continue

        schema_props = schemas.get(tool, {})
        actual, adapt_notes = adapt_arguments(schema_props, planned)
        record["arguments"] = actual
        if adapt_notes:
            record["adaptation_notes"] = adapt_notes
        if tool not in schemas:
            record["adaptation_notes"] = record.get("adaptation_notes", []) + [
                f"WARNING: tool '{tool}' not present in list_tools output"
            ]

        text, is_error, latency = await call_tool(session, tool, actual)
        record["result_text"] = text
        record["is_error"] = is_error
        record["latency_ms"] = latency
        trace["steps"].append(record)
        if tool not in trace["tools_used"]:
            trace["tools_used"].append(tool)
        prev_text = text
        snippet = re.sub(r"\s+", " ", text)[:110]
        print(f"    step {i}: {tool} {actual} -> {latency}ms err={is_error} | {snippet}")

    trace["actual_outcome"] = classify(trace["steps"])
    trace["expectation_met"] = trace["actual_outcome"] == uc["expected_outcome"]
    return trace


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated trace ids to (re)run, e.g. uc-05,uc-15")
    ap.add_argument("--list-tools-only", action="store_true")
    args = ap.parse_args()

    usecases = load_usecases()
    only = set(args.only.split(",")) if args.only else None

    if only:
        todo = [u for u in usecases if u["id"] in only]
    else:
        existing = {t["id"] for t in (load_dataset() or {}).get("traces", [])}
        todo = [u for u in usecases if u["id"] not in existing]
    if not todo and not args.list_tools_only:
        print("Nothing to do: all traces already present (use --only to force reruns).")
        return

    print(f"Connecting to {ENDPOINT} ...")
    async with streamablehttp_client(
        ENDPOINT,
        timeout=timedelta(seconds=PER_CALL_TIMEOUT),
        sse_read_timeout=timedelta(seconds=300),
    ) as (read, write, _sid):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            schemas = {}
            printable = []
            for t in tools_resp.tools:
                props = (t.inputSchema or {}).get("properties", {}) or {}
                schemas[t.name] = props
                req = (t.inputSchema or {}).get("required", [])
                printable.append(
                    f"- {t.name}({', '.join(props.keys()) or 'no args'})"
                    + (f"  required={req}" if req else "")
                )
            SCHEMAS_PATH.write_text(
                json.dumps(
                    {
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "endpoint": ENDPOINT,
                        "tools": [
                            {
                                "name": t.name,
                                "description": t.description,
                                "inputSchema": t.inputSchema,
                            }
                            for t in tools_resp.tools
                        ],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            print(f"\n=== list_tools: {len(schemas)} tools (saved to {SCHEMAS_PATH.name}) ===")
            print("\n".join(printable))
            if args.list_tools_only:
                return

            ds = load_dataset()
            traces_by_id = {t["id"]: t for t in ds["traces"]} if ds else {}

            for uc in todo:
                print(f"\n[{uc['id']}] {uc['persona']}")
                trace = await run_trace(session, schemas, uc)
                # preserve an already-authored output text on reruns
                old = traces_by_id.get(uc["id"])
                if old and old.get("output"):
                    trace["output"] = old["output"]
                traces_by_id[uc["id"]] = trace
                save_dataset(traces_by_id, usecases)
                print(
                    f"  => outcome={trace['actual_outcome']} "
                    f"(expected={trace['expected_outcome']}, met={trace['expectation_met']})"
                )

            print(f"\nDataset now has {len(traces_by_id)} traces -> {DATASET_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
