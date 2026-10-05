# Publication gates discovered during the migration

The production probe on 2026-10-05 found `/health` and `/privacy` returning 200,
the public MCP handshake/guide working, and private-profile access correctly
rejecting anonymous requests. It also found `/terms` returning **404**. The
existing `/support` route is included in the package's supportURL.

**Do not submit this draft for public review until publisher-approved terms are
published at the declared termsOfServiceURL (or that URL is changed to the real
approved terms).** The migration does not invent a legal agreement. OpenAI's
current field reference requires all four HTTPS listing URLs for MCP review:
website, support, privacy policy and terms of service.

The package now imports the five positive and three negative scenario drafts
through `extensions.com.openai.review.test_cases`. These describe expected
behavior; they are not evidence the scenarios have already run in OpenAI. A real
reviewer-accessible demo recording, dedicated reviewer access, completed scans,
verified publishing identity, domain challenge and approval are still required.
Check the portal's category titles against `Business & Operations` before
submission and correct the category if that title is unavailable.

Backend release is independent of directory approval. The post-deployment
readiness artifact records actual endpoint checks, including unresolved `/terms`
and domain-challenge status, rather than marking publication ready because tests
passed. The eight skipped baseline OAuth cases require an explicit live Supabase
test-database opt-in; no production database tests were enabled by this migration.

References:
- https://developers.openai.com/plugins/deploy/submission
- https://developers.openai.com/plugins/build/auth
