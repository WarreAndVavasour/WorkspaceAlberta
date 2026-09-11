# Blender scene specification — W&V Pi-class brand object

Build a floating company brand object, using Pi-class proportions and a restrained open frame. This scene does not model the deployed dual-screen terminal, a harness interface, or an approved hardware bill of materials. All dimensions below are art-model dimensions in centimetres. Component placement is simplified; the board footprint and mounting pattern use the [Raspberry Pi 5 reference drawing](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf).

Save the eventual working scene as `wa_pi_terminal_master.blend`. Target Blender 4.5 LTS. Use Metric units, Unit Scale 1.0, and Length Centimeters. Enter dimensions with the `cm` suffix: an 8.5 cm board is 0.085 Blender units, not 8.5 metres. Apply mesh scale after sizing. Keep the master at real scale; never enlarge it to solve lighting or viewport clipping.

The world origin is the centre of the main PCB at its thickness mid-plane. X follows the 8.5 cm board length; +X points toward the USB/Ethernet bank. Y follows its 5.6 cm width; −Y is the power/HDMI edge and the object's front. +Z is above the components. The assembled pose uses no root rotation. It floats in a white void; there is no ground mesh. The camera supplies the three-quarter view.

The PCB spans X −4.25…4.25, Y −2.80…2.80, Z −0.08…0.08. The completed frame is approximately 10.2 × 7.2 × 3.3 cm, including screw heads and the indicator's slight projection. The board's four mounting-hole centres are (−3.90, −2.45), (−3.90, 2.45), (1.90, −2.45), (1.90, 2.45), with 0.27 cm diameter. Every coordinate below is an assembled world coordinate unless explicitly called local.

Create collections `00_RIG`, `10_BASE`, `20_STORAGE`, `30_BOARD`, `40_COOLER`, `50_FRAME`, `60_LIGHTS`, `70_CAMERAS`, and `90_REFERENCE`. The reference collection is empty by default and excluded from every render/export. Put no Google source or texture in it.

Create `WA_ROOT` at (0,0,0), scale 1. Under it create five empties at the same origin: `P_BASE`, `P_STORAGE`, `P_BOARD`, `P_COOLER`, `P_FRAME`. These have identity transforms in the assembled pose. Parent each mesh to the parent listed below, keeping its world transform. Mesh origins remain at their own geometric centres. Group offsets are in world axes and are applied only once, on the parent empties. Export these parent names with the geometry.

Use the following construction conventions throughout the mesh inventory. Dimensions mean full bounding-box extents X × Y × Z, not half extents. Rounded rectangular prisms have the specified plan-view corner radius, then a small edge bevel. If no radius is listed, use a plain cuboid with the default edge bevel. Cylinders run along Z unless another axis is given. Join repeated subpieces into the named mesh when the inventory calls them one mesh; retain separate material slots. Do not leave Boolean cutters as visible or exported geometry.

Default edge bevel is 0.025 cm with 2 segments, clamped to avoid overlap. Use 0.008 cm on chip packages, 0.005 cm on contacts/pins, and 0.06 cm with 3 segments on the base plate. Set hard faces flat and curved/bevel faces smooth; keep sharp boundaries at 45 degrees. Use 24 sides for visible large cylinders and 12 for small screws/pins. Apply Boolean modifiers before bevels. Small disconnected islands inside a joined mesh are acceptable. Do not add subdivision surfaces, random greebles, dust, stickers, or scratch geometry.

Each mesh has a semantic `part_id`, given as a two-digit value below. IDs distinguish inspection masks; parents distinguish what moves. All board chips and connectors stay under `P_BOARD`, regardless of their semantic ID.

