# WorkspaceAlberta Terminal — Canonical Spec

Single source of truth for the physical terminal. Use this as the reference for visual
artifacts (renders, exploded views, desk mockups, spec sheets). Live per-item prices and
sourcing notes live in `workspace-alberta-spec-research.md`; this file is the consolidated,
stable summary.

## Design decision (anchor)

Treat the Raspberry Pi 5 as a **visible control node and brand artifact, not the whole
compute story.** The premium object is the *whole terminal*: dual monitors, central mast,
brushed-aluminum plinth, cable discipline, and the managed WorkspaceAlberta software/support.
Heavy reasoning runs against hosted/sovereign models (Cohere Command A+) and the live
WorkspaceAlberta endpoint — the Pi is the face, not the engine.

Reference model: the Bloomberg terminal. Industrial-but-executive; trading terminal, not gamer rig.

## Canonical build — "Value-premium" prototype cart (~$2,949.68 CAD)

The build we render and prototype first. Hardware subtotal only (excludes assembly,
branding, machining revisions, shipping, tax, support margin, software/subscription).

| Role | Item |
|---|---|
| Compute core | Raspberry Pi 5 16GB (PiShop Canada) |
| Power | Raspberry Pi 45W USB-C power supply, white |
| Display I/O | 2× white micro-HDMI → HDMI cables |
| Cooling (visual) | Pi5 Passive Cooling CNC Box, silver |
| Cooling accent | Copper heatsink 4-pack |
| Monitor arm | Ergotron LX Dual Stacking Arm, tall pole, polished aluminum |
| Displays | 2× ALOGIC Clarity 27" 4K |
| Keyboard | Apple Magic Keyboard with Touch ID + Numeric Keypad, white |
| Pointer | Apple Magic Mouse, white, USB-C |
| Base | Prototype aluminum plinth — Hammond / SendCutSend allowance (custom W&V part) |

The aluminum plinth is a **custom WorkspaceAlberta part**, not an off-the-shelf case: it
mounts the Pi 5, NVMe module, exposed cooler, and rear cable exits as one deliberate desk object.

## Package tiers (hardware subtotal, CAD)

| Tier | Direction | Subtotal |
|---|---|---:|
| Flagship Apple/aluminum | dual Apple Studio Displays, Ergotron polished aluminum pole, custom base | $6,067.70 |
| **Value premium (canonical)** | dual ALOGIC Clarity 27" 4K, Ergotron pole, custom/finished base | **$2,949.68** |
| White statement | dual Samsung 32" Smart Monitor M8 (white), white Desky arm, custom base | $2,759.58 |
| Prototype | dual LG 27" 4K white/silver, budget white tall pole, Hammond base | $1,805.67 |

All tiers share the Pi 5 control-node core, Apple input set, and central-mast silhouette;
they differ in displays, arm, and base finish. Commercial offer is one universal device at a
single **$4,300/month all-in lease** (see `Company2.0/company/terminal.md`).

## Software & support layer (what makes it a terminal)

- Procurement intelligence over CanadaBuys + Alberta Purchasing Connection, Cohere Command A+
  analysis, E2B bid-room processing — hosted, live, Canadian. See the deployed MCP endpoint.
- Pi provisioning: `installer/install-workspace-alberta-pi.sh`
- Remote support / fleet access: `docs/deployment-ops/tailscale-pi-remote-support.md`

## Visual artifacts to build (brief)

These should all read from this spec so geometry and parts stay consistent:

1. **Hero render** — terminal on a desk, dual ALOGIC displays on the Ergotron tall pole,
   Pi 5 plinth visible at the base. Industrial-executive lighting.
2. **Exploded view** — Pi 5 + CNC box + copper heatsinks + NVMe + plinth + cable exits.
3. **Desk silhouette** — the central-mast "Bloomberg split" outline, for site + deck use.
4. **Cable-routing diagram** — single white USB-C PD into the base, hidden power distribution,
   clean exits (mirrors the power-architecture rules in the research doc).
5. **Brand-object close-up** — the exposed Pi as control node, brushed aluminum + copper accent.
6. **Spec one-pager** — this BOM + the $4,300/mo offer, print/PDF for sales.
