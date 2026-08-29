# Deadline Sweep — 2026-08-26

Generated 2026-08-26 ~21:20 MDT (2026-08-27 03:20 UTC). Lookahead window: 2026-08-26 → 2026-09-09 (next 14 days).

## Scope and method

- **Sources:** CanadaBuys (federal) and Alberta Purchasing Connection (APC), via the hosted endpoint `https://elbowsupknivesout.warreandvavasour.com`.
- **Calls:** `POST /deadlines` (`list_deadlines`, `source=federal|alberta`, `days=14`, `limit=50`) for the raw deadline lists, `POST /matches` (`find_matching_opportunities`, `days=14`, inline profile for a custom-AI/procurement-software shop) to surface AI-fit items across the full window, and `GET /details/{reference}` to confirm scope and eligibility on the AI-fit candidates. All live calls returned HTTP 200; no failures to record.
- **Volume:** both sources have **more than 50 open items closing in the window** (the 50-item cap truncated each list). A pure "soonest-closing" list would therefore be dominated by same-day federal notices. To keep this to the requested **up-to-40 items** while remaining useful to Workspace Alberta, the table below keeps **all 7 software/AI-fit items** found in the window and fills the rest with the soonest-closing remaining items, balanced across the two sources (19 federal, 21 Alberta).
- **Fit line** is judged against Workspace Alberta's actual business — **custom AI tools and procurement software** — not generic IT.
- **Source URL:** each title links to its live posting (CanadaBuys tender notice or APC opportunity page).
- **Timezone caveat:** deadlines are shown as returned by each source API — CanadaBuys times are Eastern (ET), APC times are Mountain (MT). Cross-source ordering is approximate because of this; ordering within a source is exact.

## Sweep table (40 items)

