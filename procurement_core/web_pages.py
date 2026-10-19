"""Human-facing web pages: landing, pricing, try-a-search, status and errors.

These pages are the browser front door for first-time visitors. They follow
the first-run QA findings (October 2026): one connection URL everywhere (the
public origin, never the Cloud Run host), plain language before jargon, a
visible path to Pro pricing and checkout, a real search that works in a phone
browser, 44px tap targets, no sideways scrolling at 375px, and a short French
summary. Every interpolated value is escaped; the try page renders results
with ``textContent`` only.
"""

from __future__ import annotations

from html import escape

STRIPE_SUBSCRIBE_URL = "https://buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a"
PRO_PRICE = "C$85 / month"
SUPPORT_EMAIL = "christian@warreandvavasour.com"
COMPANY_URL = "https://warreandvavasour.com"
REPO_URL = "https://github.com/WarreAndVavasour/WorkspaceAlberta"

ICON_LINKS = (
    '<link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" href="/icon.svg" type="image/svg+xml">'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
)

STYLE = """
:root { --ink:#1c1c1c; --muted:#555; --line:#ddd; --accent:#16382d; --accent-ink:#fff7e8; --link:#0b57d0; --soft:#f4f4f1; }
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0; color: var(--ink); background: #fff; line-height: 1.55; font-size: 17px; }
main, header.top, footer { max-width: 46rem; margin: 0 auto; padding: 0 16px; }
header.top { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; padding-top: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }
header.top .brand { font-weight: 700; color: var(--ink); text-decoration: none; font-size: 1.1rem; min-height: 44px; display: inline-flex; align-items: center; }
header.top nav { display: flex; flex-wrap: wrap; gap: 4px; }
header.top nav a { min-height: 44px; display: inline-flex; align-items: center; padding: 0 10px; border-radius: 8px; color: var(--ink); text-decoration: none; }
header.top nav a:hover, header.top nav a[aria-current="page"] { background: var(--soft); }
h1 { font-size: 1.9rem; line-height: 1.2; margin: 1.6rem 0 0.4rem; }
h2 { font-size: 1.3rem; margin: 2rem 0 0.5rem; }
p, li { overflow-wrap: anywhere; }
a { color: var(--link); }
.lead { font-size: 1.15rem; color: #333; margin-top: 0; }
.muted { color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 1.2rem 0; }
.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 48px; padding: 0 18px; border-radius: 10px; font: inherit; font-weight: 600; text-decoration: none; border: 2px solid var(--accent); cursor: pointer; }
.btn.primary { background: var(--accent); color: var(--accent-ink); }
.btn.secondary { background: #fff; color: var(--accent); }
.urlbox { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; margin: 0.6rem 0 0.4rem; }
.urlbox code { flex: 1 1 16rem; min-width: 0; display: flex; align-items: center; padding: 10px 12px; background: var(--soft); border: 1px solid var(--line); border-radius: 10px; font-size: 0.95rem; overflow-wrap: anywhere; word-break: break-all; user-select: all; -webkit-user-select: all; }
code { background: var(--soft); border-radius: 6px; padding: 0.1rem 0.35rem; overflow-wrap: anywhere; }
pre { background: var(--soft); border-radius: 8px; padding: 12px; overflow-x: auto; font-size: 0.9rem; }
.steps { padding-left: 1.3rem; }
.steps li { margin: 0.5rem 0; }
.card { border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; margin: 12px 0; }
.plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 12px; }
.plans .card h3 { margin: 0 0 0.2rem; }
.price { font-size: 1.6rem; font-weight: 700; margin: 0.2rem 0 0.6rem; }
.plans ul { padding-left: 1.2rem; margin: 0.4rem 0 0.8rem; }
dl.glossary dt { font-weight: 600; margin-top: 0.6rem; }
dl.glossary dd { margin: 0.1rem 0 0 0; color: #333; }
details { border-top: 1px solid var(--line); padding: 4px 0; }
details summary { min-height: 44px; padding: 10px 0; cursor: pointer; font-weight: 600; list-style: none; }
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "▸"; display: inline-block; width: 1.2em; color: var(--accent); transition: transform .15s; }
details[open] summary::before { transform: rotate(90deg); }
.notice { background: #fff8e1; border-radius: 10px; padding: 12px 14px; }
.error { color: #9b1c1c; }
form.search { display: grid; gap: 10px; margin: 1rem 0; }
form.search label { display: grid; gap: 4px; font-weight: 600; }
form.search input, form.search select { font: inherit; min-height: 48px; padding: 8px 12px; border: 1px solid #bbb; border-radius: 10px; width: 100%; background: #fff; }
.result h3 { margin: 0 0 0.3rem; font-size: 1.05rem; }
.result p { margin: 0.15rem 0; }
.result .meta { color: var(--muted); font-size: 0.95rem; }
.result a { display: inline-flex; min-height: 44px; align-items: center; }
footer { margin-top: 3rem; padding-top: 12px; padding-bottom: 32px; border-top: 1px solid var(--line); color: var(--muted); font-size: 0.95rem; }
footer nav { display: flex; flex-wrap: wrap; gap: 4px 2px; }
footer nav a { min-height: 44px; display: inline-flex; align-items: center; padding: 0 8px; }
section[lang="fr"] { background: var(--soft); border-radius: 12px; padding: 4px 16px 12px; margin-top: 2rem; }
"""

