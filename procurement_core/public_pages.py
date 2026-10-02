"""Small public pages for connector setup and data-handling transparency."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response, FileResponse
from procurement_core.oauth_http import _page
from procurement_core.auth_pages import ARTWORK

PRIVACY = """
<h1>workspaceAlberta privacy notice</h1>
<p>Updated October 1, 2026. This notice covers the hosted workspaceAlberta procurement connector operated by Warre &amp; Vavasour.</p>
<h2>What the connector handles</h2>
<p>Public procurement searches can be used without signing in. Requests include the search terms, filters, business descriptions or documents you choose to provide. Your AI client sends tool inputs to this service and receives the results.</p>
<p>When you sign in with Google, we receive your Google account identifier and verified email to create your account and check paid access. We request only OpenID identity and email scopes, not Gmail messages, contacts or Drive files. We do not keep Google's access or ID tokens after verifying sign-in.</p>
<p>We store account details, saved business profiles and watchlists, OAuth client registrations and grant records, and subscription status and Stripe customer references. Payment details are handled by Stripe's checkout. Our connector does not receive your full card number.</p>
<h2>Service providers and locations</h2>
<p>The application runs on Google Cloud Run in Montréal; the account database is Supabase in Toronto. Cloudflare fronts the public endpoint. Google processes sign-in and Stripe processes payments under their own policies. These Canadian hosting locations do not mean every provider processes all data only in Canada.</p>
<p><strong>Cohere and E2B are subprocessors</strong> used to deliver the optional planning and document-analysis features. Data sent to them can leave Canada:</p>
<ul>
<li><strong>Cohere:</strong> when the planner is configured, search terms, search intent or business capabilities go to its public API to select APC commodity filters. Requested tender analysis also sends tender text, business context and questions. Bid-room review sends extracted evidence and profile context; Cohere Parse receives images and rasterized PDF page images. Cohere describes its public SaaS hosting as Google Cloud US-Central, United States. We use the public API, not a Canadian private deployment. See <a href="https://trustcenter.cohere.com/?format=html">Cohere's hosting and data-handling information</a> and <a href="https://cohere.com/enterprise-data-commitments">data commitments</a>. Retention depends on the key and account agreement; we do not promise zero retention.</li>
<li><strong>E2B (FoundryLabs, Inc.):</strong> requested bid-room processing sends opportunity metadata, attachment URLs, documents, business capabilities and bid context to an isolated sandbox for downloading, extraction and review. We use E2B's default managed US region; its published default is Google Cloud <code>us-west1</code>, United States. E2B may change placement. This service does not configure Canadian sandbox residency. The sandbox sends the evidence and page images described above to Cohere and returns the result to us. We attempt to destroy the sandbox after the call and also set a short automatic expiry; this does not erase provider operational logs. See <a href="https://docs.e2b.dev/faq/egress-ip-ranges">E2B regions</a>, <a href="https://e2b.dev/security">security</a> and <a href="https://e2b.dev/privacy">privacy policy</a>.</li>
</ul>
<p>Configured alternative model routes may use Hugging Face, whose processing location depends on the selected provider. These are not a promise of Canadian-only processing. Only submit documents and business information you are permitted to share with the named providers. Public lookup tools without model planning do not send documents to E2B.</p>
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
<h2>Which tools need sign-in?</h2>
<p>The connector is <strong>authless with partial authentication</strong>: connect and use public tools first; a protected tool returns HTTP 401 so your client can start OAuth sign-in.</p>
<ul><li><strong>Free sign-in:</strong> <code>set_business_profile</code> and <code>get_my_profile</code> save or read your own profile. No Pro subscription is needed.</li>
<li><strong>Sign-in and active Pro:</strong> <code>watch_opportunity</code>, <code>list_watchlist</code>, <code>unwatch_opportunity</code>, <code>bid_no_bid_scorecard</code>, <code>process_bid_room</code> and <code>analyze_contract_with_cohere</code>.</li>
<li><strong>Public:</strong> all remaining tools, including combined search, details, deadlines, daily briefs and matching with an inline profile. Legacy federal tools cover CanadaBuys only; prefer the combined opportunity tools for CanadaBuys and Alberta APC together.</li></ul>
<p>APC search and matching may send your search terms or business capabilities to Cohere for commodity-filter selection. Document analysis sends data to the providers described in our <a href="/privacy">privacy notice</a>. Bid-room processing has a 145-second overall limit and may ask you to retry a large package with fewer attachments. A timeout means no completed analysis is available.</p>
<p>Always verify deadlines, eligibility and requirements in the original tender documents. Summaries and scores assist your review; they do not submit a bid.</p>
<p>For sign-in help, account-data requests or subscription questions: <a href="mailto:christian@warreandvavasour.com">christian@warreandvavasour.com</a>. Include the client name and a description of the issue; never send passwords, API keys or access tokens.</p>
<p><a href="/blog">News and notes</a> · <a href="/privacy">Privacy</a> · <a href="https://github.com/WarreAndVavasour/WorkspaceAlberta">Source and documentation</a></p>
"""

# The listing mark as outlined paths, so it renders the same without any installed font.
ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#16382d"/><path fill="#fff7e8" d="M236.400390625 315.0H210.296875L195.1796875 256.9921875Q194.125 253.037109375 191.048828125 237.48046875L186.478515625 257.16796875L171.185546875 315.0H145.08203125L120.47265625 219.90234375H143.67578125L159.3203125 292.587890625L160.55078125 286.083984375L162.748046875 275.80078125L177.689453125 219.90234375H204.14453125L218.734375 275.80078125Q219.96484375 280.37109375 222.337890625 292.587890625L224.798828125 280.986328125L238.509765625 219.90234375H261.361328125ZM360.58984375 315.0 349.603515625 283.359375H302.40625L291.419921875 315.0H265.4921875L310.66796875 191.162109375H341.25390625L386.25390625 315.0ZM325.9609375 210.234375 325.43359375 212.16796875Q324.5546875 215.33203125 323.32421875 219.375Q322.09375 223.41796875 308.20703125 263.84765625H343.802734375L331.5859375 228.251953125L327.806640625 216.298828125Z"/></svg>'

# Raster copies of the same mark for clients and directories that do not accept SVG.
ICON_FILES = {
    "favicon.ico": "image/x-icon",
    "favicon-32.png": "image/png",
    "icon-192.png": "image/png",
    "icon.png": "image/png",
    "apple-touch-icon.png": "image/png",
}
_ICON_SOURCES = {"icon.png": "icon-512.png"}


def register_public_pages(app: FastAPI) -> None:
    from procurement_core.blog import register_blog_routes
    register_blog_routes(app)
    # A fixed allowlist exposes only selected web derivatives, never source folios.
    artwork_files = {f"{scan}.webp" for scan, *_ in ARTWORK}

    @app.get("/assets/archive/{filename}", include_in_schema=False)
    async def archival_artwork(filename: str):
        if filename not in artwork_files:
            return Response(status_code=404)
        return FileResponse(Path(__file__).with_name("assets") / "archive" / filename,
                            media_type="image/webp",
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/assets/google-signin.png", include_in_schema=False)
    async def google_signin_button():
        return FileResponse(Path(__file__).with_name("assets") / "google-signin.png",
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/privacy", include_in_schema=False)
    async def privacy():
        return HTMLResponse(_page("workspaceAlberta privacy", PRIVACY))

    @app.get("/support", include_in_schema=False)
    async def support():
        return HTMLResponse(_page("workspaceAlberta setup and support", SUPPORT))

    @app.get("/icon.svg", include_in_schema=False)
    async def icon():
        return Response(ICON, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})

    icon_dir = Path(__file__).with_name("assets") / "icons"

    def icon_route(path: Path, media_type: str):
        async def serve_icon():
            return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})
        return serve_icon

    for name, media_type in ICON_FILES.items():
        app.add_api_route(f"/{name}", icon_route(icon_dir / _ICON_SOURCES.get(name, name), media_type),
                          methods=["GET"], include_in_schema=False)