| Named mesh or exact family | Count | Parent / ID | Dimensions and assembled placement | Construction / material |
|---|---:|---|---|---|
| `wa_base_plate` | 1 | P_BASE / 15 | 10.0 × 7.0 × 0.25; centre (0,0,−1.175) | Rounded prism, corner radius 0.40; M_ALUMINUM |
| `wa_base_board_post_01`…`04` | 4 | P_BASE / 15 | XY at the four PCB mounting centres | Each joins a Ø0.22 shaft from Z −1.05 to −0.08, Ø0.42 bottom flange from −1.05 to −0.94, Ø0.42 upper flange from −0.20 to −0.08; M_METAL |
| `wa_base_frame_post_01`…`04` | 4 | P_BASE / 15 | XY (−4.78,−3.18), (−4.78,3.18), (4.78,−3.18), (4.78,3.18); centre Z 0.34 | Ø0.22 × 2.78 cylinders, top at 1.73; M_ALUMINUM |
| `wa_hat_board` | 1 | P_STORAGE / 13 | 6.40 × 5.50 × 0.12; centre (−1.0,0,−0.78) | Corner radius 0.16; same four Ø0.27 mounting holes as main PCB; M_PCB |
| `wa_hat_pads` | 1 | P_STORAGE / 13 | Four annuli at the mounting XY, centre Z −0.717 | Each outer Ø0.46, inner Ø0.27, thickness 0.006; M_METAL |
| `wa_hat_pcie_socket` | 1 | P_STORAGE / 13 | 0.70 × 0.35 × 0.18; centre (−3.55,1.25,−0.63) | Black socket with a 0.62 × 0.20 × 0.08 cavity centred at local (−0.10,0,0), open on −X; M_CONNECTOR, front rim M_METAL |
| `wa_m2_socket` | 1 | P_STORAGE / 14 | 0.65 × 2.40 × 0.26; centre (0.95,−0.25,−0.58) | Slot opens toward −X, inner height 0.12 centred at Z −0.62; M_CONNECTOR |
| `wa_ssd_board` | 1 | P_STORAGE / 14 | 4.20 × 2.20 × 0.10; centre (−1.10,−0.25,−0.62) | Corner radius 0.08; small Ø0.24 end notch centred (−3.20,−0.25); M_PCB |
| `wa_ssd_chip_01`, `wa_ssd_chip_02` | 2 | P_STORAGE / 14 | Each 1.15 × 1.45 × 0.18; centres (−2.05,−0.25,−0.48), (−0.55,−0.25,−0.48) | M_SILICON |
| `wa_ssd_retainer` | 1 | P_STORAGE / 14 | Centre (−3.10,−0.25,−0.49) | Ø0.30 head, height 0.06; Ø0.12 shaft down to Z −0.72; M_METAL; screw recipe below |
| `wa_board` | 1 | P_BOARD / 01 | 8.50 × 5.60 × 0.16; centre (0,0,0) | Corner radius 0.30, four holes specified above; M_PCB |
| `wa_board_pads` | 1 | P_BOARD / 01 | Four annuli at mounting XY, centre Z 0.083 | Outer Ø0.48, inner Ø0.27, thickness 0.006; M_METAL |
| `wa_board_screw_01`…`04` | 4 | P_BOARD / 01 | Mounting XY, head centre Z 0.115 | Ø0.38 head × 0.06, Ø0.16 shaft from Z −0.08 to 0.085; M_METAL |
| `wa_soc` | 1 | P_BOARD / 02 | 1.80 × 1.80 × 0.22; centre (−1.20,0,0.19) | M_SILICON; no logo or processor claim |
| `wa_ram` | 1 | P_BOARD / 03 | 1.00 × 1.10 × 0.15; centre (0.65,1.36,0.155) | M_SILICON |
| `wa_rp1` | 1 | P_BOARD / 10 | 1.15 × 1.15 × 0.16; centre (1.25,−0.90,0.16) | M_SILICON; simplified controller package |
| `wa_pmic` | 1 | P_BOARD / 10 | 0.70 × 0.80 × 0.15; centre (−3.30,−0.65,0.155) | M_SILICON |
| `wa_oscillator` | 1 | P_BOARD / 10 | 0.60 × 0.38 × 0.15; centre (1.55,0.65,0.155) | M_METAL |
| `wa_usb3_stack`, `wa_usb2_stack` | 2 | P_BOARD / 04 | Each 1.70 × 1.38 × 1.60; centres (3.70,0,0.88), (3.70,−1.62,0.88) | Two-port module recipe below; quiet dark tongues on both stacks |
| `wa_ethernet` | 1 | P_BOARD / 05 | 2.10 × 1.58 × 1.35; centre (3.50,1.70,0.755) | Ethernet recipe below; opening faces +X |
| `wa_gpio_base` | 1 | P_BOARD / 06 | 5.13 × 0.52 × 0.25; centre (−1.0,2.36,0.205) | M_CONNECTOR |
| `wa_gpio_pins` | 1 | P_BOARD / 06 | 40 pins; X = −3.413 + 0.254i, i=0…19; Y=2.233 and 2.487; centre Z 0.565 | Each pin 0.064 × 0.064 × 0.89, top Z 1.01; join into one mesh; M_METAL |
| `wa_sd_socket` | 1 | P_BOARD / 07 | 1.50 × 1.50 × 0.24; centre (−3.35,0,−0.20) | Hollow shell 0.035 walls, open on −X; M_METAL; slot aligned with card |
| `wa_sd_card` | 1 | P_BOARD / 07 | 1.30 × 1.10 × 0.08; centre (−4.00,0,−0.20) | Corner radius 0.06; M_CONNECTOR; no printed label |
| `wa_power_usb_c` | 1 | P_BOARD / 08 | 0.90 × 0.65 × 0.34; centre (−3.55,−2.62,0.25) | Front-port recipe below, opens on −Y; M_METAL + M_CONNECTOR |
| `wa_power_button` | 1 | P_BOARD / 08 | 0.24 × 0.32 × 0.20; centre (−4.19,−1.62,0.18) | M_CONNECTOR; outer face on −X |
| `wa_hdmi_01`, `wa_hdmi_02` | 2 | P_BOARD / 09 | Each 0.72 × 0.55 × 0.28; centres (−1.95,−2.62,0.22), (−0.65,−2.62,0.22) | Front-port recipe below; openings face −Y |
| `wa_fpc_01`, `wa_fpc_02` | 2 | P_BOARD / 10 | Each 0.80 × 0.30 × 0.14; centres (−2.70,1.48,0.15), (−1.35,1.48,0.15) | M_CONNECTOR; 0.76 × 0.08 × 0.04 top latch at local (0,−0.08,0.08), joined |
| `wa_pcie_socket` | 1 | P_BOARD / 10 | 0.70 × 0.35 × 0.16; centre (−3.55,0.85,0.16) | Same cavity as HAT socket, opening on −X; front rim M_METAL; no cable in this art model |
| `wa_passives` | 1 | P_BOARD / 10 | Twelve 0.18 × 0.10 × 0.09 pieces at the XY centres below; centre Z 0.125 | M_SILICON bodies with 0.025-cm-long M_METAL end caps; joined |
| `wa_cooler_pad` | 1 | P_COOLER / 11 | 1.70 × 1.70 × 0.03; centre (−1.20,0,0.315) | M_PAD; pad remains with cooler in explode |
| `wa_cooler_foot` | 1 | P_COOLER / 11 | 2.65 × 2.40 × 0.20; centre (−1.20,0,0.43) | Corner radius 0.12; M_ALUMINUM |
| `wa_cooler_fins` | 1 | P_COOLER / 11 | 12 fins, each 0.07 × 1.60 × 0.65; X = −2.32 + 0.204i, i=0…11; Y=0; Z=0.855 | Join fins; 0.012 edge bevel, 2 segments; M_ALUMINUM |
| `wa_cooler_fasteners` | 1 | P_COOLER / 11 | Two heads at (−1.20,−1.04,0.57), (−1.20,1.04,0.57) | Ø0.22 head × 0.08; shafts to Z 0.34; M_METAL; joined |
| `wa_frame` | 1 | P_FRAME / 12 | Outer 10.20 × 7.20 × 0.18, centre (0,0,1.82); inner opening 9.10 × 6.10 through Z | Outer corner radius 0.35, inner radius 0.18; frame recipe below; M_ALUMINUM |
| `wa_frame_screw_01`…`04` | 4 | P_FRAME / 12 | XY at the four frame posts; head centre Z 1.94 | Ø0.28 head × 0.06, Ø0.14 shaft to Z 1.54; M_METAL |
| `wa_status_lens` | 1 | P_FRAME / 16 | 0.22 × 0.035 × 0.10; centre (0,−3.608,1.82) | Radius 0.025; shallow amber lens facing −Y; M_LED |

