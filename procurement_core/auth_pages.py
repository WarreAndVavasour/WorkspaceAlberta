"""Shared presentation for sign-in and consent; no authentication logic lives here."""
from html import escape
from pathlib import Path
from string import Template

_ROOT = Path(__file__).parent
_SHELL = Template((_ROOT / "templates" / "auth.html").read_text(encoding="utf-8"))
CONSENT = Template((_ROOT / "templates" / "consent.html").read_text(encoding="utf-8"))
_STYLE = (_ROOT / "assets" / "auth.css").read_text(encoding="utf-8")

# (file stem, kind, caption, note, width, height)
# Plates: hand-coloured lithographs from Henry J. Warre, "Sketches in North America and the
# Oregon Territory" (London: Dickinson & Co., 1848), cropped to the painted image.
# Handwriting: Warre's diary "Red River to the Columbia", July 1845 (folio H-1700).
# Source scans, page numbers and crop bounds are recorded in docs/consent-page-design.md.
ARTWORK = (
    ("plate-fort-garry", "plate", "Fort Garry", "Red River", 560, 377),
    ("plate-kaministiquia-falls", "plate", "Falls of the Kamanis Taquoih River", "Kaministiquia River", 560, 375),
    ("plate-buffalo-hunting", "plate", "Buffalo Hunting on the W. Prairies", "Western prairies", 560, 346),
    ("plate-burning-prairie", "plate", "Forcing a Passage through the Burning Prairie", "Western prairies", 560, 355),
    ("plate-distant-rockies", "plate", "Distant View of the Rocky Mountains", "Rocky Mountains", 560, 348),
    ("plate-rocky-mountains", "plate", "The Rocky Mountains", "Rocky Mountains", 560, 354),
    ("plate-columbia-source", "plate", "Source of the Columbia River", "Upper Columbia", 560, 363),
    ("plate-fort-vancouver", "plate", "Fort Vancouver", "Columbia River", 560, 353),
    ("plate-mount-baker", "plate", "Mount Baker", "Cascade Range", 560, 348),
    ("plate-cape-disappointment", "plate", "Cape Disappointment", "Mouth of the Columbia", 560, 353),
    ("plate-willamette-valley", "plate", "Valley of the Willamette River", "Oregon Territory", 560, 366),
    ("plate-american-village", "plate", "The American Village", "Oregon Territory", 560, 398),
    ("plate-fort-george", "plate", "Fort George, formerly Astoria", "Columbia River", 560, 353),
    ("plate-kootenay-river", "plate", "McGillivray or Kootoonai River", "Kootenay River", 560, 355),
    ("plate-les-dalles", "plate", "Les Dalles, Columbia River", "Columbia River", 560, 363),
    ("plate-mount-hood-les-dalles", "plate", "Mount Hood from Les Dalles", "Columbia River", 560, 365),
    ("plate-mount-hood", "plate", "Mount Hood", "Cascade Range", 560, 358),
    ("plate-palouse-falls", "plate", "Fall of the Peloos River", "Palouse River", 560, 416),
    ("plate-rockies-from-columbia", "plate", "The Rocky Mountains from the Columbia River", "Looking north-west", 560, 364),
    ("hand-bow-river", "hand", "“We continued our course up Bow River”", "Diary · 23 July 1845", 560, 129),
    ("hand-lower-steps", "hand", "“the ascent of the lower steps of the Mountains”", "Diary · 25 July 1845", 560, 137),
    ("hand-beautiful-lakes", "hand", "“very beautifully situated lakes”", "Diary · July 1845", 560, 91),
    ("hand-height-of-land", "hand", "“over the height of land … & the Columbia”", "Diary · 29 July 1845", 560, 199),
)

# Four slow columns, two either side of the card. Each piece appears exactly once.
_RAILS = (
    ("plate-rocky-mountains", "plate-fort-garry", "hand-bow-river", "plate-palouse-falls",
     "plate-fort-vancouver", "plate-cape-disappointment"),
    ("plate-buffalo-hunting", "plate-rockies-from-columbia", "plate-fort-george", "hand-lower-steps",
     "plate-kaministiquia-falls", "plate-mount-hood-les-dalles"),
    ("plate-kootenay-river", "hand-height-of-land", "plate-burning-prairie", "plate-mount-baker",
     "plate-willamette-valley"),
    ("plate-distant-rockies", "plate-les-dalles", "plate-columbia-source", "hand-beautiful-lakes",
     "plate-american-village", "plate-mount-hood"),
)

_BY_STEM = {art[0]: art for art in ARTWORK}


def _img(stem: str) -> str:
    _, _, _, _, width, height = _BY_STEM[stem]
    return (f'<img src="/assets/archive/{stem}.webp" alt="" width="{width}" height="{height}" '
            f'decoding="async">')


def _piece(stem: str, position: int) -> str:
    _, kind, caption, note, _, _ = _BY_STEM[stem]
    # Width variants come from the position in the run, so every repeat of a run is identical.
    return (f'<figure class="piece piece-{kind} v{position % 3}"><span class="fillet">{_img(stem)}</span>'
            f'<figcaption>{escape(caption)}<small>{escape(note)}</small></figcaption></figure>')


def _archive() -> str:
    """Decorative columns; each run repeats three times so the drift loops without a seam."""
    rails = []
    for i, stems in enumerate(_RAILS, 1):
        run = "".join(_piece(stem, position) for position, stem in enumerate(stems))
        rails.append(f'<div class="rail rail-{i}"><div class="rail-track">{run * 3}</div></div>')
    return rails[0] + rails[1] + '<div class="rail-gap"></div>' + rails[2] + rails[3]


def _band() -> str:
    """Narrow screens get a single horizontal strip of plates above the card."""
    run = "".join(f'<span class="band-plate">{_img(art[0])}</span>'
                  for art in ARTWORK if art[1] == "plate")
    return f'<div class="band-track">{run}{run}</div>'


_ARCHIVE = _archive()
_BAND = _band()


def auth_page(title: str, content: str, *, step: str, step_label: str) -> str:
    """Wrap trusted markup; callers must escape all interpolated user values."""
    return _SHELL.substitute(title=escape(title), style=_STYLE, archive=_ARCHIVE, band=_BAND,
                             content=content, step=escape(step), step_label=escape(step_label))
