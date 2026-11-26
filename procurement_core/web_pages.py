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

_NAV = (("/", "Home"), ("/try", "Try a search"), ("/features", "Features"), ("/pricing", "Pricing"), ("/support", "Help"))


def page(
    title: str,
    body: str,
    *,
    current: str = "",
    script: str = "",
    description: str = "",
    extra_jsonld: str = "",
) -> str:
    """Wrap trusted body markup in the shared shell (header nav + footer)."""
    from procurement_core.discovery import build_site_jsonld

    current_attr = ' aria-current="page"'
    nav = "".join(
        f'<a href="{href}"{current_attr if href == current else ""}>{label}</a>'
        for href, label in _NAV
    )
    meta = f'<meta name="description" content="{escape(description)}">' if description else ""
    jsonld_tags = f'<script type="application/ld+json">{build_site_jsonld()}</script>'
    if extra_jsonld:
        jsonld_tags += f'<script type="application/ld+json">{extra_jsonld}</script>'
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title>{meta}{ICON_LINKS}{jsonld_tags}<style>{STYLE}</style></head><body>"
        f'<header class="top"><a class="brand" href="/">workspaceAlberta</a><nav aria-label="Main">{nav}</nav></header>'
        f"<main>{body}</main>"
        '<footer><nav aria-label="Footer">'
        '<a href="/victory-garden">Victory Garden</a><a href="/tenders">By trade</a><a href="/features">Features</a><a href="/pricing">Pricing &amp; terms</a><a href="/privacy">Privacy</a><a href="/support">Help</a>'
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
  <a class="btn secondary" href="/features">See all tools &amp; uses</a>
  <a class="btn secondary" href="#connect">Add it to my AI app</a>
  <a class="btn secondary" href="/pricing">See pricing</a>
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

<h2>Free, Bid Packs, and Pro</h2>
<p><strong>Free, no account:</strong> search, tender details, closing deadlines, daily briefs, industrial support programs, and matching against a business description.</p>
<p><strong>Free sign-in (C$0):</strong> saved business profile, <strong>5-tender watchlist</strong>, <strong>bid/no-bid scorecards</strong>, and <strong>2 free tender Requirements Boards</strong> (<code>classify_tender</code> / bid-room trial). Signing in never starts a paid subscription.</p>
<p><strong>Bid Packs (C$19 / C$49) or Pro ({PRO_PRICE}):</strong> pay per tender with non-expiring credits, or go unlimited with Pro (unlimited Requirements Boards, E2B bid rooms, Cohere Command A+ reviews, unlimited watchlist, and self-serve billing).</p>
<p><a class="btn secondary" href="/pricing">Compare Free, Bid Packs, and Pro</a></p>

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
<p class="lead">Search is free. Sign in free for watchlists, scorecards, and 2 free tender Requirements Boards. Pay per tender or go unlimited with Pro.</p>
<div class="plans">
<div class="card"><h3>Free Account</h3><p class="price">C$0</p>
<p class="muted">Search works with no account. Free sign-in unlocks saved tools.</p>
<ul><li>Unified CanadaBuys + Alberta APC search, details, deadlines &amp; daily brief</li>
<li>Saved business profile</li>
<li><strong>Watchlist</strong> (up to 5 tenders)</li>
<li><strong>Bid/no-bid scorecards</strong> on demand</li>
<li><strong>2 free tender reviews</strong> (<code>classify_tender</code> Requirements Board or Bid Room)</li></ul>
<a class="btn secondary" href="/try">Try a search</a></div>

<div class="card"><h3>Bid Packs</h3><p class="price">C$19 <small style="font-size:0.95rem;font-weight:400;">/ 1 tender</small></p>
<p class="muted">Or C$49 for 3 tenders. One-time purchase — credits never expire.</p>
<ul><li>Ideal for shops bidding 4–8 public tenders a year</li>
<li>Interactive <strong>Requirements Board</strong> (<code>classify_tender</code>) with lead-time schedule &amp; evidence quotes</li>
<li><strong>E2B Bid Room</strong> attachment analysis (Cohere Parse + Command A+)</li>
<li>Full Cohere Command A+ tender explainer</li>
<li>No recurring subscription</li></ul>
<div class="actions" style="margin:0.6rem 0 0;">
<a class="btn secondary" href="/checkout?plan=pack_1" rel="noopener">Buy 1 credit — C$19</a>
<a class="btn secondary" href="/checkout?plan=pack_3" rel="noopener">Buy 3 credits — C$49</a>
</div></div>

