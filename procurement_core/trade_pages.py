"""Live trade-specific public tender & historical-awards index pages.

Exposes clean, crawlable HTML and Markdown pages (``/tenders`` and
``/tenders/{slug}[.md]``) for high-intent Canadian trades and industrial
verticals. Backed by a 30-minute in-memory TTL cache over the existing
CanadaBuys + Alberta APC feeds and local ``awards.db`` (if already warm), so
search engines and AI search agents can index live tender counts, closing dates,
and award medians without triggering slow upstream downloads on page load.
"""

from __future__ import annotations

import asyncio
import json
import time
from html import escape
from typing import Any

from procurement_core.discovery import (
    CLAUDE_DIRECTORY_URL,
    PUBLIC_ORIGIN,
    TRADE_VERTICALS,
    TRADE_VERTICALS_BY_SLUG,
    TradeVertical,
)
from procurement_core.web_pages import COPY_SCRIPT, page as _web_page

TRADE_CACHE_TTL_SECONDS = 30 * 60
TRADE_FETCH_TIMEOUT_SECONDS = 12.0
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def clear_trade_cache() -> None:
    """Reset the in-memory trade page cache (used by tests)."""
    _CACHE.clear()


def _fmt_cad(amount: float | None) -> str:
    if amount is None:
        return "Not disclosed"
    if amount >= 1_000_000:
        return f"C${amount / 1_000_000:,.2f}M"
    return f"C${amount:,.0f}"


def _warm_awards_snapshot(vertical: TradeVertical) -> dict[str, Any]:
    """Read historical awards from local ``awards.db`` only if it is already present on disk."""
    try:
        from procurement_core import awards as awards_mod

        db_path = awards_mod.awards_db_path()
        if not db_path.exists():
            return {"available": False, "count": 0, "summary": {}, "top_suppliers": []}
        rows, _warnings = awards_mod.query_canadabuys_awards(
            keywords=vertical.keywords,
            province=vertical.province,
            limit=25,
        )
        if not rows:
            return {"available": True, "count": 0, "summary": {}, "top_suppliers": []}
        summary = awards_mod.summarize_awards(rows)
        return {
            "available": True,
            "count": len(rows),
            "summary": summary,
            "top_suppliers": summary.get("top_suppliers", [])[:4],
        }
    except Exception:  # noqa: BLE001 - never break a public SEO page
        return {"available": False, "count": 0, "summary": {}, "top_suppliers": []}


