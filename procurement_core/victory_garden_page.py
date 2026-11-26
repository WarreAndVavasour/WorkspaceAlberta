"""The Victory Garden public page (/victory-garden).

Uses Warre & Vavasour's Prairie-at-Dusk editorial system (linking the untouched
``/assets/blog.css`` and ``/assets/brand/fonts.css``) paired with four verified
public-domain WWII archival museum plates and a live interactive URL analyzer
backed by ``POST /victory-garden``. All dynamic results render strictly via
``textContent`` (zero innerHTML / XSS).
"""

from __future__ import annotations

import json
from html import escape

from procurement_core.discovery import CLAUDE_DIRECTORY_URL, COMPANY_URL, PUBLIC_ORIGIN, SUPPORT_EMAIL, build_site_jsonld

VICTORY_GARDEN_ASSETS: dict[str, str] = {
    "victory-garden-canada.webp": "image/webp",
    "rosemont-rubber-drive-1942.webp": "image/webp",
    "scrap-metal-magnet-1942.webp": "image/webp",
    "geco-canada-war-factory.webp": "image/webp",
}

_PAGE_STYLE = """
.vg-main { max-width: 80rem; margin: 0 auto; padding: 0 var(--gut) 96px; }
.vg-hero {
  padding: clamp(44px, 7vw, 88px) 0 clamp(44px, 6vw, 72px);
  display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.9fr);
  gap: clamp(32px, 5vw, 72px); align-items: center;
}
@media (max-width: 880px) { .vg-hero { grid-template-columns: 1fr; } }
.vg-hero h1 { font-size: clamp(44px, 6vw, 78px); line-height: 1.04; margin: 0 0 24px; }
.vg-lead { font: 300 clamp(19px, 2.1vw, 23px)/1.5 var(--serif); color: var(--ink); max-width: 38rem; margin: 0 0 18px; }
.vg-sub { font-size: 16px; line-height: 1.72; color: var(--ink-2); max-width: 38rem; margin: 0 0 26px; }
.vg-plate {
  margin: 0; padding: 13px 13px 18px; background: #e8dcc1; color: #59472d;
  box-shadow: 0 22px 60px rgba(0, 0, 0, 0.55); transform: rotate(1.4deg);
}
.vg-plate.tilt-left { transform: rotate(-1.3deg); }
.vg-plate.flat { transform: rotate(0.4deg); }
.vg-plate img { display: block; width: 100%; height: auto; filter: contrast(1.03); }
.vg-plate figcaption {
  margin-top: 12px; font: 400 9.5px/1.55 var(--mono);
  text-transform: uppercase; letter-spacing: 0.065em;
}
.vg-rule { border: 0; border-top: 1px solid var(--line); margin: 0; }
.vg-section { padding: clamp(44px, 6vw, 72px) 0; }
.vg-kicker {
  margin: 0 0 14px; font: 400 11px/1.5 var(--mono);
  letter-spacing: 0.15em; text-transform: uppercase; color: var(--gold-2);
}
.vg-kicker span { margin-right: 14px; opacity: 0.6; }
.vg-section h2 {
  font: 300 clamp(28px, 3.6vw, 46px)/1.14 var(--serif);
  letter-spacing: -0.025em; margin: 0 0 20px; max-width: 48rem; color: var(--ink);
}
.vg-section h2 em { font-style: italic; font-weight: 300; color: var(--gold-2); }
.vg-essay {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 28px 52px;
  font-size: 16.5px; line-height: 1.75; color: var(--ink-2);
}
@media (max-width: 820px) { .vg-essay { grid-template-columns: 1fr; } }
.vg-essay p { margin: 0 0 18px; }
.vg-essay strong { color: var(--ink); font-weight: 500; }
.vg-sprint-box {
  border-top: 1px solid var(--gold); border-bottom: 1px solid var(--line);
  background: rgba(243, 237, 225, 0.035); padding: 26px 28px; margin-top: 28px;
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px;
}
@media (max-width: 820px) { .vg-sprint-box { grid-template-columns: 1fr; } }
.vg-sprint-stat strong {
  display: block; font: 300 30px/1.15 var(--serif); color: var(--gold-2); margin-bottom: 6px;
}
.vg-sprint-stat span { display: block; font-size: 14px; line-height: 1.6; color: var(--ink-2); }

/* Archival Museum Triptych */
.vg-gallery {
  display: grid; grid-template-columns: 1.15fr 0.95fr 0.9fr; gap: clamp(22px, 3vw, 40px);
  align-items: start; margin-top: 32px;
}
@media (max-width: 900px) { .vg-gallery { grid-template-columns: 1fr; max-width: 34rem; } }

/* Live Interactive Tool */
.vg-tool {
  border: 1px solid var(--line); border-top: 2px solid var(--gold);
  background: rgba(243, 237, 225, 0.035); padding: clamp(22px, 4vw, 38px);
}
.vg-form { display: grid; gap: 16px; max-width: 52rem; }
.vg-form-row { display: grid; grid-template-columns: 1.4fr 0.6fr; gap: 14px; }
@media (max-width: 720px) { .vg-form-row { grid-template-columns: 1fr; } }
.vg-form label { display: grid; gap: 7px; font: 400 12px/1.4 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--gold-2); }
.vg-form input, .vg-form select {
  font: 400 16px/1.4 var(--sans); min-height: 48px; padding: 11px 14px;
  border: 1px solid rgba(243, 237, 225, 0.28); border-radius: 2px;
  background: rgba(0, 0, 0, 0.42); color: var(--ink); width: 100%;
}
.vg-form option { background: #161310; color: var(--ink); }
.vg-actions { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 6px; }
.vg-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 46px; padding: 0 22px; border-radius: 2px; cursor: pointer;
  font: 500 14px/1 var(--sans); text-decoration: none; border: 1px solid var(--gold);
}
.vg-btn.primary { background: var(--gold); color: #161109; }
.vg-btn.primary:hover { background: var(--gold-2); border-color: var(--gold-2); }
.vg-btn.secondary { background: transparent; color: var(--ink); border-color: rgba(243, 237, 225, 0.28); }
.vg-btn.secondary:hover { border-color: var(--gold-2); color: var(--gold-2); }
.vg-status { margin: 18px 0 0; font-size: 14.5px; color: var(--gold-2); min-height: 1.4em; }
.vg-results { margin-top: 24px; display: grid; gap: 24px; }
.vg-block { border-top: 1px solid var(--line); padding-top: 20px; }
.vg-block h3 { font: 300 24px/1.2 var(--serif); margin: 0 0 12px; color: var(--ink); }
.vg-meta-line { font: 400 12px/1.6 var(--mono); color: var(--gold-2); margin: 4px 0 10px; }
.vg-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr)); gap: 16px; }
.vg-card {
  border: 1px solid var(--line); background: rgba(0, 0, 0, 0.26);
  padding: 16px 18px;
}
.vg-card h4 { font: 500 16px/1.35 var(--sans); margin: 0 0 6px; color: var(--ink); }
.vg-card p { font-size: 14px; line-height: 1.55; color: var(--ink-2); margin: 4px 0; }
.vg-card a { color: var(--gold-2); font-size: 13.5px; display: inline-block; margin-top: 8px; }
.vg-badge {
  display: inline-block; font: 400 10.5px/1.2 var(--mono); text-transform: uppercase;
  letter-spacing: 0.08em; padding: 3px 7px; border: 1px solid var(--gold); color: var(--gold-2);
  margin: 0 6px 8px 0;
}
.vg-notice {
  border-left: 2px solid var(--gold); background: rgba(243, 237, 225, 0.035);
  padding: 14px 18px; font-size: 14px; color: var(--ink-2); margin-top: 28px;
}
.vg-notice strong { color: var(--ink); font-weight: 500; }
"""

