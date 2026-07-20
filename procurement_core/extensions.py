"""Scaffolded extension tools: opportunity watchlist and bid/no-bid scorecard.

These are the first two roadmap tools (see ``docs/tooling-roadmap.md``),
implemented in the same style as ``service.py``: deterministic, markdown-out,
warnings over failures.

- **Watchlist** (``watch_opportunity`` / ``list_watchlist`` /
  ``unwatch_opportunity``): persist opportunities the owner is tracking to
  ``DATA_DIR/watchlist.json`` with an optional note. The retention loop for
  the Pro tier.
- **Scorecard** (``bid_no_bid_scorecard``): a fast, reproducible bid/no-bid
  checklist for one reference — profile fit, runway to close, region match,
  and an explicit verdict with reasons. No model call; it is the free cousin
  of ``process_bid_room``.

Handlers are imported into ``service.py``'s namespace at the bottom of that
module so ``call_tool_text`` dispatch (which resolves handlers by name from
``service`` globals) finds them. Service helpers are imported lazily inside
functions to avoid a circular import at module load.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

WATCHLIST_FILENAME = "watchlist.json"


# ============== Persistence ==============


def _watchlist_path():
    from procurement_core import service

    return service.DATA_DIR / WATCHLIST_FILENAME


def load_watchlist() -> list[dict[str, Any]]:
    """Load the watchlist (tenant row when hosted, local file otherwise)."""
    from procurement_core import storage

    if storage.tenant_active():
        data = storage.get_json_field("watchlist", [])
        return data if isinstance(data, list) else []

    path = _watchlist_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def save_watchlist(items: list[dict[str, Any]]) -> None:
    """Persist the watchlist (tenant row when hosted, disk otherwise)."""
    from procurement_core import storage

    if storage.tenant_active():
        storage.set_json_field("watchlist", items)
        return

    _watchlist_path().write_text(json.dumps(items, indent=2), encoding="utf-8")


def _find_opportunity(reference: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Resolve a reference to a normalized opportunity across both sources."""
    from procurement_core import service

    warnings: list[str] = []
    if service.is_alberta_reference(reference):
        try:
            details = service.get_alberta_api_details(reference)
            opp = details.get("opportunity", {}) or {}
            return service.normalize_alberta_opportunity(opp), warnings
        except (RuntimeError, ValueError) as exc:
            warnings.append(f"Alberta APC lookup failed: {exc}")
            return None, warnings

    contracts, federal_warnings = service.load_contracts_for_unified()
    warnings.extend(federal_warnings)
    contract = service.find_contract_by_reference(reference, contracts)
    if contract:
        return service.normalize_canadabuys_contract(contract), warnings
    return None, warnings


# ============== Watchlist Tools ==============


async def watch_opportunity(args: dict) -> str:
    """Add an opportunity to the persistent watchlist with an optional note."""
    reference = str(args.get("reference") or "").strip()
    if not reference:
        return "Please provide a reference number to watch."

    items = load_watchlist()
    if any(item.get("reference", "").lower() == reference.lower() for item in items):
        return f"`{reference}` is already on your watchlist. Use `list_watchlist` to review it."

    opportunity, warnings = _find_opportunity(reference)
    entry: dict[str, Any] = {
        "reference": reference,
        "note": str(args.get("note") or "").strip(),
        "added_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if opportunity:
        entry.update(
            {
                "title": opportunity.get("title", ""),
                "source": opportunity.get("source", ""),
                "buyer": opportunity.get("buyer", ""),
                "closing": opportunity.get("closing", ""),
                "url": opportunity.get("url", ""),
            }
        )
    items.append(entry)
    save_watchlist(items)

    output = f"# Watching `{reference}`\n\n"
    if opportunity:
        output += f"**{entry['title']}**\n"
        output += f"- Source: {entry['source']}\n"
        output += f"- Buyer: {entry['buyer']}\n"
        output += f"- Closing: {entry['closing']}\n"
    else:
        output += "Saved by reference only — details could not be resolved right now.\n"
    if entry["note"]:
        output += f"- Note: {entry['note']}\n"
    output += f"\nWatchlist size: {len(items)}. Use `list_watchlist` any time."
    if warnings:
        output += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings[:3])
    return output


async def list_watchlist(args: dict) -> str:
    """Show watched opportunities sorted by closing date with days remaining."""
    from procurement_core import service

    items = load_watchlist()
    if not items:
        return "Your watchlist is empty. Use `watch_opportunity` with a reference number to start tracking."

    now = datetime.now(timezone.utc)

    def sort_key(item: dict[str, Any]):
        parsed = service.parse_date(str(item.get("closing") or ""))
        if not parsed:
            return datetime.max.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    items = sorted(items, key=sort_key)
    output = f"# Watchlist ({len(items)} opportunities)\n\n"
    for i, item in enumerate(items, 1):
        title = str(item.get("title") or "Details pending")[:90]
        output += f"**{i}. {title}**\n"
        output += f"   Reference: `{item.get('reference', '')}`\n"
        if item.get("buyer"):
            output += f"   Buyer: {item['buyer'][:70]}\n"
        closing = service.parse_date(str(item.get("closing") or ""))
        if closing:
            if closing.tzinfo is None:
                closing = closing.replace(tzinfo=timezone.utc)
            days = (closing - now).days
            status = f"closes in {days} days" if days >= 0 else f"closed {-days} days ago"
            output += f"   Closing: {item.get('closing', '')} ({status})\n"
        if item.get("note"):
            output += f"   Note: {item['note']}\n"
        output += "\n"
    output += "Use `bid_no_bid_scorecard` on any reference for a go/no-go read, or `unwatch_opportunity` to remove one."
    return output