COPY_SCRIPT = """
<script>
(function () {
  var touch = window.matchMedia && window.matchMedia('(hover: none)').matches;
  document.querySelectorAll('[data-copy]').forEach(function (button) {
    var label = button.textContent;
    button.addEventListener('click', function () {
      var text = button.getAttribute('data-copy');
      var done = function () { button.textContent = 'Copied'; setTimeout(function () { button.textContent = label; }, 1800); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { window.prompt('Copy this address:', text); });
      } else { window.prompt('Copy this address:', text); }
    });
    if (touch) { button.setAttribute('aria-label', 'Tap to copy the address'); }
  });
})();
</script>
"""

_NAV = (("/", "Home"), ("/try", "Try a search"), ("/pricing", "Pricing"), ("/support", "Help"))


def page(title: str, body: str, *, current: str = "", script: str = "", description: str = "") -> str:
    """Wrap trusted body markup in the shared shell (header nav + footer)."""
    current_attr = ' aria-current="page"'
    nav = "".join(
        f'<a href="{href}"{current_attr if href == current else ""}>{label}</a>'
        for href, label in _NAV
    )
    meta = f'<meta name="description" content="{escape(description)}">' if description else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title>{meta}{ICON_LINKS}<style>{STYLE}</style></head><body>"
        f'<header class="top"><a class="brand" href="/">workspaceAlberta</a><nav aria-label="Main">{nav}</nav></header>'
        f"<main>{body}</main>"
        '<footer><nav aria-label="Footer">'
        '<a href="/pricing">Pricing &amp; terms</a><a href="/privacy">Privacy</a><a href="/support">Help</a>'
        '<a href="/blog">News</a><a href="/developers">For developers</a>'
        f'<a href="{COMPANY_URL}">Warre &amp; Vavasour</a></nav>'
        "<p>workspaceAlberta is operated by Warre &amp; Vavasour Ltd, Alberta, Canada. "
        f'Contact: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p></footer>'
        f"{script}</body></html>"
    )


def _url_box(mcp_url: str) -> str:
    safe = escape(mcp_url)
    return (
        f'<div class="urlbox"><code id="mcp-url">{safe}</code>'
        f'<button type="button" class="btn primary" data-copy="{safe}">Copy address</button></div>'
    )