_PAGE_SCRIPT = """
<script>
(function () {
  var form = document.getElementById('vg-form');
  var statusEl = document.getElementById('vg-status');
  var out = document.getElementById('vg-results');
  var btn = form.querySelector('button[type="submit"]');

  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text) { e.textContent = text; }
    if (cls) { e.className = cls; }
    return e;
  }

  function renderOppList(title, items, showPivotMeta) {
    var block = el('div', '', 'vg-block');
    block.appendChild(el('h3', title + ' (' + items.length + ')'));
    if (!items.length) {
      block.appendChild(el('p', 'No open matches returned for this slice. Try adding a short note about your machines or trades.', 'vg-sub'));
      return block;
    }
    var grid = el('div', '', 'vg-cards');
    items.forEach(function (o) {
      var card = el('article', '', 'vg-card');
      if (showPivotMeta) {
        if (o.pivot_feasibility) { card.appendChild(el('span', o.pivot_feasibility.replace(/_/g, ' '), 'vg-badge')); }
        if (o.sovereign_lane) { card.appendChild(el('span', o.sovereign_lane.replace(/_/g, ' '), 'vg-badge')); }
      }
      card.appendChild(el('h4', o.title || 'Untitled notice'));
      var meta = (o.buyer || 'Public buyer') + ' · ' + (o.source || '') + (o.reference ? ' · ' + o.reference : '');
      card.appendChild(el('p', meta, 'vg-meta-line'));
      var closes = String(o.closing_text || o.closes_at || 'See official posting').split(';')[0];
      card.appendChild(el('p', 'Closes: ' + closes));
      if (showPivotMeta && o.bridge_type) {
        card.appendChild(el('p', 'Bridge to verify: ' + o.bridge_type.replace(/_/g, ' ')));
      }
      if (o.domestic_policies && o.domestic_policies.length) {
        card.appendChild(el('p', 'Domestic signal: ' + o.domestic_policies.join(', ')));
      }
      if (o.url) {
        var a = el('a', 'Open official posting →');
        a.href = o.url;
        a.target = '_blank';
        a.rel = 'noopener';
        card.appendChild(a);
      }
      grid.appendChild(card);
    });
    block.appendChild(grid);
    return block;
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var website = form.website_url.value.trim();
    var desc = form.description.value.trim();
    if (!website && !desc) {
      statusEl.textContent = 'Enter a business website URL or a brief description of your shop and equipment.';
      return;
    }
    btn.disabled = true;
    btn.textContent = 'Analyzing shop & live tenders…';
    statusEl.textContent = 'Reading website capabilities, running the Mobilization Crosswalk, and checking live CanadaBuys + Alberta APC tenders (10–25 seconds)…';
    out.textContent = '';

    fetch('/victory-garden', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ website_url: website, description: desc, source: form.source.value, limit: 6 })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          statusEl.textContent = (res.data && (res.data.detail || res.data.message)) || 'Could not complete audit. Check the website URL or add a short shop description.';
          return;
        }
        var d = res.data || {};
        var shop = d.shop || {};
        statusEl.textContent = 'Brief ready for ' + (shop.company_name || 'your shop') + ' — ' + (d.core_count || 0) + ' core matches and ' + (d.pivot_count || 0) + ' adjacent Victory Garden pivots.';

        var assetBlock = el('div', '', 'vg-block');
        assetBlock.appendChild(el('h3', 'Shop Asset & Tooling Card — ' + (shop.company_name || 'Business')));
        assetBlock.appendChild(el('p', 'Location: ' + (shop.location || 'Canada') + (shop.pages_fetched && shop.pages_fetched.length ? ' · Pages read: ' + shop.pages_fetched.length : ''), 'vg-meta-line'));
        if (shop.detected_processes && shop.detected_processes.length) {
          assetBlock.appendChild(el('p', 'Detected processes & equipment: ' + shop.detected_processes.join(', ')));
        }
        assetBlock.appendChild(el('p', 'Stated certifications on site: ' + (shop.stated_certs && shop.stated_certs.length ? shop.stated_certs.join(', ') : 'None explicitly listed — verify CWB, COR, ISO 9001, CGP, or NCAGE before bidding.')));
        out.appendChild(assetBlock);

        if (d.pivot_lanes && d.pivot_lanes.length) {
          var lanesBlock = el('div', '', 'vg-block');
          lanesBlock.appendChild(el('h3', 'Recommended Victory Garden Pivot Lanes'));
          var lgrid = el('div', '', 'vg-cards');
          d.pivot_lanes.forEach(function (cl) {
            var card = el('article', '', 'vg-card');
            card.appendChild(el('span', (cl.typical_role || '').replace(/_/g, ' '), 'vg-badge'));
            card.appendChild(el('span', (cl.sovereign_lane || '').replace(/_/g, ' '), 'vg-badge'));
            card.appendChild(el('h4', cl.title || 'Pivot lane'));
            card.appendChild(el('p', cl.why_canada_needs_it || ''));
            card.appendChild(el('p', 'Retooling: ' + (cl.retooling_effort || '')));
            if (cl.common_gates && cl.common_gates.length) {
              card.appendChild(el('p', 'Gates to verify: ' + cl.common_gates.join(' · ')));
            }
            lgrid.appendChild(card);
          });
          lanesBlock.appendChild(lgrid);
          out.appendChild(lanesBlock);
        }

        out.appendChild(renderOppList('Lane 1 — Core Fit (Bid Today)', d.core_opportunities || [], false));
        out.appendChild(renderOppList('Lane 2 — Victory Garden Pivot Tenders', d.pivot_opportunities || [], true));

        if (d.support_programs && d.support_programs.length) {
          var progBlock = el('div', '', 'vg-block');
          progBlock.appendChild(el('h3', 'Lane 3 — Canadian Retooling & Industrial Support Programs'));
          var pgrid = el('div', '', 'vg-cards');
          d.support_programs.forEach(function (pr) {
            var card = el('article', '', 'vg-card');
            card.appendChild(el('h4', pr.name || pr.title || 'Support program'));
            if (pr.agency || pr.sponsor) { card.appendChild(el('p', pr.agency || pr.sponsor, 'vg-meta-line')); }
            if (pr.summary || pr.description) { card.appendChild(el('p', String(pr.summary || pr.description).slice(0, 220))); }
            if (pr.url) {
              var a = el('a', 'Program details →');
              a.href = pr.url; a.target = '_blank'; a.rel = 'noopener';
              card.appendChild(a);
            }
            pgrid.appendChild(card);
          });
          progBlock.appendChild(pgrid);
          out.appendChild(progBlock);
        }

        if (d.warnings && d.warnings.length) {
          var wBlock = el('div', '', 'vg-notice');
          wBlock.appendChild(el('strong', 'Notes: '));
          wBlock.appendChild(document.createTextNode(d.warnings.join(' ')));
          out.appendChild(wBlock);
        }
      })
      .catch(function () {
        statusEl.textContent = 'Request failed. Check your connection and try again.';
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = 'Run Victory Garden Audit';
      });
  });
})();
</script>
"""


