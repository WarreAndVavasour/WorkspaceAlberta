"""Build budget2026.warreandvavasour.com end to end. Python 3.9+, standard library only.

    python scripts/build_all.py            # writes out/
    python scripts/build_all.py --preview  # writes out-preview/ with relative links

Steps: parse the chapter cost tables -> extract measures -> tax annex -> verify -> build the site.
The build stops if verify.py finds a figure that does not match its cited page.
(data/source.json is produced from the budget PDF by scripts/index_pdf.py.)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S, D = ROOT / "scripts", ROOT / "data"
preview = "--preview" in sys.argv
steps = [
    [S / "parse_tables.py", D / "source.json", D / "tables.json"],
    [S / "extract.py", D],
    [S / "annex.py", D],
    [S / "verify.py", D],
    [S / "build_site.py", D, ROOT / ("out-preview" if preview else "out")] + (["--preview"] if preview else []),
]
for step in steps:
    print("::", step[0].name)
    subprocess.run([sys.executable, "-I", *map(str, step)], check=True)
