# Bidder-requirement classifier

Goal: for any tender package, list every item the bidder must supply, and
from that list decide which tools WorkspaceAlberta needs to collect each
item from the user.

## Pipeline

| Stage | Where | What it does | Output |
|---|---|---|---|
| 1. Extract | HF Job, CPU part of the same job | PyMuPDF text per page; removes running headers and footers; keeps section path; splits into clauses, list items and paragraphs | units (`doc`, `page`, `section`, `text`, context) |
| 2. Silver labels | HF Job, `l4x1`, vLLM + `Qwen/Qwen3-8B` | One JSON-schema-constrained call per unit, temperature 0 | `response_types`, `mandatory`, `what_is_needed`, `form_or_schedule`, `evaluation_points`, `tools` |
| 3. Gold set | By hand | Correct about 300 rows across 10 to 20 documents | evaluation set |
| 4. Small classifier | HF Job, one short GPU run | Multi-label fine-tune (ModernBERT-base or SetFit) on silver labels; measure on gold | model on the Hub |
| 5. Production | Cloud Run, CPU | Small model labels every unit; only low-confidence units go to an LLM | requirement list per bid room |

Stage 1–2 script: `label_requirements.py` (UV script, PEP 723 dependencies).

## Response types and the tools they need

| Response type | The bidder must... | Tool that collects it |
|---|---|---|
| `attach_document` | attach an existing document (WCB letter, COR, insurance, licence) | `document_vault` |
| `form_field` | enter a company fact (legal name, GST number, contact) | `business_profile` |
| `declaration` | sign, certify or acknowledge (conflict of interest, addenda) | `signature_confirmation` |
| `compliance_confirm` | confirm it meets a requirement | `compliance_checklist` |
| `narrative` | write methodology, work plan, schedule, safety plan | `drafting_interview` |
| `pricing` | give prices, rates, lump sums | `pricing_worksheet` |
| `experience_reference` | list projects, references, key people | `project_and_people_records` |
| `security_bond` | supply bid bond or surety letter | `surety_request` |
| `attendance` | attend a site visit or meeting | `calendar` |
| `submission_instruction` | follow a submission rule or deadline | `submission_checklist` |
| `none` | nothing (information or buyer obligation) | none |

The counts of `tools` across a corpus show which tools to build first.

## Training corpus

Use public CanadaBuys tender attachments for the training corpus. They are
public, and `procurement_core/e2b_bid_room.py` already resolves their URLs.
Use APC documents only at inference time, from the user's own upload. Keep
any dataset that holds tender documents private.

## Run

```bash
# Extraction only, local, no GPU
uv run label_requirements.py --input 'docs/*.pdf' --dry-run

# Full run on HF Jobs
hf jobs uv run --flavor l4x1 --timeout 1h --secrets HF_TOKEN \
  -v hf://datasets/WarreVavasour/tender-documents:/data:ro \
  label_requirements.py --input '/data/**/*.pdf' \
  --output-repo WarreVavasour/tender-requirements-silver
```

## Known limits (v1)

- Scanned PDFs have no text layer. The job warns and skips; OCR is a later step.
- Tables come out as flattened text blocks. Pricing forms are found, but row-level structure is lost.
- Word and Excel files are not read yet. Convert them to PDF, or add a reader.
- The vLLM pin (`>=0.10.1,<0.11`) matches the `GuidedDecodingParams` API. Newer vLLM renames it.

## Classification-first pipeline (Jev)

Set `TYPESAFE_API_KEY` in `.env`. Set `REQ_TENDER_DIR` to the tender folder (default
`drive-downloads/tenders/AB-2026-06600`, git-ignored). Tender documents and outputs never go
into git.

Every step after splitting is a Jev classification. No LLM, no extraction. AB-2026-06600
(473 pages): about $0.30 and under 40 seconds in total.

| Step | Script | Jev questions | Output | AB-2026-06600 |
|---|---|---|---|---|
| Split | `label_requirements.py --dry-run` | none | `units.jsonl` (PDF text blocks) | 4,949 units |
| L0 unit triage | `jev_classify.py --output …/jev_labels_v2.jsonl` | response type (11), in bid?, mandatory? | `jev_labels_v2.jsonl` | 256 pass the unit gate |
| Page layer | `jev_pages.py` | document part (8), page asks for bid content? | `jev_pages.jsonl` | 59 pages pass |
| L1 tag + merge | `jev_l1.py` | sub-tag per response type (+ reject) | `jev_l1.jsonl`, `requirements.json` | 165 units → 31 requirements, 23 mandatory |

Gates:
- unit gate: type is not `none` and `in_bid` ≥ 0.5; attendance and submission rules exempt;
- page gate: page part is cover, instructions or bid forms, or `bid_content` ≥ 0.5.

`requirement_tags.py` holds everything that is not a model output: the sub-tags, the document
parts, and the routing per tag (answer source, lead time, connector, question). Routing is fixed
per tag on purpose; it does not vary by clause.

A requirement is one canonical tag (`<type>.<sub_tag>`) with all its evidence units and pages.
`other_*` share (12.9% here) shows where the tag library needs new tags.
