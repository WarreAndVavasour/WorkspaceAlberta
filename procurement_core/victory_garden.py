"""Victory Garden: Industrial Mobilization & Capability-Pivot Pipeline.

Takes a Canadian small business website URL (and/or plain-language shop
description), extracts real floor capabilities, equipment, materials, and
stated certifications, and maps them across two distinct lanes:

1. **Core Fit ("Bid Right Now")** — open federal CanadaBuys and Alberta APC
   tenders matching what the business already delivers today.
2. **Victory Garden Pivots ("What Your Existing Tooling Can Build Next")** —
   adjacent sovereign, defence, Arctic/northern logistics, infrastructure,
   energy, and emergency-supply demand that Canada is actively buying right
   now, evaluated via a dedicated TypeSafe Jev classifier (``jev-pivot-v1``)
   with deterministic fallback when Jev is unconfigured or times out.
3. **The Bridge ("Retooling, Clearances & Support Programs")** — explicit
   Canadian regulatory gates to verify (CGP, NCAGE, ISO 9001, CWB, COR,
   security clearances) paired with matching public industrial support
   programs (PrairiesCan, BDC, ISED, NRCan) and warm historical CAD award
   medians from ``awards.db`` when available.

Security:
- Website fetching is strictly SSRF-hardened (public HTTP/HTTPS hosts only;
  blocks loopback, RFC 1918, link-local, multicast, and cloud metadata IPs).
- Website copy and tender notices are treated strictly as untrusted evidence,
  never instructions.
- Certifications are never invented: only credentials literally stated in the
  source text are recorded as ``stated_certs``.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
import threading
import time
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from procurement_core import business_fit, industrial_programs, usage
from procurement_core.requirements import jev

PIVOT_PROMPT_VERSION = "jev-pivot-v1"
PIVOT_MAX_CANDIDATES = 14
PIVOT_CONCURRENCY = 4
PIVOT_DEADLINE_SECONDS = 8.0
PIVOT_REQUEST_TIMEOUT = 6.0
PIVOT_CACHE_MAX = 512

FETCH_TIMEOUT_SECONDS = 8
MAX_HOME_BYTES = 250_000
MAX_SUBPAGE_BYTES = 120_000
MAX_SUBPAGES = 3
USER_AGENT = "WorkspaceAlberta-VictoryGarden/1.0 (+https://elbowsupknivesout.warreandvavasour.com/victory-garden)"

_PIVOT_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_PIVOT_CACHE_LOCK = threading.Lock()


@dataclass(frozen=True)
class MobilizationCluster:
    id: str
    title: str
    sovereign_lane: str
    why_canada_needs_it: str
    triggers: tuple[str, ...]
    search_keywords: tuple[str, ...]
    unspsc_prefixes: tuple[str, ...]
    typical_role: str
    retooling_effort: str
    common_gates: tuple[str, ...]


# Deterministic Mobilization Crosswalk: maps existing Canadian shop-floor
# processes, machines, and crews -> adjacent sovereign & public demand lanes.
MOBILIZATION_CLUSTERS: tuple[MobilizationCluster, ...] = (
    MobilizationCluster(
        id="precision_machining_defence",
        title="Precision Defence, Marine & Aerospace Components",
        sovereign_lane="defence_security",
        why_canada_needs_it=(
            "Oilfield, forestry, and industrial CNC shops hold the 5-axis mills, lathes, and metrology "
            "needed for DND spare parts, Coast Guard marine assemblies, vehicle drivetrains, and UAV tooling."
        ),
        triggers=(
            "cnc", "machining", "machine shop", "lathe", "milling", "5-axis", "5 axis", "turning",
            "tool and die", "precision", "hydraulic", "valve", "pump", "downhole", "oilfield",
            "metrology", "cmm", "shaft", "gear", "turbine",
        ),
        search_keywords=("machining", "hydraulic", "valve", "marine", "defence", "parts"),
        unspsc_prefixes=("2315", "2510", "2511", "2711", "3116", "4014", "4015", "4610"),
        typical_role="subcontract_tier2",
        retooling_effort="Moderate — fixtures, first-article inspection, and QA documentation",
        common_gates=("Controlled Goods Program (CGP) if ITAR/defence-controlled", "ISO 9001 / AS9100", "NATO CAGE / NCAGE"),
    ),
    MobilizationCluster(
        id="structural_welding_shelters",
        title="Modular Command Skids, Bridges, Frames & Field Fabrication",
        sovereign_lane="critical_infrastructure",
        why_canada_needs_it=(
            "CWB welding bays, plate rollers, and custom trailer/skid shops can rapidly fabricate "
            "generator skids, bridge repair steel, armoured/protective enclosures, Arctic sleds, and base frames."
        ),
        triggers=(
            "welding", "cwb", "structural steel", "steel fabrication", "metal fabrication", "platework",
            "ironworks", "boilermaker", "trailer", "skid", "pressure vessel", "pipefitting",
            "aluminum fabrication", "plasma", "laser cutting", "press brake",
        ),
        search_keywords=("steel", "fabrication", "welding", "bridge", "enclosure", "skid"),
        unspsc_prefixes=("3010", "3022", "7215", "7315", "2410", "2510"),
        typical_role="direct_redeploy",
        retooling_effort="Low — existing welding bays and overhead cranes; verify spec & coating",
        common_gates=("CWB W47.1 / W47.2", "COR / SECOR safety", "Buy Canadian steel mill test reports"),
    ),
    MobilizationCluster(
        id="sheet_metal_hvac_enclosures",
        title="Ruggedized Enclosures, Marine/Base HVAC & Filtration Systems",
        sovereign_lane="critical_infrastructure",
        why_canada_needs_it=(
            "Commercial HVAC, boiler, and sheet-metal shops can pivot into base mechanical retrofits, "
            "ruggedized comms/generator housings, cold-weather air handling, and hospital/shelter filtration."
        ),
        triggers=(
            "hvac", "sheet metal", "ductwork", "boiler", "chiller", "plumbing", "mechanical",
            "refrigeration", "ventilation", "furnace", "air handling", "hydronic",
        ),
        search_keywords=("hvac", "mechanical", "boiler", "ventilation", "enclosure", "refrigeration"),
        unspsc_prefixes=("4010", "4014", "4016", "7215", "4110"),
        typical_role="direct_redeploy",
        retooling_effort="Low to moderate — existing press brakes, mechanical tickets, and shop floor",
        common_gates=("Red Seal / provincial mechanical tickets", "COR safety", "Buy Canadian equipment rules"),
    ),
    MobilizationCluster(
        id="textiles_shelters_tactical",
        title="Field Shelters, Arctic Thermal Covers & Load-Bearing Textiles",
        sovereign_lane="defence_security",
        why_canada_needs_it=(
            "Industrial sewing, awning, tarp, and upholstery shops can produce cold-weather equipment covers, "
            "insulated tent liners, vehicle tarps, webbing harnesses, and medical/field soft goods."
        ),
        triggers=(
            "upholstery", "canvas", "tarp", "awning", "sewing", "textile", "apparel", "garment",
            "sail", "tent", "webbing", "industrial fabric", "leather", "vinyl",
        ),
        search_keywords=("tent", "shelter", "tarp", "textile", "clothing", "cover"),
        unspsc_prefixes=("1116", "4618", "4912", "5310", "5311"),
        typical_role="light_retool",
        retooling_effort="Low — heavy-duty walking-foot machines & RF welders match defence/field specs",
        common_gates=("CAN/CGSB textile specs", "Flame-retardant / cold-crack material certs", "Buy Canadian content"),
    ),
    MobilizationCluster(
        id="modular_lumber_crating",
        title="Rapid Modular Barracks, Northern Housing & Heavy Equipment Crating",
        sovereign_lane="arctic_logistics",
        why_canada_needs_it=(
            "Modular builders, truss plants, sawmills, and cabinet/millwork shops can pivot into "
            "rapid-deployable northern housing, base billets, timber bridge decking, and ISPM-15 export/munitions crating."
        ),
        triggers=(
            "lumber", "sawmill", "millwork", "cabinet", "truss", "modular", "prefab", "carpentry",
            "timber", "woodworking", "pallet", "crate", "framing", "roofing", "general contractor",
        ),
        search_keywords=("modular", "building", "lumber", "renovation", "crate", "prefab"),
        unspsc_prefixes=("1112", "2411", "3010", "3020", "7211", "7212"),
        typical_role="direct_redeploy",
        retooling_effort="Low — existing panel/framing lines; add ISPM-15 heat-treat stamp for export crating",
        common_gates=("ISPM-15 / CFIA certification (crating)", "CSA A277 (modular buildings)", "Buy Canadian lumber"),
    ),
    MobilizationCluster(
        id="plastics_composites_cases",
        title="Ruggedized Transit Cases, UAV Airframes & Field Water/Fuel Tanks",
        sovereign_lane="defence_security",
        why_canada_needs_it=(
            "Plastics thermoformers, rotomoulders, fibreglass boatbuilders, and composite shops hold the ovens "
            "and moulds needed for rugged equipment cases, drone airframes, marine floats, and field tanks."
        ),
        triggers=(
            "plastic", "thermoform", "injection mold", "injection mould", "rotomold", "rotomould",
            "fiberglass", "fibreglass", "composite", "carbon fiber", "carbon fibre", "polyethylene",
            "rubber", "gasket", "moulding", "molding", "boat", "marine hull",
        ),
        search_keywords=("composite", "plastic", "tank", "container", "marine", "case"),
        unspsc_prefixes=("1310", "2411", "2412", "2511", "3115", "4615"),
        typical_role="light_retool",
        retooling_effort="Moderate — new CNC-cut moulds/plugs using existing presses, ovens, and layup bays",
        common_gates=("MIL-STD / IP67 drop & environmental testing", "ISO 9001", "CGP if UAV defence payload"),
    ),
    MobilizationCluster(
        id="electrical_power_resilience",
        title="Backup Power, Microgrids, Base Electrical & Control Panels",
        sovereign_lane="energy_industrial",
        why_canada_needs_it=(
            "Electrical contractors, UL/CSA panel shops, and instrumentation crews are essential for "
            "base backup generators, substation hardening, remote Arctic microgrids, and automated controls."
        ),
        triggers=(
            "electrical", "electrician", "switchgear", "generator", "panel shop", "instrumentation",
            "scada", "plc", "automation", "solar", "battery", "microgrid", "transformer", "lighting",
        ),
        search_keywords=("electrical", "generator", "switchgear", "lighting", "power", "controls"),
        unspsc_prefixes=("2610", "2611", "2612", "3911", "3912", "7215"),
        typical_role="direct_redeploy",
        retooling_effort="Low — CSA-certified panel assembly & field crews transfer straight to public infrastructure",
        common_gates=("CSA C22.2 / UL 508A panel certification", "Master Electrician", "COR safety"),
    ),
    MobilizationCluster(
        id="civil_hardening_infrastructure",
        title="Airfield, Port, Bridge & Perimeter Civil Hardening",
        sovereign_lane="critical_infrastructure",
        why_canada_needs_it=(
            "Civil, paving, concrete, and earthworks contractors build the runways, northern roads, "
            "bridges, drainage, and hardened perimeter infrastructure required for allied logistics."
        ),
        triggers=(
            "concrete", "paving", "asphalt", "excavation", "earthworks", "grading", "civil",
            "aggregate", "gravel", "culvert", "bridge", "demolition", "hydrovac", "drilling",
        ),
        search_keywords=("concrete", "paving", "bridge", "excavation", "road", "civil"),
        unspsc_prefixes=("3011", "3012", "7214", "7215"),
        typical_role="direct_redeploy",
        retooling_effort="Low — existing yellow iron, batching, and civil crews",
        common_gates=("Bid & performance bonding (10% / 50%)", "COR safety", "Buy Canadian concrete/steel"),
    ),
    MobilizationCluster(
        id="heavy_fleet_arctic_logistics",
        title="Heavy Haulage, Northern Resupply & Fleet Maintenance",
        sovereign_lane="arctic_logistics",
        why_canada_needs_it=(
            "Trucking outfits, crane/rigging fleets, heavy-duty mechanics, and warehouses are the backbone "
            "of rapid mobilization, remote northern/Arctic staging, and emergency equipment transport."
        ),
        triggers=(
            "trucking", "hauling", "freight", "logistics", "warehouse", "crane", "rigging",
            "heavy equipment", "fleet", "diesel", "mechanic", "hotshot", "lowboy", "snow removal",
        ),
        search_keywords=("transport", "freight", "equipment", "fleet", "maintenance", "storage"),
        unspsc_prefixes=("2510", "7810", "7811", "7812", "7813", "7814", "7818"),
        typical_role="direct_redeploy",
        retooling_effort="Low — existing commercial fleet, CVOR/NSC safety fitness, and yards",
        common_gates=("NSC safety fitness certificate", "TDG (Dangerous Goods) if fuel/munitions", "WCB clearance"),
    ),
    MobilizationCluster(
        id="comms_drones_cyber",
        title="ISR Drones, Remote Comms, Geomatics & Sovereign Cybersecurity",
        sovereign_lane="defence_security",
        why_canada_needs_it=(
            "Commercial UAV operators, telecom tower crews, geospatial teams, and Canadian IT/cyber firms "
            "directly supply drone inspection/ISR, Arctic comms maintenance, and sovereign cyber defence."
        ),
        triggers=(
            "drone", "uav", "rpas", "geomatics", "survey", "lidar", "telecom", "tower", "radio",
            "cybersecurity", "software", "it support", "network", "electronics", "pcb", "avionics",
            "sensor", "engineering",
        ),
        search_keywords=("software", "cyber", "radio", "survey", "drone", "engineering"),
        unspsc_prefixes=("4321", "4322", "4323", "8111", "8114", "8116", "4111"),
        typical_role="direct_redeploy",
        retooling_effort="Low to moderate — sovereign hosting, security clearance, or Transport Canada SFOC",
        common_gates=("Reliability / Secret Security Clearance", "Transport Canada RPAS Advanced", "Canadian data residency"),
    ),
    MobilizationCluster(
        id="food_agri_resilience",
        title="Base Rations, Northern Food Security & Emergency Supply",
        sovereign_lane="health_emergency",
        why_canada_needs_it=(
            "Canadian food processors, commercial bakeries, meat packers, greenhouses, and cold-chain "
            "distributors underpin DND base provisioning, remote northern supply, and emergency food reserves."
        ),
        triggers=(
            "bakery", "food", "meat", "butcher", "greenhouse", "agriculture", "grain", "catering",
            "cold storage", "packaging", "produce", "dairy", "beverage", "commissary",
        ),
        search_keywords=("food", "catering", "rations", "groceries", "commissary", "kitchen"),
        unspsc_prefixes=("5010", "5011", "5013", "5018", "5019", "9010"),
        typical_role="direct_redeploy",
        retooling_effort="Low — CFIA / HACCP food-safety compliance + standing-offer delivery schedule",
        common_gates=("CFIA / Safe Food for Canadians Licence", "HACCP / GFSI audit", "Cold-chain traceability"),
    ),
    MobilizationCluster(
        id="safety_hazmat_facilities",
        title="Emergency Readiness, Hazmat/Environmental & Base Facilities",
        sovereign_lane="health_emergency",
        why_canada_needs_it=(
            "Industrial safety suppliers, environmental remediation firms, and commercial facilities crews "
            "support base readiness, water/hazmat response, medical supply logistics, and 24/7 facility upkeep."
        ),
        triggers=(
            "safety", "ppe", "hazmat", "environmental", "remediation", "water treatment", "janitorial",
            "cleaning", "facilities", "medical", "first aid", "fire", "security guard", "sanitation",
        ),
        search_keywords=("environmental", "safety", "water", "janitorial", "medical", "security"),
        unspsc_prefixes=("4217", "4618", "4619", "7611", "7612", "7710", "7712"),
        typical_role="direct_redeploy",
        retooling_effort="Low — existing crews, safety gear, and provincial certifications",
        common_gates=("Health Canada MDEL (if medical devices)", "COR safety", "Reliability security screening"),
    ),
)

_CERT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bcwb\b|canadian welding bureau|w47\.1|w47\.2", "CWB Certified"),
    (r"\bcor\b|certificate of recognition", "COR Safety"),
    (r"\bsecor\b", "SECOR Safety"),
    (r"\biso\s*9001\b", "ISO 9001"),
    (r"\bas\s*9100\b", "AS9100 Aerospace"),
    (r"\basme\b", "ASME"),
    (r"\babsa\b", "ABSA Pressure Equipment"),
    (r"\bapi\s*(?:q1|6a|5l|spec)\b", "API Certified"),
    (r"\bcsa\b", "CSA Certified"),
    (r"\bcontrolled goods\b|\bcgp\b", "Controlled Goods Program (CGP)"),
    (r"\bncage\b|\bcage code\b", "NATO NCAGE"),
    (r"\bisfm-15\b|\bispm-15\b|\bispm 15\b", "ISPM-15 Export Crating"),
    (r"\bcfia\b|\bhaccp\b", "CFIA / HACCP"),
    (r"\bred seal\b", "Red Seal Trades"),
    (r"\bwcb\b", "WCB Coverage"),
    (r"\bsecurity clearance\b|\breliability status\b", "Security Clearance"),
)

_LOCATION_HINTS: tuple[tuple[str, str], ...] = (
    (r"\bred deer\b", "Red Deer, Alberta"),
    (r"\bedmonton\b|\bnisku\b|\bleduc\b|\bsherwood park\b|\bst\.?\s*albert\b|\bspruce grove\b", "Edmonton Region, Alberta"),
    (r"\bcalgary\b|\bairdrie\b|\bokotoks\b|\bcochrane\b", "Calgary Region, Alberta"),
    (r"\blethbridge\b", "Lethbridge, Alberta"),
    (r"\bmedicine hat\b", "Medicine Hat, Alberta"),
    (r"\bgrande prairie\b", "Grande Prairie, Alberta"),
    (r"\bfort mcmurray\b|\bwood buffalo\b", "Fort McMurray, Alberta"),
    (r"\blloydminster\b", "Lloydminster, Alberta"),
    (r"\balberta\b|\b,\s*ab\b", "Alberta, Canada"),
    (r"\bvancouver\b|\bsurrey\b|\bvictoria\b|\bkelowna\b|\bbritish columbia\b|\b,\s*bc\b", "British Columbia, Canada"),
    (r"\bsaskatoon\b|\bregina\b|\bsaskatchewan\b|\b,\s*sk\b", "Saskatchewan, Canada"),
    (r"\bwinnipeg\b|\bmanitoba\b|\b,\s*mb\b", "Manitoba, Canada"),
    (r"\btoronto\b|\bottawa\b|\bhamilton\b|\blondon,\s*on\b|\bontario\b|\b,\s*on\b", "Ontario, Canada"),
    (r"\bmontreal\b|\bmontréal\b|\bquebec\b|\bquébec\b|\b,\s*qc\b", "Quebec, Canada"),
    (r"\bhalifax\b|\bnova scotia\b|\bnew brunswick\b|\bnewfoundland\b|\bmoncton\b", "Atlantic Canada"),
)

# Jev 1.13 leans toward the first Choice option, so negative options go LAST.
PIVOT_QUESTIONS = {
    "pivot_feasibility": {
        "type": "choice",
        "instructions": (
            "`shop_assets` summarizes a Canadian small business's existing equipment, processes, materials, "
            "and crew extracted from its website. `notice_title`, `notice_buyer`, `notice_codes`, and "
            "`notice_text` describe one open Canadian government procurement notice. "
            "Could this business redeploy its existing machines, tooling, or skilled crew to supply this "
            "notice — either directly, with light retooling, or as a Tier-2 subcontractor to a prime? "
            "Pick direct_redeploy if their existing shop can deliver this with minimal change. "
            "Pick light_retool if the same machines/skills apply with minor jigs, specs, or QA. "
            "Pick subcontract_tier2 if the notice is a large defence/infrastructure program where this shop "
            "could plausibly supply components, sub-assemblies, crating, or trade scope to the prime. "
            "Pick unlikely if their equipment and skills do not transfer."
        ),
        "criteria": {
            "direct_redeploy": "Existing equipment, crew, and processes can deliver this notice directly.",
            "light_retool": "Existing machines and expertise transfer with light fixtures, spec adjustments, or QA.",
            "subcontract_tier2": "Shop can supply components, sub-fabrication, or specialty trade scope to a prime contractor.",
            "unlikely": "Equipment and skills do not plausibly transfer to what this notice buys.",
        },
    },
    "bridge_type": {
        "type": "choice",
        "instructions": (
            "What is the main gap this business would need to bridge to win or supply this pivot notice? "
            "Pick none_needed if they can bid as-is, tooling_or_qa for jigs/testing/specs, "
            "cert_or_clearance for CGP/ISO/CWB/COR/security clearances, prime_teaming when best entered "
            "as a Tier-2 subcontractor, or not_applicable when pivot_feasibility is unlikely."
        ),
        "criteria": {
            "none_needed": "Existing shop credentials and tooling fit as-is.",
            "tooling_or_qa": "Needs minor tooling, jigs, packaging, or quality inspection setup.",
            "cert_or_clearance": "Needs a Canadian certification or clearance (CGP, ISO 9001, CWB, COR, security).",
            "prime_teaming": "Best pursued as a Tier-2 supplier or subcontractor to a Canadian prime.",
            "not_applicable": "Not a plausible pivot.",
        },
    },
    "sovereign_lane": {
        "type": "choice",
        "instructions": (
            "Which Canadian national resilience or public-demand lane best fits this notice?"
        ),
        "criteria": {
            "defence_security": "National defence (DND), Coast Guard, RCMP, security, tactical, or dual-use hardware.",
            "critical_infrastructure": "Bridges, roads, airfields, ports, public buildings, water, or base facilities.",
            "arctic_logistics": "Northern, Arctic, remote staging, modular shelters, heavy haulage, or resupply.",
            "energy_industrial": "Power grid, backup generators, energy infrastructure, or heavy industrial systems.",
            "health_emergency": "Medical, emergency response, hazmat, CBRN, or resilient food supply.",
            "general_public": "Routine municipal, school, or general government procurement.",
        },
    },
}

PIVOT_RANK = {"direct_redeploy": 3, "light_retool": 2, "subcontract_tier2": 1, "unclassified": 1, "unlikely": 0}


class _SimpleHTMLTextExtractor(HTMLParser):
    """Strip scripts/styles/markup and collect clean text + same-origin links."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self._in_h1 = False
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg", "iframe"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if t == "title":
            self._in_title = True
        elif t == "h1":
            self._in_h1 = True
        elif t == "a":
            href = dict(attrs).get("href")
            if href:
                self._current_href = href.strip()
                self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript", "svg", "iframe"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if t == "title":
            self._in_title = False
        elif t == "h1":
            self._in_h1 = False
        elif t == "a" and self._current_href is not None:
            self.links.append((self._current_href, " ".join(self._current_link_text).strip()))
            self._current_href = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        if self._in_h1:
            self.h1_parts.append(cleaned)
        if self._current_href is not None:
            self._current_link_text.append(cleaned)
        self.text_parts.append(cleaned)


