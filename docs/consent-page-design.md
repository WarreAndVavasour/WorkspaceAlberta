# Archival sign-in and consent design

The sign-in and consent pages sit on ELL's deep blue (`#002A3A`). Nineteen
hand-coloured plates from Henry J. Warre's *Sketches in North America and the
Oregon Territory* (London: Dickinson & Co., 1848) drift slowly in four columns
either side of the card, mixed with four fragments of Warre's own handwriting
from his diary of the July 1845 crossing up the Bow River and over to the
Columbia. Every plate is cropped to the painted image (no paper margin, no
title line) and framed with a single gold hairline set a few pixels off the
image. The consent card carries the same hairline. There are no perforated or
postage-stamp frames.

## Edit or hand off to another coding agent

- `procurement_core/templates/consent.html`: permission copy, the account ledger
  (signed-in email and return host), Allow/Cancel controls and the recognition
  note under the buttons.
- `procurement_core/templates/auth.html`: shared page, branding, archive columns,
  mobile band, footer credit and the motion pause control.
- `procurement_core/assets/auth.css`: colours, gold hairlines, card, column grid,
  drift animation, responsive rules and reduced-motion behaviour.
- `procurement_core/auth_pages.py`: `ARTWORK` (file, caption, note, size) and
  `_RAILS` (which pieces go in which column, top to bottom). `ARTWORK` is also the
  public allowlist used by `public_pages.py` and the OAuth security tests.
- `procurement_core/oauth_http.py`: Google sign-in content and escaped dynamic
  values passed into the consent template. Preserve the existing form action,
  hidden consent ID, and approve/deny values when refining the design.

Run `python scripts/preview_auth_pages.py` from the repo with dependencies
installed. Open `http://127.0.0.1:8765/` for consent or `/signin` for Google sign-in.
The preview binds only to loopback, uses a fictional account, and never issues
tokens or contacts Google. Its buttons show a preview result. Production OAuth
routes and security checks are unchanged.

## Layout

| Viewport | Archive |
| --- | --- |
| 1361 px and wider | Four columns, up to 220 px each, two per side |
| 881–1360 px | The two inner columns, up to 200 px each |
| 880 px and narrower | Columns hidden; one 62 px strip of plates above the card |

Each column repeats its run of pieces three times and moves one run length per
cycle (118–144 s), alternating up and down, so the loop has no visible seam. The
columns fade out under the masthead and above the footer. "Pause the archive"
in the footer stops every column (via `:has()`); `prefers-reduced-motion`
removes the animation and the control. In forced-colours mode the archive is
hidden. All archive images are decorative (`alt=""`, `aria-hidden`), and the
footer names both sources in text.

## Source files

### Plates

The plates are the ones the January 2025 warreandvavasour.com design used for
its hero and business-line cards (`public/business-lines/000000NN.jpg`,
7,200 px wide, added in `warre-vavasour` commit `3843491`, removed in
`c93ca97`). Recover a full-resolution original with:

    git -C C:\Users\chris\warre-vavasour show 3843491:public/business-lines/00000027.jpg > 00000027.jpg

Plate `00000031.jpg` (period title "Indian Tomb") and the route map
`00000045.jpg` are not used.

Crops are in source pixels (left, top, right, bottom). Each crop was resized to
560 px wide with Lanczos, given a light lift (colour ×1.12, contrast ×1.05), and
saved as WebP quality 80.