async def fetch_trade_snapshot(
    vertical: TradeVertical,
    *,
    search_fn: Any = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch (or return cached) live open tenders + warm historical awards for a trade vertical."""
    now = time.monotonic()
    cached = _CACHE.get(vertical.slug)
    if cached and not force_refresh and (now - cached[0]) < TRADE_CACHE_TTL_SECONDS:
        return cached[1]

    opportunities: list[dict[str, Any]] = []
    warnings: list[str] = []

    if search_fn is not None:
        try:
            _text, structured = await asyncio.wait_for(
                search_fn(
                    "search_opportunities",
                    {
                        "keywords": vertical.keywords,
                        "source": vertical.source,
                        "limit": 12,
                    },
                ),
                timeout=TRADE_FETCH_TIMEOUT_SECONDS,
            )
            if isinstance(structured, dict):
                raw_opps = structured.get("opportunities") or []
                if isinstance(raw_opps, list):
                    opportunities = [o for o in raw_opps if isinstance(o, dict)][:12]
                raw_warn = structured.get("warnings") or []
                if isinstance(raw_warn, list):
                    warnings = [str(w) for w in raw_warn[:3]]
        except Exception:  # noqa: BLE001 - degrade gracefully if upstream is slow/offline
            warnings.append("Live feed refresh is temporarily busy; query the MCP endpoint or /try for real-time results.")

    awards_snap = _warm_awards_snapshot(vertical)
    snapshot = {
        "slug": vertical.slug,
        "count": len(opportunities),
        "opportunities": opportunities,
        "awards": awards_snap,
        "warnings": warnings,
        "fetched_at": int(time.time()),
    }
    _CACHE[vertical.slug] = (now, snapshot)
    return snapshot


def _trade_jsonld(base: str, vertical: TradeVertical, snapshot: dict[str, Any]) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": vertical.title,
        "description": vertical.summary,
        "url": f"{base}/tenders/{vertical.slug}",
        "keywords": ", ".join(vertical.tags),
        "mainEntity": {
            "@type": "Dataset",
            "name": f"Open {vertical.short_label} Government Tenders ({vertical.province or 'Canada'})",
            "description": vertical.summary,
            "creator": {"@type": "Organization", "name": "Warre & Vavasour Ltd"},
            "distribution": [
                {
                    "@type": "DataDownload",
                    "encodingFormat": "text/markdown",
                    "contentUrl": f"{base}/tenders/{vertical.slug}.md",
                },
                {
                    "@type": "DataDownload",
                    "encodingFormat": "application/json",
                    "contentUrl": f"{base}/mcp",
                },
            ],
            "variableMeasured": f"{snapshot.get('count', 0)} open tenders listed",
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def render_trades_index_html(base: str = PUBLIC_ORIGIN) -> str:
    """HTML hub linking to all 8 live trade-specific government contract pages."""
    cards = []
    for v in TRADE_VERTICALS:
        cards.append(
            '<article class="card">'
            f'<h3><a href="/tenders/{v.slug}">{escape(v.short_label)}</a>'
            f' <span class="muted" style="font-size:0.85rem;font-weight:400;">· {escape(v.province or "Canada-wide")}</span></h3>'
            f'<p>{escape(v.summary)}</p>'
            f'<p class="muted" style="margin:0.4rem 0 0;font-size:0.9rem;">'
            f'<a href="/tenders/{v.slug}">View live tenders →</a> · '
            f'<a href="/tenders/{v.slug}.md">Markdown feed (.md)</a></p>'
            "</article>"
        )
    mcp_url = f"{base}/mcp"
    body = f"""
<h1>Canadian Government Contracts by Trade</h1>
<p class="lead">Live federal (CanadaBuys) and Alberta (Alberta Purchasing Connection) tenders organized for trades, contractors, fabricators, and service crews — plus direct AI / MCP access for Claude, ChatGPT, and Cursor.</p>
<div class="actions">
  <a class="btn primary" href="{CLAUDE_DIRECTORY_URL}" rel="noopener">Add to Claude</a>
  <a class="btn secondary" href="/try">Custom live search</a>
  <a class="btn secondary" href="/features">See all 18 AI tools</a>
</div>
<div class="plans">
{"".join(cards)}
</div>
<h2>Query any trade live with AI (MCP)</h2>
<p>Paste this single endpoint into Claude, ChatGPT, Cursor, or Claude Code — free search needs no account:</p>
<div class="urlbox"><code>{escape(mcp_url)}</code><button type="button" class="btn primary" data-copy="{escape(mcp_url)}">Copy address</button></div>
<p class="muted">Machine-readable index for agents: <a href="/tenders.md">/tenders.md</a> · <a href="/llms.txt">/llms.txt</a> · <a href="/.well-known/agent.json">A2A Agent Card</a>.</p>
"""
    return _web_page(
        "Canadian Government Contracts by Trade — workspaceAlberta",
        body,
        current="",
        script=COPY_SCRIPT,
        description="Browse open CanadaBuys and Alberta Purchasing Connection government contracts by trade: welding, electrical, HVAC, concrete, general contracting, janitorial, heavy equipment, and engineering.",
    )


def render_trades_index_md(base: str = PUBLIC_ORIGIN) -> str:
    """Markdown index of all trade tender verticals for LLMs and autonomous agents."""
    lines = [
        "# Canadian Government Contracts by Trade — workspaceAlberta",
        "",
        "Live open tender feeds combining federal **CanadaBuys** and **Alberta Purchasing Connection (APC)** for trades, contractors, fabricators, and Canadian businesses.",
        "",
        f"- **Live MCP Endpoint (Streamable HTTP):** `{base}/mcp`",
        f"- **Claude Connector:** {CLAUDE_DIRECTORY_URL}",
        f"- **Full LLM Directory:** {base}/llms.txt",
        "",
        "## Trade Verticals",
        "",
    ]
    for v in TRADE_VERTICALS:
        lines.append(f"### {v.short_label} ({v.province or 'Canada-wide'})")
        lines.append(f"- **HTML:** {base}/tenders/{v.slug}")
        lines.append(f"- **Markdown:** {base}/tenders/{v.slug}.md")
        lines.append(f"- **Summary:** {v.summary}")
        lines.append(f"- **Ask an AI agent:** \"{v.sample_prompt}\"")
        lines.append("")
    return "\n".join(lines)


def render_trade_detail_html(vertical: TradeVertical, snapshot: dict[str, Any], base: str = PUBLIC_ORIGIN) -> str:
    """Render a live, crawlable HTML page for one trade vertical."""
    opps = snapshot.get("opportunities") or []
    awards = snapshot.get("awards") or {}
    mcp_url = f"{base}/mcp"

    opp_cards = []
    for o in opps:
        title = str(o.get("title") or "Untitled tender")
        buyer = str(o.get("buyer") or "Public buyer")
        source = str(o.get("source") or o.get("source_key") or "Public feed")
        closes = str(o.get("closing_text") or o.get("closes_at") or "See official posting").split(";")[0]
        ref = str(o.get("reference") or "")
        url = str(o.get("url") or "")
        policies = o.get("domestic_policies") or []
        policy_badge = f" · Domestic signal: {escape(', '.join(str(p) for p in policies))}" if policies else ""
        link_html = (
            f'<a href="{escape(url)}" rel="noopener" target="_blank">Open official posting →</a>'
            if url
            else ""
        )
        opp_cards.append(
            '<article class="card result">'
            f"<h3>{escape(title)}</h3>"
            f'<p class="meta">{escape(buyer)} · {escape(source)} · Ref: {escape(ref)}{policy_badge}</p>'
            f"<p><strong>Closes:</strong> {escape(closes)}</p>"
            f"{link_html}"
            "</article>"
        )

    if not opp_cards:
        opp_html = (
            '<div class="card"><p>Use the live search or connect the MCP endpoint to pull real-time tenders '
            f'for <strong>{escape(vertical.short_label)}</strong>.</p>'
            f'<a class="btn primary" href="/try?q={escape(vertical.keywords.split()[0])}">Run live search now</a></div>'
        )
    else:
        opp_html = "".join(opp_cards)

    awards_html = ""
    if awards.get("available") and awards.get("count", 0) > 0:
        summary = awards.get("summary") or {}
        top_sups = awards.get("top_suppliers") or []
        sup_list = "".join(
            f"<li><strong>{escape(str(s.get('supplier', '')))}</strong> — {s.get('wins', 0)} recent awards "
            f"({_fmt_cad(s.get('total_awarded_cad'))})</li>"
            for s in top_sups
        )
        awards_html = (
            "<h2>Historical Contract Awards Snapshot</h2>"
            '<div class="card">'
            f"<p><strong>Comparable federal awards indexed:</strong> {awards['count']} · "
            f"<strong>Median value:</strong> {_fmt_cad(summary.get('median_cad'))} · "
            f"<strong>Range:</strong> {_fmt_cad(summary.get('min_cad'))} – {_fmt_cad(summary.get('max_cad'))}</p>"
            + (f"<ul>{sup_list}</ul>" if sup_list else "")
            + '<p class="muted" style="margin-bottom:0;">Run <code>get_buyer_award_history</code> inside Claude or ChatGPT to inspect buyer-specific incumbents and Alberta APC competition counts (2 free reviews on sign-in).</p>'
            "</div>"
        )

    other_links = " · ".join(
        f'<a href="/tenders/{v.slug}">{escape(v.short_label)}</a>'
        for v in TRADE_VERTICALS
        if v.slug != vertical.slug
    )

    body = f"""
<p class="muted" style="margin-bottom:0.2rem;"><a href="/tenders">← All Canadian trades</a> · <a href="/tenders/{vertical.slug}.md">Markdown (.md)</a></p>
<h1>{escape(vertical.title)}</h1>
<p class="lead">{escape(vertical.summary)}</p>

<div class="actions">
  <a class="btn primary" href="{CLAUDE_DIRECTORY_URL}" rel="noopener">Run in Claude (Free Search)</a>
  <a class="btn secondary" href="/try?q={escape(vertical.keywords.split()[0])}">Search live in browser</a>
  <a class="btn secondary" href="/features">Requirements Boards &amp; Award Radar</a>
</div>

<div class="card">
  <h3>Ask your AI assistant directly (copy prompt)</h3>
  <p><em>“{escape(vertical.sample_prompt)}”</em></p>
  <div class="actions" style="margin:0.5rem 0 0;">
    <button type="button" class="btn secondary" data-copy="{escape(vertical.sample_prompt)}">Copy prompt</button>
    <button type="button" class="btn secondary" data-copy="{escape(mcp_url)}">Copy MCP URL</button>
  </div>
</div>

<h2>Currently Open Tenders ({len(opps)} matched)</h2>
{opp_html}

{awards_html}

<p class="notice"><strong>Honest boundary:</strong> workspaceAlberta finds, ranks, and breaks down public tenders. It does not submit bids, contact buyers, or guarantee awards. Verify requirements and addenda on the official posting.</p>
<p class="muted"><strong>Other trades:</strong> {other_links}</p>
"""
    return _web_page(
        f"{vertical.title} — workspaceAlberta",
        body,
        current="",
        script=COPY_SCRIPT,
        description=vertical.summary,
        extra_jsonld=_trade_jsonld(base, vertical, snapshot),
    )


def render_trade_detail_md(vertical: TradeVertical, snapshot: dict[str, Any], base: str = PUBLIC_ORIGIN) -> str:
    """Render clean Markdown for LLM search bots and A2A agent ingestion."""
    opps = snapshot.get("opportunities") or []
    awards = snapshot.get("awards") or {}
    lines = [
        f"# {vertical.title}",
        "",
        vertical.summary,
        "",
        f"- **Canonical HTML:** {base}/tenders/{vertical.slug}",
        f"- **Live MCP Endpoint:** `{base}/mcp`",
        f"- **Keywords:** `{vertical.keywords}`",
        f"- **Sample AI Prompt:** \"{vertical.sample_prompt}\"",
        "",
        f"## Currently Open Tenders ({len(opps)} matched)",
        "",
    ]
    if opps:
        for o in opps:
            title = str(o.get("title") or "Untitled tender")
            buyer = str(o.get("buyer") or "Public buyer")
            source = str(o.get("source") or o.get("source_key") or "Public feed")
            closes = str(o.get("closing_text") or o.get("closes_at") or "See posting").split(";")[0]
            ref = str(o.get("reference") or "")
            url = str(o.get("url") or "")
            lines.append(f"- **{title}** (`{ref}`) — {buyer} ({source}) · Closes: {closes}" + (f" · {url}" if url else ""))
    else:
        lines.append(f"No cached rows at this moment; call `search_opportunities` via `{base}/mcp` or `POST {base}/search`.")

    if awards.get("available") and awards.get("count", 0) > 0:
        summary = awards.get("summary") or {}
        lines.extend(
            [
                "",
                "## Historical Contract Awards Snapshot",
                f"- Comparable federal awards indexed: {awards['count']}",
                f"- Median value: {_fmt_cad(summary.get('median_cad'))} (Range: {_fmt_cad(summary.get('min_cad'))} – {_fmt_cad(summary.get('max_cad'))})",
            ]
        )
        for s in awards.get("top_suppliers") or []:
            lines.append(f"- Top winner: **{s.get('supplier', '')}** ({s.get('wins', 0)} wins, {_fmt_cad(s.get('total_awarded_cad'))})")

    lines.extend(
        [
            "",
            "---",
            f"Powered by workspaceAlberta (Warre & Vavasour Ltd). Connect via MCP at `{base}/mcp` for live supply-fit ranking, historical contract awards (`get_buyer_award_history`), and interactive RFP Requirements Boards (`classify_tender`).",
        ]
    )
    return "\n".join(lines) + "\n"


def get_trade_vertical(slug: str) -> TradeVertical | None:
    return TRADE_VERTICALS_BY_SLUG.get(slug.strip().lower())