def _validate_public_url(raw_url: str) -> str:
    """Validate and normalize an external HTTP(S) URL, blocking SSRF targets."""
    url = raw_url.strip()
    if not url:
        raise ValueError("Provide a website URL or a business description.")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Website URL must be a valid http:// or https:// address.")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Private or local hostnames are not permitted.")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{host}'.") from exc
    for info in infos:
        ip_str = info[4][0]
        ip_obj = ipaddress.ip_address(ip_str)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            raise ValueError("Private, loopback, or reserved IP addresses are not permitted.")
    return parsed.geturl()


def _fetch_html(url: str, *, max_bytes: int) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
        },
    )
    with urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if ctype and "html" not in ctype and "text/" not in ctype and "xml" not in ctype:
            return ""
        raw = resp.read(max_bytes)
        return raw.decode("utf-8", errors="replace")


_SUBPAGE_HINT_RE = re.compile(
    r"(service|capabilit|equipment|machin|about|product|certif|fabricat|weld|fleet|project|manufactur|shop|facility)",
    re.I,
)


def _select_subpages(base_url: str, links: list[tuple[str, str]]) -> list[str]:
    base_parsed = urlparse(base_url)
    base_host = (base_parsed.hostname or "").lower()
    seen: set[str] = {base_url.rstrip("/")}
    scored: list[tuple[int, str]] = []
    for href, label in links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full = urljoin(base_url, href).split("#", 1)[0]
        p = urlparse(full)
        if p.scheme not in {"http", "https"} or (p.hostname or "").lower() != base_host:
            continue
        if any(p.path.lower().endswith(ext) for ext in (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".zip", ".mp4", ".svg")):
            continue
        norm = full.rstrip("/")
        if norm in seen:
            continue
        seen.add(norm)
        score = 0
        if _SUBPAGE_HINT_RE.search(p.path):
            score += 3
        if _SUBPAGE_HINT_RE.search(label):
            score += 2
        if score > 0 and p.path.count("/") <= 3:
            scored.append((score, full))
    scored.sort(key=lambda item: (-item[0], len(item[1])))
    return [u for _, u in scored[:MAX_SUBPAGES]]