def landing_page(mcp_url: str) -> str:
    body = f"""
<h1>Find Canadian government tenders from inside your AI app</h1>
<p class="lead">workspaceAlberta searches federal tenders (CanadaBuys) and Alberta tenders (Alberta Purchasing Connection) for you.
Ask in plain words, for example: <em>“Find Alberta construction tenders closing in the next 30 days.”</em></p>
<p>Searching is free. You do not need an account.</p>
<div class="actions">
  <a class="btn primary" href="/try">Try a search now</a>
  <a class="btn secondary" href="#connect">Add it to my AI app</a>
  <a class="btn secondary" href="/pricing">See Pro pricing</a>
</div>

<h2 id="connect">Add it to your AI app (2 minutes)</h2>
<p>Your AI app needs this address. Copy it:</p>
{_url_box(mcp_url)}
<p class="muted">This is the only address you need. It is the same on every page.</p>
<details open><summary>Claude (website, desktop or phone)</summary>
<ol class="steps">
<li>On claude.ai or in Claude Desktop, open <strong>Customize → Connectors</strong>.</li>
<li>Choose <strong>Add custom connector</strong>, name it <em>workspaceAlberta</em>, and paste the address.</li>
<li>Start a new chat and ask for tenders. The connector you added also works in the Claude phone app.</li>
</ol></details>
<details><summary>ChatGPT</summary>
<ol class="steps">
<li>If your plan allows custom connectors, add a new connector in ChatGPT settings.</li>
<li>Paste the address and save. Then ask for tenders in a new chat.</li>
</ol></details>
<details><summary>Claude Code, Cursor, VS Code and other developer tools</summary>
<ol class="steps">
<li>Add a remote HTTP server with the address above. Example configuration:</li>
</ol>
<pre>{{"mcpServers": {{"workspaceAlberta": {{"type": "http", "url": "{escape(mcp_url)}"}}}}}}</pre>
</details>

<h2>Free and Pro</h2>
<p><strong>Free, no account:</strong> search, tender details, closing deadlines, daily briefs, and matching against a business description.</p>
<p><strong>Pro, {PRO_PRICE}:</strong> saved watchlists, bid/no-bid scorecards and AI review of tender documents.
Your AI app asks you to sign in with Google the first time you use a Pro feature. Signing in is free and does not charge you.</p>
<p><a class="btn secondary" href="/pricing">Compare Free and Pro</a></p>

<h2>Words you may see</h2>
<dl class="glossary">
<dt>Connector (also called “MCP server”)</dt><dd>An add-on that lets your AI app use an outside service. MCP is the standard these add-ons use.</dd>
<dt>Tender</dt><dd>A public request from a government buyer for goods, services or construction.</dd>
<dt>Sign in</dt><dd>You sign in with Google, inside your AI app, only when you use a Pro feature.</dd>
</dl>

<p class="notice">Always open and check the original tender before you bid. workspaceAlberta helps you find and sort tenders; it does not replace the official posting.</p>

<section lang="fr" aria-labelledby="fr-title">
<h2 id="fr-title">En français</h2>
<p>workspaceAlberta trouve les appels d'offres publics fédéraux (AchatsCanada) et albertains (Alberta Purchasing Connection) directement dans votre application d'IA.
La recherche est gratuite et sans compte. Ajoutez l'adresse ci-dessus comme connecteur dans votre application (Claude : <strong>Personnaliser → Connecteurs</strong>).
L'abonnement Pro coûte 85 $ CA par mois. Les résultats sont en anglais. Vérifiez toujours l'avis officiel avant de soumissionner.
<a href="/pricing#fr">Tarifs en français</a>.</p>
</section>
"""
    return page(
        "workspaceAlberta — Canadian tender search for your AI app",
        body,
        current="/",
        script=COPY_SCRIPT,
        description="Search CanadaBuys and Alberta Purchasing Connection tenders from Claude, ChatGPT and other AI apps. Free search; Pro C$85/month.",
    )


def developers_page(mcp_url: str) -> str:
    body = f"""
<h1>For developers</h1>
<p>Connection address (MCP over streamable HTTP):</p>
{_url_box(mcp_url)}
<pre>{{
  "mcpServers": {{
    "workspaceAlberta": {{ "type": "http", "url": "{escape(mcp_url)}" }}
  }}
}}</pre>
<p>Pro tools use OAuth 2.1 sign-in (PKCE, dynamic client registration). Legacy <code>Authorization: Bearer wa_live_…</code> subscriber keys still work.
Check a token at <code>GET /me</code> with that header.</p>
<h2>REST</h2>
<p>The same tools are available over REST: <a href="/docs">interactive API docs</a> · <a href="/openapi.json">openapi.json</a> ·
<a href="/tools">tool schemas</a> · <a href="/health">health</a>.</p>
<h2>Discovery documents</h2>
<p><a href="/.well-known/agent.json">A2A agent card</a> · <a href="/.well-known/mcp.json">mcp.json</a> ·
<a href="/.well-known/oauth-protected-resource">protected-resource metadata</a> ·
<a href="/.well-known/oauth-authorization-server">authorization-server metadata</a></p>
<p><a href="{REPO_URL}">Source and documentation on GitHub</a></p>
"""
    return page("workspaceAlberta for developers", body, current="", script=COPY_SCRIPT)


