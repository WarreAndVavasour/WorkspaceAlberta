"""Terms of service page for workspaceAlberta (directory listings link to /terms)."""

from __future__ import annotations

from procurement_core.web_pages import PRO_PRICE, SUPPORT_EMAIL, page

TERMS_UPDATED = "November 27, 2026"


def terms_page() -> str:
    body = f"""
<h1>Terms of service</h1>
<p class="lead">These terms cover your use of workspaceAlberta: the website, the MCP connector at <code>/mcp</code>, and the Claude and ChatGPT plugins that connect to it.</p>
<p class="muted">Last updated {TERMS_UPDATED}.</p>

<h2 id="who">1. Who we are</h2>
<p>workspaceAlberta is operated by Warre &amp; Vavasour Ltd, Alberta, Canada (“we”, “us”). Contact: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>

<h2 id="service">2. What the service does</h2>
<ul>
<li>workspaceAlberta searches public procurement notices from CanadaBuys and the Alberta Purchasing Connection, and helps you review tender documents.</li>
<li>It does not submit bids, contact buyers on your behalf, or guarantee any award.</li>
<li>Notices, summaries, classifications, scores and fit ratings can be incomplete or wrong. Some are produced by AI models. Always check the official posting, its amendments and its documents before you decide to bid.</li>
</ul>

<h2 id="accounts">3. Accounts and sign-in</h2>
<ul>
<li>Search works without an account. Some features need a free sign-in through your AI app (Google or a one-time email code).</li>
<li>Keep your sign-in to yourself. You are responsible for activity on your account.</li>
<li>Signing in never starts a paid subscription.</li>
</ul>

<h2 id="billing">4. Paid plans and billing</h2>
<ul>
<li><strong>Pro Unlimited</strong> is {PRO_PRICE} in Canadian dollars and renews every month until you cancel. Pro stays active to the end of the paid month.</li>
<li><strong>Bid Packs</strong> are C$19 (1 credit) or C$49 (3 credits), one-time. Credits do not renew and do not expire.</li>
<li>Checkout runs on Stripe and shows the final amount before you pay. We never see your card number.</li>
<li>Manage or cancel any time in the <a href="/billing/portal">billing portal</a> or by email. Billing details are also on the <a href="/pricing#terms">pricing page</a>.</li>
</ul>

<h2 id="use">5. Acceptable use</h2>
<ul>
<li>Use the service lawfully and for your own procurement research and bid preparation.</li>
<li>Do not try to break, overload, scrape at scale, or get around sign-in or usage limits.</li>
<li>Upload only documents you are allowed to share. Do not put passwords, API keys or access tokens into searches, documents or messages.</li>
<li>Follow the terms of CanadaBuys, the Alberta Purchasing Connection and any buyer portal you use.</li>
</ul>

<h2 id="data">6. Your data</h2>
<p>You keep ownership of the business details and documents you provide. We use them only to run the features you ask for. The <a href="/privacy">privacy notice</a> explains what we store and which service providers receive data for document review and matching.</p>

<h2 id="public">7. Public notice data</h2>
<p>Tender notices come from public government sources and stay subject to those sources' terms. We do not own them and cannot promise they are current or complete.</p>

<h2 id="availability">8. Availability and changes</h2>
<p>We work to keep the service running but do not promise it will always be available or error-free. We may change, add or remove features. If we change these terms in a material way, we will update the date above.</p>

<h2 id="liability">9. Limits of liability</h2>
<p>The service is provided “as is”. To the extent the law allows, we are not liable for lost bids, lost profits or indirect losses from using the service, and our total liability is limited to what you paid us in the 12 months before the claim.</p>

<h2 id="ending">10. Ending use</h2>
<p>You can stop using the service and cancel any plan at any time. We may suspend accounts that break these terms. To have your account data deleted, contact us at the address above.</p>

<h2 id="law">11. Governing law</h2>
<p>These terms are governed by the laws of Alberta and the federal laws of Canada that apply there.</p>
"""
    return page(
        "workspaceAlberta terms of service",
        body,
        description="Terms of service for workspaceAlberta, the Canadian public procurement search connector by Warre & Vavasour.",
    )
