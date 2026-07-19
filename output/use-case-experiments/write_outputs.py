#!/usr/bin/env python3
"""
Second pass over alberta-usecase-traces.json: writes the user-facing `output`
field for each trace, authored from the actual raw result texts captured live.
Safe to re-run; only touches the `output` field (and one appended note on uc-15).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATASET_PATH = BASE / "alberta-usecase-traces.json"

OUTPUTS = {
    "uc-01": (
        "Your profile is saved, so matches are ranked against what your shop actually does. "
        "The strongest fit right now is Alberta Transportation's Hwy 2:36 tender near Morinville "
        "(AB-2026-04073) — grading plus a structural steel girder bridge — closing July 30, 2026, "
        "with a match score of 55. There's also a cluster of Special Areas Board culvert RFPs and an "
        "asphalt tender closing July 21 if you want smaller, faster work. Worth opening the bridge "
        "tender first and checking the pre-tender meeting notes."
    ),
    "uc-02": (
        "There are 14 HVAC-related postings on Alberta Purchasing Connection right now. Heads-up on "
        "the top hit: the City of Lethbridge pool HVAC upgrade is a Notice of Award, meaning that "
        "work is already handed out — not something you can bid. The live ones to look at are the "
        "University of Calgary air and hydronic balancing pre-qualification (closes August 3, 2026) "
        "and the City of Calgary's mechanical/HVAC RFP 26-1630, which closes July 23, 2026."
    ),
    "uc-03": (
        "I searched both governments filtered to Alberta delivery, but the top results leaned toward "
        "big general construction — the Fort Saskatchewan Community Hospital renovation (closes "
        "August 6, 2026) and a Calgary Transit lift station — rather than grounds maintenance work. "
        "The hospital tender details confirm it's a clinical renovation, not landscaping. No dedicated "
        "landscaping or grounds maintenance tender surfaced in the top 10; try a single keyword like "
        "\"landscaping\" or \"mowing\" for a tighter match."
    ),
    "uc-04": (
        "The Alberta search matched 989 records, which tells you the matching is loose — and the top "
        "10 were general construction and services postings, not catering. The record pulled in full "
        "(Strathcona County's Woodbridge Way wastewater pre-qualification, closing August 18, 2026) "
        "is heavy civil work, not food service. Bottom line: no camp, crew food, or events catering "
        "RFP showed up in the top results this run, so nothing worth chasing today."
    ),
    "uc-05": (
        "The gravel search matched 402 Alberta records, but the top 10 weren't gravel-specific — the "
        "matcher is returning the freshest postings overall. On the deadline side, the soonest "
        "closings within 30 days are a Special Areas Board crack-sealing RFP (July 20, 2026), a "
        "MacEwan University compactor, and a Red Deer Catholic school division quote. No gravel supply "
        "or hauling tender surfaced in the top hits; a single-word \"gravel\" search or watching "
        "Transportation's tenders would be the next move."
    ),
    "uc-06": (
        "There's at least one real cleaning contract in the results: Forestry and Parks has a "
        "\"Janitorial Services\" RFP (AB-2026-05017) closing July 23, 2026 — that's the one to open "
        "first. The top-ranked hit I pulled in full was a vault toilet replacement construction job "
        "at Cypress Hills and Park Lake provincial parks (closes August 13, 2026), which is building "
        "work, not a cleaning contract. Also in the mix: an Epcor wastewater hauling RFP closing "
        "July 30. Go look at the janitorial RFP before Thursday."
    ),
    "uc-07": (
        "The keyword search didn't surface IT support or managed services RFPs in the top 10 — the "
        "results came back as general recent postings. The market summary gives the bigger picture: "
        "1,523 open Alberta Purchasing Connection opportunities, with 762 in Services, which is the "
        "bucket where IT support work sits. For a 5-person shop, the realistic play is watching the "
        "Services category for municipal and school-board IT RFPs rather than the general search."
    ),
    "uc-08": (
        "Yes, municipalities and public bodies do tender this kind of work — the search matched 33 "
        "Alberta postings — but the top results were mixed: a St. Albert Public Library managed IT "
        "RFP, a Town of Taber facility naming-rights EOI, and a school division photography RFP. "
        "No signs, forms, or commercial printing tender showed up in the top 10 this run. Context: "
        "there are 1,523 open APC postings overall (762 services, 599 goods), and printing jobs "
        "usually land in Goods — worth checking that category regularly."
    ),
    "uc-09": (
        "The search found 8 postings, but only one is security-related: the Barrhead Provincial "
        "Building security-system replacement ITB (closes August 11, 2026) — and that's a systems "
        "install job, not guard services. On the straight answer you asked for: I couldn't give one, "
        "because the bid/no-bid scorecard is a WorkspaceAlberta Pro feature ($85 CAD/month) and the "
        "server asked for a Pro API key. You can still open the Barrhead tender and eyeball the "
        "scope yourself for free."
    ),
    "uc-10": (
        "Fifteen Alberta postings close within your two-week window. Soonest: a Special Areas Board "
        "crack-sealing RFP and a Calgary Board of Education MCC panel replacement general-contractor "
        "bid both close July 20, 2026. On the electrical-specific search (69 matches), the ones that "
        "fit a master electrician include the Calgary Alberta Innovates fume hood replacement ITB "
        "closing July 29 and a Service Alberta communications test-set RFQ closing July 27. If you "
        "can mobilize fast, the fume hood job is the most credible electrical target."
    ),
    "uc-11": (
        "Morning brief is ready. Market snapshot: 919 open federal CanadaBuys notices and 1,523 open "
        "Alberta APC opportunities in your 14-day window. Your best fit is the Hwy 2:36 bridge and "
        "grading tender near Morinville (AB-2026-04073, score 91) closing July 30, 2026 — followed by "
        "another Transportation grading tender closing July 28 and a City of Calgary butterfly valve "
        "supply RFP closing July 22. Today's closing-soon flag: a Special Areas Board crack-sealing "
        "RFP closes within 24 hours."
    ),
    "uc-12": (
        "Straight answer: nothing snow-related is out right now. The search for snow removal and ice "
        "control returned summer work — the top hit I pulled in full is the Barrhead Provincial "
        "Building security-system replacement (closes August 11, 2026), which is irrelevant to you. "
        "Snow clearing contracts with towns and the province typically post in late summer and fall, "
        "so set a reminder to re-check in a few weeks rather than burning time today."
    ),
    "uc-13": (
        "There are 48 concrete-related matches, and several are genuinely your kind of work. Top of "
        "the list: the Bow River Pathway refurbishment in Fish Creek Provincial Park — tagged with "
        "concrete work commodity codes, requiring a COR or SECOR safety certificate — closes "
        "August 14, 2026. Also live: the Town of Mundare's 2026 Downtown Surface Replacement (closes "
        "July 28) and Wheatland County's Carseland Pathway Phase 2 (closes July 30). The pathway "
        "jobs are the closest fit for sidewalk and flatwork crews."
    ),
    "uc-14": (
        "Confirmed — the RMA fencing RFP is real and still open: AB-2026-04199, \"Fencing Materials "
        "and Products with Related Services,\" closes July 28, 2026. To your question: it's primarily "
        "a materials-and-products supply arrangement with related services on top, run as a national "
        "cooperative through Canoe Procurement on behalf of RMA and other provincial municipal "
        "associations — so it's more supply-than-install, and big in scope. If you want install work, "
        "the search also turned up contract fencing from the Special Areas Board (closes July 29) "
        "and a City of Camrose lagoon sani-dump fencing job (closes July 27)."
    ),
    "uc-15": (
        "The tender details are pulled: TND0012201 is the Hwy 2:36 job near Morinville — grading, "
        "granular base, asphalt concrete pavement, street lights, a structural steel girder bridge, "
        "and culvert work — an open-competitive ITB from Transportation and Economic Corridors "
        "closing July 30, 2026, with pre-tender meetings held in June. On the AI review: it didn't "
        "happen — analyze_contract_with_cohere came back with a WorkspaceAlberta Pro paywall "
        "($85 CAD/month, requires a Pro API key), so no risk analysis was returned. You have the "
        "full scope and dates above to start your own review."
    ),
    "uc-16": (
        "Side by side, the same keyword tells a clear story. The federal top 10 is dominated by "
        "Defence Construction Canada \"open construction source lists\" for bases in Halifax, Gander, "
        "Goose Bay, Greenwood and Esquimalt — standing lists running to 2029, and mostly out of "
        "region for a Calgary crew. The Alberta side shows fresh, local, biddable construction: "
        "Strathcona County's wastewater pre-qualification (August 18), the Fort Saskatchewan hospital "
        "renovation (August 6), and a Calgary Transit lift station modification (August 13). Focus on "
        "the Alberta side — that's where the immediately winnable work is for you."
    ),
    "uc-17": (
        "I couldn't add it to a watchlist — both the watch and watchlist tools came back with a "
        "WorkspaceAlberta Pro paywall: watchlist tracking is a Pro feature at $85 CAD/month and needs "
        "a Pro API key. Nothing was saved, so the bridge tender is not being tracked. The free "
        "fallback: the Hwy 2:36 tender (AB-2026-04073) closes July 30, 2026 — put that date in your "
        "own calendar today."
    ),
    "uc-18": (
        "Yes — it's still open. City of Calgary RFP 26-1524, \"Supply and Delivery of Shop Supplies "
        "and Fleet Parts\" (AB-2026-04750), closes July 23, 2026 at 4:00 PM. What they're buying is "
        "right in your lane: eight schedules covering filters, belts, wiper blades, electrical, "
        "clamps/hoses/fittings and air tools, caps and fuel components, ignition, and general shop "
        "tools and supplies. Bids go through the City's Ariba portal — get registered there before "
        "Thursday if you're not already."
    ),
    "uc-19": (
        "Transportation and Economic Corridors has a healthy slate out right now. Headliners: "
        "TND0021637 grading and granular base course (closes August 20, 2026), TND0025870 bridge "
        "rehabilitation (closes August 18), TND0023901 selective grading, plus a functional planning "
        "RFP (CON0026285) if you ever partner with engineers. Zooming out: Alberta Purchasing "
        "Connection has 1,523 open postings — 762 services, 599 goods, 162 construction — so the "
        "road-building pipeline is one slice of a busy market. Plenty here to price."
    ),
    "uc-20": (
        "Seven plumbing-adjacent results came back. The top hit, pulled in full, is the City of "
        "Edmonton's boiler and heating system chemical supply and service contract — commodity codes "
        "include plumbing/heating work — closing August 10, 2026, with a pre-bid meeting July 23. "
        "The more direct fit is further down the list: City of Calgary RFP 26-1630 for mechanical, "
        "heating, air conditioning and plumbing, closing July 23, 2026. Nothing flagged specifically "
        "as a school or hospital plumbing job in these results, but the Calgary mechanical RFP is "
        "worth a read this week."
    ),
    "uc-21": (
        "Here's your triage list: 20 opportunities close within 7 days across both governments. Most "
        "urgent is the Special Areas Board crack-sealing RFP — it closes today, July 20, 2026 at "
        "10:00 AM. Also closing July 20: a MacEwan University compactor, a Red Deer Catholic school "
        "division exterior quote, and the Onion Lake wellness centre build, plus federal items like a "
        "DND air dryer and several CFHA responsive-maintenance standing offers. Skim the 20 and "
        "no-bid anything you can't price by Wednesday."
    ),
    "uc-22": (
        "There's real paving work out there — 59 matches on the Alberta side. The ones worth your "
        "estimating time: the Bow River Pathway and Acadia Pathway pavement rehabilitation in Fish "
        "Creek Provincial Park (closes August 14, 2026), the Town of Mundare's 2026 Downtown Surface "
        "Replacement (closes July 28), and Wheatland County's Carseland Pathway Phase 2 (closes "
        "July 30). Market-wide there are 1,523 open APC postings with 162 in construction, so paving "
        "is an active niche right now. Yes — worth your time, starting with the pathway rehab bids."
    ),
}

EXTRA_NOTES = {
    "uc-15": (
        " Observed in this run: analyze_contract_with_cohere returned the WorkspaceAlberta Pro "
        "paywall message before any contract lookup, so the previously seen 'Contract not found' "
        "dead-end was not reachable without a Pro API key. Trace classified as 'paywall' "
        "(expectation_met=false against the spec's 'known-bug')."
    ),
}


def main():
    ds = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    missing = []
    for trace in ds["traces"]:
        tid = trace["id"]
        if tid in OUTPUTS:
            trace["output"] = OUTPUTS[tid]
        else:
            missing.append(tid)
        if tid in EXTRA_NOTES and EXTRA_NOTES[tid].strip() not in trace.get("notes", ""):
            trace["notes"] = (trace.get("notes", "") + EXTRA_NOTES[tid]).strip()
    if missing:
        raise SystemExit(f"ERROR: no output authored for: {missing}")

    # recompute summary + expectation flags for consistency
    summary = {}
    for trace in ds["traces"]:
        trace["expectation_met"] = trace["actual_outcome"] == trace["expected_outcome"]
        summary[trace["actual_outcome"]] = summary.get(trace["actual_outcome"], 0) + 1
    ds["outcome_summary"] = summary
    ds["trace_count"] = len(ds["traces"])
    ds["generated_at"] = datetime.now(timezone.utc).isoformat()

    DATASET_PATH.write_text(json.dumps(ds, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote outputs for {len(OUTPUTS)} traces.")
    print(f"trace_count={ds['trace_count']} outcome_summary={summary}")
    print(f"expectations met: {sum(1 for t in ds['traces'] if t['expectation_met'])}/{ds['trace_count']}")


if __name__ == "__main__":
    main()
