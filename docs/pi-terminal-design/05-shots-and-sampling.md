# Shot, pass and sampling schedule

This is the export plan for the Blender builder and the later web-animation builder. No listed image, GLB or movie has been exported as part of this planning task. Keep the eventual scene as `wa_pi_terminal_master.blend`; use the camera and five parent names from the Blender specification unchanged.

Render canonical Hero and Explode at 2048 × 2048 pixels with pixel aspect 1. Keep both cameras at the exact same transform, 16.5 cm orthographic scale, zero shift and the same target. Do not crop to visible bounds, recenter each part, or normalize each pose independently. The empty frame area is meaningful registration data. Use a shared 1024 × 1024 derivative for point generation and a shared 512 × 512 derivative for low-resolution checks.

Five useful examine angles are Hero three-quarter, Front, Top, Back three-quarter and Ports close. Render assembled and exploded versions of the first four; render Ports close in assembled pose only. The four full-object views support static examine controls. Ports is an intentional detail crop, not an additional morph target. Never animate an endless turntable on Home.

| Shot / pose | Camera and size | Required planned filenames | Review purpose |
|---|---|---|---|
| S01 — assembled hero | CAM_HERO, 2048 square | `wa_pi_beauty_ortho.png`, `wa_pi_beauty_ortho_white.png`, `wa_pi_silhouette.png`, `wa_pi_hero_data.exr`, `wa_pi_hero_depth.png`, `wa_pi_hero_id.png` | Arrival silhouette, material proof and canonical target |
| S02 — exploded hero | CAM_EXPLODE, 2048 square | `wa_pi_exploded_beauty.png`, `wa_pi_exploded_white.png`, `wa_pi_exploded_silhouette.png`, `wa_pi_exploded_data.exr`, `wa_pi_exploded_depth.png`, `wa_pi_exploded_id.png` | Five assembly levels and matching registration |
| S03 — front | CAM_FRONT, 2048 square | `wa_pi_front.png`, `wa_pi_front_exploded.png` | Power edge, thin frame, steady status indicator |
| S04 — top | CAM_TOP, 2048 square | `wa_pi_top.png`, `wa_pi_top_exploded.png` | Board footprint, opening, occupied/free regions |
| S05 — reverse three-quarter | CAM_BACK, 2048 square | `wa_pi_back_threequarter.png`, `wa_pi_back_threequarter_exploded.png` | SD side, GPIO and reverse assembly readability |
| S06 — ports detail | CAM_PORTS, 2048 square | `wa_pi_ports_close.png` | Open sockets, quiet highlights; intended crop recorded in metadata |
| S07 — commit/materialize proof | CAM_HERO, 1080 square, 60 fps, frames 1–73 | `wa_pi_commit_review.mp4` | 1.20 seconds of field-to-object timing; Blender point proxy permitted |
| S08 — open proof | CAM_HERO, 1080 square, 60 fps, frames 1–97 | `wa_pi_open_review.mp4` | 1.60-second parent travel, clearance, final composition |
| S09 — assemble proof | CAM_HERO, 1080 square, 60 fps, frames 1–61 | `wa_pi_assemble_review.mp4` | 1.00-second return without sideways scraping |
| S10 — dismiss proof | CAM_HERO and one mid-orbit view, 1080 square, 60 fps, frames 1–30 | `wa_pi_dismiss_review.mp4`, `wa_pi_dismiss_orbit_review.mp4` | Target 0.48-second exit; 29 frame intervals give a 0.483-second proof |
| S11 — immediate/static states | Corresponding stills above, 1024 square | `wa_pi_static_rest.png`, `wa_pi_static_exploded.png` | Reduced-motion and unsupported-renderer path |
| S12 — small silhouette check | Hero and Explode downscaled on white | `wa_pi_readability_240.png`, `wa_pi_readability_390.png` | Assembled and exploded side by side; dimensions refer to each object's stage width |

