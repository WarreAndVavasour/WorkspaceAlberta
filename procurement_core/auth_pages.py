"""Shared presentation for sign-in and consent; no authentication logic lives here."""
from html import escape
from pathlib import Path
from string import Template

_ROOT = Path(__file__).parent
_SHELL = Template((_ROOT / "templates" / "auth.html").read_text(encoding="utf-8"))
CONSENT = Template((_ROOT / "templates" / "consent.html").read_text(encoding="utf-8"))
_STYLE = (_ROOT / "assets" / "auth.css").read_text(encoding="utf-8")

# PDF page numbers are retained so each detail can be traced to the original folio.
ARTWORK = (
    ("h1700-662", "En route to the Columbia", 900, 543),
    ("h1700-454", "Falls on the St. Maurice", 900, 710),
    ("h1700-448", "Sleighs & winter travel", 900, 704),
    ("h1701-250", "A meeting in the mountains", 900, 586),
    ("h1700-461", "Notes from the journey", 900, 716),
    ("h1700-198", "A camp beside the river", 900, 548),
    ("h1700-840", "The handwritten journal", 400, 1339),
)


def auth_page(title: str, content: str, *, step: str, step_label: str) -> str:
    """Wrap trusted markup; callers must escape all interpolated user values."""
    plates = "".join(
        f'<figure class="plate plate-{i}"><div class="stamp">'
        f'<img src="/assets/archive/{scan}.webp" alt="" '
        f'width="{width}" height="{height}" decoding="async">'
        f'<figcaption><span>{escape(label)}</span><span>{i:02}</span></figcaption>'
        f'</div></figure>'
        for i, (scan, label, width, height) in enumerate(ARTWORK, 1)
    )
    return _SHELL.substitute(title=escape(title), style=_STYLE, plates=plates,
                             content=content, step=escape(step), step_label=escape(step_label))