| # | Deadline | Reference | Title | Source | Fit |
|---:|---|---|---|---|---|
| 1 | 2026-08-27T08:00 MT | `AB-2026-05379` | [Prairie Land School Division - Request for Proposal - Outdoor Learning Space](https://purchasing.alberta.ca/opportunity/2026/5379) | APC | Skip — outdoor construction (school learning space) |
| 2 | 2026-08-27T12:00 ET | `cb-621-72087923` | [Leading in Complex Systems – In-Person Training](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-621-72087923) | CanadaBuys | Skip — in-person systems-thinking training delivery |
| 3 | 2026-08-27T13:00 ET | `cb-254-50562195` | [CCTV installation services for RCMP in PEI and NS](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-254-50562195) | CanadaBuys | Skip — services (not software) |
| 4 | 2026-08-27T13:00 ET | `cb-53-60958033` | [Waste Removal Services](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-53-60958033) | CanadaBuys | Skip — services (not software) |
| 5 | 2026-08-27T14:00 MT | `AB-2026-05560` | [Technology and Innovation - Negotiated Request for Proposal - Self-sustaining Application](https://purchasing.alberta.ca/opportunity/2026/5560) | APC | Fit — AI-enabled application services under AMSA (SOW No. 14; closes 08-27) |
| 6 | 2026-08-27T14:00 MT | `AB-2026-05409` | [City of Lloydminster - Invitation to Bid - Old City Shop - Site Reclamation](https://purchasing.alberta.ca/opportunity/2026/5409) | APC | Skip — construction |
| 7 | 2026-08-27T14:00 MT | `AB-2026-05619` | [Municipality of Crowsnest Pass - Request for Quotes - 20 Avenue Rehabilitation](https://purchasing.alberta.ca/opportunity/2026/5619) | APC | Skip — construction |
| 8 | 2026-08-27T14:00 MT | `AB-2026-05681` | [Infrastructure - Invitation to Bid - MIDLAND PROVINCIAL PARK - ROYAL TYRRELL MUSEUM OF PA…](https://purchasing.alberta.ca/opportunity/2026/5681) | APC | Skip — services (not software) |
| 9 | 2026-08-27T14:00 MT | `AB-2026-05362` | [University of Calgary - Negotiated Request for Proposal - 2026RFP0046 Steam Sterilizers a…](https://purchasing.alberta.ca/opportunity/2026/5362) | APC | Skip — goods/equipment |
| 10 | 2026-08-27T14:00 MT | `AB-2026-05493` | [Town of Whitecourt - Request for Proposal - Town of Whitecourt Compensation Review](https://purchasing.alberta.ca/opportunity/2026/5493) | APC | Skip — services (not software) |
| 11 | 2026-08-27T14:00 MT | `AB-2026-05530` | [Town of Canmore - Request for Proposal - NEIGHBOURHOOD DEEP UTILITY REPLACEMENT – PHASE 2](https://purchasing.alberta.ca/opportunity/2026/5530) | APC | Skip — construction |
| 12 | 2026-08-27T14:00 MT | `AB-2026-05564` | [Parkland County - Request for Proposal - Parkland County Valve Replacement Project](https://purchasing.alberta.ca/opportunity/2026/5564) | APC | Skip — services (not software) |
| 13 | 2026-08-27T14:00 ET | `cb-236-30865714` | [Long-Endurance, Electric-Powered, Hybrid Gyroplane–Helicopter Vertical Takeoff and Landin…](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-236-30865714) | CanadaBuys | Skip — goods/equipment |
| 14 | 2026-08-27T14:00 ET | `cb-291-44852968` | [Seal Assembly](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-291-44852968) | CanadaBuys | Skip — goods/equipment |
| 15 | 2026-08-27T14:00 ET | `cb-196-82966834` | [Dummy Cord Detonating, Inert](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-196-82966834) | CanadaBuys | Skip — goods/equipment |
| 16 | 2026-08-27T14:00 ET | `cb-314-75088154` | [GE46 Electoral Material –  Self Adhesive Floor Marking Strip](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-314-75088154) | CanadaBuys | Skip — goods/equipment |
| 17 | 2026-08-27T14:00 ET | `cb-982-84111430` | [RFP Seating - Oakville office](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-982-84111430) | CanadaBuys | Skip — goods/equipment |
| 18 | 2026-08-27T14:00 ET | `cb-865-53597242` | [Installation Services – NCR – CORCAN](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-865-53597242) | CanadaBuys | Skip — services (not software) |
| 19 | 2026-08-27T14:00 ET | `cb-120-30888735` | [Lease of Two Highway Tractors with Sleepers - 1 Oct 2026 - 31 March 2027](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-120-30888735) | CanadaBuys | Skip — services (not software) |
| 20 | 2026-08-27T14:00 ET | `cb-988-85502265` | [In-Service Support for the Arctic Mobility Amphibious Vehicles](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-988-85502265) | CanadaBuys | Skip — mixed goods/services (not software) |
| 21 | 2026-08-27T14:00 ET | `cb-180-40241040` | [Classified Solutions Modernization - DFATD](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-180-40241040) | CanadaBuys | Skip — classified IM/IT modernization staffing, not a tool build |
| 22 | 2026-08-27T14:00 ET | `cb-975-91831666` | [Gender-based Analysis plus (GBA plus) Training Facilitators](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-975-91831666) | CanadaBuys | Skip — GBA+ training facilitation |
| 23 | 2026-08-27T14:00 ET | `cb-51-24308482` | [Hotel Accommodation block](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-51-24308482) | CanadaBuys | Skip — services (not software) |
| 24 | 2026-08-27T14:00 ET | `cb-687-35070409` | [Provision of Laundry and dry-cleaning services to Department of National Defence](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-687-35070409) | CanadaBuys | Skip — services (not software) |
| 25 | 2026-08-27T14:00 ET | `cb-804-31438240` | [Church Leader / Church Administrator](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-804-31438240) | CanadaBuys | Skip — services (not software) |
| 26 | 2026-08-27T14:00 ET | `WS5658186389-Doc5658229348` | [50100-269137 – RISO - Fresh Bread – CSC](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/ws5658186389-doc5658229348) | CanadaBuys | Skip — goods/equipment |
| 27 | 2026-08-27T14:00 MT | `AB-2026-05588` | [Mountain View Regional Water Services Commission - Request for Proposal - MVRWSC - Anthon…](https://purchasing.alberta.ca/opportunity/2026/5588) | APC | Skip — construction |
| 28 | 2026-08-27T14:00 MT | `AB-2026-05213` | [Silvera for Seniors - Invitation to Bid - 3 Suite Renewal - Friendship Manor](https://purchasing.alberta.ca/opportunity/2026/5213) | APC | Skip — construction |
| 29 | 2026-08-27T14:00 MT | `AB-2026-05419` | [City of Calgary - Request for Quotes -  RFQ 26-0168 Demolition of Ogden Block](https://purchasing.alberta.ca/opportunity/2026/5419) | APC | Skip — construction |
| 30 | 2026-08-27T14:00 MT | `AB-2026-05579` | [Justice - Request for Proposal - Graphic Design Services for the Alberta Human Rights Com…](https://purchasing.alberta.ca/opportunity/2026/5579) | APC | Skip — services (not software) |
| 31 | 2026-08-27T14:00 MT | `AB-2026-05672` | [Town of Blackfalds - Invitation to Bid - Sterling Industries Sports Park Baseball Diamond](https://purchasing.alberta.ca/opportunity/2026/5672) | APC | Skip — construction |
| 32 | 2026-08-27T14:00 MT | `AB-2026-05702` | [Environment and Protected Areas - Request for Proposal - Security of Water Supply in Albe…](https://purchasing.alberta.ca/opportunity/2026/5702) | APC | Skip — services (not software) |
| 33 | 2026-08-27T14:00 MT | `AB-2026-05687` | [Forestry and Parks - Request for Quotes - ATV/Quad 400cc](https://purchasing.alberta.ca/opportunity/2026/5687) | APC | Skip — goods/equipment |
| 34 | 2026-08-27T14:01 MT | `AB-2026-05349` | [Transportation and Economic Corridors - Invitation to Bid - TND0025114 - Hwy 841 Erosion …](https://purchasing.alberta.ca/opportunity/2026/5349) | APC | Skip — construction |
| 35 | 2026-08-28T14:00 ET | `cb-40-97221487` | [TBIPS AI Support Services](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-40-97221487) | CanadaBuys | Fit — TBIPS AI support services (invited SA holders only) |
| 36 | 2026-08-28T14:00 MT | `AB-2026-05357` | [Technology and Innovation - Negotiated Request for Proposal - TRA Tax and Revenue Managem…](https://purchasing.alberta.ca/opportunity/2026/5357) | APC | Fit — revenue-management software modernization (open competitive, 5-yr) |
| 37 | 2026-08-30T14:00 ET | `cb-630-4686939` | [TBIPS: Department of Foreign Affairs Trade and Development – Professional Services for Da…](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-630-4686939) | CanadaBuys | Fit — data, analytics & AI foundations for a digital service (TBIPS) |
| 38 | 2026-09-01T13:00 MT | `AB-2026-05745` | [Technology and Innovation - Negotiated Request for Proposal - AMSA Application Developmen…](https://purchasing.alberta.ca/opportunity/2026/5745) | APC | Fit — custom AI application build (AI-assisted EAL benchmark assessment app, K–6) |
| 39 | 2026-09-01T14:00 MT | `AB-2026-05671` | [Technology and Innovation - Negotiated Request for Proposal - Self-sustaining Application…](https://purchasing.alberta.ca/opportunity/2026/5671) | APC | Fit — AI-enabled application services under AMSA (SOW No. 15) |
| 40 | 2026-09-08T16:00 MT | `AB-2026-05595` | [Technology and Innovation - Negotiated Request for Proposal - Self-sustaining Application…](https://purchasing.alberta.ca/opportunity/2026/5595) | APC | Fit — AI-enabled application services under AMSA (SOW No. 17) |

## AI-fit items (7) and what to do

1. **AB-2026-05745** — AI-assisted EAL Benchmark Assessment Application (custom AI build). → **bid brief written.**
2. **cb-630-4686939** — GAC data/analytics/AI foundations. → **bid brief written.**
3. **AB-2026-05671** — AMSA self-sustaining application services, "AI-Enabled Service Delivery". → **bid brief written.**
4. **AB-2026-05595** — same AMSA vehicle (SOW No. 17), closes 09-08; hold if the shop is AMSA-eligible.
5. **AB-2026-05560** — same AMSA vehicle (SOW No. 14), closes 08-27; too tight for this run.
6. **AB-2026-05357** — TRA revenue-management system modernization; the one **open-competitive (no pre-qualification)** software build in the window; strong backup brief.
7. **cb-40-97221487** — TBIPS "AI Support Services" but **selective tendering (invited SA holders only)**; skip unless already invited.

**Eligibility note (matters for go/no-go):** the Alberta "Technology and Innovation" software RFPs (#1, #3, #4, #5) are all issued **under the Application Master Services Agreement (AMSA)** — a pre-qualified supplier vehicle — and the two federal AI items (#2, #7) are **TBIPS Supply Arrangement** tenders. Confirm the shop holds (or can join) these vehicles before committing; AB-2026-05357 is the one AI-adjacent build with no such gate.

Full go/no-go for the earliest item (`AB-2026-05379`) is in `docs/GO-NOGO-AB-2026-05379.md`.
