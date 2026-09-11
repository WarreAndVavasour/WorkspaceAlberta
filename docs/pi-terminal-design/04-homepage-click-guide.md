# Company homepage click guide

Home introduces Warre & Vavasour and provides four paths into its work. The Pi-class object is a visual invitation. Dual-screen usage, device deployment, harness settings, installation steps, and workspace setup are outside this homepage's information architecture.

At rest, show only “W&V”, “Custom AI tools for real work.”, “Explore our work”, and the particle stage. The field leaves a clear pocket behind the sentence and CTA. Do not add a hero paragraph, service cards, project carousel, testimonials, a pricing section, or a scrolling hardware story.

“Explore our work” opens the guide immediately while the field resolves into the assembled object. It does not navigate away. Activating the stage's equivalent “Explore our work” control produces the same result. Use one shared accessible action; avoid two duplicate keyboard stops for the same action.

In the open guide, show four text links, one “Open object” control, and one “Back” control. The original CTA is replaced by this guide. The company mark and sentence stay visible. “Open object” separates the hardware layers and becomes “Assemble object”; route labels retain their positions. Looking around is optional and never a prerequisite for navigation.

| Route label | Planned destination | What the later page can explain | Homepage treatment |
|---|---|---|---|
| Workspace Alberta desk | `/workspace-alberta` | The Workspace Alberta work offering, with its own product/desk context | One text link; no deployment specifications |
| Claude / onsite training | `/training` | Training and working with people onsite | One text link; no claim of vendor affiliation |
| Hospitality maps toolkit | `/hospitality-maps` | The maps toolkit and its work context | One text link; no map artwork or MapBot redesign |
| Company | `/company` | Warre & Vavasour, Canmore / Western Canada, approach and contact | One text link; no added company history or client claims |

These are planning labels and route names, not created pages or claims that routes currently exist. There is no separate homepage Pi deployment route. The first link identifies a branch of company work; it does not redefine the company homepage as a terminal sales page.

Use the object to open the guide, then use the labels to choose a destination. Mesh hover may reveal one plain inspection label such as “Board”, “Cooling”, or “Frame”. It must not navigate or reveal a service description. This preserves the physical meaning of the object and the clarity of the company navigation.

For desktop, design against a 1440 × 900 CSS-pixel canvas with 40-pixel outside margins. Put the mark at the upper left, 28-pixel type with a 44-pixel minimum interaction box. The idle copy pocket is centered at 50% width and 46% height, with a maximum width of 480 pixels. Set the sentence to 30/38 pixels and the CTA to 16/24 pixels, 24 pixels beneath it. Keep a 32-pixel particle exclusion margin around the copy's combined bounds.

When the guide opens, the sentence and guide move together to a 320-pixel column beginning 8% from the left edge and centered vertically. The object stage occupies a square no larger than 620 pixels, centered at 68% width and 49% height. Its orthographic image retains the padding specified in the shot schedule. The outer particle field fades to a quiet trace outside both the guide and object. Keep at least 40 pixels between text bounds and visible object bounds; shrink the stage first when necessary.

Place the four route links vertically at 44-pixel minimum row height with 8-pixel gaps. Put the object control and Back beneath them. Links use 17/24-pixel type, charcoal text, and an underline on hover or focus. The object control and Back use 15/22-pixel type. Do not surround the guide with a card, glass panel, or border. An inspection label sits near its selected part only if it clears all route labels by 24 pixels; otherwise place it under the stage.

At 768–1099 pixels wide, use a stacked layout: mark, sentence, square stage, then the guide. At less than 768 pixels wide, use 20-pixel margins, 24/32-pixel sentence type, and a stage width of `min(available width, 420 pixels)`. In the idle state the copy remains in the field pocket. In the open state it sits above the stage. The links follow the stage in a single column. Allow ordinary vertical scrolling when height is limited or text is enlarged. Do not force everything into one screen.

Use pure white `#FFFFFF` for the page, `#222725` for primary text and focus outlines, and `#555E59` for inspection hints. The amber hardware indicator does not become a general interface accent. Use a 2-pixel focus outline with 3-pixel offset. Maintain readable text contrast and 44 × 44-pixel minimum action targets in all layouts.

| Input or circumstance | Result |
|---|---|
| Pointer moves over idle stage | Subtle ring attraction; no content change |
| Pointer hovers primary action | Small local particle invitation for 0.24 seconds; leave restores it |
| Click/tap Explore our work | Open guide; start 1.20-second materialization if motion is enabled |
| Click/tap Open object | Run the 1.60-second assembly explode; change control label to Assemble object |
| Drag on object | Orbit only after 6 CSS pixels of travel; consume the following click so dragging does not activate anything |
| Touch on mobile | Single tap opens; use named Front, Three-quarter, Top, Ports view buttons when the object is open; page scrolling remains native |
| Arrow keys while object control has focus | Step yaw by 10 degrees or elevation by 5 degrees within the specified orbit bounds |
| Home while object control has focus | Restore the canonical three-quarter view in 0.24 seconds, or immediately with reduced motion |
| Tab / Shift+Tab | Traverse the guide and object controls in visible reading order; do not trap focus |
| Escape or Back inside the guide | Dismiss the guide and object; restore focus to Explore our work |
| Select a route | Navigate immediately; optional outgoing 0.24-second fade never delays the link |
| Browser Back from a detail page | Restore the open guide and last assembled/exploded state without replaying the entrance |

The mark is a Home link. While already on Home, activating it returns to the idle state and resets the view. Back within the guide changes local UI state without adding browser-history entries. Detail navigation uses ordinary history so the browser Back button behaves predictably.

For reduced motion, show the static assembled Blender still at rest with the copy in its separate zone. Explore our work reveals the same guide instantly. Open object swaps to the matching exploded still; named view buttons swap stills without tweening. No automatic morph, live particle field, animated orbit, flashing indicator, or simulated camera drift runs. Preserve all four routes and inspection labels.

Give the still the description “Pi-class hardware object with an open silver frame and green circuit board.” Treat the decorative particle field as hidden from assistive technology. Expose the guide as navigation, the object controls as buttons, and one short state announcement after a user action. Do not announce motion frames or changing particle values.

If the visual cannot load, keep the same mark, sentence, CTA and text guide. Display the Blender still if available; otherwise retain white space in the stage. A visual failure must not turn into a loading gate for the company links. No public loading message should mention shaders, textures, WebGL, or Blender.
