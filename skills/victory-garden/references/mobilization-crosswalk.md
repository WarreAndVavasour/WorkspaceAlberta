# Canadian Mobilization Crosswalk (Existing Tooling → Urgent Public Demand)

Reference lexicon used by the **Victory Garden** skill and `procurement_core/victory_garden.py` (`jev-pivot-v1`) to bridge peacetime Canadian small-business shop floors into what Canada is buying during the 18-month industrial mobilization sprint.

| Existing Shop Floor / Equipment | Victory Garden Pivot Lane | Typical Role | Gates to Verify |
|---|---|---|---|
| **Oilfield / industrial CNC machine shops** (5-axis mills, lathes, CMM metrology, valves/pumps) | Precision defence, Coast Guard marine spares, NATO vehicle drivetrains, UAV tooling | `subcontract_tier2` | Controlled Goods Program (CGP), ISO 9001 / AS9100, NATO NCAGE |
| **CWB welding bays, structural steel, custom trailers & skid shops** | Mobile command/generator skids, bridge repair steel, protective enclosures, Arctic sleds | `direct_redeploy` | CWB W47.1/W47.2, COR safety, Buy Canadian steel mill test reports |
| **Commercial HVAC, boilers, refrigeration & sheet-metal shops** | Ruggedized equipment enclosures, marine/base HVAC, CBRN & hospital air handling | `direct_redeploy` | Red Seal mechanical tickets, COR safety, Buy Canadian content |
| **Upholstery, commercial sewing, awning, tarp & canvas shops** | Field shelters, insulated Arctic equipment covers, tactical webbing, medical soft goods | `light_retool` | CAN/CGSB textile specs, flame-retardant / cold-crack certs |
| **Sawmills, truss plants, modular home builders, cabinet/millwork shops** | Rapid-deployable barracks, northern housing, timber bridges, ISPM-15 export/munitions crating | `direct_redeploy` | ISPM-15 (CFIA), CSA A277 (modular), Buy Canadian lumber |
| **Thermoforming, rotomoulding, fibreglass boats & composite shops** | Ruggedized transit cases, UAV/drone airframes, marine floats, field water & fuel tanks | `light_retool` | MIL-STD / IP67 testing, ISO 9001, CGP (if defence UAV) |
| **Electrical contractors, CSA panel shops, solar/battery & SCADA crews** | Backup generators, substation hardening, remote Arctic microgrids, base controls | `direct_redeploy` | CSA C22.2 / UL 508A, Master Electrician, COR safety |
| **Civil, concrete, paving, excavation & aggregate contractors** | Airfield/northern runway repair, port/bridge hardening, perimeter barriers, drainage | `direct_redeploy` | 10% bid / 50% performance bonding, COR safety, Buy Canadian steel/concrete |
| **Trucking, lowboys, crane/rigging, heavy mechanics & yards** | Heavy haulage, northern/Arctic resupply, emergency staging yards, fleet maintenance | `direct_redeploy` | NSC safety fitness, TDG (Dangerous Goods), WCB clearance |
| **Commercial drone (RPAS), telecom towers, geomatics & Canadian IT/cyber** | ISR drone ops, remote Arctic comms maintenance, LiDAR survey, sovereign cybersecurity | `direct_redeploy` | Reliability / Secret clearance, Transport Canada RPAS Advanced, Canadian residency |
| **Commercial bakeries, meat packers, greenhouses & cold-chain food** | DND base rations, northern/Arctic food security, emergency institutional supply | `direct_redeploy` | CFIA / Safe Food for Canadians Licence, HACCP / GFSI |
| **Safety supply, hazmat, environmental remediation & facilities** | Emergency response, water/hazmat decon, medical supply logistics, base facility upkeep | `direct_redeploy` | Health Canada MDEL (if devices), COR safety, Reliability screening |
