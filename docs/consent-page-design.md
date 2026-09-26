# Archival sign-in and consent design

The collage uses the owner's **Warre & Vavasour journal folios**. Atelier is a
layout reference only. No artwork from the Atelier collection is used.

## Edit or hand off to another coding agent

- `procurement_core/templates/consent.html`: permission copy, account details and
  Allow/Cancel controls.
- `procurement_core/templates/auth.html`: shared page, branding, collage and footer.
- `procurement_core/assets/auth.css`: ELL blue (`#002A3A`), paper frames, typography,
  placement, responsive layout, motion and reduced-motion behavior.
- `procurement_core/auth_pages.py`: artwork selection and presentation wrapper.
- `procurement_core/oauth_http.py`: Google sign-in content and escaped dynamic
  values passed into the consent template. Preserve the existing form action,
  hidden consent ID, and approve/deny values when refining the design.

Run `python scripts/preview_auth_pages.py` from the repo with dependencies
installed. Open `http://127.0.0.1:8765/` for consent or `/signin` for Google sign-in.
The preview binds only to loopback, uses a fictional account, and never issues
tokens or contacts Google. Its buttons show a preview result. Production OAuth
routes and security checks are unchanged.

## Source files

The source archive is `C:\Users\chris\Downloads\Warre Vavasour Original scans.zip`.
Complete extracted copies are in `C:\Users\chris\wvjournals\sources\H-1700.pdf`
and `H-1701.pdf`. The earlier website documents the same archive in
`C:\Users\chris\warre-vavasour\private\journals\README.md`; its local H-1700 copy
is smaller than the complete archive, so use the `wvjournals` copies.

The seven displayed details are rendered from those PDFs. Original folios are
unchanged and are not included in the public server. Only selected WebP images
are served through an exact filename allowlist. No external image or font host,
tracking script, JavaScript animation or new OAuth scope is added.

| Web asset | Source PDF page (1-based) | Visible subject |
| --- | --- | --- |
| `h1700-662.webp` | H-1700, 662 | Landscape from sketches en route to the Columbia |
| `h1700-454.webp` | H-1700, 454 | Waterfall and handwritten journal text |
| `h1700-448.webp` | H-1700, 448 | Sleighs and handwritten journal text |
| `h1701-250.webp` | H-1701, 250 | Meeting in the mountains |
| `h1700-461.webp` | H-1700, 461 | Travellers, shelter and handwritten journal text |
| `h1700-198.webp` | H-1700, 198 | Camp sketch, oriented upright |
| `h1700-840.webp` | H-1700, 840 | Narrow handwritten journal page |

These are descriptive captions, not a new claim of historical attribution.
The scans retain the original monochrome appearance. The paper colour and
perforations are CSS framing, not alterations to the artwork. Their on-page
presentation is decorative and kept out of the screen-reader reading order.

All selected details were rendered with Poppler at a 2,400-pixel page height,
then resized and encoded as WebP at quality 86. Crop bounds below are measured
in the reviewed 928 × 1,200 preview coordinate space, before rotation:

| PDF page | x | y | width | height | Rotation |
| --- | ---: | ---: | ---: | ---: | --- |
| H-1700 / 662 | 63 | 401 | 622 | 375 | none |
| H-1700 / 454 | 102 | 304 | 698 | 551 | none |
| H-1700 / 448 | 102 | 310 | 697 | 545 | none |
| H-1700 / 461 | 111 | 328 | 645 | 513 | none |
| H-1700 / 198 | 268 | 309 | 354 | 581 | 90° clockwise |
| H-1700 / 840 | 372 | 159 | 230 | 770 | none |
| H-1701 / 250 | 189 | 277 | 490 | 319 | none |

The page includes a keyboard-accessible motion pause control. The system
reduced-motion preference disables animation automatically. On narrow screens,
two small plates sit above the form, leaving permissions and actions unobstructed.
The official Google sign-in image stays unmodified.

Initial validation: the OAuth, OAuth security, Google login and CanadaBuys smoke
suites ran 56 tests: 48 passed and eight opt-in database tests were skipped.

Deployed September 26, 2026 from merged commit `fa746ae305f4`. Revision
`workspacealberta-archive-fa746ae305f4` serves 100% of production traffic. The
full pre-deployment suite passed 162 tests with eight opt-in tests skipped.
The tagged revision and public domain passed OAuth discovery/challenge checks,
all 26 tool titles, Google sign-in rendering, byte-for-byte archive image checks,
procurement search, details and matching. Browser inspection confirmed all seven
archive images and the Google button loaded on the live sign-in page.
The underlying Google authentication configuration and credentials are unchanged.
See [the release workflow](cloud-run-workflow.md) for future deployments.
