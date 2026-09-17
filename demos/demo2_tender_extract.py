#!/usr/bin/env python3
"""Demo 2 - Tender document pipeline: download -> E2B extract -> artifact.

Boots an E2B sandbox, downloads a real tender document from a public URL,
extracts text, and writes the bid-room artifact + human report into the
shared workspace. Extraction-only: works without COHERE_API_KEY; if the key
is present in ~/WorkspaceAlberta/.env the Cohere analysis runs too.

Run:  .venv/bin/python demos/demo2_tender_extract.py [tender-pdf-url] [reference] [title]
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

for line in (REPO / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from procurement_core import e2b_bid_room as br  # noqa: E402

DEFAULT_URL = (
    "https://rockymountainhouse.municipalwebsites.ca/ckfinder/connector"
    "?command=Proxy&lang=en&type=Files&currentFolder=%2F"
    "&hash=c245c263ce0eced480effe66bbede6b4d46c15ae"
    "&fileName=Website%20RFP%20(AB-2026-05302)%20-%20Responses%20to%20Questions"
    "%20Received%20as%20of%20August%205.pdf"
)
SHARED = Path("/data/tasks/from-grok")
OUT = Path(__file__).resolve().parent / "output"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    reference = sys.argv[2] if len(sys.argv) > 2 else "AB-2026-05302"
    title = sys.argv[3] if len(sys.argv) > 3 else (
        "Town of Rocky Mountain House — Website Redesign (Q&A Addendum)")

    full_chain = br.has_cohere_api_key()
    payload = br.build_process_payload(
        opportunity={
            "source": "url", "reference": reference, "title": title,
            "buyer": "", "closing": "", "url": "",
        },
        profile=br.profile_for_bid_room({
            "company_name": "Rocky Mountain Carpentry",
            "location": "Rocky Mountain House, Alberta",
            "description": (
                "Carpentry contractor serving Clearwater County and Nordegg: "
                "framing, finishing, custom woodwork, renovations, design/build "
                "small commercial and residential projects."
            ),
            "capabilities": ["carpentry", "framing", "finishing", "renovation",
                             "design/build", "residential", "construction"],
        }),
        documents=[],
        attachments=[{"name": f"{reference}.pdf", "url": url, "source": "url"}],
        cohere_enabled=full_chain,
    )
    if full_chain:
        print(f"running FULL chain (download -> extract -> Cohere) for {reference}")
        result = br.run_live_bid_room_process(payload, timeout_seconds=600)
    else:
        print(f"running extraction chain (no COHERE_API_KEY) for {reference}")
        result = br._run_e2b_payload(payload, timeout_seconds=600,
                                     require_cohere=False)

    artifact = result.artifact
    OUT.mkdir(parents=True, exist_ok=True)
    SHARED.mkdir(parents=True, exist_ok=True)
    for base in (OUT, SHARED):
        (base / f"ARTIFACT-{reference}.json").write_text(
            json.dumps(artifact, indent=2))
        (base / f"REPORT-{reference}.md").write_text(
            br.render_bid_room_markdown(result))

    doc = next(iter(artifact.get("documents", [])), {})
    stage = "full (Cohere analysis included)" if full_chain else "extraction-only"
    print(f"chain: {stage} | sandbox {result.sandbox_id}")
    print(f"document: {doc.get('name')} — {doc.get('bytes')} bytes, "
          f"{doc.get('text_length')} chars extracted")
    print(f"requirement lines: {len(artifact.get('evidence', {}).get('requirements', []))}")
    print(f"outputs: demos/output/ + {SHARED}/")


if __name__ == "__main__":
    main()