This inventory contains 53 final mesh objects. Joined islands do not count as additional objects. It is the complete LOD0 scope. No OLED, fan, cable, antenna, display, keyboard, mouse, environment prop, or extra branding mesh is required.

The twelve passive XY centres, in order, are (−3.15,1.35), (−2.70,1.78), (−1.90,1.78), (−0.65,−1.55), (0,−1.55), (0.70,−1.70), (1.35,1.52), (1.65,2.05), (−3.10,−1.40), (−3.45,0.20), (1.95,0.55), (2.10,−1.20). This is an intentionally sparse arrangement. Do not fill the remaining board surface with invented circuitry.

For each USB stack, make a metal shell with two cavities opening on +X. In module-local coordinates, cut cavities of 1.58 × 1.14 × 0.53 at (0.10,0,−0.39) and (0.10,0,0.39); the cutters extend through the +X face and leave a rear wall. Place a dark tongue of 1.25 × 0.92 × 0.12 at local (0.14,0,−0.44) and (0.14,0,0.34). On each tongue add four 0.48 × 0.09 × 0.012 contact strips, centred at local X 0.44, Y −0.30, −0.10, 0.10, 0.30, and Z 0.067 above that tongue's centre. These are reduced contact details for visual readability, not an electrically exact USB model. Join shell, tongues and contacts into the named stack mesh using M_METAL, M_CONNECTOR and M_METAL slots.