def analyze_shop_text(
    text: str,
    *,
    website_url: str = "",
    company_name: str = "",
    location: str = "",
    extra_context: str = "",
    pages_fetched: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministically build a Shop Asset Card + matched Mobilization Clusters from text."""
    combined = " ".join(part.strip() for part in (text, extra_context) if part and part.strip())
    low = combined.lower()

    detected_location = location.strip()
    if not detected_location:
        for pattern, label in _LOCATION_HINTS:
            if re.search(pattern, low, re.I):
                detected_location = label
                break
    if not detected_location:
        detected_location = "Canada"

    stated_certs: list[str] = []
    for pattern, label in _CERT_PATTERNS:
        if re.search(pattern, low, re.I) and label not in stated_certs:
            stated_certs.append(label)

    cluster_hits: list[tuple[int, list[str], MobilizationCluster]] = []
    for cluster in MOBILIZATION_CLUSTERS:
        matched_triggers = [t for t in cluster.triggers if re.search(rf"\b{re.escape(t)}\b", low)]
        if matched_triggers:
            cluster_hits.append((len(matched_triggers), matched_triggers, cluster))
    cluster_hits.sort(key=lambda item: (-item[0], item[2].id))

    if not cluster_hits:
        # Broad fallback: if a shop's website is sparse, suggest the 3 most versatile Canadian mobilization lanes.
        fallback_ids = {"structural_welding_shelters", "modular_lumber_crating", "heavy_fleet_arctic_logistics"}
        cluster_hits = [(0, [], c) for c in MOBILIZATION_CLUSTERS if c.id in fallback_ids]

    matched_processes: list[str] = []
    for _, trigs, _ in cluster_hits[:5]:
        for t in trigs:
            if t not in matched_processes:
                matched_processes.append(t)

    inferred_name = company_name.strip()
    if not inferred_name and website_url:
        host = (urlparse(website_url).hostname or "").replace("www.", "")
        inferred_name = host.split(".")[0].replace("-", " ").title() if host else "Canadian Business"
    if not inferred_name:
        inferred_name = "Canadian Business"

    # Build a crisp, evidence-bounded summary for Jev and search tools.
    excerpt = re.sub(r"\s+", " ", combined).strip()[:1200]
    core_desc = (
        f"{inferred_name} ({detected_location}). "
        + (f"Detected processes & tooling: {', '.join(matched_processes[:12])}. " if matched_processes else "")
        + (f"Stated certifications: {', '.join(stated_certs)}. " if stated_certs else "")
        + excerpt[:420]
    ).strip()

    return {
        "company_name": inferred_name,
        "website_url": website_url,
        "location": detected_location,
        "pages_fetched": pages_fetched or [],
        "detected_processes": matched_processes[:16],
        "stated_certs": stated_certs,
        "core_description": core_desc[:750],
        "evidence_excerpt": excerpt[:600],
        "matched_clusters": [
            {
                "id": c.id,
                "title": c.title,
                "sovereign_lane": c.sovereign_lane,
                "why_canada_needs_it": c.why_canada_needs_it,
                "matched_triggers": trigs[:8],
                "typical_role": c.typical_role,
                "retooling_effort": c.retooling_effort,
                "common_gates": list(c.common_gates),
                "search_keywords": list(c.search_keywords),
            }
            for _, trigs, c in cluster_hits[:4]
        ],
    }


def extract_website_profile(
    *,
    website_url: str = "",
    description: str = "",
    company_name: str = "",
    location: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Fetch a small business website (SSRF-safe) and return ``(shop_card, warnings)``."""
    warnings: list[str] = []
    pages_fetched: list[str] = []
    texts: list[str] = []
    inferred_title = company_name.strip()
    normalized_url = ""

    if website_url.strip():
        normalized_url = _validate_public_url(website_url)
        try:
            home_html = _fetch_html(normalized_url, max_bytes=MAX_HOME_BYTES)
            pages_fetched.append(normalized_url)
        except (HTTPError, URLError, OSError) as exc:
            if not description.strip():
                raise ValueError(f"Could not read website '{normalized_url}': {exc}") from exc
            warnings.append(f"Could not fetch '{normalized_url}' ({exc}); using supplied business description.")
            home_html = ""

        if home_html:
            parser = _SimpleHTMLTextExtractor()
            parser.feed(home_html)
            if not inferred_title:
                raw_title = " ".join(parser.title_parts).strip() or " ".join(parser.h1_parts).strip()
                inferred_title = re.split(r"\s*[|–—-]\s*", raw_title)[0].strip()[:80]
            texts.append(" ".join(parser.text_parts)[:6000])

            for sub_url in _select_subpages(normalized_url, parser.links):
                try:
                    sub_html = _fetch_html(sub_url, max_bytes=MAX_SUBPAGE_BYTES)
                    if sub_html:
                        sp = _SimpleHTMLTextExtractor()
                        sp.feed(sub_html)
                        texts.append(" ".join(sp.text_parts)[:3500])
                        pages_fetched.append(sub_url)
                except (HTTPError, URLError, OSError):
                    continue

    merged_text = "\n".join(texts)
    if not merged_text.strip() and not description.strip():
        raise ValueError("Provide a readable website URL or a brief description of your shop and equipment.")

    shop_card = analyze_shop_text(
        merged_text,
        website_url=normalized_url,
        company_name=inferred_title,
        location=location,
        extra_context=description,
        pages_fetched=pages_fetched,
    )
    return shop_card, warnings


def _pivot_cache_key(model: str, state: dict[str, Any]) -> str:
    raw = json.dumps({"v": PIVOT_PROMPT_VERSION, "m": model, "s": state}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _pivot_state(shop_card: dict[str, Any], notice: dict[str, Any]) -> dict[str, str]:
    codes = " ".join(
        str(x) for x in (notice.get("unspsc"), notice.get("unspsc_description"), notice.get("gsin"), notice.get("gsin_description")) if x
    )
    return {
        "shop_assets": shop_card["core_description"][:550],
        "notice_title": str(notice.get("title") or "")[:200],
        "notice_buyer": str(notice.get("buyer") or "")[:120],
        "notice_codes": codes[:180],
        "notice_text": str(notice.get("description") or notice.get("summary") or "")[:550],
    }


def _extract_pivot_verdict(response: dict[str, Any]) -> dict[str, str]:
    results = response.get("results") if isinstance(response, dict) else {}
    if not isinstance(results, dict):
        results = {}

    def _pick(field: str, allowed: set[str], default: str) -> str:
        entry = results.get(field)
        val = entry.get("answer") if isinstance(entry, dict) else entry
        val_s = str(val or "").strip().lower()
        return val_s if val_s in allowed else default

    feas = _pick("pivot_feasibility", {"direct_redeploy", "light_retool", "subcontract_tier2", "unlikely"}, "unclassified")
    bridge = _pick("bridge_type", {"none_needed", "tooling_or_qa", "cert_or_clearance", "prime_teaming", "not_applicable"}, "tooling_or_qa")
    lane = _pick(
        "sovereign_lane",
        {"defence_security", "critical_infrastructure", "arctic_logistics", "energy_industrial", "health_emergency", "general_public"},
        "general_public",
    )
    return {"pivot_feasibility": feas, "bridge_type": bridge, "sovereign_lane": lane}


def classify_pivots_with_jev(
    shop_card: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Run bounded TypeSafe Jev pivot classification (``jev-pivot-v1``) on adjacent tenders."""
    if not candidates:
        return {}, []
    api_key = business_fit.typesafe_api_key()
    if not api_key:
        return {}, ["TypeSafe Jev is not configured; Victory Garden pivots ranked via the deterministic Mobilization Crosswalk."]

    model = os.environ.get("TYPESAFE_MODEL", "").strip() or business_fit.DEFAULT_MODEL
    verdicts: dict[str, dict[str, str]] = {}
    to_call: list[tuple[str, str, dict[str, str]]] = []
    warnings: list[str] = []

    for notice in candidates[:PIVOT_MAX_CANDIDATES]:
        ref = str(notice.get("reference") or notice.get("title") or "")
        state = _pivot_state(shop_card, notice)
        key = _pivot_cache_key(model, state)
        with _PIVOT_CACHE_LOCK:
            cached = _PIVOT_CACHE.get(key)
            if cached is not None:
                _PIVOT_CACHE.move_to_end(key)
                verdicts[ref] = dict(cached)
                continue
        to_call.append((ref, key, state))

    if not to_call:
        return verdicts, []

    def _one(state: dict[str, str]) -> dict[str, Any]:
        return jev.call_jev(
            state,
            PIVOT_QUESTIONS,
            api_key=api_key,
            model=model,
            timeout=PIVOT_REQUEST_TIMEOUT,
            max_retries=1,
        )

    deadline = time.monotonic() + PIVOT_DEADLINE_SECONDS
    pool = ThreadPoolExecutor(max_workers=PIVOT_CONCURRENCY, thread_name_prefix="jev-pivot")
    futures = {pool.submit(_one, st): (ref, key) for ref, key, st in to_call}
    pending = set(futures.keys())
    auth_failed = False

    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                warnings.append("TypeSafe Jev pivot pass hit time budget; remaining pivots ranked deterministically.")
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                warnings.append("TypeSafe Jev pivot pass hit time budget; remaining pivots ranked deterministically.")
                break
            for fut in done:
                ref, key = futures[fut]
                try:
                    raw = fut.result()
                    verdict = _extract_pivot_verdict(raw)
                    verdicts[ref] = verdict
                    with _PIVOT_CACHE_LOCK:
                        _PIVOT_CACHE[key] = verdict
                        while len(_PIVOT_CACHE) > PIVOT_CACHE_MAX:
                            _PIVOT_CACHE.popitem(last=False)
                    usage.record_jev_usage(raw, feature="victory_garden_pivot")
                except jev.AuthError:
                    auth_failed = True
                    warnings.append("TypeSafe Jev rejected API key; using deterministic Mobilization Crosswalk.")
                    pending.clear()
                    break
                except Exception:  # noqa: BLE001
                    continue
            if auth_failed:
                break
    finally:
        for fut in pending:
            fut.cancel()
        pool.shutdown(wait=False, cancel_futures=True)

    return verdicts, warnings


def _warm_cluster_awards(cluster: dict[str, Any], province: str) -> dict[str, Any] | None:
    """Attach warm federal historical award medians if ``awards.db`` is already on disk."""
    try:
        from procurement_core import awards as awards_mod

        if not awards_mod.awards_db_path().exists():
            return None
        kws = " ".join((cluster.get("search_keywords") or [])[:3])
        rows, _ = awards_mod.query_canadabuys_awards(keywords=kws, province=province, limit=20)
        if not rows:
            return None
        summary = awards_mod.summarize_awards(rows)
        return {
            "count": len(rows),
            "median_cad": summary.get("median_cad"),
            "min_cad": summary.get("min_cad"),
            "max_cad": summary.get("max_cad"),
            "top_suppliers": [s["supplier"] for s in summary.get("top_suppliers", [])[:3]],
        }
    except Exception:  # noqa: BLE001
        return None


def _fmt_cad(val: float | None) -> str:
    if val is None:
        return "n/a"
    if val >= 1_000_000:
        return f"C${val / 1_000_000:,.2f}M"
    return f"C${val:,.0f}"


def _render_victory_garden_markdown(payload: dict[str, Any]) -> str:
    shop = payload["shop"]
    core = payload["core_opportunities"]
    pivots = payload["pivot_opportunities"]
    clusters = payload["pivot_lanes"]
    programs = payload["support_programs"]
    warnings = payload["warnings"]

    lines = [
        f"# Victory Garden Mobilization Brief — {shop['company_name']}",
        "",
        f"- **Location:** {shop['location']}",
    ]
    if shop.get("website_url"):
        lines.append(f"- **Website analyzed:** {shop['website_url']} ({len(shop.get('pages_fetched') or [])} page(s) inspected)")
    if shop.get("detected_processes"):
        lines.append(f"- **Detected shop processes & tooling:** {', '.join(shop['detected_processes'])}")
    if shop.get("stated_certs"):
        lines.append(f"- **Stated certifications (from site):** {', '.join(shop['stated_certs'])}")
    else:
        lines.append("- **Stated certifications:** None explicitly detected on site (verify CWB, COR, ISO 9001, CGP, or NCAGE before bidding)")
    lines.append("")

    lines.append(f"## Lane 1 — Core Fit: What You Can Bid Today ({len(core)} matched)")
    if core:
        for idx, o in enumerate(core[:6], 1):
            closes = str(o.get("closing_text") or o.get("closes_at") or "See posting").split(";")[0]
            dom = ", ".join(o.get("domestic_policies") or [])
            dom_s = f" · Domestic: `{dom}`" if dom else ""
            url = o.get("url") or ""
            lines.append(
                f"{idx}. **{o.get('title', 'Untitled')}** (`{o.get('reference', '')}`) — {o.get('buyer', 'Public buyer')} "
                f"({o.get('source', '')}) · Closes: {closes}{dom_s}" + (f" · {url}" if url else "")
            )
    else:
        lines.append("No immediate core-fit notices matched the extracted description; broaden keywords via `search_opportunities`.")
    lines.append("")

    lines.append("## Lane 2 — Victory Garden Pivots: What Your Existing Tooling Can Build Next")
    for cl in clusters[:3]:
        lines.append(f"### {cl['title']} (`{cl['sovereign_lane']}`)")
        lines.append(f"- **Why Canada needs it now:** {cl['why_canada_needs_it']}")
        lines.append(f"- **Typical entry role:** `{cl['typical_role']}` · **Retooling effort:** {cl['retooling_effort']}")
        lines.append(f"- **Gates to verify:** {', '.join(cl['common_gates'])}")
        aw = cl.get("awards_snapshot")
        if aw and aw.get("count"):
            lines.append(
                f"- **Historical federal awards snapshot:** {aw['count']} comparable awards · "
                f"Median {_fmt_cad(aw.get('median_cad'))} (Range {_fmt_cad(aw.get('min_cad'))} – {_fmt_cad(aw.get('max_cad'))})"
            )
        lines.append("")

    if pivots:
        lines.append(f"### Live Adjacent Pivot Tenders ({len(pivots)} ranked)")
        for idx, p in enumerate(pivots[:8], 1):
            closes = str(p.get("closing_text") or p.get("closes_at") or "See posting").split(";")[0]
            feas = p.get("pivot_feasibility", "light_retool")
            bridge = p.get("bridge_type", "tooling_or_qa")
            lane = p.get("sovereign_lane", "general_public")
            dom = ", ".join(p.get("domestic_policies") or [])
            dom_s = f" · Domestic: `{dom}`" if dom else ""
            url = p.get("url") or ""
            lines.append(
                f"{idx}. **[{feas} · {lane}] {p.get('title', 'Untitled')}** (`{p.get('reference', '')}`) — "
                f"{p.get('buyer', 'Public buyer')} · Bridge: `{bridge}` · Closes: {closes}{dom_s}"
                + (f" · {url}" if url else "")
            )
        lines.append("")

    lines.append("## Lane 3 — Canadian Retooling & Industrial Support Programs")
    if programs:
        for pr in programs[:4]:
            name = pr.get("name") or pr.get("title") or "Program"
            agency = pr.get("agency") or pr.get("sponsor") or ""
            url = pr.get("url") or ""
            summary = str(pr.get("summary") or pr.get("description") or "")[:180]
            lines.append(f"- **{name}**" + (f" ({agency})" if agency else "") + f": {summary}" + (f" · {url}" if url else ""))
    else:
        lines.append("Run `match_industrial_support_programs` with your province and equipment upgrade plan to check PrairiesCan, BDC, ISED, and NRCan streams.")
    lines.append("")

    lines.append("## Recommended Next Actions")
    lines.append("1. Pick 1–2 high-fit tenders above and run `get_buyer_award_history` to see who won past awards and at what CAD price.")
    lines.append("2. Run `classify_tender` to generate a lead-time **Requirements Board** (bid bonds, CWB/COR/CGP gates, page-cited clauses).")
    lines.append("3. Verify all eligibility, clearances, and addenda directly on the official CanadaBuys or Alberta Purchasing Connection notice — workspaceAlberta never submits bids or guarantees awards.")
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings[:4]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


async def victory_garden_brief_result(args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Run the full Victory Garden pipeline and return ``(markdown, structured_payload)``."""
    from procurement_core import service

    website_url = str(args.get("website_url") or args.get("url") or "").strip()
    description = str(args.get("description") or "").strip()
    company_name = str(args.get("company_name") or "").strip()
    location = str(args.get("location") or "").strip()
    source = str(args.get("source") or "all").strip().lower()
    if source not in {"all", "federal", "alberta"}:
        source = "all"
    limit = service.clamp_int(args.get("limit"), default=8, minimum=1, maximum=15)

    shop_card, warnings = await asyncio.to_thread(
        extract_website_profile,
        website_url=website_url,
        description=description,
        company_name=company_name,
        location=location,
    )

    # Lane 1: Core Fit (what the business already delivers today)
    core_opps: list[dict[str, Any]] = []
    try:
        _, core_struct = await service.call_tool_text_and_structured(
            "find_matching_opportunities",
            {
                "profile": {
                    "company_name": shop_card["company_name"],
                    "location": shop_card["location"],
                    "description": shop_card["core_description"],
                },
                "source": source,
                "limit": limit,
            },
        )
        if isinstance(core_struct, dict):
            core_opps = [o for o in (core_struct.get("opportunities") or []) if isinstance(o, dict)][:limit]
            for w in (core_struct.get("warnings") or [])[:2]:
                if str(w) not in warnings:
                    warnings.append(str(w))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Core tender lookup degraded: {exc}")

    core_refs = {str(o.get("reference") or "") for o in core_opps if o.get("reference")}

    # Lane 2: Adjacent Victory Garden Pivot candidates across top 3 mobilization clusters
    pivot_lanes: list[dict[str, Any]] = []
    candidate_pool: list[dict[str, Any]] = []
    seen_pivot_refs: set[str] = set(core_refs)
    province_hint = "Alberta" if "alberta" in shop_card["location"].lower() else ""

    for cl in shop_card["matched_clusters"][:3]:
        cl_copy = dict(cl)
        cl_copy["awards_snapshot"] = await asyncio.to_thread(_warm_cluster_awards, cl_copy, province_hint)
        pivot_lanes.append(cl_copy)

        query_kw = " ".join((cl.get("search_keywords") or [])[:3])
        if not query_kw:
            continue
        try:
            _, p_struct = await service.call_tool_text_and_structured(
                "search_opportunities",
                {"keywords": query_kw, "source": source, "limit": 8},
            )
            raw_list = (p_struct.get("opportunities") or []) if isinstance(p_struct, dict) else []
            for o in raw_list:
                if not isinstance(o, dict):
                    continue
                ref = str(o.get("reference") or "")
                if not ref or ref in seen_pivot_refs:
                    continue
                seen_pivot_refs.add(ref)
                tagged = dict(o)
                tagged["pivot_cluster_id"] = cl["id"]
                tagged["pivot_cluster_title"] = cl["title"]
                tagged["pivot_feasibility"] = cl["typical_role"]
                tagged["bridge_type"] = "cert_or_clearance" if cl["common_gates"] else "tooling_or_qa"
                tagged["sovereign_lane"] = cl["sovereign_lane"]
                candidate_pool.append(tagged)
        except Exception:  # noqa: BLE001
            continue

    # Stage 3: TypeSafe Jev Pivot Classification (`jev-pivot-v1`)
    jev_verdicts, jev_warnings = await asyncio.to_thread(classify_pivots_with_jev, shop_card, candidate_pool)
    warnings.extend(w for w in jev_warnings if w not in warnings)

    ranked_pivots: list[dict[str, Any]] = []
    for item in candidate_pool:
        ref = str(item.get("reference") or "")
        verdict = jev_verdicts.get(ref)
        if verdict:
            if verdict["pivot_feasibility"] == "unlikely":
                continue
            item = {**item, **verdict, "jev_classified": True}
        else:
            item = {**item, "jev_classified": False}
        ranked_pivots.append(item)

    ranked_pivots.sort(
        key=lambda o: (
            PIVOT_RANK.get(str(o.get("pivot_feasibility") or ""), 0),
            1 if o.get("domestic_policies") else 0,
            1 if o.get("sovereign_lane") in {"defence_security", "arctic_logistics", "critical_infrastructure"} else 0,
        ),
        reverse=True,
    )
    ranked_pivots = ranked_pivots[:limit]

    # Lane 3: Industrial Support & Retooling Programs (deterministic catalog match)
    support_programs: list[dict[str, Any]] = []
    try:
        catalog = industrial_programs.load_catalog()
        bucket = industrial_programs.location_bucket(shop_card["location"])
        norm_text = business_fit.normalize_text(
            " ".join([shop_card["core_description"], " ".join(shop_card["detected_processes"]), shop_card["location"]])
        )
        activity = business_fit.activity_label(shop_card["core_description"])
        scored_progs: list[tuple[int, dict[str, Any]]] = []
        for prog in catalog.get("programs") or []:
            section = industrial_programs._section_for(prog, bucket)
            if bucket != "other" and section != "applies":
                continue
            if bucket == "other" and section not in {"applies", "national_note"}:
                continue
            sc, _reasons = industrial_programs._program_score(prog, norm_text, shop_card["detected_processes"], activity)
            if sc > 0 or prog.get("audience") == "broad":
                scored_progs.append(
                    (
                        sc,
                        {
                            "id": prog.get("id", ""),
                            "name": prog.get("name", ""),
                            "agency": prog.get("delivery") or prog.get("agency") or "",
                            "summary": prog.get("summary") or prog.get("what_it_does") or "",
                            "url": prog.get("url") or "",
                        },
                    )
                )
        scored_progs.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
        support_programs = [p for _, p in scored_progs[:5]]
    except Exception:  # noqa: BLE001
        pass

    payload = {
        "kind": "victory_garden_brief",
        "shop": {
            "company_name": shop_card["company_name"],
            "website_url": shop_card["website_url"],
            "location": shop_card["location"],
            "pages_fetched": shop_card["pages_fetched"],
            "detected_processes": shop_card["detected_processes"],
            "stated_certs": shop_card["stated_certs"],
        },
        "core_count": len(core_opps),
        "pivot_count": len(ranked_pivots),
        "core_opportunities": core_opps,
        "pivot_lanes": pivot_lanes,
        "pivot_opportunities": ranked_pivots,
        "support_programs": support_programs,
        "warnings": warnings,
    }
    markdown = _render_victory_garden_markdown(payload)
    return markdown, payload


async def victory_garden_brief(args: dict[str, Any]) -> str:
    markdown, _ = await victory_garden_brief_result(args)
    return markdown
