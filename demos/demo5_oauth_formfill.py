#!/usr/bin/env python3
"""Demo 5 - OAuth identity + bid form auto-fill pipeline.

Chain: central credential store (business profile + platform tokens) ->
load the newest tender artifact from the E2B pipeline -> map each tender
requirement against the stored profile capabilities -> emit a filled bid
form (coverage verdict per requirement, signature block) -> shared workspace.

This is the "fill out the docs based on the business" stage: the same
stored identity the MCP server, harness, and mobile client all read.

Run:  python3 demos/demo5_oauth_formfill.py [artifact.json]
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wa_credentials as creds  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
SHARED = Path("/data/tasks/from-grok")
ARTIFACT_GLOBS = ["/data/tasks/from-grok/ARTIFACT-*.json",
                  str(OUT / "ARTIFACT-*.json")]

# requirement keywords -> profile capability that satisfies them
COVERAGE_MAP = {
    "insurance": "business registration & insurability",
    "bonding": "bonding capacity",
    "wcb": "WCB clearance",
    "signature": "authorized signing authority",
    "deadline": "on-time submission",
    "submission": "on-time submission",
    "reference": "past project references",
    "experience": "project experience",
    "safety": "safety program (COR)",
}


def newest_artifact() -> Path | None:
    import glob
    for pattern in ARTIFACT_GLOBS:
        hits = sorted(glob.glob(pattern), key=lambda p: Path(p).stat().st_mtime)
        if hits:
            return Path(hits[-1])
    return None


def requirement_lines(artifact: dict) -> list[str]:
    return [r.get("text", "") for r in
            artifact.get("evidence", {}).get("requirements", [])
            if r.get("text")]


def coverage(line: str, profile: dict) -> tuple[str, str]:
    """Return (verdict, basis) for one requirement against the profile."""
    low = line.lower()
    hay = " ".join(profile.get("capabilities", [])).lower()
    for key, basis in COVERAGE_MAP.items():
        if key in low:
            return ("PARTIAL — administrative", basis)
    for cap in profile.get("capabilities", []):
        if cap.lower() in low:
            return ("COVERED", f"capability: {cap}")
    if any(w in low for w in ("supply", "deliver", "goods", "equipment")):
        return ("OUT OF SCOPE", "goods/equipment requirement")
    return ("REVIEW", "no direct capability match — estimator decision")


def fill_form(profile: dict, artifact: dict, source: str) -> str:
    today = datetime.date.today().isoformat()
    opp = artifact.get("opportunity", {})
    lines = requirement_lines(artifact)
    covered = sum(1 for l in lines if coverage(l, profile)[0] == "COVERED")

    form = [
        f"# Bid Form — {opp.get('title', 'Untitled opportunity')}",
        "",
        f"**Reference:** {opp.get('reference', 'n/a')}  |  "
        f"**Buyer:** {opp.get('buyer') or 'n/a'}  |  "
        f"**Generated:** {today}",
        f"**Tender source:** {source}",
        "",
        "## Section 1 — Bidder Identity (auto-filled from central store)",
        f"- Company: **{profile['company_name']}**",
        f"- Location: {profile['location']}",
        f"- Scope: {profile['description']}",
        f"- Industries: {', '.join(profile.get('industries', []))}",
        "",
        "## Section 2 — Requirement Coverage",
        "",
    ]
    for line in lines:
        verdict, basis = coverage(line, profile)
        form.append(f"- [{verdict}] {line}\n      basis: {basis}")
    form += [
        "",
        f"**Coverage summary:** {covered}/{len(lines)} requirements fully "
        f"covered by stored capabilities.",
        "",
        "## Section 3 — Platform Credentials Status",
        "",
    ]
    store = creds.load()
    for name, slot in store.get("platforms", {}).items():
        state = "token stored" if slot.get("token") else "NOT LINKED"
        form.append(f"- {name}: {state}")
    key_state = "subscriber key present (Pro tools + saved profile)" \
        if store.get("wa_live") else "no subscriber key (per-call profile mode)"
    form.append(f"- workspacealberta identity: {key_state}")
    form += [
        "",
        "## Section 4 — Signature",
        "",
        f"Signed: ____________________  ({profile['company_name']})  {today}",
        "",
        "_Auto-filled by demo5 from the central workspace identity. "
        "Administrative PARTIAL rows need human documents attached "
        "(insurance certificates, WCB clearance, references) before submission._",
    ]
    return "\n".join(form)


def main() -> None:
    store = creds.ensure()
    profile = store["business_profile"]
    print(f"identity loaded from central store: {profile['company_name']} "
          f"({creds.STORE})")

    artifact_path = newest_artifact()
    if not artifact_path:
        sys.exit("no ARTIFACT-*.json found — run demo2 first")
    artifact = json.loads(artifact_path.read_text())
    print(f"tender artifact: {artifact_path.name}")

    form = fill_form(profile, artifact, artifact_path.name)

    OUT.mkdir(parents=True, exist_ok=True)
    SHARED.mkdir(parents=True, exist_ok=True)
    ref = artifact.get("opportunity", {}).get("reference", "bid")
    for base in (OUT, SHARED):
        (base / f"BID-FORM-{ref}.md").write_text(form)
    print(f"requirement rows: {len(requirement_lines(artifact))}")
    print(f"bid form -> demos/output/BID-FORM-{ref}.md")
    print(f"         -> /data/tasks/from-grok/BID-FORM-{ref}.md")


if __name__ == "__main__":
    main()