For Ethernet, cut a 1.88 × 1.25 × 1.00 cavity at local (0.18,0,0.05), extending through +X. Keep the rear and side walls. Add a dark rear insert at local X −0.76, thickness 0.12, filling 1.15 × 0.90 in Y/Z. Add eight 0.70 × 0.045 × 0.025 contact bars at local X 0.38, Y −0.42 + 0.12i for i=0…7, Z 0.45. Cut a 0.40 × 0.50 × 0.15 latch recess into the lower opening lip, centred at local (0.93,0,−0.59). Join all pieces. Port interiors are charcoal; do not add extra status LEDs.

For USB-C and HDMI, subtract an inner cavity extending out the −Y face, inset 0.06 from the X and Z outside edges, leaving a 0.06 rear wall on +Y. Add one central dark tongue, width 65% of the opening, depth 65% of the cavity and height 0.055, centred in Z and flush 0.08 behind the front face. USB-C uses a rounded opening with a 0.08 corner radius. For HDMI, bevel the two lower opening corners by 0.08 to suggest the socket outline. Join tongue and shell. Microscopic individual contacts are omitted on these small ports.

For the frame, cut the rounded centre opening and four Ø0.18 screw holes at the frame-post XY positions. Cut a 0.24 × 0.10 × 0.12 indicator recess centred at (0,−3.58,1.82), open through the front face. Fit the lens to that recess. The frame is a thin open bezel, with all four sides visible. Its lower face at Z 1.73 clears the USB shells' top at Z 1.68. No lid fills the opening.

For each screw head, subtract one centred slot 60% of head diameter long, 0.045 wide and 0.025 deep, aligned with X. All hardware remains clean and almost matte. Screw heads and shafts are one mesh each; the two cooler screws are joined as specified. These are visual fasteners, without modelled threads.

Use the following materials with Principled BSDF. Hex values are sRGB inputs in Blender's colour picker. Roughness and metallic are scalar values. Keep alpha 1, transmission 0, coat 0, subsurface 0, and IOR 1.45 unless overridden. Metal uses metallic 1 and the stated roughness. No texture is needed for LOD0.

