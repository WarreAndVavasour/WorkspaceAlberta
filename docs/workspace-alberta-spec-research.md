# WorkspaceAlberta Spec Research

Live equipment list for a premium, Bloomberg-inspired AI/product-development workspace.

Research snapshot: 2026-05-25. Prices are live-listing snapshots and should be rechecked before purchase. Currency is CAD unless marked USD.

## Product intent

WorkspaceAlberta should feel like a dedicated machine, not a laptop accessory.

The reference model is Bloomberg LP: a high-trust, dedicated workspace for executives who need ideas, data, product work, and agentic execution in one place. The physical object should justify a premium setup fee and subscription before anyone sees a line of software.

Business model note: the customer does not own the equipment. The hardware is leased as part of the WorkspaceAlberta subscription and comes back when the subscription ends. The setup fee covers installation, configuration, onboarding, and deployment time; the monthly fee covers the ongoing workspace, support, updates, workflows, and equipment access. Psychologically, the first payment should be framed as setup plus the first month of hands-on AI adoption/training, not as buying hardware. That lowers sunk-cost anxiety while still creating a serious commitment.

The look we are aiming for:

- exposed, deliberate, visibly technical Raspberry Pi 5 core
- brushed aluminum or white/silver hardware palette
- controlled cable routing, no consumer clutter
- dual-monitor desk presence with a central mast or clean symmetric arms
- industrial-but-executive: more trading terminal than gamer rig

## Current recommendation

Build the prototype around the Raspberry Pi 5 16GB, but treat the Pi as a visible control node and brand artifact, not as the full compute story.

The AI HAT is optional. It creates a useful visual and demo story, especially for camera inference, but the strongest customer impression will come from the monitors, arm geometry, aluminum base, cable discipline, and the WorkspaceAlberta software experience.

Recommended path:

1. Prototype with Pi 5 16GB, white power, two white HDMI cables, silver/copper cooling, and a weighted aluminum base.
2. Use a premium central-pole dual arm if the monitors are not too heavy.
3. Choose either Apple Studio Displays for the flagship $5,000 physical package or ALOGIC/Samsung for a lower-cost prototype.
4. Add M.2 NVMe as a standard local workspace/boot module.
5. Add Raspberry Pi AI HAT+ only if we have a camera/object-recognition demo that makes the hardware acceleration visible and explainable.

Hardware design update: the exact open aluminum plinth shown in the current reference image does not appear to exist as a polished off-the-shelf Raspberry Pi 5 case. Treat the case as a custom WorkspaceAlberta part, not a shopping problem. The flagship hardware object should be a custom brushed-aluminum `Open Compute Plinth` that mounts the Pi 5, the NVMe module, the exposed copper/silver cooler, and rear cable exits as one deliberate desk object. Off-the-shelf Pi cases can inform the thermals, but they either hide the board too much or look like maker accessories.

## Build packages

These totals include hardware only. They do not include assembly labour, branding, cable sleeves, custom machining revisions, shipping, taxes, support margin, software setup, or subscription onboarding.

| Package | Hardware direction | Estimated hardware total |
|---|---|---:|
| Flagship Apple/aluminum | dual Apple Studio Displays, Ergotron polished aluminum central pole, custom fabricated base, Apple keyboard and mouse | $6,067.70 CAD |
| Value premium | dual ALOGIC Clarity 27 inch 4K monitors, Ergotron polished aluminum central pole, custom/finished base, Apple keyboard and mouse | $2,949.68 CAD |
| White statement | dual Samsung 32 inch Smart Monitor M8 white displays, white Desky arm, custom/finished base, Apple keyboard and mouse | $2,759.58 CAD |
| Prototype | dual LG 27 inch 4K white/silver monitors, budget white tall pole, Hammond base, Apple keyboard and mouse | $1,805.67 CAD |

The flagship package clears the $5,000 visual bar. The value-premium and white-statement packages are better for early mockups, demos, and procurement experiments.

## Core Raspberry Pi 5 bill of materials

