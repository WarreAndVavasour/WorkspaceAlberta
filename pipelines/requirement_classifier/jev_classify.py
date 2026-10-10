# /// script
# requires-python = ">=3.10"
# dependencies = ["requests>=2.28"]
# ///
"""Label tender units with TypeSafe's Jev (System One) model.

Reads the units.jsonl written by label_requirements.py (stage 1) and asks Jev
two questions per unit in one request:

- ``response_type``: a Choice over the same 11 response types as
  label_requirements.py (RESPONSE_TYPES, imported from that file so the label
  set and definitions cannot drift). Jev's Choice is single-select: the answer
  is the top option plus the full probability distribution over all 11.
- ``in_bid``: a Noul (probability that the bidder must put something in its bid or act before
  bids close). ``requires_response`` = label is not 'none' and in_bid >= 0.5.
- ``mandatory``: a Noul (probability that the clause makes a bid item mandatory).

API (https://docs.typesafe.ai/api):
    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <TYPESAFE_API_KEY>
    {"model": ..., "state": ..., "questions": {...}}

Output: one JSON line per unit in jev_labels.jsonl next to units.jsonl.
Re-running resumes: units already labelled without error are skipped, and the
file is compacted (one row per unit_index, sorted) at the end of each run.

    python jev_classify.py --dry-run --limit 3      # build requests, send nothing
    python jev_classify.py --limit 20               # first 20 units
    python jev_classify.py                          # everything (resumes)
    python jev_classify.py --summary-only           # summarise the output file

The API key is read from the TYPESAFE_API_KEY (or JEV_API_KEY) environment
variable, else from the repo's .env file. It is never printed or logged.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import random
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
# Tender folder (git-ignored). Set REQ_TENDER_DIR to work on another tender.
TENDER_DIR = Path(os.environ.get("REQ_TENDER_DIR", REPO / "drive-downloads/tenders/AB-2026-06600"))
DEFAULT_INPUT = TENDER_DIR / "units.jsonl"
API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"  # pinned; "jev-latest" moves when a new release ships
PRICE_PER_MTOK = 0.042  # USD per million input tokens, output free (docs.typesafe.ai/models)
RETRY_STATUSES = {408, 429} | set(range(500, 600))  # same set as the Python SDK's RetryPolicy
PROMPT_VERSION = "jev-req-v2"


def load_response_types() -> dict[str, tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("label_requirements", HERE / "label_requirements.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # heavy imports in that file are inside functions
    return module.RESPONSE_TYPES


RESPONSE_TYPES = load_response_types()

# Jev 1.13 can lean toward the first Choice option (docs: model-jaggedness/jev-1.13),
# so the catch-all "none" goes last rather than first.
OPTION_ORDER = [k for k in RESPONSE_TYPES if k != "none"] + ["none"]

# Dates and submission logistics are acted on before bids close (calendar, checklist), but Jev's
# in_bid score for them is low because nothing is "put in" the bid. They skip the in_bid gate.
GATE_EXEMPT = {"attendance", "submission_instruction"}
IN_BID_THRESHOLD = 0.5


def derive(row: dict) -> dict:
    """requires_response = a response type was chosen and it passes the in_bid gate."""
    label, ib = row.get("label"), row.get("in_bid_prob")
    if label:
        row["requires_response"] = label != "none" and (ib is None or ib >= IN_BID_THRESHOLD or label in GATE_EXEMPT)
    return row

QUESTIONS = {
    "response_type": {
        "type": "choice",
        "instructions": (
            "`clause` is one clause from a Canadian public-sector tender document. "
            "What must the bidder put in its bid submission, before bids close, because of `clause`? "
            "Judge what the bidder must do, not what the clause is about. "
            "Use `section`, `text_before` and `text_after` only as context. "
            "Pick 'none' for background, definitions, the buyer's process, specifications of the work, "
            "the printed wording of a form, bond or contract, and any duty of the contractor after award."
        ),
        "criteria": {k: RESPONSE_TYPES[k][0] for k in OPTION_ORDER},
    },
    "in_bid": {
        "type": "noul",
        "instructions": (
            "Must the bidder include something in its bid or proposal, or do something before bids close "
            "(such as attend a site visit), because of `clause`? Duties after contract award, definitions, "
            "specifications of the work and printed form wording do not count."
        ),
        "criteria": {
            "true": "The bidder must put something in its bid, or act before bids close, because of this clause.",
            "false": "Nothing goes in the bid because of this clause, or it only applies after award.",
        },
    },
    "mandatory": {
        "type": "noul",
        "instructions": (
            "Does `clause` say that something the bidder must put in its bid is mandatory or required, "
            "or that a bid will be rejected or disqualified without it? Mandatory duties after award do not count."
        ),
        "criteria": {
            "true": "The clause states the item is mandatory or required, or a bid without it is rejected.",
            "false": "The clause does not make anything mandatory for the bid, or the bidder supplies nothing.",
        },
    },
}


def build_state(unit: dict) -> dict:
    """Same content as label_requirements.build_messages, as named fields."""
    return {
        "document": unit.get("doc_name", ""),
        "section": unit.get("section") or "(none)",
        "page": unit.get("page"),
        "text_before": unit.get("prev_text") or "(start)",
        "clause": unit.get("text", ""),
        "text_after": unit.get("next_text") or "(end)",
    }


def build_request(unit: dict, model: str) -> dict:
    return {"model": model, "state": build_state(unit), "questions": QUESTIONS}


def estimate_tokens(payload: dict) -> int:
    # No tokenizer is published; ~4 characters per token for English JSON text.
    return max(1, len(json.dumps(payload, ensure_ascii=False)) // 4)


# --------------------------------------------------------------------------- key

def read_api_key() -> str | None:
    for name in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        if os.environ.get(name):
            return os.environ[name].strip()
    env_file = REPO / ".env"
    if not env_file.exists():
        return None
    values = {}
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip().removeprefix("export ").strip()
        values[name] = value.strip().strip('"').strip("'")
    for name in ("TYPESAFE_API_KEY", "JEV_API_KEY"):
        if values.get(name):
            return values[name]
    return None


# --------------------------------------------------------------------------- calling

class AuthError(RuntimeError):
    pass


_local = threading.local()


def session(api_key: str):
    import requests

    if getattr(_local, "session", None) is None:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        _local.session = s
    return _local.session


def retry_delay(response, attempt: int) -> float:
    if response is not None:
        ms = response.headers.get("retry-after-ms")
        sec = response.headers.get("retry-after")
        try:
            if ms:
                return min(60.0, float(ms) / 1000)
            if sec:
                return min(60.0, float(sec))
        except ValueError:
            pass
    return min(30.0, 0.5 * 2 ** attempt) * (1 + random.uniform(-0.25, 0.25))


def call_jev(payload: dict, api_key: str, max_retries: int, timeout: float) -> tuple[dict | None, str, int]:
    """Return (body, error, attempts). Raises AuthError on 401/403."""
    import requests

    error = ""
    for attempt in range(max_retries + 1):
        response = None
        try:
            response = session(api_key).post(API_URL, json=payload, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:200]}"
        else:
            if response.status_code == 200:
                return response.json(), "", attempt + 1
            body = response.text[:500]
            error = f"HTTP {response.status_code}: {body}"
            if response.status_code in (401, 403):
                raise AuthError(f"HTTP {response.status_code}: {body}")
            if response.status_code not in RETRY_STATUSES:
                return None, error, attempt + 1
        if attempt < max_retries:
            time.sleep(retry_delay(response, attempt))
    return None, error, max_retries + 1


def to_row(unit: dict, body: dict | None, error: str, latency_ms: float, attempts: int) -> dict:
    row = {
        "unit_index": unit["unit_index"],
        "page": unit.get("page"),
        "doc_sha256": unit.get("doc_sha256", ""),
        "label": None,
        "prob": None,
        "confidence": None,
        "probabilities": None,
        "in_bid_prob": None,
        "requires_response": None,
        "mandatory": None,
        "mandatory_prob": None,
        "model": None,
        "input_tokens": None,
        "latency_ms": round(latency_ms, 1),
        "attempts": attempts,
        "prompt_version": PROMPT_VERSION,
        "error": error or None,
    }
    if body is None:
        return row
    try:
        rt = body["answers"]["response_type"]
        probs = {k: float(v) for k, v in rt["probabilities"].items()}
        row.update(
            label=rt["choice"],
            prob=probs.get(rt["choice"]),
            confidence=rt.get("confidence"),
            probabilities=probs,
            model=body.get("model"),
            input_tokens=(body.get("usage") or {}).get("input_tokens"),
        )
        ib = body["answers"].get("in_bid")
        if ib is not None:
            row["in_bid_prob"] = float(ib["noul"])
        md = body["answers"].get("mandatory")
        if md is not None:
            row["mandatory_prob"] = float(md["noul"])
            row["mandatory"] = row["mandatory_prob"] >= 0.5
        derive(row)
    except (KeyError, TypeError, ValueError) as exc:
        row["error"] = f"unexpected response shape ({exc}): {json.dumps(body)[:400]}"
    return row


# --------------------------------------------------------------------------- io

def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def latest_by_index(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    out = {}
    for row in read_jsonl(path):
        out[row["unit_index"]] = row
    return out


def compact(path: Path) -> dict[int, dict]:
    rows = latest_by_index(path)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for idx in sorted(rows):
            fh.write(json.dumps(derive(rows[idx]), ensure_ascii=False) + "\n")
    tmp.replace(path)
    return rows


# --------------------------------------------------------------------------- summary

def summarize(rows: dict[int, dict], units: dict[int, dict], wall_s: float | None) -> dict:
    ok = [r for r in rows.values() if not r.get("error") and r.get("label")]
    failed = [r for r in rows.values() if r.get("error")]
    labels = collections.Counter(r["label"] for r in ok)
    probs = [r["prob"] for r in ok if r.get("prob") is not None]
    lat = [r["latency_ms"] for r in ok if r.get("latency_ms") is not None]
    tokens = sum(r.get("input_tokens") or 0 for r in ok)
    md = [r for r in ok if r.get("mandatory") is not None]
    summary = {
        "rows_in_output": len(rows),
        "units_in_input": len(units),
        "labelled_ok": len(ok),
        "failures": len(failed),
        "label_counts": dict(labels.most_common()),
        "requires_response": sum(1 for r in ok if r["label"] != "none"),
        "requires_response_share": round(sum(1 for r in ok if r["label"] != "none") / len(ok), 4) if ok else None,
        "in_bid_true": sum(1 for r in ok if (r.get("in_bid_prob") or 0) >= 0.5),
        "requires_response_gated": sum(1 for r in ok if r.get("requires_response")),
        "label_counts_gated": dict(collections.Counter(r["label"] for r in ok if r.get("requires_response")).most_common()),
        "mandatory_true": sum(1 for r in md if r["mandatory"]),
        "mandatory_true_among_gated": sum(1 for r in md if r["mandatory"] and r.get("requires_response")),
        "mandatory_true_among_requires_response": sum(1 for r in md if r["mandatory"] and r["label"] != "none"),
        "mean_top_prob": round(statistics.mean(probs), 4) if probs else None,
        "median_top_prob": round(statistics.median(probs), 4) if probs else None,
        "low_confidence_rows_top_prob_lt_0_6": sum(1 for p in probs if p < 0.6),
        "mean_latency_ms": round(statistics.mean(lat), 1) if lat else None,
        "p95_latency_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 1) if lat else None,
        "input_tokens_reported": tokens,
        "cost_usd_from_reported_tokens": round(tokens / 1e6 * PRICE_PER_MTOK, 4),
        "models": dict(collections.Counter(r.get("model") for r in ok)),
        "wall_time_s_last_run": round(wall_s, 1) if wall_s is not None else None,
        "error_samples": [r["error"][:200] for r in failed[:5]],
    }
    # Examples: up to 10 rows, round-robin across labels, highest-probability first.
    by_label: dict[str, list[dict]] = collections.defaultdict(list)
    for r in sorted(ok, key=lambda r: -(r["prob"] or 0)):
        by_label[r["label"]].append(r)
    examples, depth = [], 0
    while len(examples) < 10 and any(len(v) > depth for v in by_label.values()):
        for label in sorted(by_label, key=lambda k: -len(by_label[k])):
            if len(by_label[label]) > depth and len(examples) < 10:
                r = by_label[label][depth]
                text = units.get(r["unit_index"], {}).get("text", "")
                examples.append({
                    "unit_index": r["unit_index"], "page": r["page"], "label": r["label"],
                    "prob": round(r["prob"], 3), "mandatory_prob": r.get("mandatory_prob"),
                    "text": text[:160],
                })
        depth += 1
    summary["examples"] = examples
    return summary


# --------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="Default: jev_labels.jsonl next to --input.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, help="Only the first N units (by unit_index).")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-cost", type=float, default=5.0, help="Abort if the estimate exceeds this (USD).")
    parser.add_argument("--dry-run", action="store_true", help="Build requests and estimate cost; send nothing.")
    parser.add_argument("--summary-only", action="store_true", help="Summarise the output file and exit.")
    args = parser.parse_args()

    output = args.output or args.input.with_name("jev_labels.jsonl")
    summary_path = output.with_name(output.stem.replace("labels", "summary") + ".json")
    units_list = read_jsonl(args.input)
    units = {u["unit_index"]: u for u in units_list}
    print(f"input: {args.input} ({len(units_list)} units)")

    if args.summary_only:
        rows = compact(output) if output.exists() else {}
        summary = summarize(rows, units, None)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    selected = sorted(units_list, key=lambda u: u["unit_index"])
    if args.limit is not None:
        selected = selected[: args.limit]
    done = {i for i, r in latest_by_index(output).items() if not r.get("error")}
    todo = [u for u in selected if u["unit_index"] not in done]

    payloads = {u["unit_index"]: build_request(u, args.model) for u in todo}
    est_tokens = sum(estimate_tokens(p) for p in payloads.values())
    est_cost = est_tokens / 1e6 * PRICE_PER_MTOK
    print(f"selected {len(selected)}; already done {len(selected) - len(todo)}; to send {len(todo)}")
    print(f"estimated input tokens ~{est_tokens:,} (chars/4); estimated cost ~${est_cost:.4f} "
          f"at ${PRICE_PER_MTOK}/Mtok; model {args.model}")
    if est_cost > args.max_cost:
        print(f"ABORT: estimate exceeds --max-cost ${args.max_cost}", file=sys.stderr)
        return 3

    if args.dry_run:
        for u in todo[:3]:
            p = payloads[u["unit_index"]]
            print(f"\n--- unit {u['unit_index']} (~{estimate_tokens(p)} tokens) ---")
            print(json.dumps(p, indent=2, ensure_ascii=False)[:2500])
        print("\ndry run: nothing sent")
        return 0

    if not todo:
        print("nothing to do")
    else:
        api_key = read_api_key()
        if not api_key:
            print("ABORT: no TYPESAFE_API_KEY / JEV_API_KEY in environment or .env", file=sys.stderr)
            return 2
        lock = threading.Lock()
        stop = threading.Event()
        counts = collections.Counter()
        started = time.monotonic()

        def work(unit: dict) -> dict | None:
            if stop.is_set():
                return None
            t0 = time.monotonic()
            try:
                body, error, attempts = call_jev(payloads[unit["unit_index"]], api_key, args.max_retries, args.timeout)
            except AuthError as exc:
                stop.set()
                raise exc
            return to_row(unit, body, error, (time.monotonic() - t0) * 1000, attempts)

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(args.concurrency) as pool:
            futures = [pool.submit(work, u) for u in todo]
            for n, fut in enumerate(as_completed(futures), 1):
                try:
                    row = fut.result()
                except AuthError as exc:
                    print(f"ABORT: authentication failed ({str(exc)[:200]})", file=sys.stderr)
                    for f in futures:
                        f.cancel()
                    break
                if row is None:
                    continue
                with lock:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                counts["error" if row["error"] else "ok"] += 1
                if n % 250 == 0 or n == len(todo):
                    rate = n / max(1e-6, time.monotonic() - started)
                    print(f"  {n}/{len(todo)} ok={counts['ok']} err={counts['error']} ({rate:.1f}/s)", flush=True)
        wall = time.monotonic() - started
        print(f"run finished in {wall:.1f}s: ok={counts['ok']} errors={counts['error']}")
        if stop.is_set():
            compact(output)
            return 4

    rows = compact(output)
    summary = summarize(rows, units, wall if todo else None)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "examples"}, indent=2))
    print(f"\noutput: {output} ({len(rows)} rows)\nsummary: {summary_path}")
    return 0 if summary["failures"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