<div class="card"><h3>Pro Unlimited</h3><p class="price">{PRO_PRICE}</p>
<p class="muted">Billed monthly in CAD. Cancel any time in one click.</p>
<ul><li>Everything in Free</li>
<li><strong>Historical Contract Awards &amp; Incumbent Radar</strong> (<code>get_buyer_award_history</code>)</li>
<li><strong>Unlimited watchlist</strong> tracking</li>
<li><strong>Unlimited Requirements Boards</strong> from tender PDFs</li>
<li><strong>Unlimited E2B Bid Rooms</strong> &amp; Cohere Command A+ reviews</li>
<li>Self-serve billing portal &amp; priority Canadian support</li></ul>
<a class="btn primary" href="/checkout?plan=pro" rel="noopener">Start Pro — {PRO_PRICE}</a>
<p class="muted" style="font-size:0.85rem;margin:0.5rem 0 0;">Direct Stripe link: <a href="{STRIPE_SUBSCRIBE_URL}" rel="noopener">buy.stripe.com</a></p></div>
</div>

<h2>How it works</h2>
<ol class="steps">
<li>Connect workspaceAlberta in Claude, ChatGPT, Cursor, or Claude Code and sign in when asked. Every new account starts with <strong>2 free tender reviews</strong>, a 5-tender watchlist, and bid/no-bid scorecards at C$0.</li>
<li>When you are ready for more tenders, pick a one-time <strong>Bid Pack</strong> (C$19 or C$49) or <strong>Pro Unlimited</strong> ({PRO_PRICE}). Checkout runs on Stripe — we never see your card number.</li>
<li>Links opened from your AI app automatically attach your account ID and email, so Pro or Bid Pack credits unlock immediately when you return to chat.</li>
</ol>

<h2 id="terms">Subscription &amp; billing terms</h2>
<ul>
<li><strong>Seller:</strong> Warre &amp; Vavasour Ltd, Alberta, Canada.</li>
<li><strong>Pricing:</strong> Pro is {PRO_PRICE} in Canadian dollars; Bid Packs are C$19 (1 credit) or C$49 (3 credits), one-time. Checkout shows the final amount before you pay.</li>
<li><strong>Renewal:</strong> Pro renews every month until you cancel. Bid Pack credits do not renew and do not expire.</li>
<li><strong>Manage or cancel:</strong> open the <a href="/billing/portal">self-serve billing portal</a> any time, or email <a href="mailto:{SUPPORT_EMAIL}?subject=Cancel%20workspaceAlberta%20Pro">{SUPPORT_EMAIL}</a>. Pro stays active through the end of the paid month.</li>
<li><strong>Data:</strong> see the <a href="/privacy">privacy notice</a> for what document-review features send to service providers.</li>
<li><strong>Results:</strong> workspaceAlberta helps you find and review tenders. It does not submit bids and does not guarantee awards. Always check the official posting.</li>
</ul>
<p>Questions before you buy? Email <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>