| Role | Vendor | Product | Price | Link | Notes |
|---|---|---:|---|---|
| Compute core | PiShop Canada | Raspberry Pi 5/16GB | $426.95 CAD | https://www.pishop.ca/product/raspberry-pi-5-16gb/ | Canadian source. High live price, but it is the right board for the premium spec. |
| Compute core alternate | CanaKit | Raspberry Pi 5 16GB | $305.00 USD | https://www.canakit.com/raspberry-pi-5-16gb.html | US price found. Useful if ordering through CanaKit ecosystem. |
| Power, recommended | PiShop Canada | Raspberry Pi 45W USB-C Power Supply, white | $21.45 CAD | https://www.pishop.ca/product/raspberry-pi-45w-usb-c-power-supply-white/ | White, clean, higher-headroom official Raspberry Pi USB-C PD supply. |
| Power, minimum official class | PiShop Canada | Raspberry Pi 27W USB-C Power Supply, white US | $16.95 CAD | https://www.pishop.ca/product/raspberry-pi-27w-usb-c-power-supply-white-us/ | Pi 5 uses USB-C. Recommended class is 5V/5A, sold as the 27W supply. |
| HDMI cable | PiShop Canada | Micro-HDMI to Standard HDMI, 2m, white | $8.95 CAD each | https://www.pishop.ca/product/micro-hdmi-to-standard-hdmi-a-m-2m-cable-white/ | Buy two for dual displays. Pi 5 uses two micro-HDMI outputs. |
| Premium exposed cooling | PiShop Canada | Pi5 Passive Cooling CNC Box, silver | $23.95 CAD | https://www.pishop.ca/product/pi5-passive-cooling-cnc-box-silver/ | Best simple silver/aluminum visual option. Turns the Pi into a metal object. |
| Copper visual accent | PiShop Canada | Raspberry Pi 5 copper heatsink 4-pack | $5.45 CAD | https://www.pishop.ca/product/set-of-heatsinks-for-raspberry-pi-5-4-pack-copper/ | Good exposed-board accent. Use if we want copper visible rather than enclosed silver. |
| Active cooling baseline | PiShop Canada | Raspberry Pi Active Cooler | $7.00 CAD | https://www.pishop.ca/product/raspberry-pi-active-cooler/ | Most practical for sustained load, but less visually premium. |
| Active aluminum cooler | PiShop Canada | Dedicated All-In-One Aluminum Cooler for Raspberry Pi 5, PWM | $7.95 CAD | https://www.pishop.ca/product/dedicated-all-in-one-aluminum-cooler-for-raspberry-pi-5-pwm/ | Small active aluminum look. Good compromise if thermals matter. |
| White case alternate | CanaKit | CanaKit Turbine Case for Raspberry Pi 5, white | $14.95 USD | https://www.canakit.com/canakit-raspberry-pi-5-turbine-case-white.html | Matches white theme, but hides the board more than ideal. |

Power note: Raspberry Pi 5 power input is USB-C. Use a Pi 5-specific 5V/5A USB-C PD supply. A generic phone charger may boot the board, but it weakens the premium story and can cause peripheral-current limits or undervoltage.

## Power architecture for external fans

If we add a dramatic external fan or adapted CPU cooler, power cannot be an afterthought. The clean build should hide fan power inside the aluminum base rather than hanging another wall wart off the desk.

Rules:

- Do not power a 12V PC CPU fan directly from the Raspberry Pi fan header. The Pi fan header is for Pi-class 5V PWM cooling, not a 12V desktop cooler fan.
- Do not power fans from 3.3V GPIO.
- A small 5V fan can run from the Pi 5 fan header or 5V rail if current is modest, but it still competes with the Pi and peripherals.
- A 12V Noctua CPU-cooler fan needs a separate 12V rail, or a USB-C PD trigger/buck-boost power module hidden in the base.
- If the Pi controls fan speed with PWM, use a proper driver/MOSFET or 4-wire PWM fan interface and a shared ground. Do not improvise fan power through GPIO pins.

Recommended physical design:

1. One white USB-C PD supply enters the aluminum base.
2. Inside the base, a hidden power distribution board creates:
   - clean 5V/5A USB-C output for the Raspberry Pi 5
   - separate 5V or 12V fan rail, depending on fan choice
3. The Pi receives normal USB-C power.
4. The external fan receives separate power from the base.
5. Only a small PWM/control lead, if needed, runs between the Pi and fan driver.

Representative fan loads:

