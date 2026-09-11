# Reference notes and open questions

The four exact script URLs in the brief were fetched successfully as text on 8 September 2026. The public homepage markup was also inspected to distinguish live attribute values from constructor defaults. The source was read for mechanics; no Antigravity source, icon texture, or brand asset was added to this repository.

| Source | Observation verified in the source | Consequence for this plan |
|---|---|---|
| [Mouse.ZrlRGzn3.js](https://antigravity.google/_astro/Mouse.ZrlRGzn3.js) | Shared bundle includes WebGL renderer, buffer geometry and render-target machinery | Treat this as shared runtime support, not as the hero's animation specification |
| [MainParticlesComponent…Dox42TL8.js](https://antigravity.google/_astro/MainParticlesComponent.astro_astro_type_script_index_0_lang.Dox42TL8.js) | A 256 × 256 simulation uses position/reference textures and alternating render targets. Ring uniforms influence the field. Theme changes shader behavior. The observer stops/resumes the scene; unload cleans up. | Preserve a responsive field and readable pocket; add the company's own object and lifecycle policy |
| [MorphingParticlesComponent…B4r3VvfF.js](https://antigravity.google/_astro/MorphingParticlesComponent.astro_astro_type_script_index_0_lang.B4r3VvfF.js) | Contains fixed- and variable-density Poisson sampling. Textures are read at 500 × 500. The image sampler uses the red channel, cubed, as a density-distance function. Hover uses 0.5 seconds with power3.out; its push uses 2 seconds with power2.out. | Define an explicit alpha contract and 3D handoff. Do not assume a white alpha mask can be dropped into the reference sampler unchanged. |
| [gsap.Bi_c5vh2.js](https://antigravity.google/_astro/gsap.Bi_c5vh2.js) | Easing runtime defines the power families; the component supplies the actual interaction durations | Use power3.out for decisive moves and power2.out for larger assembly travel |
| [Antigravity homepage markup](https://antigravity.google/) | Light Main attributes: density 230, scale 0.59, ring widths 0.006 / 0.107, displacement 0.62. Light Morph examples: density 50, scale 0.6, camera zoom 8.8; individual and cube texture references are present. | These values are the reference baseline, not universal particle counts or measured performance guarantees |

Both particle components generate base samples on a 500 × 500 domain. Their base-sampling distance mapping gives approximately 3.87–4.87 units at density 230 and 8.67–9.67 units at density 50. A 256 × 256 texture has 65,536 slots; it does not mean 65,536 particles are drawn. Our later implementation must measure the actual sample count and draw only active slots. These are observations of the [Main](https://antigravity.google/_astro/MainParticlesComponent.astro_astro_type_script_index_0_lang.Dox42TL8.js) and [Morph](https://antigravity.google/_astro/MorphingParticlesComponent.astro_astro_type_script_index_0_lang.B4r3VvfF.js) sampling setup.

The reference observer pauses rendering when the component leaves the viewport. It does not, by itself, dispose of the field at every exit. Delayed release of our idle GPU resources is a new lifecycle decision in this pack. Likewise, the reference morph targets are flat images; freely examining a shaded 3D assembly is new work, supported here by geometry and registered data passes.

The requested `/workspace/antigravity-orb/FINDINGS.md` mirror was absent in the available Windows path and Ubuntu environment. The attachment contained the written request only. The white authentication-page screenshot was not attached, so it was not visually inspected. The white-page composition follows the user's description, not an asserted pixel match to that screenshot.

The board's 8.5 × 5.6 cm footprint and 5.8 × 4.9 cm mounting pattern are grounded in the [official Raspberry Pi 5 mechanical drawing](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf). That drawing describes approximate reference dimensions. The component placements, frame, cooler and storage treatment in this pack are a simplified visual model; they do not establish manufacturing clearances or electrical compatibility.

Blender planning targets [Blender 4.5 LTS](https://www.blender.org/releases/4-5/). The [Blender passes manual](https://docs.blender.org/manual/en/4.5/render/layers/passes.html) documents world-space Position and Normal passes and the lack of antialiasing on Z, Position and index passes. This is why the sampling schedule keeps coverage, integer identity and floating-point position separate. The planned data outputs do not run through the beauty grade.

Two questions remain for the first visual review. Neither blocks building the specified scene.

| Review question | Decision to use now | Change only if the review shows a problem |
|---|---|---|
| Does the open frame preserve enough of the Pi outline at 240 pixels wide? | Keep the 10.2 × 7.2 cm frame and 9.1 × 6.1 cm opening specified in the mesh sheet | Thin the frame rails while keeping the board and camera fixed |
| Does the separated assembly still feel like one company brand object? | Use the five assembly levels and short split specified in the motion bible | Reduce explode distance before changing the metaphor or adding labels |

There is no pending choice about dual monitors or deployment content. The user's clarification places those in the deployed-device setup, outside this homepage pack.

Planning validation on 8 September 2026 found six linked documents and 53 specified mesh objects. Conservative bounding-box projection fits both poses in Hero, Front, Top and Back without changing their camera registration; the smallest Hero exploded margin is approximately 0.75 cm in its 16.5 cm frame. The storage carrier has approximately 0.057 cm clearance above the withdrawn support tips before its lateral move begins. Local document links and whitespace checks pass, and the existing CanadaBuys MCP smoke test passes. These are numerical and document checks; rendered appearance, actual mesh intersections and browser performance remain checks for the future build.
