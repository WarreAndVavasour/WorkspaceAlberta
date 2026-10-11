# Corporate OpenAI delivery pipeline

Canonical repository: `WarreAndVavasour/WorkspaceAlberta`, repository ID
`1400771945`, organization ID `323728381`. The personal repository is not a
release source for this change. The harness and Cohere adapter are unaffected.

## Package and checks

The portable package is `plugins/workspacealberta/`, version 1.1.0. It contains
one remote Streamable HTTP MCP connection, a provider-neutral procurement skill
with its requirements-board HTML template, the existing icon, listing copy and five positive/three negative review scenarios.
It does not contain credentials, customer records, server source or local hooks.
The scenarios describe expected behavior; they are not a completed OpenAI review.

```sh
python -m pip install -r requirements.txt -r mcp-servers/canadabuys/requirements.txt -r tests/requirements.txt
python -m unittest tests.test_openai_plugin tests.test_openai_wire tests.test_openai_pipeline
python scripts/openai_plugin.py build --output output/openai/workspacealberta-openai.zip
python scripts/openai_plugin.py probe --output output/openai/live-readiness.json
```

The OpenAI verification workflow runs the production regression selection plus
OpenAI interoperability, actual HTTP serialization, APC document and local
bid-room tests. It has read-only GitHub permissions and archives the package,
source SHA, test results and an explicit public-endpoint readiness report.
Missing `/terms` or domain verification does not become a fabricated passing
submission verdict merely because unit tests passed.

## Corporate Cloud Run release

The existing workflow remains manual, with distinct stage and promote decisions.
Its guard now requires the exact corporate repository name, repository ID and
owner ID. That guard does **not** revoke any separate Google IAM grant held by
the former personal repository; Google trust must be audited separately.

```sh
gh workflow run deploy-cloud-run.yml --repo WarreAndVavasour/WorkspaceAlberta --ref main -f action=stage
```

Staging builds tracked source only, deploys an immutable image at zero production
traffic, compares runtime configuration privately, and verifies OAuth, tool
schemas, assets and procurement responses. OpenAI backend checks now run against
the actual candidate before promotion, and against the public origin afterward.
They verify the advertised identity scopes/UserInfo location, explicit tool
security schemes, public guide and unauthorized private-profile challenge.
They do not impersonate a user or purchase an entitlement.

Promotion requires the exact staged revision and recorded previous production
revision. Preserve the helper's stale-traffic, immutable-image, source-history,
configuration and rollback guards. Never substitute `LATEST` or deploy the
personal repository's candidate. Release reports include the corporate source
repository, exact commit, image digest, revision, checks and traffic outcome.

`probe --base-url <candidate-origin> --require-backend` is a fail-closed backend
gate. Only the canonical production host or a tagged URL for the existing Cloud
Run service is accepted. `--require-ready` additionally gates technical listing
checks, including `/terms` and the domain challenge; genuine host sign-in,
reviewer cases, portal ownership verification and OpenAI review remain separate.

## Portal handoff

Official portal: https://platform.openai.com/plugins

Upload the MCP-plus-skill ZIP as the initial package under the verified owning
OpenAI organization/project. Include the MCP connection from the beginning,
rather than attempting to turn a skills-only draft into an MCP plugin later.
The source migration guide calls this the With MCP path; the current submission
page presents a ZIP-first import. Both require the actual remote MCP endpoint.

The server serves the exact portal-issued domain token from
`/.well-known/openai-apps-challenge` when `WA_OPENAI_APPS_CHALLENGE` is configured.
It deliberately returns 404 when unset. Never invent a token, overwrite another
plugin's domain challenge, or treat HTTP 200 alone as proof of portal ownership.
The stable ChatGPT callback is enabled. Callback-ID-specific URLs require an
exact entry in `WA_OPENAI_REDIRECT_URIS`; no callback host wildcard is accepted.

The public terms URL must contain publisher-approved terms. This change does
not create a legal agreement. Reviewer access must be a dedicated sample account
with the entitlements required by the cases, not the owner's Google session.
No authentication bypass or password is added for review. Complete genuine
OpenAI sign-in/refresh, reviewer scenarios, accessible video and portal scans
before submission. Approval and publication cannot be inferred from CI or a
successful Cloud Run deployment.

Official references checked 2026-10-05:
- https://developers.openai.com/plugins/guides/submit-claude-plugin
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/deploy/submission

## Intermittent planner transport errors during acceptance

The live release check may retry only `search_opportunities` and
`find_matching_opportunities` when the server reports the exact
`request-failed` planner fallback. It waits two then five seconds, at most
two additional calls, and records every attempt, warning and delay in
the release report. Persistent fallback still fails. Other warnings, partial
enumeration, tool errors, authorization failures and all write actions are not
retryable. The existing successful-result and completeness assertions remain
unchanged. This handles transient upstream failures in acceptance; it does not
claim to eliminate intermittent Cohere failures in the product.