| Web asset | Source | Crop | Printed title |
| --- | --- | --- | --- |
| `plate-fort-garry.webp` | `00000021.jpg` | 1116, 569, 5688, 3646 | Fort Garry |
| `plate-kaministiquia-falls.webp` | `00000022.jpg` | 1238, 530, 5990, 3711 | Falls of the Kamanis Taquoih River |
| `plate-buffalo-hunting.webp` | `00000024.jpg` | 432, 499, 6768, 4414 | Buffalo Hunting on the W. Prairies |
| `plate-burning-prairie.webp` | `00000025.jpg` | 432, 472, 6768, 4493 | Forcing a Passage through the Burning Prairie |
| `plate-distant-rockies.webp` | `00000026.jpg` | 1008, 596, 6300, 3889 | Distant View of the Rocky Mountains |
| `plate-rocky-mountains.webp` | `00000027.jpg` | 1080, 572, 6228, 3827 | The Rocky Mountains |
| `plate-columbia-source.webp` | `00000028.jpg` | 1188, 652, 6156, 3868 | Source of the Columbia River |
| `plate-fort-vancouver.webp` | `00000030.jpg` | 432, 472, 6768, 4466 | Fort Vancouver |
| `plate-mount-baker.webp` | `00000033.jpg` | 432, 525, 6768, 4466 | Mount Baker |
| `plate-cape-disappointment.webp` | `00000034.jpg` | 432, 499, 6768, 4493 | Cape Disappointment |
| `plate-willamette-valley.webp` | `00000035.jpg` | 1260, 752, 5904, 3789 | Valley of the Willamette River |
| `plate-american-village.webp` | `00000036.jpg` | 1476, 704, 5688, 3694 | The American Village |
| `plate-fort-george.webp` | `00000038.jpg` | 468, 472, 6768, 4440 | Fort George, formerly Astoria |
| `plate-kootenay-river.webp` | `00000039.jpg` | 468, 446, 6732, 4414 | McGillivray or Kootoonai River |
| `plate-les-dalles.webp` | `00000040.jpg` | 1116, 557, 6084, 3778 | Les Dalles, Columbia River |
| `plate-mount-hood-les-dalles.webp` | `00000041.jpg` | 1101, 593, 6156, 3887 | Mount Hood from Les Dalles |
| `plate-mount-hood.webp` | `00000042.jpg` | 1116, 741, 6026, 3878 | Mount Hood |
| `plate-palouse-falls.webp` | `00000043.jpg` | 1418, 565, 5925, 3917 | Fall of the Peloos River |
| `plate-rockies-from-columbia.webp` | `00000044.jpg` | 1058, 501, 6206, 3843 | The Rocky Mountains from the Columbia River looking N.W. |

The small note under each caption (Red River, Columbia River, Cascade Range and
so on) is a plain locator, not a new historical attribution.

### Handwriting

From `C:\Users\chris\wvjournals\sources\H-1700.pdf` (Library and Archives Canada
microfilm of Warre's diary "Red River to the Columbia", June–August 1845). Page
numbers are 1-based PDF pages; transcriptions are in
`wvjournals\workbench\transcriptions\h1700-0NNN.md`. Each clip was rendered with
PyMuPDF at 8× (the source scan is 1,984 × 5,160 px per page), auto-levelled, mapped
to sepia ink `#2B2118` on paper `#ECE2CC`, resized to 560 px wide, and saved as
WebP quality 82. Clip rectangles are in PDF points.

| Web asset | PDF page | Clip (x0, y0, x1, y1) | Caption |
| --- | --- | --- | --- |
| `hand-bow-river.webp` | H-1700, 840 | 241.9, 300.9, 390.9, 335.1 | "We continued our course up Bow River", 23 July 1845 |
| `hand-lower-steps.webp` | H-1700, 842 | 242.2, 121.8, 392.1, 158.5 | "the ascent of the lower steps of the Mountains", 25 July 1845 |
| `hand-beautiful-lakes.webp` | H-1700, 843 | 240.9, 124.5, 390.9, 149.0 | "very beautifully situated lakes", July 1845 |
| `hand-height-of-land.webp` | H-1700, 845 | 240.9, 110.2, 390.9, 163.4 | "over the height of land … & the Columbia", 29 July 1845 |

Original scans are unchanged and are not served. Only the 23 WebP files above
(about 400 KB together) are served, through an exact filename allowlist. No
external image or font host, tracking script, JavaScript or new OAuth scope is
added.
