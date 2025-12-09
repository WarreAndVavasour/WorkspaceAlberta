#!/usr/bin/env python3
"""
TikZ to SVG/PNG Renderer for WorkspaceAlberta Documentation

Renders TikZ diagrams to SVG files that can be embedded in markdown.

Requirements:
    pip install pdf2svg  # or use inkscape/dvisvgm
    
System requirements:
    - pdflatex (from TeX Live or MiKTeX)
    - pdf2svg or dvisvgm or inkscape

Usage:
    python render-tikz.py                    # Render all .tex files in diagrams/src/
    python render-tikz.py auth-flow.tex      # Render specific file
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path

# Directories
SCRIPT_DIR = Path(__file__).parent
SRC_DIR = SCRIPT_DIR / "src"
OUTPUT_DIR = SCRIPT_DIR / "output"
TEMP_DIR = SCRIPT_DIR / ".temp"

# LaTeX template for standalone TikZ
LATEX_TEMPLATE = r"""
\documentclass[tikz,border=10pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{shapes.geometric, arrows.meta, positioning, fit, backgrounds, calc}

% Define colors
\definecolor{primary}{HTML}{2563EB}
\definecolor{secondary}{HTML}{7C3AED}
\definecolor{success}{HTML}{10B981}
\definecolor{warning}{HTML}{F59E0B}
\definecolor{danger}{HTML}{EF4444}
\definecolor{neutral}{HTML}{6B7280}
\definecolor{lightbg}{HTML}{F3F4F6}
\definecolor{darktext}{HTML}{1F2937}

% Define styles
\tikzstyle{box} = [
    rectangle, 
    rounded corners=4pt, 
    minimum width=2.5cm, 
    minimum height=1cm,
    text centered, 
    draw=neutral, 
    fill=lightbg,
    font=\sffamily\small
]

\tikzstyle{primarybox} = [
    box,
    draw=primary,
    fill=primary!10,
    text=darktext
]

\tikzstyle{secondarybox} = [
    box,
    draw=secondary,
    fill=secondary!10,
    text=darktext
]

\tikzstyle{successbox} = [
    box,
    draw=success,
    fill=success!10,
    text=darktext
]

\tikzstyle{arrow} = [
    thick,
    ->,
    >=Stealth,
    color=neutral
]

\tikzstyle{dashedarrow} = [
    thick,
    ->,
    >=Stealth,
    dashed,
    color=neutral
]

\tikzstyle{label} = [
    font=\sffamily\footnotesize,
    color=neutral
]

\begin{document}
%TIKZ_CONTENT%
\end{document}
"""


def ensure_dirs():
    """Create necessary directories."""
    SRC_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)


def find_latex():
    """Find pdflatex executable."""
    if shutil.which("pdflatex"):
        return "pdflatex"
    # Windows paths
    for path in [
        r"C:\texlive\2023\bin\win64\pdflatex.exe",
        r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
    ]:
        if os.path.exists(path):
            return path
    return None


def find_converter():
    """Find PDF to SVG converter."""
    converters = [
        ("dvisvgm", ["dvisvgm", "--pdf", "{input}", "-o", "{output}"]),
        ("pdf2svg", ["pdf2svg", "{input}", "{output}"]),
        ("inkscape", ["inkscape", "--export-type=svg", "--export-filename={output}", "{input}"]),
    ]
    
    for name, cmd in converters:
        if shutil.which(name) or shutil.which(cmd[0]):
            return name, cmd
    
    return None, None


def render_tikz(tikz_file: Path) -> Path:
    """Render a TikZ file to SVG."""
    print(f"Rendering {tikz_file.name}...")
    
    # Read TikZ content
    tikz_content = tikz_file.read_text(encoding="utf-8")
    
    # Create full LaTeX document
    latex_doc = LATEX_TEMPLATE.replace("%TIKZ_CONTENT%", tikz_content)
    
    # Write to temp file
    tex_file = TEMP_DIR / f"{tikz_file.stem}.tex"
    tex_file.write_text(latex_doc, encoding="utf-8")
    
    # Find pdflatex
    pdflatex = find_latex()
    if not pdflatex:
        print("ERROR: pdflatex not found. Install TeX Live or MiKTeX.")
        return None
    
    # Run pdflatex
    try:
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-output-directory", str(TEMP_DIR), str(tex_file)],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            print(f"pdflatex error:\n{result.stdout}\n{result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("pdflatex timed out")
        return None
    
    pdf_file = TEMP_DIR / f"{tikz_file.stem}.pdf"
    if not pdf_file.exists():
        print(f"PDF not created: {pdf_file}")
        return None
    
    # Convert to SVG
    svg_file = OUTPUT_DIR / f"{tikz_file.stem}.svg"
    converter_name, converter_cmd = find_converter()
    
    if not converter_name:
        print("WARNING: No PDF-to-SVG converter found. Keeping PDF only.")
        shutil.copy(pdf_file, OUTPUT_DIR / f"{tikz_file.stem}.pdf")
        return pdf_file
    
    # Build command with substitutions
    cmd = [
        arg.format(input=str(pdf_file), output=str(svg_file))
        for arg in converter_cmd
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"Converter error:\n{result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("Converter timed out")
        return None
    
    if svg_file.exists():
        print(f"  -> {svg_file}")
        return svg_file
    
    return None


def render_all():
    """Render all TikZ files in src directory."""
    ensure_dirs()
    
    tikz_files = list(SRC_DIR.glob("*.tex"))
    if not tikz_files:
        print(f"No .tex files found in {SRC_DIR}")
        print("Creating example diagrams...")
        create_example_diagrams()
        tikz_files = list(SRC_DIR.glob("*.tex"))
    
    results = []
    for tikz_file in tikz_files:
        result = render_tikz(tikz_file)
        results.append((tikz_file.name, result))
    
    # Summary
    print("\n--- Summary ---")
    for name, result in results:
        status = "OK" if result else "FAILED"
        print(f"  {name}: {status}")
    
    # Cleanup temp
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)


def create_example_diagrams():
    """Create the example TikZ diagrams for WorkspaceAlberta."""
    ensure_dirs()
    
    # Auth flow diagram
    auth_flow = r"""
\begin{tikzpicture}[node distance=2cm]
    % Nodes
    \node[primarybox, minimum width=3.5cm] (you) {WorkspaceAlberta\\(Template Owner)};
    \node[secondarybox, minimum width=3.5cm, right=3cm of you] (github) {GitHub Codespaces\\(Backend Host)};
    \node[successbox, minimum width=3.5cm, below=2.5cm of $(you)!0.5!(github)$] (users) {Business Users\\(Each with own setup)};
    
    % Arrows
    \draw[arrow] (you) -- node[label, above] {Template configs} (github);
    \draw[arrow] (github) -- node[label, right, align=left] {Auth \& hosting} (users);
    \draw[dashedarrow] (you) -- node[label, left, align=right] {You control\\setup process} (users);
    
    % Labels
    \node[label, above=0.3cm of you] {YOU CONTROL};
    \node[label, above=0.3cm of github] {GITHUB HOSTS};
\end{tikzpicture}
"""
    (SRC_DIR / "auth-flow.tex").write_text(auth_flow, encoding="utf-8")
    
    # User isolation diagram
    user_isolation = r"""
\begin{tikzpicture}[node distance=1.5cm]
    % Template
    \node[primarybox, minimum width=4cm] (template) {Your Template Repo};
    
    % Users
    \node[successbox, below left=2cm and 0.5cm of template] (user1) {User A's Repo\\+ Codespace};
    \node[successbox, below=2cm of template] (user2) {User B's Repo\\+ Codespace};
    \node[successbox, below right=2cm and 0.5cm of template] (user3) {User C's Repo\\+ Codespace};
    
    % Arrows
    \draw[arrow] (template) -- node[label, left] {copy} (user1);
    \draw[arrow] (template) -- node[label, right] {copy} (user2);
    \draw[arrow] (template) -- node[label, right] {copy} (user3);
    
    % Isolation boxes
    \begin{scope}[on background layer]
        \node[draw=success, dashed, rounded corners, fit=(user1), inner sep=8pt, label=below:{\scriptsize Their account}] {};
        \node[draw=success, dashed, rounded corners, fit=(user2), inner sep=8pt, label=below:{\scriptsize Their account}] {};
        \node[draw=success, dashed, rounded corners, fit=(user3), inner sep=8pt, label=below:{\scriptsize Their account}] {};
    \end{scope}
\end{tikzpicture}
"""
    (SRC_DIR / "user-isolation.tex").write_text(user_isolation, encoding="utf-8")
    
    # Secrets flow diagram  
    secrets_flow = r"""
\begin{tikzpicture}[node distance=2cm]
    % Flow
    \node[box] (user) {Business User};
    \node[secondarybox, right=2.5cm of user] (ghsettings) {GitHub Settings\\Codespaces Secrets};
    \node[successbox, right=2.5cm of ghsettings] (codespace) {Their Codespace\\(Secrets injected)};
    
    % Arrows
    \draw[arrow] (user) -- node[label, above] {adds API keys} (ghsettings);
    \draw[arrow] (ghsettings) -- node[label, above] {auto-injected} (codespace);
    
    % Note
    \node[label, below=1cm of ghsettings, align=center] {You never see\\their secrets};
\end{tikzpicture}
"""
    (SRC_DIR / "secrets-flow.tex").write_text(secrets_flow, encoding="utf-8")
    
    # Full architecture diagram
    architecture = r"""
\begin{tikzpicture}[node distance=1.5cm and 2cm]
    % Web App
    \node[primarybox, minimum width=3cm, minimum height=1.5cm] (webapp) {Your Web App\\(Tool Selection)};
    
    % Generator
    \node[primarybox, minimum width=3cm, minimum height=1.5cm, right=2cm of webapp] (generator) {Generator\\(This Repo)};
    
    % GitHub API
    \node[secondarybox, minimum width=3cm, minimum height=1.5cm, right=2cm of generator] (api) {GitHub API};
    
    % User's Repo
    \node[successbox, minimum width=3cm, minimum height=1.5cm, below=2cm of api] (repo) {User's Repo\\(In their account)};
    
    % Codespace
    \node[successbox, minimum width=3cm, minimum height=1.5cm, below=1.5cm of repo] (codespace) {Codespace\\(Pre-configured)};
    
    % Arrows
    \draw[arrow] (webapp) -- node[label, above] {config} (generator);
    \draw[arrow] (generator) -- node[label, above] {create repo} (api);
    \draw[arrow] (api) -- node[label, right] {in user's\\account} (repo);
    \draw[arrow] (repo) -- node[label, right] {launch} (codespace);
    
    % User flow
    \node[box, below=2cm of webapp] (user) {Business Owner};
    \draw[arrow] (user) -- node[label, left] {selects tools} (webapp);
    \draw[dashedarrow, bend right=30] (user.east) to node[label, below] {opens workspace} (codespace.west);
\end{tikzpicture}
"""
    (SRC_DIR / "architecture.tex").write_text(architecture, encoding="utf-8")
    
    print(f"Created example diagrams in {SRC_DIR}/")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Render specific file
        tikz_file = Path(sys.argv[1])
        if not tikz_file.exists():
            tikz_file = SRC_DIR / sys.argv[1]
        if tikz_file.exists():
            ensure_dirs()
            render_tikz(tikz_file)
        else:
            print(f"File not found: {sys.argv[1]}")
    else:
        render_all()