def pricing_page() -> str:
    body = f"""
<h1>Pricing</h1>
<p class="lead">Searching is free. Pro adds saved work and document review.</p>
<div class="plans">
<div class="card"><h3>Free</h3><p class="price">C$0</p>
<p class="muted">No account needed.</p>
<ul><li>Search federal and Alberta tenders</li><li>Tender details and closing deadlines</li>
<li>Daily bid brief</li><li>Matching against a business description you type in</li>
<li>Save a business profile (free sign-in)</li></ul>
<a class="btn secondary" href="/try">Try a search</a></div>
<div class="card"><h3>Pro</h3><p class="price">{PRO_PRICE}</p>
<p class="muted">Billed monthly in Canadian dollars. Cancel any time.</p>
<ul><li>Everything in Free</li><li>Watchlist: save tenders and follow them</li>
<li>Bid/no-bid scorecard</li><li>AI review of tender documents (bid room)</li>
<li>Requirements list from tender documents</li><li>AI analysis of a CanadaBuys tender</li></ul>
<a class="btn primary" href="{STRIPE_SUBSCRIBE_URL}" rel="noopener">Start Pro — {PRO_PRICE}</a></div>
</div>

<h2>How Pro works</h2>
<ol class="steps">
<li>Subscribe with the button above. Checkout is on Stripe, our payment provider. We never see your card number.</li>
<li>Use the <strong>same email</strong> for checkout and for Google sign-in. A Gmail or Google Workspace account works. Another email address will not work yet; write to us first.</li>
<li>In your AI app, use a Pro feature. The app asks you to sign in with Google. After sign-in, Pro features work.</li>
</ol>

<h2 id="terms">Subscription terms</h2>
<ul>
<li><strong>Seller:</strong> Warre &amp; Vavasour Ltd, Alberta, Canada.</li>
<li><strong>Price:</strong> {PRO_PRICE}, in Canadian dollars. Checkout shows the final amount before you pay.</li>
<li><strong>Renewal:</strong> the subscription renews every month until you cancel.</li>
<li><strong>Cancel:</strong> email <a href="mailto:{SUPPORT_EMAIL}?subject=Cancel%20workspaceAlberta%20Pro">{SUPPORT_EMAIL}</a> from your subscription email. Pro stops at the end of the paid month.</li>
<li><strong>Data:</strong> see the <a href="/privacy">privacy notice</a> for what Pro features send to service providers.</li>
<li><strong>Results:</strong> workspaceAlberta helps you find and review tenders. It does not submit bids and does not guarantee awards. Always check the official posting.</li>
</ul>
<p>Questions before you buy? Email <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>

<section lang="fr" id="fr" aria-labelledby="fr-pricing">
<h2 id="fr-pricing">Tarifs en français</h2>
<p><strong>Gratuit :</strong> recherche, détails, dates de clôture et résumé quotidien, sans compte.
<strong>Pro : 85 $ CA par mois</strong>, facturé chaque mois en dollars canadiens, renouvelé jusqu'à l'annulation.
Pro ajoute la liste de suivi, la grille « soumissionner ou non » et l'analyse des documents d'appel d'offres.
Pour annuler, écrivez à <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>. Utilisez le même courriel pour le paiement et pour la connexion Google.</p>
</section>
"""
    return page("workspaceAlberta pricing — Free and Pro", body, current="/pricing",
                description="workspaceAlberta Free and Pro plans. Pro is C$85/month, billed monthly in CAD.")