<section lang="fr" id="fr" aria-labelledby="fr-pricing">
<h2 id="fr-pricing">Tarifs en français</h2>
<p><strong>Gratuit :</strong> recherche, détails, dates de clôture et résumé quotidien sans compte. La connexion gratuite inclut le profil d'entreprise, la liste de suivi (jusqu'à 5 appels d'offres), la grille « soumissionner ou non » et <strong>2 analyses gratuites</strong>.
<strong>Crédits à l'unité :</strong> 19 $ CA (1 appel d'offres) ou 49 $ CA (3 appels d'offres), sans abonnement.
<strong>Pro illimité : 85 $ CA par mois</strong>, facturé en dollars canadiens, résiliable en tout temps via le <a href="/billing/portal">portail de facturation</a> ou par courriel à <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>
</section>
"""
    return page("workspaceAlberta pricing — Free, Bid Packs, and Pro", body, current="/pricing",
                description="workspaceAlberta Free (with 2 free tender reviews), pay-per-tender Bid Packs (C$19/C$49), and Pro Unlimited (C$85/month CAD).")


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
<p>Sign-in happens inside your AI app. The first time you save a profile, watchlist, scorecard, or tender review, the app opens a sign-in window.
Every signed-in account starts with 2 free tender Requirements Boards, a 5-tender watchlist, and bid/no-bid scorecards.</p>
<div class="actions"><a class="btn primary" href="/#connect">Add it to my AI app</a><a class="btn secondary" href="/pricing">See plans &amp; Bid Packs</a><a class="btn secondary" href="/billing/portal">Manage billing</a></div>
<p class="muted">Developers: send <code>GET /me</code> with an <code>Authorization: Bearer</code> header to check your plan and remaining tender credits.</p>
"""
    return page("workspaceAlberta account status", body)


def billing_success_page(plan: str = "pro") -> str:
    plan_key = str(plan or "pro").strip().lower()
    if plan_key == "pack_3":
        headline = "Your 3-tender Bid Pack is ready"
        detail = "We added 3 non-expiring tender credits to your workspaceAlberta account. Return to Claude (or your MCP client) and re-run classify_tender or process_bid_room — no key pasting needed."
    elif plan_key == "pack_1":
        headline = "Your tender credit is ready"
        detail = "We added 1 non-expiring tender credit to your workspaceAlberta account. Return to Claude (or your MCP client) and re-run classify_tender or process_bid_room — no key pasting needed."
    else:
        headline = "WorkspaceAlberta Pro is active"
        detail = "Your unlimited Pro plan is active. Return to Claude (or your MCP client) and re-run your tool — your existing sign-in now has unlimited Requirements Boards, Bid Rooms, Cohere reviews, and watchlists."
    body = f"""
<h1>{escape(headline)}</h1>
<p class="lead">{escape(detail)}</p>
<div class="actions">
  <a class="btn primary" href="/#connect">Back to connection guide</a>
  <a class="btn secondary" href="/billing/portal">Manage billing</a>
</div>
<p class="muted">Need help or paid with a different accounting email? Email <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a> with your receipt and we will link your account right away.</p>
"""
    return page(f"{headline} — workspaceAlberta", body)


def features_page(mcp_url: str) -> str:
    body = f"""
<h1>Tools &amp; practical uses for Canadian bidders</h1>
<p class="lead">Everything workspaceAlberta adds to Claude, ChatGPT, Cursor, or Claude Code — from free daily tender discovery to historical contract awards, Requirements Boards, and isolated bid-room reviews.</p>
<div class="actions">
  <a class="btn primary" href="/#connect">Connect in 2 minutes</a>
  <a class="btn secondary" href="/try">Try a free search</a>
  <a class="btn secondary" href="/pricing">Free, Bid Packs &amp; Pro</a>
</div>

<h2>New: Historical Contract Awards &amp; Incumbent Radar</h2>
<div class="card">
  <h3><code>get_buyer_award_history</code> <span class="muted" style="font-weight:400;font-size:0.9rem;">· Included in 2 free reviews, Bid Packs &amp; Pro</span></h3>
  <p>Before spending an estimator's week on an RFP, check who actually won this buyer's past similar contracts across <strong>CanadaBuys open data</strong> and <strong>Alberta Purchasing Connection</strong>.</p>
  <ul>
    <li><strong>Pass any live tender reference</strong> (e.g. <code>AB-2026-06788</code> or a federal notice) and it automatically resolves the buyer, UNSPSC/GSIN codes, and scope keywords.</li>
    <li><strong>Pricing sanity check:</strong> see disclosed contract award values — minimum, median, and maximum in CAD.</li>
    <li><strong>Incumbent detection:</strong> flags repeat winners who took multiple recent awards from the same buyer.</li>
    <li><strong>Competition density (Alberta APC):</strong> see how many interested suppliers downloaded similar awarded postings.</li>
  </ul>
  <p class="muted" style="margin-bottom:0;"><strong>Try asking Claude:</strong> <em>“Check historical awards for AB-2026-06788 — who won similar work for this buyer, and what were the award values?”</em></p>
</div>

<h2>Turn tender PDFs into action (2 free runs when you sign in)</h2>
<div class="plans">
  <div class="card">
    <h3>Requirements Board (<code>classify_tender</code>)</h3>
    <p>Splits tender PDFs into clauses, classifies every bidder obligation, and generates an interactive HTML Requirements Board with <strong>weeks / days / minutes lead times</strong>, mandatory flags, and page-cited evidence quotes.</p>
    <p class="muted"><strong>Ask:</strong> <em>“Classify tender PW-26-00412 and build my requirements board.”</em></p>
  </div>
  <div class="card">
    <h3>Sandboxed Bid Room (<code>process_bid_room</code>)</h3>
    <p>Opens tender PDFs, DOCX, XLSX, and ZIP attachments inside an isolated E2B sandbox, runs Cohere Parse v5.0 on tables and forms, and returns a structured fit score, risks, missing info, and questions to ask the buyer.</p>
    <p class="muted"><strong>Ask:</strong> <em>“Run a bid room review on this tender against my saved business profile.”</em></p>
  </div>
  <div class="card">
    <h3>Owner Explainer (<code>analyze_contract_with_cohere</code>)</h3>
    <p>Reads the entire tender package (amendments first, enriched with comparable historical awards) with Cohere Command A+ and explains who can bid, how offers are scored, and every mandatory submission item.</p>
    <p class="muted"><strong>Ask:</strong> <em>“Explain this federal tender in plain English — what are the deal-breakers?”</em></p>
  </div>
</div>

<h2>Free habit tools (sign in free — C$0, no credit card)</h2>
<div class="plans">
  <div class="card">
    <h3>Bid/No-Bid Scorecard (<code>bid_no_bid_scorecard</code>)</h3>
    <p>Fast deterministic <strong>GO / CAUTION / LEAN NO-BID</strong> checklist covering profile fit, closing runway, region match, Buy Canadian flags, and a historical-awards teaser — no model wait.</p>
  </div>
  <div class="card">
    <h3>Watchlist (<code>watch_opportunity</code>, <code>list_watchlist</code>)</h3>
    <p>Save up to <strong>5 tenders free</strong> (unlimited on Pro) with your own estimator notes and closing-date countdowns in Alberta time.</p>
  </div>
  <div class="card">
    <h3>Saved Profile (<code>set_business_profile</code>)</h3>
    <p>Describe your shop once — trades, certifications, region, products — so every brief, match, and scorecard ranks against what you actually deliver.</p>
  </div>
</div>

<h2>Public discovery (free, no account required)</h2>
<div class="card">
  <ul>
    <li><strong>Unified Search &amp; Supply-Fit Ranking (<code>search_opportunities</code>, <code>find_matching_opportunities</code>):</strong> searches federal CanadaBuys and Alberta APC together using commodity codes, TypeSafe Jev supply-fit classification, and Buy Canadian flags.</li>
    <li><strong>Morning Bid Brief (<code>daily_bid_brief</code>):</strong> open market counts, best fits for your shop, soonest deadlines, and one concrete next action.</li>
    <li><strong>Closing Deadlines &amp; Full Dossiers (<code>list_deadlines</code>, <code>get_opportunity_details</code>):</strong> exact closing times in Alberta time with direct links back to official postings.</li>
    <li><strong>Industrial &amp; Tariff Support Catalog (<code>match_industrial_support_programs</code>):</strong> read-only guide to federal &amp; prairie industrial programs (including PrairiesCan, BDC, ISED, NRCan), with Ontario-only streams clearly labeled.</li>
  </ul>
</div>

<h2>Connect in 2 minutes</h2>
<p>Paste this address into Claude (<strong>Customize → Connectors</strong>), ChatGPT, Cursor, or Claude Code:</p>
{_url_box(mcp_url)}
<div class="actions">
  <a class="btn primary" href="/pricing">See Free, Bid Packs (C$19) &amp; Pro (C$85/mo)</a>
  <a class="btn secondary" href="/developers">Developer &amp; REST API docs</a>
</div>

<section lang="fr" aria-labelledby="fr-features">
  <h2 id="fr-features">Nouveautés en français</h2>
  <p>workspaceAlberta ajoute l'historique des contrats attribués (<code>get_buyer_award_history</code>) sur AchatsCanada et Alberta Purchasing Connection pour voir les fournisseurs gagnants, les montants médians et les signaux de titulaires sortants avant de soumissionner. La connexion gratuite inclut désormais la liste de suivi (jusqu'à 5 avis), la grille « soumissionner ou non » et <strong>2 analyses gratuites</strong> (tableau des exigences, salle de soumission ou historique d'attribution).</p>
</section>
"""
    return page(
        "Features & new tools — workspaceAlberta",
        body,
        current="/features",
        script=COPY_SCRIPT,
        description="Explore workspaceAlberta's procurement tools: historical contract awards & incumbent radar, interactive Requirements Boards, E2B Bid Rooms, free watchlists, and bid/no-bid scorecards.",
    )


def billing_portal_page(*, error: str = "") -> str:
    err_html = f'<p class="error">{escape(error)}</p>' if error else ""
    body = f"""
<h1>Manage billing &amp; cancellation</h1>
<p class="lead">Update your card, download receipts, or cancel WorkspaceAlberta Pro in one click through Stripe's self-serve portal.</p>
{err_html}
<form method="post" action="/billing/portal" class="search">
  <label>Billing email used at Stripe checkout
    <input name="email" type="email" required autocomplete="email" placeholder="you@yourcompany.ca">
  </label>
  <button class="btn primary" type="submit">Open Stripe Billing Portal</button>
</form>
<p class="muted">Prefer email? Write to <a href="mailto:{SUPPORT_EMAIL}?subject=Manage%20workspaceAlberta%20billing">{SUPPORT_EMAIL}</a> from your billing address and we will handle it promptly.</p>
"""
    return page("Manage billing — workspaceAlberta", body)
