"""E2B-backed bid room processing for isolated tender package work."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


SAMPLE_DOCUMENTS = [
    {
        "name": "opportunity-notice.txt",
        "text": (
            "Alberta public sector opportunity for structural steel fabrication. "
            "Closing date: 2026-06-18 14:00 MT. Mandatory site meeting: "
            "2026-05-29 10:00 MT. The supplier shall provide shop drawings, "
            "CSA W47.1 certification, commercial general liability insurance, "
            "and proof of bonding capacity."
        ),
    },
    {
        "name": "submission-instructions.txt",
        "text": (
            "Responses must include a signed bid form, safety program summary, "
            "three comparable project references, delivery schedule, and price "
            "breakdown. Late submissions will not be accepted. Questions must be "
            "submitted five business days before closing."
        ),
    },
    {
        "name": "company-profile.txt",
        "text": (
            "Company profile: Edmonton steel fabrication shop specializing in "
            "structural beams, railings, custom metalwork, commercial construction, "
            "and shop drawings. Located in Edmonton, Alberta."
        ),
    },
]


SANDBOX_PROCESSOR = r"""
import hashlib
import json
import re
from datetime import datetime, timezone

payload = json.loads(__PAYLOAD_JSON__)
documents = payload["documents"]
profile = payload["profile"]

requirement_patterns = [
    r"\bmust\b[^.]*\.",
    r"\bshall\b[^.]*\.",
    r"\bmandatory\b[^.]*\.",
    r"\brequired\b[^.]*\.",
    r"\binsurance\b[^.]*\.",
    r"\bbond(?:ing)?\b[^.]*\.",
    r"\bcertification\b[^.]*\.",
]

deadline_patterns = [
    r"(?:closing date|closing|site meeting|questions? must be submitted)[: ]+[^.]*\.",
]

requirements = []
deadlines = []
profile_keywords = [word.lower() for word in profile["keywords"]]
matched_terms = set()

for document in documents:
    text = document["text"]
    lowered = text.lower()
    for keyword in profile_keywords:
        if keyword in lowered:
            matched_terms.add(keyword)

    for pattern in requirement_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            requirements.append({
                "document": document["name"],
                "text": " ".join(match.group(0).split()),
            })

    for pattern in deadline_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            deadlines.append({
                "document": document["name"],
                "text": " ".join(match.group(0).split()),
            })

requirements = list({item["document"] + item["text"]: item for item in requirements}.values())
deadlines = list({item["document"] + item["text"]: item for item in deadlines}.values())
fit_score = min(100, 35 + len(matched_terms) * 8 + len(requirements) * 3)

next_actions = [
    "Confirm CSA W47.1 certification status before bid/no-bid decision.",
    "Verify bonding capacity and insurance certificates.",
    "Calendar the site meeting and question deadline.",
    "Open the bid form and price breakdown before estimating effort.",
]

artifact = {
    "processor": "workspacealberta-e2b-bid-room-smoke-v1",
    "processed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "profile": profile,
    "documents": [
        {
            "name": document["name"],
            "characters": len(document["text"]),
            "sha256": hashlib.sha256(document["text"].encode("utf-8")).hexdigest(),
        }
        for document in documents
    ],
    "matched_terms": sorted(matched_terms),
    "fit_score": fit_score,
    "requirements": requirements,
    "deadlines": deadlines,
    "next_actions": next_actions,
}

print(json.dumps(artifact, indent=2))
"""


@dataclass
class BidRoomSandboxResult:
    """Result returned by a live E2B bid room smoke run."""

    sandbox_id: str
    killed: bool
    artifact: dict[str, Any]
    stdout: str
    stderr: str


def load_local_env() -> None:
    """Load repo-local .env values without printing secrets."""
    for env_path in (ROOT_DIR / ".env", Path.cwd() / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


def has_e2b_api_key() -> bool:
    """Return true when an E2B key is present in the environment or local .env."""
    load_local_env()
    return bool(os.environ.get("E2B_API_KEY", "").strip())


def build_sample_payload() -> dict[str, Any]:
    """Build the sample bid package payload used by the live smoke run."""
    return {
        "profile": {
            "company_name": "Edmonton Steel Works",
            "location": "Edmonton, Alberta",
            "keywords": [
                "steel",
                "structural",
                "fabrication",
                "shop drawings",
                "commercial",
                "edmonton",
            ],
        },
        "documents": SAMPLE_DOCUMENTS,
    }


def build_sandbox_command(payload: dict[str, Any]) -> str:
    """Build a Python command that processes a bid package inside E2B."""
    script = SANDBOX_PROCESSOR.replace("__PAYLOAD_JSON__", repr(json.dumps(payload)))
    return "python3 - <<'PY'\n" + script + "\nPY"


def parse_artifact(stdout: str) -> dict[str, Any]:
    """Parse the JSON artifact printed by the sandbox processor."""
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Sandbox output did not contain a JSON artifact.")
    return json.loads(stdout[start : end + 1])


def _result_text(command_result: Any, name: str) -> str:
    value = getattr(command_result, name, "")
    return "" if value is None else str(value)


def run_live_bid_room_smoke(
    *,
    timeout_seconds: int = 900,
    command_timeout_seconds: int = 120,
    keep_alive: bool = False,
) -> BidRoomSandboxResult:
    """Create a live E2B sandbox, process a sample bid room, and return JSON."""
    load_local_env()
    if not os.environ.get("E2B_API_KEY", "").strip():
        raise RuntimeError("E2B_API_KEY is not configured.")

    try:
        from e2b import Sandbox
    except ImportError as exc:
        raise RuntimeError("Install the E2B SDK with `python -m pip install e2b>=2.21.1`.") from exc

    sandbox = Sandbox.create(
        timeout=timeout_seconds,
        metadata={
            "project": "workspacealberta",
            "feature": "bid-room-smoke",
        },
    )
    sandbox_id = str(
        getattr(sandbox, "sandbox_id", "")
        or getattr(sandbox, "id", "")
        or "unknown"
    )
    artifact: dict[str, Any] | None = None
    stdout = ""
    stderr = ""

    try:
        command = build_sandbox_command(build_sample_payload())
        command_result = sandbox.commands.run(command, timeout=command_timeout_seconds)
        stdout = _result_text(command_result, "stdout")
        stderr = _result_text(command_result, "stderr")
        artifact = parse_artifact(stdout)
    finally:
        killed = False
        if not keep_alive:
            sandbox.kill()
            killed = True

    if artifact is None:
        raise RuntimeError("E2B sandbox did not return a bid room artifact.")
    return BidRoomSandboxResult(
        sandbox_id=sandbox_id,
        killed=killed,
        artifact=artifact,
        stdout=stdout,
        stderr=stderr,
    )