| Fan class | Voltage | Current | Power | Fit for WorkspaceAlberta |
|---|---:|---:|---:|---|
| Tiny 5V Pi-class fan | 5V | ~0.05A | ~0.25W | Electrically easy, visually not dramatic. |
| Medium 5V fan | 5V | ~0.25A | ~1.25W | Possible from a dedicated 5V rail; avoid cluttering the Pi rail. |
| Noctua NH-L9i-class 92mm slim fan | 12V | ~0.11A | ~1.32W | Needs hidden 12V rail. Mechanically possible, visually wrong unless modified. |

Conclusion: for the premium build, the base should be the power system. The Pi should not be asked to power a showpiece cooler. If the cooler is only copper/brass passive, the problem disappears and the build stays cleaner.

## Optional AI accelerator

The AI HAT is not required for the first premium desk object unless we can show a local camera/inference demo. It is a good optional story, not the center of the product.

| Role | Vendor | Product | Price | Link | Verdict |
|---|---|---:|---|---|
| Sane official AI option | PiShop Canada | Raspberry Pi AI HAT+ 13 TOPS | $101.45 CAD | https://www.pishop.ca/product/raspberry-pi-ai-hat-13-tops/ | Use only if we have a visible local AI demo. Clean official HAT+ form factor. |
| Premium official AI option | PiShop Canada | Raspberry Pi AI HAT+ 26 TOPS | $159.45 CAD | https://www.pishop.ca/product/raspberry-pi-ai-hat-26-tops/ | Best premium spec line, but likely overkill for WorkspaceAlberta unless demos need it. |
| Older/alternate Hailo route | CanaKit | Raspberry Pi AI Kit | $70.00 USD, sold out when checked | https://www.canakit.com/raspberry-pi-ai-kit.html | Less elegant than the official AI HAT+. Not first choice. |
| Alternate Hailo route | Seeed Studio | Raspberry Pi AI Kit | $74.99 USD | https://www.seeedstudio.com/Raspberry-Pi-AI-Kit-p-5900.html | Acceptable if sourcing requires it, but not as clean as PiShop official HAT+. |
| Avoid for premium build | Seeed Studio | Google Coral USB Accelerator | $111.00 USD | https://www.seeedstudio.com/Coral-USB-Accelerator-p-2899.html | External dongle/cable clutter. Poor fit for a polished exposed device. |

## Monitors

Monitors are the most important hardware choice. They set the customer’s first impression and determine whether the installation feels like a dedicated executive terminal.

| Tier | Vendor | Product | Size | Resolution | Look | Price | Link | Notes |
|---|---|---:|---:|---|---|---:|---|---|
| Flagship | Apple Canada | Apple Studio Display, standard glass/base config | 27 in | 5120 x 2880 5K | silver aluminum | $2,099.00 CAD each | https://www.apple.com/ca/shop/buy-mac/studio-display | Strongest premium look. Best physical justification for a $5,000 install. Dual setup is expensive but iconic. |
| Value premium | ALOGIC Canada | CLARITY 27 inch UHD 4K Monitor with 90W USB-C hub | 27 in | 3840 x 2160 4K | Apple-like silver/aluminum | $639.99 CAD sale, $799.99 regular | https://ca.alogic.co/products/clarity-27-uhd-4k-monitor | Strong Apple Studio Display alternative. Good dual setup candidate. |
| White statement | Samsung Canada | Smart Monitor M8 M80F 4K, white | 32 in | 3840 x 2160 4K | white | $749.99 CAD sale, $899.99 regular | https://www.samsung.com/ca/monitors/smart/smart-monitor-m8-32-inch-smart-tv-apps-4k-uhd-ls32fm801unxza/ | Most visually white/designer. Less pro-panel than Apple/LG/BenQ, but excellent showroom presence. |
| Budget clean | LG Canada | LG 27UP850K-W 27 inch UHD 4K IPS | 27 in | 3840 x 2160 4K | white/silver | $429.99 CAD | https://www.lg.com/ca_en/monitors/uhd-4k-5k/27up850k-w/ | Clean lower-cost 4K option. Backorder shown when checked. |
| Mac-specific alternate | BenQ US | MA270U / MA270UP Mac-ready monitor | 27 in | 3840 x 2160 4K | light silver/white-gray | $549.99-$579.99 USD | https://www.benq.com/en-us/monitor/home/ma270u/buy.html | Good MacBook integration, but Canadian direct availability needs confirmation. |
| Large Mac-specific alternate | BenQ US | MA320U / MA320UP | 32 in | 3840 x 2160 4K | light silver/white-gray | $649.99-$699.99 USD | https://www.benq.com/en-us/monitor/home/ma320u/buy.html | Strong 32 inch non-Apple option. US listing only in this pass. |
| Technical best | LG Canada | LG UltraFine evo 32U990A-S 6K Thunderbolt 5 | 32 in | 6K class | silver/black premium | $2,699.99 CAD | https://www.lg.com/ca_en/monitors/uhd-4k-5k/32u990a-s/ | More technical/pro than showroom-white. Expensive, but impressive. |

