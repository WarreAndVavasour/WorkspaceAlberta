# APC document processing

`get_opportunity_details` now lists APC procurement-file and addendum IDs, versions,
amendments, sizes, and the correct `/posting/AB-YYYY-NNNNN` source URL. Search rows
and Bid Room artifacts use the same posting route. The public APC API's document
metadata does not, by itself, provide permission or a public download URL.

`process_bid_room` discovers the files and addenda in that metadata. Public download
URLs supplied by the source can be processed. Where the source only lists document
IDs, callers can map those IDs to already authorized, publicly accessible HTTPS
copies using `apc_document_urls`. Unknown IDs, URL credentials, private addresses,
APC authenticated/download URLs, and source-declared NDA/authentication/registration
requirements are rejected or marked as requiring access. Redirects to APC downloads
are blocked too. The tool does not sign in, express supplier interest, subscribe
notifications, accept cookies, or pass APC credentials into a sandbox.

An example **after obtaining permission for processing and an authorized public
copy**, using the actual RE9256 document ID:

```json
{
  "reference": "AB-2026-06584",
  "max_attachments": 1,
  "apc_document_urls": {
    "f245a5f8-d095-4e7c-8872-ddcc900dc24c": "https://your-authorized-public-source.example/re9256.pdf"
  }
}
```

The example URL is a placeholder, not a verified copy. A caller-provided mapping
does not prove that a public copy matches the current APC version. Verify its
provenance, version and amendments before bidding. Do not publish confidential
documents merely to make them reachable by this tool.

A default APC call with no readable procurement files fails **before E2B creation**.
An explicit `max_attachments=0` can request notice-only processing; it still invokes
the paid processing path, and its result is clearly labelled `notice_only` and
incomplete. Increasing the attachment limit cannot resolve access requirements.

For a readable file, its URL goes into the actual E2B processor payload. The
sandbox downloads it, checks PDF content rather than accepting a login page as
a document, extracts the body, and includes that evidence in the model review.
PDF page images go to Cohere Parse when enabled. The file ID, version, amendment,
byte count, SHA-256, extraction status and truncation flags remain in the artifact.

Coverage is returned as `complete`, `partial`, or `notice_only`, with counts and
per-file issues. Gated files, omitted addenda, attachment limits, failed downloads,
empty/failed extracts, missing processor records, and extraction/model-text limits
prevent a complete status. An external posting page alone never counts as an
extracted procurement document. Both the model prompt and the user-visible result
include coverage warnings; the host recomputes coverage rather than trusting a
processor-provided `complete` flag. `complete` describes extraction of the listed
files, not a guarantee of OCR accuracy, supplier eligibility or bid compliance.

## Verification and limits

`tests.test_apc_documents` uses a reduced public metadata snapshot of RE9256 and
generated local PDFs. It executes the actual embedded processor, with only its
transport mapped to a loopback fixture server and work directory redirected to a
temporary directory. It proves that base-PDF and addendum body text absent from the
notice reaches the evidence artifact. It also verifies access gating before paid
work and incomplete coverage on errors and limits. No E2B or Cohere request is
needed for these tests; Parse and model review are disabled, and provider/installation
requests are rejected.

Live sandbox provisioning, Cohere Parse/model calls, the authenticated production
connection, APC account/document access and deployment remain separate verification
steps. This patch does not authorize or perform them.