| Material | Base colour | Metallic | Roughness | Additional setting / use |
|---|---|---:|---:|---|
| `M_PCB` | `#466258` | 0 | 0.72 | Muted solder-mask green; same on board edges for visual restraint |
| `M_SILICON` | `#242A27` | 0 | 0.68 | Chip packages and passive bodies |
| `M_CONNECTOR` | `#303633` | 0 | 0.61 | Connector inserts, GPIO base and SD card |
| `M_ALUMINUM` | `#C4C8C5` | 1 | 0.46 | Frame, base, cooler and outer posts; neutral white reflections |
| `M_METAL` | `#AEB5B0` | 1 | 0.36 | Pins, shell lips, pads and fasteners |
| `M_PAD` | `#626B65` | 0 | 0.90 | Cooler contact pad |
| `M_LED` | `#D7A352` | 0 | 0.40 | Emission same colour, strength 0.35; steady, no bloom, no animated pulse |

The PCB is muted enough to read as a material rather than an interface accent. Amber is the sole signal accent. Avoid blue USB plastic, copper ornaments, chrome, rainbow highlights and strong rim glow. Set material node displacement to none. Do not put a screen interface on the board or frame.

Create a neutral world, colour white, strength 0.25. Set Film Transparent on for delivery assets. The beauty on white is composited from that same transparent render over pure white after the view transform. Reflection illumination remains present even when the background is transparent. Do not use a coloured HDRI or add a floor to obtain contact shadows.

| Light name | Type / dimensions | Position in cm | Power | Aim |
|---|---|---|---:|---|
| `L_KEY` | Square area, 20 cm | (−12,−18,24) | 3 W | (0,0,0.3) |
| `L_FILL` | Square area, 25 cm | (16,−2,14) | 1.5 W | (0,0,0.3) |
| `L_EDGE` | Square area, 18 cm | (−8,16,20) | 2 W | (0,0,0.3) |

All lights are white and point along their local −Z toward the aim point. These powers assume the real-scale scene above. Use Cycles, 256 samples, adaptive threshold 0.01, denoising for beauty only, 8 total bounces, 4 diffuse and 4 glossy. Turn off caustics, motion blur and depth of field. Use AgX, base contrast, exposure 0 and gamma 1 for beauty. Set preview sequences to 64 samples; data passes have their own settings in the shot schedule. Keep self-shadowing, but do not multiply a dark ambient-occlusion grade into the image.

The cameras are orthographic. All look at their target using local −Z forward and local +Y up. For every camera except Top, keep the image upright with world +Z as the up reference. For Top, use world +Y as image up. Clip start is 0.1 cm; clip end is 150 cm. Square output, pixel aspect 1, zero shift. The listed orthographic scales are image height in centimetres; square frames have the same image width.

| Camera | Position in cm | Target in cm | Ortho scale | Purpose |
|---|---|---|---:|---|
| `CAM_HERO` | (13,−18,14.65) | (0,0,1.00) | 16.5 cm | Assembled rest, morph target and canonical examine view |
| `CAM_EXPLODE` | (13,−18,14.65) | (0,0,1.00) | 16.5 cm | Exact duplicate of Hero; exploded passes must register to it |
| `CAM_FRONT` | (0,−26,7.45) | (0,0,1.00) | 16.5 cm | Front edge, indicator and horizontal assembly levels |
| `CAM_TOP` | (0,0,29.00) | (0,0,1.00) | 16.5 cm | Board footprint, layout and frame opening |
| `CAM_BACK` | (−17,15,12.65) | (0,0,1.00) | 16.5 cm | Reverse three-quarter; SD/GPIO and open construction |
| `CAM_PORTS` | (23.70,−1.40,8.90) | (3.70,0,0.90) | 7.5 cm | Deliberate detail crop of USB/Ethernet; never substitute for hero target |

Create `WA_REST` and `WA_EXPLODED` pose states. Keep object rotations zero in both; there is no mechanical spinning. Use the following final translations on the five parents. The exact same mesh origins and vertices are used in both states. Board sub-IDs follow P_BOARD, and the indicator follows P_FRAME.

