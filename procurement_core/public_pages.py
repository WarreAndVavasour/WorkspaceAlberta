"""Small public pages for connector setup and data-handling transparency."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from procurement_core.oauth_http import _page

PRIVACY = """
<h1>workspaceAlberta privacy notice</h1>
<p>Updated September 26, 2026. This notice covers the hosted workspaceAlberta procurement connector operated by Warre &amp; Vavasour.</p>
<h2>What the connector handles</h2>
<p>Public procurement searches can be used without signing in. Requests include the search terms, filters, business descriptions or documents you choose to provide. Your AI client sends tool inputs to this service and receives the results.</p>
<p>When you sign in with Google, we receive your Google account identifier and verified email to create your account and check paid access. We request only OpenID identity and email scopes, not Gmail messages, contacts or Drive files. We do not keep Google's access or ID tokens after verifying sign-in.</p>
<p>We store account details, saved business profiles and watchlists, OAuth client registrations and grant records, and subscription status and Stripe customer references. Payment details are handled by Stripe's checkout. Our connector does not receive your full card number.</p>
<h2>Service providers and locations</h2>
<p>The application runs on Google Cloud Run in Montréal; the account database is Supabase in Toronto. Cloudflare fronts the public endpoint. Google processes sign-in and Stripe processes payments under their own policies. These Canadian hosting locations do not mean every provider processes all data only in Canada.</p>
<p>Cohere receives search text for query planning and, when you request analysis, relevant tender text and business context. Bid-room processing uses E2B sandboxes and may send extracted document text to Cohere. Configured alternative model routes may use Hugging Face. Only submit documents you are permitted to share with these services.</p>
<p>When enabled, PostHog receives operational events such as tool names, timing, success, plan and a pseudonymous subscriber identifier. These events exclude tool request bodies, profile contents and email addresses. Hosting and network providers may also retain request and security logs.</p>
<h2>Use, retention and your choices</h2>
<p>We use this data to provide procurement results, save your settings, authenticate connections, manage subscriptions and operate the service. Google sign-in is separate from marketing or outreach; this flow does not enroll you in a SendGrid campaign.</p>
<p>Saved account information persists until removed. Authorization sessions and tokens expire, but expiry does not automatically erase their database records or provider logs. You can remove watched opportunities with the connector, disconnect it in your AI client, and contact us to request account-data access, correction, deletion or revocation of outstanding connections. Some billing and operational records may need separate handling.</p>
<p>Your AI client's handling of conversations and tool results is governed by that client's policies. Revoking Google access does not itself cancel a workspaceAlberta subscription or immediately revoke previously issued MCP tokens; contact us if you need those revoked.</p>
<p>Contact: <a href="mailto:christian@warreandvavasour.com">christian@warreandvavasour.com</a>.</p>
<p><a href="/support">Setup and support</a> · <a href="/">Home</a></p>
"""

SUPPORT = """
<h1>Connect workspaceAlberta</h1>
<p>Wouldn't it be great if the next contract was easier to find? Search CanadaBuys and Alberta Purchasing Connection from your compatible AI client.</p>
<ol><li>Add a remote HTTP MCP server with the URL <code>https://elbowsupknivesout.warreandvavasour.com/mcp</code>.</li>
<li>Try: “Find open Alberta construction opportunities closing in the next 30 days.” Public search does not require an account.</li>
<li>For saved watchlists, bid scorecards or document analysis, follow your client's Connect prompt. Continue with your Gmail or Google Workspace account, then approve access for the client shown.</li>
<li>Pro tools require an active workspaceAlberta Pro subscription with the same email. Signing in is free and does not charge you. Subscription payments use our separate Stripe checkout.</li></ol>
<p>Claude: add the URL in Customize → Connectors. Claude Code: add it as an HTTP MCP server, then use <code>/mcp</code> to authenticate. Other clients need remote MCP and OAuth with PKCE support.</p>
<p>Google accounts using an external email address without Gmail or Google Workspace are not currently supported, because we must verify ownership of the subscription email. If an email is already attached to another sign-in, contact support to link accounts.</p>
<p>Always verify deadlines, eligibility and requirements in the original tender documents. Summaries and scores assist your review; they do not submit a bid.</p>
<p>For sign-in help, account-data requests or subscription questions: <a href="mailto:christian@warreandvavasour.com">christian@warreandvavasour.com</a>. Include the client name and a description of the issue; never send passwords, API keys or access tokens.</p>
<p><a href="/privacy">Privacy</a> · <a href="https://github.com/HarleyCoops/WorkspaceAlberta">Source and documentation</a></p>
"""

# A simple vector wordmark keeps the public listing asset part of this service.
ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#16382d"/><text x="256" y="315" font-family="Arial,sans-serif" font-size="180" font-weight="700" text-anchor="middle" fill="#fff7e8">wA</text></svg>'


def register_public_pages(app: FastAPI) -> None:
    @app.get("/privacy", include_in_schema=False)
    async def privacy():
        return HTMLResponse(_page("workspaceAlberta privacy", PRIVACY))

    @app.get("/support", include_in_schema=False)
    async def support():
        return HTMLResponse(_page("workspaceAlberta setup and support", SUPPORT))

    @app.get("/icon.svg", include_in_schema=False)
    async def icon():
        return Response(ICON, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})