Frame ranges include both endpoint samples. When encoding proof movies, do not add a duplicate endpoint or an extra hold to claim an exact duration. Review durations are measured between endpoint states. Endpoint stills are authoritative where a duration does not divide evenly into frames.

For beauty, use the scene's Cycles lighting and colour management. Transparent PNGs are RGBA, 16-bit, sRGB display encoded, with straight alpha. Produce a separate white-composited image from the same render, not from a differently lit scene. Make web-sized PNG or WebP derivatives later; the source PNG remains the reference. No motion blur or depth of field is used, so every rendered edge can match the sampling target.

For `wa_pi_silhouette.png` and `wa_pi_exploded_silhouette.png`, write RGB white on covered geometry and zero outside, with alpha equal to antialiased object coverage. White means object; alpha zero means empty. Exclude lights, helpers, reference collections and any proxy particles. Holes and gaps stay transparent. Do not include self-shadows, the beauty's grey shading or a background floor in a silhouette.

Alpha is the sampling authority. Gate sample eligibility at alpha ≥0.5, with alpha 0.25…0.75 used only for optional boundary refinement. At an antialiased edge, do not assign a point to a partly covered pixel without selecting a valid covered surface. The reference morph sampler reads red intensity and does not use this alpha contract. If its density idea is re-created, explicitly convert to a suitable density field, such as 1−alpha with outside pixels rejected; never feed the raw white-on-transparent mask into an unmodified red-channel sampler. The [Morph component](https://antigravity.google/_astro/MorphingParticlesComponent.astro_astro_type_script_index_0_lang.B4r3VvfF.js) is the source of that distinction.

Use a dedicated data view layer with no motion blur, depth of field, denoising, exposure adjustment, tone mapping, gamma, bloom, filtering across IDs, or artistic grade. Enable Position, Normal, Z and Object Index. Keep Position/Normal in world space as described by [Blender's passes documentation](https://docs.blender.org/manual/en/4.5/render/layers/passes.html). Write a 32-bit float, ZIP-compressed multilayer OpenEXR. Store `Position.X/Y/Z`, `Normal.X/Y/Z`, `Z`, `IndexOB` and coverage. Preserve negative positions. Z/Position/index edges need special handling because those passes are not antialiased.

Treat raw Blender Z as a diagnostic. For a portable signed camera-depth channel, derive `DepthCamera_m = dot(P−C, F)` from world position P, camera position C, and unit camera-forward vector F. Add that as a named channel to the data EXR. Background pixels have coverage zero and are ignored, not interpreted as a real depth of zero. This definition avoids ambiguity about ray distance versus projected depth.

The PNG depth preview is 16-bit single-channel linear data, never a beauty image. Map 0.05…0.55 metres of `DepthCamera_m` to 0…65534, with near black and far white. Reserve 65535 for background. Use the same range for assembled and exploded Hero. Store this range in metadata. If any valid pixel falls outside it, revise the common range for both poses and rerender both; do not silently clamp or independently normalize. EXR remains authoritative for position reconstruction.

For hard identity maps, assign the numeric IDs below as object Pass Index. Save `wa_pi_hero_id.png` and `wa_pi_exploded_id.png` as 16-bit grayscale non-colour integer data: stored sample 0 is background, 1…16 identify parts. In the compositor, divide the IndexOB value by 65535 before a 16-bit BW PNG File Output; use Raw/non-colour output with the beauty view transform disabled. On reading the PNG, recover the stored integer sample without sRGB conversion. Do not stretch occupied values to fill the 16-bit range. Use nearest-neighbour sampling and the separate alpha coverage map. Preserve exact integer values on roundtrip; a conventional colour-managed PNG export is insufficient.

| Numeric ID | Mask suffix | Moving parent | Includes |
|---:|---|---|---|
| 1 | `board` | P_BOARD | PCB, board pads and its four screws |
| 2 | `soc` | P_BOARD | SoC package only |
| 3 | `ram` | P_BOARD | RAM package only |
| 4 | `usb` | P_BOARD | Both USB stacks and their joined interiors |
| 5 | `ethernet` | P_BOARD | Ethernet shell and interior |
| 6 | `gpio` | P_BOARD | GPIO base and pins |
| 7 | `sd` | P_BOARD | SD socket and card |
| 8 | `power` | P_BOARD | USB-C power socket and power button |
| 9 | `hdmi` | P_BOARD | Both HDMI sockets |
| 10 | `utility` | P_BOARD | Controller, PMIC, oscillator, FPC/PCIe sockets and passives |
| 11 | `cooler` | P_COOLER | Pad, foot, fins and cooler fasteners |
| 12 | `frame` | P_FRAME | Upper frame and frame screws |
| 13 | `hat` | P_STORAGE | Carrier board, its pads and PCIe socket |
| 14 | `storage` | P_STORAGE | M.2 socket, SSD board, chips and retainer |
| 15 | `base` | P_BASE | Base plate and all support posts |
| 16 | `status` | P_FRAME | Single indicator lens |

For each suffix above, plan both `wa_pi_hero_mask_{suffix}.png` and `wa_pi_explode_mask_{suffix}.png`: 32 visible masks in total. Thus the SoC files are `wa_pi_hero_mask_soc.png` and `wa_pi_explode_mask_soc.png`; the latter reveals the package after its cooler has lifted. Generate visible masks with Cryptomatte object selections or dedicated coverage renders, with all other geometry still occluding. These are white coverage masks over transparent black, with no shadows baked in. Do not derive smooth coverage by blurring integer ID maps.

| Assembled visible mask | Exploded visible mask |
|---|---|
| `wa_pi_hero_mask_board.png` | `wa_pi_explode_mask_board.png` |
| `wa_pi_hero_mask_soc.png` | `wa_pi_explode_mask_soc.png` |
| `wa_pi_hero_mask_ram.png` | `wa_pi_explode_mask_ram.png` |
| `wa_pi_hero_mask_usb.png` | `wa_pi_explode_mask_usb.png` |
| `wa_pi_hero_mask_ethernet.png` | `wa_pi_explode_mask_ethernet.png` |
| `wa_pi_hero_mask_gpio.png` | `wa_pi_explode_mask_gpio.png` |
| `wa_pi_hero_mask_sd.png` | `wa_pi_explode_mask_sd.png` |
| `wa_pi_hero_mask_power.png` | `wa_pi_explode_mask_power.png` |
| `wa_pi_hero_mask_hdmi.png` | `wa_pi_explode_mask_hdmi.png` |
| `wa_pi_hero_mask_utility.png` | `wa_pi_explode_mask_utility.png` |
| `wa_pi_hero_mask_cooler.png` | `wa_pi_explode_mask_cooler.png` |
| `wa_pi_hero_mask_frame.png` | `wa_pi_explode_mask_frame.png` |
| `wa_pi_hero_mask_hat.png` | `wa_pi_explode_mask_hat.png` |
| `wa_pi_hero_mask_storage.png` | `wa_pi_explode_mask_storage.png` |
| `wa_pi_hero_mask_base.png` | `wa_pi_explode_mask_base.png` |
| `wa_pi_hero_mask_status.png` | `wa_pi_explode_mask_status.png` |

Additionally render five isolated assembly sets at the Hero camera in rest coordinates, hiding all other parents: `wa_pi_isolated_base_silhouette.png`, `wa_pi_isolated_storage_silhouette.png`, `wa_pi_isolated_board_silhouette.png`, `wa_pi_isolated_cooler_silhouette.png`, `wa_pi_isolated_frame_silhouette.png`. Pair each with the corresponding `wa_pi_isolated_{base|storage|board|cooler|frame}_data.exr`. These preserve concealed geometry needed when the assembly separates. The frame set includes its indicator. Never merge isolated passes into one first-surface depth image.

A silhouette/depth pair represents only visible surfaces from its camera. It is sufficient for the flat entrance target but cannot support arbitrary rotation or reveal hidden backs. Deliver `wa_pi_terminal_lod0.glb` and `wa_pi_terminal_lod1.glb` from the same scene as planned geometry handoffs. Preserve the five parents, mesh names, local origins, PBR materials and semantic IDs. Bake no exploded displacement into rest vertices. Preserve separate groups in any mesh optimization. Keep the original Blender scene as the geometry authority.

The GLB coordinate basis follows glTF's metre/Y-up convention. Record the conversion explicitly: Blender (x,y,z) metres becomes glTF (x,z,−y) metres. Applying the inverse yields Blender coordinates. Parent offset vectors and camera transforms must use the same basis conversion. Never mix centimetre scene notes with metre EXR or GLB coordinates.

Plan `wa_pi_scene_manifest.json` as export metadata, written by the future builder. It records scene version, Blender version, seed 20260908, units, both coordinate bases, camera world matrices and inverse matrices, orthographic scale, resolution, pixel origin, alpha interpretation, depth range, semantic ID table, parent memberships, rest/explode transforms, required filenames and hashes. Include mesh triangle counts after export. This pack specifies its content only; it does not create an implementation or an empty pretend export.

Define canonical image UV with u increasing left to right and v increasing bottom to top. A PNG pixel at column x and top-origin row y maps to u=(x+0.5)/width and v=1−(y+0.5)/height. Do not flip Y twice. For the Hero frame, the image plane spans 0.165 metres both horizontally and vertically. Reconstruct a point as C + R·((u−0.5)·0.165) + U·((v−0.5)·0.165) + F·DepthCamera_m, where R/U/F are the camera's unit right/up/forward vectors. Verify against the Position pass, which remains the preferred source of actual world coordinates.

For the first silhouette target, sample visible coverage with deterministic Poisson points and attach every point to a valid Position/Normal/ID pixel, preferring a valid interior neighbour at antialiased edges. Keep each point's rest position, normal, part_id, moving parent and stable identity. Do not average depths or IDs at occlusion boundaries. During the shaded handoff, the mesh and these points must share one camera transform and one stage projection.

Allocate the actual morph point count across the five visible parents. Reserve 8% of points for the frame outline and 8% for the board/port outline, drawn from their coverage boundaries. Allocate the remainder by visible projected area, with a minimum of 3% per parent that occupies at least 1% of foreground pixels. Take those minima from the largest region. If a region is fully hidden in the rest pose, give it no visible entrance points; its later surface samples come from isolated passes or mesh sampling. Within P_BOARD, favour USB/Ethernet edges and the GPIO outline before allocating points to tiny passives. This improves recognition without raising the nominal Morph density above 50.

For examine and arbitrary-angle dismissal, sample the actual triangles by surface area with a stable seed, recording triangle identity, barycentric coordinates and parent membership. Use the shaded geometry's visibility/depth to hide back-facing or occluded points. This 3D sample set is separate from the sparse 2D entrance allocation, but may reuse stable identities during the opacity handoff. Keep its active count within the same 4,000-point desktop or 2,000-point mobile morph cap. Future dissolve targets are transformed from the current pose, not from a cached front-view PNG.

To make the motion proofs without implementing a website, create a separate `WA_MOTION_PREVIS` Blender scene linked to the master geometry. Represent samples as instanced camera-facing discs at the planned positions. Match 0.8–2.0 CSS-pixel apparent size at the proof resolution; use flat grey materials with the motion bible's opacity limits. Animate stable sample positions between an annular rest field and their surface targets, with the same timing and pose groups. This is an editable visual proxy for review, not a performance test or a requirement to reproduce Antigravity's shaders inside Blender.

Verify the eventual exports in this order: the 8.5 × 5.6 cm board and named parents; assembled/exploded clearance; 240-pixel readability; identical Hero/Explode camera metadata; matching beauty/mask outlines; integer ID roundtrip; Position/depth reconstruction within 0.05 cm; matching GLB projection within one pixel at 1024 square; motion timing and interruption proofs; and static state coverage. Overlays must not show a framing jump between points and mesh. Do not mark exports complete until the images, geometry and their manifest agree.
