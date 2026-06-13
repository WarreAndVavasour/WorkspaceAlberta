# Terminal — Render Briefs (artifacts 1 & 5)

Ready-to-run prompts for the two photoreal images. Keep palette and parts consistent
with `docs/terminal-spec.md`: brushed aluminum + white + copper accent; Pi 5 as the
visible control node; dual 27" displays on a polished aluminum tall pole.

How to generate (any of):
- HF MCP `Z-Image-Turbo` once a token is set at https://hf.co/settings/mcp (anon quota is exhausted).
- An HF token with the **Inference Providers** scope (current token lacks it) → FLUX.1-schnell / fal-ai.
- Any external tool (Midjourney / DALL·E / local SDXL) using the prompts below.

---

## 1 — Hero render  (3:2, e.g. 1536×1024, seed 7)

**Prompt:**
Product photograph of a premium executive AI desk terminal modeled on a Bloomberg terminal.
Two 27-inch 4K monitors side by side on a single polished aluminum central-pole monitor arm
(Ergotron-style tall pole). At the desk base, an exposed Raspberry Pi single-board computer as a
visible control node inside a brushed silver aluminum CNC cooling box with copper heatsink accents,
mounted on a custom brushed-aluminum plinth with clean rear cable exits. White Apple Magic Keyboard
with numeric keypad and white Magic Mouse on a clean desk. Industrial-but-executive aesthetic,
brushed aluminum and white palette, disciplined cable management, no clutter, soft studio lighting,
dark moody office background, shallow depth of field, high-end commercial product photography.

**Negative:** gamer RGB lighting, plastic clutter, tangled cables, logos, text, people, warm yellow tint.
**Composition:** eye-level, monitors filling upper two-thirds, plinth/control node sharp in foreground.

---

## 2 — Brand-object close-up  (3:2, e.g. 1536×1024, seed 19)

**Prompt:**
Extreme close-up macro product photograph of a Raspberry Pi 5 single-board computer presented as a
premium brand object and control node. The board sits inside an open brushed-silver aluminum CNC
machined cooling box with visible copper heatsinks, mounted on a custom brushed-aluminum plinth.
Exposed, deliberate, visibly technical. Brushed aluminum, silver and copper palette, a small white
USB-C power cable exiting cleanly at the rear. Dramatic directional studio lighting, dark background,
shallow depth of field, luxury technology product photography, sharp detail.

**Negative:** clutter, multiple boards, RGB, text, watermark, hands.
**Composition:** 45° macro, copper heatsinks catching the key light, single clean cable exit.
