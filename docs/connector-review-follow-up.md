# Community connector review follow-up — October 1, 2026

Anthropic approved workspaceAlberta as a community connector. At verification
the submission portal said **Approved**, with **Live: not yet** and a Publish
button. Approval and directory publication are separate steps.

## Review fixes

| Feedback | Change | Verification |
| --- | --- | --- |
| Auth declaration disagrees with on-demand OAuth | Runtime guide declares `auth_type: none`, `partial_auth: true`; support and OAuth docs list the exact public, free sign-in and Pro tool groups. Saved profiles now challenge anonymous hosted requests. Portal on-demand OAuth/CIMD setting was saved without losing approval. | Anonymous protected MCP/REST calls return HTTP 401 with the resource-metadata challenge; discovery/public tools remain open; a signed-in unpaid user can read their own profile but receives 402 for Pro. |
| Legacy federal tools overlap combined tools | Keep names for existing clients; all five descriptions explicitly say legacy, federal CanadaBuys only and identify the combined alternative. | Tool-list regression tests. |
| Unsupported status filter advertised | Remove the status claim from `search_contracts`; keep its existing keyword/province schema. | Schema/description regression test. |
| Subprocessors and cross-border processing unclear | Public privacy names Cohere and E2B, the data each receives and US processing locations. APC planning tools and bid-room tool disclose data sharing in their descriptions. | HTTP privacy assertions and live tool-description checks after rollout. |
| Bid-room timeouts exceed client ceiling | Remove agent timeout parameters. Overall response limit 145 seconds; worker budget 135 seconds; sandbox expiry at most 130 seconds, command execution at most 120, setup request at most 10, cleanup request at most 5; no SDK retries. Older REST timeout/keep-alive inputs cannot extend these limits. | Delayed host lookup returns an error promptly and cannot subsequently create a sandbox. Remote command timeout still kills the sandbox. MCP timeout result is marked as an error. |

Large document packages can still exceed the budget. They receive an explicit
incomplete/timeout response and can be retried with fewer attachments, including
`max_attachments=0` for notice-only analysis. This is bounded synchronous work,
not a background-job system. A source lookup already in a worker thread may
finish after the response deadline; it cannot then start sandbox processing.
If sandbox cleanup cannot be confirmed, automatic expiry still applies and a
successful artifact includes a warning. Provider logs have separate retention.

The declaration is directory metadata, not the standard MCP registry schema.
The portal's overview still labels Authentication as **None** even though its
saved connection editor selects **Required when the server asks**, OAuth and
CIMD. The UI does not expose the underlying `partial_auth` boolean; do not claim
it was independently inspected. If review still sees `partial_auth: false`, ask
the directory team to reconcile that legacy declaration with the saved on-demand
connection settings. Do not toggle to mandatory authentication for public tools.

## Public website

Added `/blog`, individual post URLs and an RSS feed to this same FastAPI service.
Posts are repo-authored Markdown with explicit publication status; drafts and
future posts are not publicly accessible. The first announcement describes
community approval accurately and links to setup and privacy. See
[Blog publishing](blog-publishing.md).

## Release checks

The smoke and Cloud Run workflows include the review regressions, blog tests
and offline E2B payload/cleanup tests. The release verifier checks live blog
routes, published-post/feed consistency and the exact reviewed CSS hash.
OAuth readiness verifies every protected tool advertised by the runtime guide
returns the required challenge with missing or invalid credentials.
No database migration or new secret is
required. Merge, stage at zero traffic, verify the protected-profile OAuth
upgrade and the public blog, then promote the exact tested revision. Directory
publication is a separate portal action; changing reviewed listing details
before publication can withdraw approval. Authentication-only edits preserve
approval according to the portal.

Provider location sources checked October 1, 2026:

- [Cohere Trust Center](https://trustcenter.cohere.com/?format=html): public hosting in Google Cloud US-Central.
- [Cohere data commitments](https://cohere.com/enterprise-data-commitments): retention depends on account terms; no unconditional ZDR claim.
- [E2B region documentation](https://docs.e2b.dev/faq/egress-ip-ranges): default US region on Google Cloud `us-west1`; placement may change.
- [E2B security](https://e2b.dev/security) and [privacy](https://e2b.dev/privacy): sandbox lifecycle and provider data handling.
- [Anthropic connector labels](https://claude.com/docs/connectors/verification): Community and Verified are distinct; community screening is not a security audit.