Monitor recommendation:

- If the goal is to justify the premium install immediately: dual Apple Studio Displays.
- If the goal is to prototype the brand affordably: dual ALOGIC Clarity 27 inch monitors.
- If the goal is a bright white executive object: dual Samsung M8 32 inch monitors.

## Keyboard and pointer

These are obvious but important. The keyboard and mouse are the daily touchpoints, so they should match the brushed aluminum / white executive look rather than feel like commodity peripherals.

| Role | Vendor | Product | Price | Link | Notes |
|---|---|---|---:|---|---|
| Top keyboard | Apple Canada | Magic Keyboard with Touch ID and Numeric Keypad for Mac models with Apple silicon, USB-C, US English, white keys | $229.00 CAD | https://www.apple.com/ca/shop/product/mxk73ll/a/magic-keyboard-with-touch-id-and-numeric-keypad-for-mac-models-with-apple-silicon-usb%E2%80%91c-us-english-white-keys | Best fit. Full-size aluminum/white Apple keyboard with Touch ID and numeric keypad. In stock when checked. |
| Compact keyboard alternate | Apple Canada | Magic Keyboard with Touch ID for Mac models with Apple silicon, USB-C, US English | $179.00 CAD | https://www.apple.com/ca/shop/product/mxck3ll/a/magic-keyboard-with-touch-id-for-mac-models-with-apple-silicon-usb-c-us-english | Cleaner compact footprint if the desk object should stay minimal. |
| Pointer | Apple Canada | Magic Mouse, USB-C, white Multi-Touch surface | $95.00 CAD | https://www.apple.com/ca/shop/product/mxk53am/a/magic-mouse-usb%E2%80%91c-white-multi-touch-surface | Obvious matching pointer. White top, minimal profile, wireless. In stock when checked. |
| Trackpad alternate | Apple Canada | Magic Trackpad, USB-C, white Multi-Touch surface | $159.00 CAD | https://www.apple.com/ca/shop/product/mxk93am/a/magic-trackpad-usb%E2%80%91c-white-multi-touch-surface | Consider for a more gesture-heavy executive desk, but mouse is the default spec. |

Recommended input set: Magic Keyboard with Touch ID and Numeric Keypad plus white USB-C Magic Mouse. Current combined input-device allowance: $324.00 CAD.

## Monitor arms and stands

The central-pole Bloomberg split is feasible, but monitor weight and arm quality matter. Cheap tall-pole arms give the silhouette. Ergotron gives the confidence.