TRY_SCRIPT = """
<script>
(function () {
  var form = document.getElementById('search-form');
  var out = document.getElementById('results');
  var status = document.getElementById('status');
  var button = form.querySelector('button[type="submit"]');
  function el(tag, text, cls) { var e = document.createElement(tag); if (text) { e.textContent = text; } if (cls) { e.className = cls; } return e; }
  var params = new URLSearchParams(window.location.search);
  if (params.get('q')) { form.keywords.value = params.get('q'); }
  if (params.get('source')) { form.source.value = params.get('source'); }
  var running = null, lastKey = '';
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var keywords = form.keywords.value.trim();
    var key = keywords + '|' + form.source.value;
    if (running && key === lastKey) { return; }
    if (running) { running.abort(); }
    lastKey = key;
    try { history.replaceState(null, '', '/try?q=' + encodeURIComponent(keywords) + '&source=' + form.source.value); } catch (e) {}
    if (keywords.length > 200) { status.textContent = 'Please use 200 characters or fewer.'; return; }
    button.textContent = 'Searching…';
    status.textContent = 'Searching CanadaBuys and Alberta Purchasing Connection. This can take up to 20 seconds.';
    out.textContent = '';
    running = window.AbortController ? new AbortController() : null;
    fetch('/try/search', { method: 'POST', signal: running ? running.signal : undefined, headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ keywords: keywords, source: form.source.value, limit: 20 }) })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        if (!res.ok) { status.textContent = (res.data && res.data.message) || 'Search did not work. Please try again.'; return; }
        var items = res.data.opportunities || [];
        status.textContent = items.length ? res.data.summary : 'No open tenders matched. Try a shorter or more general word.';
        items.forEach(function (o) {
          var card = el('article', '', 'card result');
          card.appendChild(el('h3', o.title || 'Untitled tender'));
          card.appendChild(el('p', (o.buyer || 'Buyer not stated') + ' · ' + o.source, 'meta'));
          var closes = (o.closing_text || '').split(';')[0].replace(/ \(UTC[^)]*\)/, '');
          card.appendChild(el('p', 'Closes: ' + (closes || 'Not stated in the posting')));
          card.appendChild(el('p', 'Reference: ' + o.reference, 'meta'));
          if (o.url) { var a = el('a', 'Open the official posting'); a.href = o.url; a.rel = 'noopener'; a.target = '_blank'; card.appendChild(a); }
          out.appendChild(card);
        });
        (res.data.warnings || []).forEach(function (w) { out.appendChild(el('p', w, 'muted')); });
      })
      .catch(function (e) { if (e && e.name === 'AbortError') { return 'aborted'; } status.textContent = 'Search did not work. Check your connection and try again.'; })
      .then(function (r) { if (r === 'aborted') { return; } running = null; button.textContent = 'Search tenders'; });
  });
  if (form.keywords.value) { form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit')); }
})();
</script>
"""


def try_page() -> str:
    body = """
<h1>Try a search</h1>
<p class="lead">Search open government tenders now. No account needed. Results are in English; English search words work best.</p>
<form id="search-form" class="search">
<label>What do you sell or build?
<input name="keywords" type="search" maxlength="200" placeholder="for example: concrete, cleaning, IT support" autocomplete="off" required></label>
<label>Where?
<select name="source"><option value="all">Federal and Alberta</option><option value="alberta">Alberta only</option><option value="federal">Federal only (CanadaBuys)</option></select></label>
<button class="btn primary" type="submit">Search tenders</button>
</form>
<p id="status" role="status" aria-live="polite" class="muted"></p>
<div id="results"></div>
<p class="muted">Results match your words in tender titles and descriptions, so some may be off-topic. Times are Alberta time.</p>
<p class="notice">Like what you see? <a href="/#connect">Add workspaceAlberta to your AI app</a> to ask follow-up questions, get details and rank tenders for your business.</p>
"""
    return page("Try a tender search — workspaceAlberta", body, current="/try", script=TRY_SCRIPT)


def message_page(title: str, heading: str, message: str, *, status_hint: str = "") -> str:
    """A plain, branded page for browser-visible errors and dead ends."""
    hint = f'<p class="muted">{escape(status_hint)}</p>' if status_hint else ""
    body = f"""
<h1>{escape(heading)}</h1>
<p class="lead">{escape(message)}</p>
{hint}
<div class="actions"><a class="btn primary" href="/">Go to the home page</a><a class="btn secondary" href="/support">Get help</a></div>
"""
    return page(title, body)


def me_page() -> str:
    body = """
<h1>Account status</h1>
<p class="lead">You do not need to sign in on this website.</p>
<p>Sign-in happens inside your AI app. The first time you use a Pro feature there, the app opens a Google sign-in window.
After that, the app shows whether your Pro subscription is active.</p>
<div class="actions"><a class="btn primary" href="/#connect">Add it to my AI app</a><a class="btn secondary" href="/pricing">See Pro pricing</a></div>
<p class="muted">Developers: send <code>GET /me</code> with an <code>Authorization: Bearer</code> header to check a token.</p>
"""
    return page("workspaceAlberta account status", body)