| Parent | Rest offset (cm) | Exploded offset (cm) | Start / finish during Open | Interpretation |
|---|---|---|---|---|
| P_FRAME | (0,0,0) | (0,0,4.20) | 0.00 / 0.80 s | Upper frame and its screws lift clear |
| P_COOLER | (0,0,0) | (−0.55,0,3.45) | 0.08 / 1.28 s | Cooling lifts from the SoC |
| P_BOARD | (0,0,0) | (0.35,0,0.80) | 0.12 / 1.12 s | Populated board remains one assembly |
| P_STORAGE | (0,0,0) | (−0.55,0,−1.25) | 0.12 / 1.44 s | HAT-like carrier and SSD stay together |
| P_BASE | (0,0,0) | (0,0,−2.10) | 0.00 / 1.60 s | Base and support posts move down |

The frame uses power3.out. All other parents use power2.out. Begin travel in Z. Phase in the cooler's X offset from 0.68 to 1.28 seconds and the board's X offset from 0.62 to 1.12 seconds, each with power2.out. Hold the storage X offset at zero until 1.15 seconds, then move it to −0.55 by 1.44 seconds with power2.out. This later storage shift allows the base posts to withdraw below the carrier before lateral travel begins. There are no tethers, flying chips or part rotations. The thermal pad rides with the cooler. The absent PCIe/power cables are deliberate visual omissions; do not imply a demonstrated working electrical assembly.

Use 60 fps for motion proofs. Open starts at frame 1 and ends at frame 97; time in seconds is (frame−1)/60. Bake parent motion at every frame so the intended ease is explicit, with linear interpolation between samples. Use normalized local time clamped to 0…1: power3.out is 1−(1−t)^4; power2.out is 1−(1−t)^3. A two-key Blender Bezier curve is not assumed to match these exactly. The [GSAP runtime](https://antigravity.google/_astro/gsap.Bi_c5vh2.js) establishes these easing families; the offsets and staging above are our design.

For Assemble, all parents return from their current values in 1.00 second. During 0.00…0.24 seconds, hold each current Z offset and return all X offsets to zero with power3.out. During 0.24…1.00 seconds, keep X at zero and return all Z offsets to zero with power3.out. This seats the aligned assembly without scraping through support posts. If reversing mid-open, start from the current pose without snapping to either endpoint. Preview in `CAM_HERO`; hold the final rest pose rather than looping.

For examine, orbit the camera around (0,0,1.00), never rotate or scale WA_ROOT. Hero azimuth is about −54 degrees from +X, elevation about 31.6 degrees. Allow yaw ±65 degrees around Hero and elevation 15…65 degrees; no roll, no underside tumble, no inertia after release. Drag sensitivity is 0.20 degrees per CSS pixel horizontally and 0.12 vertically. Retain the 16.5 cm scale; a selected named Ports view alone uses its detail scale. Named Front, Top and Back views can exceed the free-drag limits. If a drag begins outside a limit, accept movement toward the supported range and ignore movement farther away; do not clamp the starting angle and cause a jump. Ports is a fixed detail view: selecting a full-object angle restores free drag.

Keep LOD0 at or below 35,000 evaluated triangles and LOD1 at or below 12,000, measured after applying modifiers and triangulating an export duplicate. For LOD1, remove passives, pads, contact strips, screw slots and chip bevel segments; replace the 40 visible pins with two joined 20-tooth combs at the same outside bounds, using 0.064-cm teeth. Keep the five moving parents, port cavities, cooler, frame opening and semantic IDs. Do not shrink or change the assembled silhouette when reducing detail. Main Blender geometry remains non-destructively archived in the master collection before export.

Before rendering, check the four mounting coordinates, the 0.05 cm clearance above USB, the gap between SSD chips and the main board, and the frame opening around GPIO. In the explode proof, posts must withdraw through their mounting holes before lateral separation. At rest, no duplicated faces should flicker; at full explode, all five levels should fit the canonical camera. The scene and shot schedule together define the builder's complete scope; no extra hardware or homepage elements should be invented to fill the frame.