def render_victory_garden_page(mcp_url: str, base: str = PUBLIC_ORIGIN) -> str:
    """Render the museum-styled editorial + interactive ``/victory-garden`` page."""
    vg_jsonld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "Victory Garden — Canadian Industrial Pivot & Mobilization Skill",
            "url": f"{base}/victory-garden",
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web, Claude, ChatGPT, Cursor, Claude Code (MCP)",
            "description": (
                "Paste any Canadian small business website to find both live core government contracts "
                "and adjacent defence, infrastructure, and Arctic mobilization tenders your existing "
                "tooling and crew can pivot into."
            ),
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "CAD"},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    safe_mcp = escape(mcp_url)
    return f"""<!doctype html>
<html lang="en-CA">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Victory Garden — Retool Existing Canadian Shops for Public &amp; Sovereign Demand · workspaceAlberta</title>
  <meta name="description" content="Paste any Canadian small business website to see what Canada is buying right now — and what defence, infrastructure, and Arctic contracts your existing tooling can pivot into during the 18-month industrial sprint.">
  <meta name="theme-color" content="#0a0807">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" href="/icon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="stylesheet" href="/assets/brand/fonts.css">
  <link rel="stylesheet" href="/assets/blog.css">
  <script type="application/ld+json">{build_site_jsonld(base)}</script>
  <script type="application/ld+json">{vg_jsonld}</script>
  <style>{_PAGE_STYLE}</style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <div class="grain" aria-hidden="true"></div>
  <header class="site-header">
    <a class="wordmark" href="/">warre <span class="amp">&amp;</span> vavasour</a>
    <nav aria-label="Main navigation">
      <a href="/">workspaceAlberta</a>
      <a href="/victory-garden" aria-current="page">Victory Garden</a>
      <a href="/tenders">By trade</a>
      <a href="/features">Features</a>
      <a href="/pricing">Pricing</a>
      <a href="/blog">Journal</a>
    </nav>
    <span class="locale">Southern Alberta</span>
  </header>

  <main id="main" class="vg-main">
    <section class="vg-hero">
      <div>
        <p class="eyebrow">Victory Garden · Canadian Industrial Mobilization Skill</p>
        <h1>Existing tooling.<br><em>Urgent demand.</em></h1>
        <p class="vg-lead">In 1941, ordinary Canadians did not wait for a mega-factory to be built from scratch. They turned vacant lots into Victory Gardens, stripped scrap iron and rubber for the foundries, and retooled peacetime shops into the fourth-largest Allied industrial arsenal on earth.</p>
        <p class="vg-sub">Paste any Canadian small business website below. Our TypeSafe Jev judgment pipeline reads what your shop already builds, finds live federal and Alberta contracts you can bid today, and maps what your existing machines, crews, and floor space can pivot into next.</p>
        <div class="vg-actions">
          <a class="vg-btn primary" href="#audit">Audit a shop website (Free)</a>
          <a class="vg-btn secondary" href="{CLAUDE_DIRECTORY_URL}" rel="noopener">Run inside Claude</a>
        </div>
      </div>

      <figure class="vg-plate">
        <img src="/assets/victory-garden/victory-garden-canada.webp" width="960" height="777" decoding="async"
             alt="Staked Canadian Victory Garden plots laid out in front of a wartime industrial plant, Ontario, c. 1943.">
        <figcaption>Victory Gardens beside an Ontario wartime plant · Archives of Ontario (I0040027) · Public Domain</figcaption>
      </figure>
    </section>

    <hr class="vg-rule">

    <section class="vg-section" id="why">
      <p class="vg-kicker"><span>01</span>Why Victory Garden · The 18-Month Sprint</p>
      <h2>Europe is settling into a long industrial war. <em>Canada’s shop floors are the reserve.</em></h2>
      <div class="vg-essay">
        <div>
          <p><strong>What lies ahead in Europe is not a short crisis.</strong> Modern high-intensity conflict has turned back into an industrial war of attrition — measured in artillery barrels, air-defence spares, drone airframes, power-grid transformers, ruggedized logistics, and cold-weather sustainment. Allied stockpiles were sized for thirty-day peacekeeping, not multi-year continental deterrence.</p>
          <p><strong>That puts Canada inside an urgent 18-month sprint.</strong> Defence procurement, Arctic and northern infrastructure, port and bridge hardening, energy resilience, and Buy Canadian domestic-preference policies are moving from press releases onto <em>CanadaBuys</em> and provincial portals right now. You cannot build ten new crown mega-plants in eighteen months — you mobilize the 15-to-80-person machine shops, CWB welding bays, sheet-metal fabricators, modular builders, composite shops, electrical crews, and haulers that already have concrete floors, cranes, and skilled people.</p>
        </div>
        <div>
          <p><strong>Why we call it Victory Garden.</strong> Victory Gardens, neighbourhood rubber brigades, and scrap-metal salvage drives worked because they converted distributed, everyday capacity into sovereign resilience without waiting for permission from a committee. An oilfield CNC shop in Nisku already owns the 5-axis mills that can machine defence and marine brackets. A commercial tarp shop already owns the walking-foot machines that can sew Arctic field covers. A custom trailer shop already knows how to weld mobile generator and command skids.</p>
          <p><strong>The bottleneck is translation, not capability.</strong> Most owners never see adjacent public contracts because procurement portals speak UNSPSC codes and federal jargon instead of shop-floor tooling. Victory Garden bridges that gap in thirty seconds — honestly separating what you can bid today, what you can pivot into with light retooling or Tier-2 prime subcontracting, and which Canadian certifications or grants bridge the rest.</p>
        </div>
      </div>

      <div class="vg-sprint-box">
        <div class="vg-sprint-stat">
          <strong>18 Months</strong>
          <span>The window to qualify Canadian small and mid-sized shops into sovereign defence, Arctic, and critical-infrastructure supply chains before backlogs lock in.</span>
        </div>
        <div class="vg-sprint-stat">
          <strong>2 Live Lanes</strong>
          <span>Core Fit (what you already sell) + Victory Garden Pivots (adjacent federal &amp; Alberta tenders your existing equipment can redeploy to, judged by TypeSafe Jev).</span>
        </div>
        <div class="vg-sprint-stat">
          <strong>C$0 to Run</strong>
          <span>Free for every Canadian shop owner in the browser or over MCP — paired with industrial retooling grants (PrairiesCan, BDC, ISED) and clear certification gates.</span>
        </div>
      </div>
    </section>

    <hr class="vg-rule">

    <section class="vg-section" aria-label="Archival Canadian Home Front Photography">
      <p class="vg-kicker"><span>02</span>From the Archive · 1941–1945</p>
      <h2>Distributed capacity won the last mobilization.</h2>
      <div class="vg-gallery">
        <figure class="vg-plate tilt-left">
          <img src="/assets/victory-garden/rosemont-rubber-drive-1942.webp" width="960" height="395" loading="lazy" decoding="async"
               alt="Young Montrealers in Rosemont gathered around a stack of reclaimed bicycle and automobile tires during the 1942 rubber salvage drive.">
          <figcaption>Rosemont Youth Rubber Salvage Brigade · Montreal, 1942 · BAnQ · Public Domain</figcaption>
        </figure>

        <figure class="vg-plate flat">
          <img src="/assets/victory-garden/scrap-metal-magnet-1942.webp" width="960" height="984" loading="lazy" decoding="async"
               alt="An industrial electro-magnet crane lifting salvaged scrap metal into a rail gondola during the May 1942 Victory Program salvage drive.">
          <figcaption>Victory Program Scrap-Metal Electro-Magnet · May 1942 · Library of Congress (8c34729v)</figcaption>
        </figure>

        <figure class="vg-plate">
          <img src="/assets/victory-garden/geco-canada-war-factory.webp" width="960" height="1219" loading="lazy" decoding="async"
               alt="A Canadian woman operating a precision press at General Engineering Company (Canada) Ltd in Scarborough, Ontario.">
          <figcaption>Precision Press Operator · General Engineering Co. (Canada), Scarborough, ON · Archives of Ontario (I0058206)</figcaption>
        </figure>
      </div>
    </section>

    <hr class="vg-rule">

    <section class="vg-section" id="audit">
      <p class="vg-kicker"><span>03</span>Live Mobilization Audit · Free, No Account</p>
      <h2>Paste a shop website. See what <em>Canada is buying</em>.</h2>

      <div class="vg-tool">
        <form id="vg-form" class="vg-form">
          <div class="vg-form-row">
            <label>Small business website URL
              <input name="website_url" type="url" placeholder="https://yourshop.ca" autocomplete="url">
            </label>
            <label>Catalogues
              <select name="source">
                <option value="all">Federal (CanadaBuys) + Alberta APC</option>
                <option value="federal">Federal only (CanadaBuys)</option>
                <option value="alberta">Alberta only (APC)</option>
              </select>
            </label>
          </div>
          <label>Optional: Idle machines, shop capabilities, or city not on the site
            <input name="description" type="text" maxlength="400" placeholder="e.g. 5-axis CNC mill, 2 CWB welding bays, 10-ton crane, Red Deer Alberta">
          </label>
          <div class="vg-actions">
            <button type="submit" class="vg-btn primary">Run Victory Garden Audit</button>
            <a class="vg-btn secondary" href="/try">Standard keyword search</a>
            <a class="vg-btn secondary" href="/features">See all 19 AI tools</a>
          </div>
        </form>

        <p id="vg-status" class="vg-status" role="status" aria-live="polite"></p>
        <div id="vg-results" class="vg-results"></div>

        <div class="vg-notice">
          <strong>Honest boundary &amp; MCP access:</strong> Victory Garden extracts capabilities from public web copy and matches open CanadaBuys &amp; Alberta APC tenders. It never invents certifications, submits bids, or guarantees awards. Run the exact same tool inside Claude, ChatGPT, or Cursor via MCP: <code>{safe_mcp}</code> (tool: <code>victory_garden_brief</code>).
        </div>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div>
      <a class="footer-brand" href="{COMPANY_URL}">warre <span class="amp">&amp;</span> vavasour</a>
      <p>Building practical Canadian industrial AI in Southern Alberta. Contact: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>
    </div>
    <nav aria-label="Footer">
      <a href="/">Home</a>
      <a href="/tenders">By trade</a>
      <a href="/features">Features</a>
      <a href="/pricing">Pricing</a>
      <a href="/privacy">Privacy</a>
      <a href="/support">Support</a>
    </nav>
  </footer>
  {_PAGE_SCRIPT}
</body>
</html>
"""