async def unwatch_opportunity(args: dict) -> str:
    """Remove an opportunity from the watchlist by reference."""
    reference = str(args.get("reference") or "").strip()
    if not reference:
        return "Please provide the reference number to remove."

    items = load_watchlist()
    remaining = [item for item in items if item.get("reference", "").lower() != reference.lower()]
    if len(remaining) == len(items):
        return f"`{reference}` was not on your watchlist."
    save_watchlist(remaining)
    return f"Removed `{reference}`. Watchlist size: {len(remaining)}."


# ============== Bid/No-Bid Scorecard ==============


async def bid_no_bid_scorecard(args: dict) -> str:
    """Deterministic bid/no-bid checklist for one opportunity reference."""
    from procurement_core import service

    reference = str(args.get("reference") or "").strip()
    if not reference:
        return "Please provide a reference number."

    opportunity, warnings = _find_opportunity(reference)
    if not opportunity:
        output = f"Opportunity not found: {reference}"
        if warnings:
            output += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings[:3])
        return output

    profile = service.load_profile()
    checks: list[tuple[str, str, str]] = []  # (signal, status, detail)
    positives = 0
    negatives = 0

    # 1. Profile fit
    if profile:
        raw = opportunity.get("raw", {})
        if opportunity.get("source_key") == "alberta":
            score, reasons = service.score_alberta_opportunity(raw, profile)
        else:
            score, reasons = service.score_contract(raw, profile)
        if score >= 15:
            checks.append(("Profile fit", "strong", f"score {score}: {'; '.join(reasons[:3])}"))
            positives += 2
        elif score > 0:
            checks.append(("Profile fit", "partial", f"score {score}: {'; '.join(reasons[:3])}"))
            positives += 1
        else:
            checks.append(("Profile fit", "weak", "no keyword, commodity, or region overlap with your profile"))
            negatives += 2
    else:
        checks.append(("Profile fit", "unknown", "no saved profile — run `set_business_profile` for a real fit read"))

    # 2. Runway to closing
    closing = service.parse_date(str(opportunity.get("closing") or ""))
    if closing:
        if closing.tzinfo is None:
            closing = closing.replace(tzinfo=timezone.utc)
        days = (closing - datetime.now(timezone.utc)).days
        if days < 0:
            checks.append(("Runway", "closed", f"closed {-days} days ago"))
            negatives += 3
        elif days < 5:
            checks.append(("Runway", "very tight", f"{days} days to closing — realistic only if documents are ready"))
            negatives += 1
        elif days <= 21:
            checks.append(("Runway", "workable", f"{days} days to closing"))
            positives += 1
        else:
            checks.append(("Runway", "comfortable", f"{days} days to closing"))
            positives += 1
    else:
        checks.append(("Runway", "unknown", "no closing date on the notice — verify at the source"))

    # 3. Region
    location = (profile or {}).get("location", "").lower()
    region = str(opportunity.get("region") or "").lower()
    if location and region:
        parts = [p.strip() for p in location.replace(",", " ").split() if len(p.strip()) > 3]
        if any(part in region for part in parts):
            checks.append(("Region", "match", f"delivery region includes your location ({opportunity.get('region', '')[:60]})"))
            positives += 1
        else:
            checks.append(("Region", "check", f"delivery region is {opportunity.get('region', '')[:60] or 'unspecified'}"))
    else:
        checks.append(("Region", "unknown", "set a profile location for a region read"))

    # 4. Buyer
    buyer = opportunity.get("buyer", "")
    checks.append(("Buyer", "info", f"{buyer[:70] or 'not listed'} ({opportunity.get('source', '')})"))

    # Verdict
    net = positives - negatives
    if any(status == "closed" for _, status, _ in checks):
        verdict, advice = "NO-BID", "This opportunity has already closed."
    elif net >= 3:
        verdict, advice = "GO", "Strong signals. Open the documents and confirm mandatory requirements today."
    elif net >= 1:
        verdict, advice = "CAUTION", "Mixed signals. Run `process_bid_room` for a document-grounded review before committing estimator time."
    else:
        verdict, advice = "LEAN NO-BID", "Weak fit on the deterministic signals. Only pursue if you know something the notice text does not show."

    output = f"# Bid/No-Bid Scorecard — `{opportunity.get('reference', reference)}`\n\n"
    output += f"**{str(opportunity.get('title', ''))[:90]}**\n\n"
    output += f"## Verdict: {verdict}\n{advice}\n\n"
    output += "## Signals\n"
    for signal, status, detail in checks:
        output += f"- **{signal}** ({status}): {detail}\n"
    if opportunity.get("url"):
        output += f"\n[View the posting]({opportunity['url']})\n"
    output += "\n---\nDeterministic checklist only — it does not read attachments. `process_bid_room` does."
    if warnings:
        output += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings[:3])
    return output