| Role | Vendor | Product | Price seen | Link | Notes |
|---|---|---|---:|---|---|
| Best central-pole fit | Ergotron | LX Dual Stacking Arm, Tall Pole, polished aluminum, 45-509-216 | ~$560-$750 CAD street | https://www.ergotron.com/en-ca/products/product-details/45-509 | Best match for Bloomberg-like central mast and offset arms. Premium polished aluminum. |
| Premium side-by-side | Ergotron | LX Dual Side-by-Side Arm, polished aluminum | ~$500-$650 CAD street | https://www.ergotron.com/en-ca/products/product-details/45-245 | Cleaner side-by-side split. Less tall-mast drama than stacking arm. |
| Clean white mid-market | Desky Canada | Dual Slim Aluminium Monitor Arm, white | $169.90 CAD | https://desky.ca/products/dual-slim-aluminium-monitor-arm | Clean white/aluminum aesthetic. Good value if central pole is not required. |
| Stronger white mid-market | Desky Canada | Dual Monitor Arm, white | $239.90 CAD | https://desky.ca/products/dual-monitor-arm | White dual arm with cable management. Good for Samsung M8 white setup. |
| Low-cost prototype | VIVO / Amazon CA | VIVO Aluminum Articulating Dual Monitor Arm, white, STAND-V102OW | $74.99 CAD seen | https://www.amazon.ca/dp/B08D6RZCG9 | Good prototype arm. Less premium. Verify weight and sag. |
| Budget central pole | SHOPPINGALL / Amazon CA | SA-D285-White extra tall 31.5 inch pole + dual arms | $65.99 CAD seen | https://www.amazon.ca/dp/B09GH1H7YN | Cheapest way to test the Bloomberg silhouette. Not final-premium hardware. |
| Budget central pole | SHOPPINGALL / Amazon CA | SA-D290-White extra tall pole dual mount | $54.99 CAD seen | https://www.amazon.ca/dp/B09GHRPCTC | Useful mockup. Check monitor compatibility carefully. |
| Corporate white | Grainger Canada | Fellowes Dual Monitor Arm, white, 8056301 | $415.80 CAD | https://www.grainger.ca/en/product/DUAL-MONITOR-ARM%2C-WHITE/p/FLW8056301 | Corporate/procurement-friendly. More expensive than Desky. |
| Premium design arm | Humanscale | M8.1 Monitor Arm, white/silver | ~$700-$1,200+ CAD depending config | https://www.humanscale.com/products/monitor-arms/m81-monitor-arm | Excellent finish, but quote/config heavy. Better for final executive install than prototype. |
| Premium design arm | Herman Miller | Ollin Monitor Arm, white/silver | ~$500-$900+ CAD per arm / quote | https://www.hermanmiller.com/products/accessories/technology-support/ollin-monitor-arm/ | Very refined. Use two symmetric arms if abandoning central pole. |

Arm recommendation:

- Prototype the shape with a budget white tall-pole arm if needed.
- Finalize the flagship with Ergotron LX Dual Stacking Arm Tall Pole in polished aluminum, unless monitor weights exceed the clean operating range.
- If using 32 inch Samsung M8 monitors, verify VESA, weight, tilt clearance, and sag before committing to a central pole.

## Brushed aluminum base / half-box concept

The base should make the Pi feel intentional. It should hide cable slack, add weight, protect connectors, and create a branded object on the desk.

Desired construction:

- brushed aluminum top plate or U-shaped half-box
- exposed Pi 5 mounted on standoffs
- rear cable exit for USB-C power, micro-HDMI x2, Ethernet, and optional USB
- internal steel or lead-free weights to make it feel anchored
- adhesive rubber feet
- optional engraved or etched WorkspaceAlberta mark
- optional white cable sleeves leaving the rear of the base

| Vendor | Product / service | Price seen / rough | Link | Notes |
|---|---|---:|---|---|
| Hammond Manufacturing | 1455 Series extruded aluminum instrument enclosure | ~$25-$70 CAD | https://www.hammfg.com/electronics/small-case/extruded/1455 | Best off-the-shelf aluminum enclosure path. Removable panels can be drilled. Natural anodized look. |
| Hammond Manufacturing | 1457 Series watertight extruded aluminum enclosure | ~$35-$100 CAD | https://www.hammfg.com/electronics/small-case/extruded/1457 | More industrial. Flanges can anchor to plate or desk. |
| Hammond Manufacturing | 1444 aluminum chassis / open utility box | ~$20-$60 CAD | https://www.hammfg.com/electronics/small-case/chassis/1444 | Best half-box starting point. Open top can carry a visible Pi plate. |
| Hammond Manufacturing | 1590 die-cast aluminum box | ~$15-$45 CAD | https://www.hammfg.com/electronics/small-case/diecast/1590 | Heavier cast box. Less polished unless sanded/brushed/powder-coated. |
| Bud Industries | Aluminum chassis / die-cast boxes | ~$15-$80 CAD | https://www.budind.com/product-category/general-use-boxes/ | Similar to Hammond. Check DigiKey/Mouser/Electro Sonic for Canadian stock. |
| Takachi | EX / MXA extruded aluminum enclosures | ~$30-$120+ CAD/import | https://www.takachi-enclosure.com/products/EX | Nicer design language, likely slower sourcing. Good premium enclosure candidate. |
| McMaster-Carr | 6061 aluminum plate / cut sizes | ~$20-$80 USD small plates | https://www.mcmaster.com/aluminum/ | Easy source for a heavy top plate. Brush with Scotch-Brite, clear coat/anodize. |
| OnlineMetals | 6061 aluminum plate/sheet cut-to-size | ~$15-$75 USD small plates | https://www.onlinemetals.com/en/buy/aluminum-sheet-plate | Good for custom rectangular base/top plate. |
| SendCutSend | Laser/waterjet/CNC-cut aluminum plates, bends, finish | ~$30-$100+ USD small custom plate | https://sendcutsend.com/materials/aluminum/ | Best for a branded plate with Pi standoff pattern, cable slots, and rounded corners. |
| Xometry | Sheet-metal / CNC aluminum fabrication | Quote, likely $100-$400+ one-off | https://www.xometry.com/capabilities/sheet-metal-fabrication/ | Good polished prototype path. Upload CAD, specify brushed/anodized finish. |
| Protocase | Custom electronic enclosures | Quote, often $200-$600+ one-off | https://www.protocase.com/products/electronic-enclosures/ | Best production-like enclosure path with PEM standoffs, logo, and rear cable panel. |
| Aluminox Canada | Cut-to-size aluminum stock | Quote/cart varies | https://aluminox.ca/collections/aluminium | Canadian plate source. Pair with local machine shop. |
| Materials Plus Canada | Cut-to-size aluminum | Quote/cart varies | https://materialsplus.ca/en/products/aluminum | Canadian supplier option. |

