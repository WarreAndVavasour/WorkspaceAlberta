# Motion bible — field to company brand object

The field invites exploration of Warre & Vavasour. The Pi-class object gives that invitation a physical form, then opens into an inspectable assembly. The four company routes remain ordinary text links. Animation never becomes a prerequisite for understanding the company or choosing a route.

Use short, decisive motion. Hold the camera still until the visitor looks around. Keep the indicator steady, the page white, and the geometry stable after each action. Use no bounce, elastic easing, overshoot, looping camera travel, or automatic assembly cycle.

The reference mapping below distinguishes source behavior from new design. Citations identify the public scripts that were inspected; numerical art-direction values outside the source column are our choices.

| Antigravity mechanism | Verified source | Translation to our Pi |
|---|---|---|
| Position and rest-position textures, alternating rt1/rt2, 256-square simulation | [MainParticles](https://antigravity.google/_astro/MainParticlesComponent.astro_astro_type_script_index_0_lang.Dox42TL8.js) | Keep persistent point identities while approaching the object; use the texture as capacity, not an instruction to draw every slot |
| uRingPos, uRingRadius, uRingWidth, uRingWidth2, uRingDisplacement | [MainParticles](https://antigravity.google/_astro/MainParticlesComponent.astro_astro_type_script_index_0_lang.Dox42TL8.js) | A shallow cursor response around a fixed readable copy pocket; the cursor cannot drag particles through the sentence |
| Light/dark theme via uColorScheme | [MainParticles](https://antigravity.google/_astro/MainParticlesComponent.astro_astro_type_script_index_0_lang.Dox42TL8.js) | White page, charcoal-grey particles and one quiet board/indicator palette; no automatic dark-mode art treatment in this pack |
| Fixed/variable Poisson sampling, image-derived nearest targets | [MorphingParticles](https://antigravity.google/_astro/MorphingParticlesComponent.astro_astro_type_script_index_0_lang.B4r3VvfF.js) | Sample our registered silhouette, then attach points to positions and semantic groups from our geometry; do not reuse flat icon textures |
| Hover 0.5 seconds power3.out; push 2 seconds power2.out | [MorphingParticles](https://antigravity.google/_astro/MorphingParticlesComponent.astro_astro_type_script_index_0_lang.B4r3VvfF.js) | Shorten the invitation and overlap commit/materialization; keep the broader push feeling for assembly separation |
| Easing implementation | [GSAP runtime](https://antigravity.google/_astro/gsap.Bi_c5vh2.js) | power3.out = 1−(1−t)^4; power2.out = 1−(1−t)^3 for normalized time t |
| Visibility observer, stop/resume, cleanup on unload | [MainParticles](https://antigravity.google/_astro/MainParticlesComponent.astro_astro_type_script_index_0_lang.Dox42TL8.js) | Stop offscreen/hidden work immediately. Add delayed disposal of idle resources and restore the current UI state on return. |
| Renderer and render-target support | [Mouse shared runtime](https://antigravity.google/_astro/Mouse.ZrlRGzn3.js) | Technical precedent only; do not copy its runtime into the repo |

The baseline settings come from the [live light-theme component attributes](https://antigravity.google/), rather than the fallback values in the constructors. Begin later prototyping with Main density 230, particle scale 0.59, widths 0.006 / 0.107 and displacement 0.62. Begin Morph at density 50 and scale 0.6. These are reference-space parameters; a new renderer must visually calibrate them to its stage, not interpret them as centimetres or exact particle counts.

| Beat | Exact target | What moves | Ease and completion | Source analogue |
|---|---|---|---|---|
| Idle field | Continuous while visible | Particle drift only; ≤2 CSS pixels per second near the pocket; outer field may reach 4 | Seeded low-energy motion; no camera animation | Main field |
| Attract / cursor | Respond on the next frame; settle in 0.12 s | Ring centre follows at 10% of pointer displacement from its resting centre, clamped to 24 CSS pixels | power3.out; pointer leave returns in 0.24 s | uRing* |
| Hover invitation | 0.24 s in / 0.18 s out | Local particle opacity increases by at most 0.08; ring radius contracts by 3% | power3.out; never auto-materializes | Morph hoverProgress |
| Commit | Click time 0.00…0.42 s | Field points approach registered Pi targets; surplus particles fade | power3.out; guide appears in parallel by 0.24 s | Morph hoverProgress |
| Materialize Pi | 0.20…1.20 s from the same click | Silhouette resolves by 0.82 s; matching shaded geometry fades in 0.72…1.20 s | power3.out target approach; complementary opacity handoff | Morph plus our silhouette/mesh |
| Explode / examine | 1.60 s after Open object | Five parent assemblies separate using scene-sheet offsets | Frame power3.out; others power2.out; no moving camera | New Blender assembly pose |
| Named angle | 0.24 s | Camera only; retain object pose | power3.out; direct pointer drag has no release inertia | New examine behavior |
| Assemble object | 1.00 s | Parents return to rest from current pose | power3.out; restore lateral alignment before reseating | New reverse assembly |
| Dismiss / ephemeral | 0.48 s | Geometry fades to registered surface points in first 0.16 s; points disperse and fade; idle field returns | power3.out; guide closes in parallel | Reverse morph |
| Route peel | Optional 0.24 s | Outgoing stage moves at most 12 CSS pixels toward selected label and fades | power3.out; navigation begins immediately | New company navigation |

Commit and materialization overlap. The complete click-to-shaded-object sequence is 1.20 seconds, not 0.42 plus 1.20 seconds. Explode is a separate deliberate action, so landing on the page never starts a multi-second show. All effects are silent.

The idle field occupies roughly 70% of the available stage width. The hollow region is the union of a soft elliptical void and the actual sentence/CTA bounds inflated by 32 CSS pixels. Keep particle opacity zero inside those inflated bounds, fading to ordinary field opacity over the next 24 pixels. The pointer-driven ring uses its clamped motion outside this exclusion. Text reflow changes the exclusion bounds before the next visible frame.

Use nominal ring radius 0.175 in the reference field coordinate space. Reduce autonomous radius oscillation to ±1% over 8 seconds; the source's larger oscillation is not required to preserve its lightness. Render particles as matte points between 0.8 and 2.0 CSS pixels at desktop scale, with most between 0.9 and 1.3. Use colour `#7E8983`, typical alpha 0.14–0.32 and peak alpha 0.45. Never use additive glow, star streaks, lens flare or a saturated halo. Reduced contrast applies only to decoration, not to text or controls.

At commit, choose the active morph subset once and retain its identities. Its screen positions travel toward the canonical Hero camera's targets while the destination stage and text settle into their open-guide layout. The remaining field points fade to zero by 0.32 seconds. Keep no more than 8% of the idle field visible outside the object and text zones once the object is shaded. That residue disappears while the visitor is dragging.

By 0.82 seconds, the visible point outline and the projected GLB outline must match. During 0.72…1.20 seconds, reduce point opacity as the shaded object gains opacity; avoid a bright double exposure. The mesh uses the same root transform, camera, scale and target as the sampled point state. The cube-to-Pi transformation is a semantic replacement of the reference target, not a requirement to show a cube first.

Use a 256 × 256 simulation capacity, allowing at most 65,536 slots, with an explicit active count. Seed base Poisson generation with 20260908 on a 500 × 500 domain. Preserve the reference density mapping: nominal Main 230 and Morph 50. Record the resulting counts rather than declaring density 230 to mean 230 points. Start with a desktop cap of 16,000 active idle points and 4,000 active morph points; if generated sets are smaller, keep them smaller. Caps are our proposed budgets and are not measured claims about the reference site.

The morph target set has exactly as many active identities as the Morph base set after capping. Generate that many object samples using the shot schedule's stratified allocation. Match each selected idle identity to a target once; never rerun random nearest matching during a transition or pointer move. Surplus Main identities fade away and retain their idle seeds for dismissal. Additional shader slots remain inactive. This makes the difference between the two density settings intentional and avoids particle births or rearrangement halfway through the silhouette.

On constrained/mobile devices, cap idle at 8,000 and morph at 2,000 points, cap device-pixel ratio at 1.5, and limit animation to 30 fps if a 60 fps prototype misses its frame budget. Desktop DPR cap is 2. These are proposed quality tiers for later measurement. Keep one field simulation running, reuse its buffers through the morph, and stop it after the mesh has resolved. Orbit manipulates geometry without running an invisible particle simulation.

The later implementation should target a 16.7 ms total frame at 60 Hz and 33.3 ms at 30 Hz during interaction. Check at a representative 1440 × 900 desktop and 390 × 844 touch viewport. If it misses repeatedly, first reduce DPR, then point count, then use the static still path. Keep the 1.20/1.60/0.48-second timing and company route access. Do not extend motion to hide slow loading.

The default state progression is Idle → Resolving → Assembled → Exploded. Assembled and Exploded both expose the same route guide. Hover is a temporary modifier of Idle. RouteLeaving and Dismissing can interrupt any state. Offscreen is a rendering suspension, not a new navigation state.

While resolving, a second Explore action has no effect. An Open request stores one desired exploded state and begins when the matching shaded object is ready; repeated requests replace the desired state rather than creating a queue. Back/Escape cancels that request and dismisses from the current visual values. A route click cancels pending visual work immediately. Once geometry is drawable, Open/Assemble retarget from the current parent transforms without snapping.

When dismissing from an arbitrary examine angle or exploded state, use surface samples transformed by the current camera and group poses. Do not jump back to the canonical silhouette for the dissolve. The field can reseed behind zero opacity. Reset the camera to Hero only after the object has disappeared. Restoring the page via browser Back shows the saved object/guide state without an entrance replay.

When the stage leaves the viewport or the document becomes hidden, stop render and simulation work immediately. Retain lightweight pose, focus and route state. After 10 seconds offscreen, the later implementation may release the field's render targets; it must recreate them once on return. Resume with a zero delta-time first frame and show the current requested state, without replaying elapsed animation. Dispose resources and event subscriptions on unmount; an IntersectionObserver pause alone is not disposal.

For reduced motion, use the rendered stills and immediate state swaps described in the click guide. Do not auto-morph, animate opacity, move the camera, or attract the pointer. Texture/GLB load failure uses the same static/text fallback. All four company links remain available through every visual state.

Motion review should answer four concrete questions: does the guide open before the visitor needs it; does the silhouette handoff stay registered; do parts remain recognizably attached to their correct assemblies; and can Back or a route click interrupt without a flash or jump? The Blender proof is responsible for composition and movement. Later browser profiling is responsible for actual frame timing and input behavior.