Base recommendation:

- Prototype: Hammond 1444 aluminum chassis or 1455 extruded enclosure, manually drilled, with stick-on weights and rubber feet.
- Premium demo: SendCutSend aluminum top plate on a Hammond chassis, with a brushed finish and engraved WorkspaceAlberta mark.
- Flagship: Protocase/Xometry folded aluminum half-box with internal weights, PEM standoffs, rear cable panel, and branded top plate.

## Suggested first-order prototype cart

This is the practical next cart if we want to build a visually convincing prototype without overcommitting to the final monitor choice.

| Item | Qty | Unit price | Extended |
|---|---:|---:|---:|
| Raspberry Pi 5 16GB, PiShop Canada | 1 | $426.95 | $426.95 |
| Raspberry Pi 45W USB-C Power Supply, white | 1 | $21.45 | $21.45 |
| White Micro-HDMI to HDMI 2m cable | 2 | $8.95 | $17.90 |
| Pi5 Passive Cooling CNC Box, silver | 1 | $23.95 | $23.95 |
| Copper heatsink 4-pack | 1 | $5.45 | $5.45 |
| Ergotron LX Dual Stacking Arm Tall Pole, polished aluminum | 1 | ~$650.00 | ~$650.00 |
| ALOGIC Clarity 27 inch 4K monitor | 2 | $639.99 | $1,279.98 |
| Apple Magic Keyboard with Touch ID and Numeric Keypad, USB-C | 1 | $229.00 | $229.00 |
| Apple Magic Mouse, USB-C, white | 1 | $95.00 | $95.00 |
| Prototype aluminum base / Hammond or SendCutSend allowance | 1 | ~$200.00 | ~$200.00 |
| Estimated hardware subtotal | | | ~$2,949.68 CAD |

This cart gives the premium monitor-arm silhouette and leaves enough budget for custom base work, branding, packaging, setup labour, and margin.

## Open decisions

1. Do we want the flagship photo/demo unit to use Apple Studio Displays, even if production packages use ALOGIC or Samsung?
2. Is the visual language silver/aluminum-first or white-first?
3. Should the Pi be fully exposed with copper details, or partially enclosed in a silver CNC cooling box?
4. Do we need a live camera AI demo? If yes, add AI HAT+ 13 TOPS or 26 TOPS. If no, prioritize cooling and base design.
5. Will the central pole mount through the aluminum base, clamp to the desk behind it, or stand separately behind the branded Pi plinth?

## Procurement cautions

- Recheck all prices before ordering.
- Confirm monitor VESA compatibility before buying arms.
- Confirm monitor arm weight range with the exact monitor model.
- Buy two white micro-HDMI cables for dual displays.
- Do not rely on generic USB-C chargers for the Pi 5.
- Avoid Coral USB for the final object unless a specific demo requires it; the cable clutter hurts the premium look.
- Treat the first aluminum base as a prototype. The cable routing and monitor-arm geometry will change after the first physical assembly.
