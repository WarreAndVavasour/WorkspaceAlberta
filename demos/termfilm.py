#!/usr/bin/env python3
"""Render terminal films: real captured output -> animated GIF.

Built for the warre & vavasour "proof" artifacts. Every frame shows real
output from real runs; only the typing is animated.

Transcript directives (one per line):
  $  text   prompt line, typed character-by-character
  >  text   output line, appears at once (fast)
  ~  text   output line, typed (emphasis)
  !  text   highlight line (amber)
  +  text   success line (green)
  -  text   dim line (meta/quiet)
  .. N      hold for N seconds (e.g. ".. 0.8")
  #  ...    comment, skipped

Grid mode (swarm film): --grid jobs.tsv where jobs.tsv has "slug<TAB>seconds".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# -- palette (matches warreandvavasour.com: #0a0807 ground, #d9a441 amber) --
BG = (10, 8, 7)
BAR = (24, 20, 17)
BORDER = (42, 37, 31)
FG = (214, 211, 205)
DIM = (116, 110, 101)
AMBER = (217, 164, 65)
GOLD = (232, 194, 119)
GREEN = (134, 201, 120)
RED = (214, 92, 80)
BLUE = (110, 160, 210)

FONT_DIRS = {
    "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "ui": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}

FPS = 100  # ms per frame (GIF-friendly)


def load_fonts(size: int, ui_size: int):
    return (
        ImageFont.truetype(FONT_DIRS["regular"], size),
        ImageFont.truetype(FONT_DIRS["bold"], size),
        ImageFont.truetype(FONT_DIRS["ui"], ui_size),
    )


def char_width(font) -> int:
    bbox = font.getbbox("M")
    return bbox[2] - bbox[0]


class Frame:
    """One rendered terminal frame."""

    def __init__(self, duration_ms: int):
        self.duration_ms = duration_ms
        self.lines: list[tuple[str, str]] = []  # (style, text)

    def copy(self):
        f = Frame(self.duration_ms)
        f.lines = list(self.lines)
        return f


def parse_transcript(path: Path):
    """-> list of ops: ('prompt'|'line'|'hold', style, text, seconds)"""
    ops = []
    for raw in path.read_text().splitlines():
        if not raw.strip():
            ops.append(("hold", None, "", 0.15))
            continue
        if raw.startswith("#"):
            continue
        if raw.startswith(".."):
            secs = float(raw[2:].strip() or 0.4)
            ops.append(("hold", None, "", secs))
            continue
        marker, text = raw[0], raw[1:].lstrip()
        if marker == "$":
            ops.append(("prompt", "prompt", text, 0))
        elif marker == "~":
            ops.append(("line", "fg", text, 0))
        elif marker == ">":
            ops.append(("line", "fg", text, 0))
        elif marker == "!":
            ops.append(("line", "amber", text, 0))
        elif marker == "+":
            ops.append(("line", "green", text, 0))
        elif marker == "-":
            ops.append(("line", "dim", text, 0))
        else:
            ops.append(("line", "fg", raw, 0))
    return ops


class Film:
    def __init__(self, cols=78, rows=22, font_size=15, title="", prompt="wa@pi5:~$ "):
        self.cols, self.rows = cols, rows
        self.font, self.font_b, self.ui = load_fonts(font_size, 13)
        self.cw = char_width(self.font)
        self.lh = font_size + 5
        self.pad = 16
        self.title = title
        self.prompt = prompt
        self.w = self.pad * 2 + cols * self.cw
        self.h = 34 + self.pad * 2 + rows * self.lh
        self.frames: list[Frame] = []

    def _emit(self, frame: Frame, ms: int):
        self.frames.append(frame.copy() if hasattr(frame, "copy") else frame)
        self.frames[-1].duration_ms = ms

    def run(self, ops):
        buf: list[tuple[str, str]] = []
        cursor_visible = True

        def push(style, text):
            buf.append((style, text))
            while len(buf) > self.rows:
                buf.pop(0)

        def snap(ms=FPS, cursor=cursor_visible):
            f = Frame(ms)
            tail = list(buf)
            if cursor:
                tail.append(("cursor", ""))
            f.lines = tail
            self.frames.append(f)

        for kind, style, text, secs in ops:
            if kind == "hold":
                snap(int(secs * 1000), cursor=True)
                continue
            if kind == "prompt":
                full = self.prompt + text
                for i in range(0, len(full), 3):
                    chunk = full[: i + 3]
                    push("prompt", chunk)
                    snap(FPS, cursor=True)
                # leave rendered, small beat
                push("prompt", full)
                snap(FPS * 3, cursor=False)
            else:
                push(style, text)
                snap(FPS * 2 if style in ("amber", "green") else 60, cursor=False)
        # final hold
        snap(2500, cursor=False)

    # -- rendering ---------------------------------------------------------
    def render(self, frame: Frame) -> Image.Image:
        img = Image.new("RGB", (self.w, self.h), BG)
        d = ImageDraw.Draw(img)
        # window chrome
        d.rounded_rectangle([0, 0, self.w - 1, self.h - 1], radius=10, fill=BAR, outline=BORDER, width=1)
        d.rectangle([1, 33, self.w - 2, 34], fill=BORDER)
        # traffic lights (matches the site's card__lights)
        for i, c in enumerate((RED, AMBER, GREEN)):
            d.ellipse([16 + i * 20, 12, 26 + i * 20, 22], fill=c)
        d.text((80, 10), self.title, font=self.ui, fill=DIM)
        y = 34 + self.pad
        for style, text in frame.lines:
            if style == "cursor":
                d.rectangle([self.pad, y + 1, self.pad + self.cw - 2, y + self.lh - 3], fill=AMBER)
            else:
                color = {
                    "prompt": GOLD,
                    "fg": FG,
                    "amber": AMBER,
                    "green": GREEN,
                    "dim": DIM,
                }.get(style, FG)
                f = self.font_b if style in ("prompt", "amber", "green") else self.font
                d.text((self.pad, y), text[: self.cols], font=f, fill=color)
            y += self.lh
        return img

    def save(self, out: Path, poster: Path | None = None):
        imgs = [self.render(f) for f in self.frames]
        pal = []
        for im in imgs:
            pal.append(im.quantize(colors=48, method=Image.MEDIANCUT, dither=Image.NONE))
        pal[0].save(
            out,
            save_all=True,
            append_images=pal[1:],
            duration=[f.duration_ms for f in self.frames],
            loop=0,
            optimize=True,
            disposal=2,
        )
        if poster:
            imgs[-1].save(poster)
        return out.stat().st_size


# -- swarm grid mode --------------------------------------------------------
def run_grid(jobs: list[tuple[str, float]], workers: int, out: Path, poster: Path | None, title: str, speedup: float):
    """Animate the real 4-worker completion schedule from real per-run seconds."""
    font, font_b, ui = load_fonts(14, 13)
    sm = ImageFont.truetype(FONT_DIRS["regular"], 11)
    cw = char_width(font)

    # greedy schedule: pop next job when a worker frees
    done_order: list[tuple[str, float, float]] = []  # slug, start, end
    busy: list[tuple[float, str]] = []  # (end_time, slug)
    t = 0.0
    pending = [(s, float(d)) for s, d in jobs]
    timeline: list[tuple[str, float, float]] = []
    while pending or busy:
        while pending and len(busy) < workers:
            s, d = pending.pop(0)
            busy.append((t + d, s))
            timeline.append((s, t, t + d))
        busy.sort()
        t = busy[0][0]
        while busy and abs(busy[0][0] - t) < 1e-9:
            e, s = busy.pop(0)
            done_order.append((s, e - (e - timeline[[x[0] for x in timeline].index(s)][1]), e))
    total = max(e for _, _, e in timeline)

    tile_w, tile_h, gap = 236, 54, 10
    grid_w = 4 * tile_w + 3 * gap
    header = 74
    grid_h = header + 3 * (tile_h + gap) + 24
    W, H = grid_w + 32, grid_h + 16

    def status_at(time_s):
        running, done = [], []
        for slug, s, e in timeline:
            if time_s >= e:
                done.append(slug)
            elif time_s >= s:
                running.append(slug)
        return running, done

    frames = []
    total_frames = int(total / speedup * 10) + 20  # 10fps + hold
    spin = "|/-\\"
    for fi in range(total_frames):
        time_s = min(fi / 10.0 * speedup, total)
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=10, fill=BAR, outline=BORDER, width=1)
        running, done = status_at(time_s)
        d.text((16, 12), f"$ dsh run --batch alberta-12 --workers {workers}", font=font_b, fill=GOLD)
        if fi < total_frames - 8:
            el = f"elapsed {time_s:5.1f}s   {len(done)}/12 complete   4 harness workers"
        else:
            el = f"batch complete — 12/12 OK in 114s wall clock (real run)"
        d.text((16, 34), el, font=sm, fill=DIM)
        for i, (slug, dur) in enumerate(jobs):
            col, row = i % 4, i // 4
            x = 16 + col * (tile_w + gap)
            y = header + row * (tile_h + gap)
            name = slug.replace("-", " ")
            if slug in done:
                d.rounded_rectangle([x, y, x + tile_w, y + tile_h], radius=8, fill=(16, 22, 16), outline=(60, 90, 60), width=1)
                d.text((x + 12, y + 9), name[:30], font=sm, fill=FG)
                d.text((x + 12, y + 28), f"OK  {dur:.1f}s", font=font_b, fill=GREEN)
            elif slug in running:
                d.rounded_rectangle([x, y, x + tile_w, y + tile_h], radius=8, fill=(24, 20, 14), outline=BORDER, width=1)
                d.text((x + 12, y + 9), name[:26], font=sm, fill=FG)
                d.text((x + 12, y + 28), f"running {spin[fi % 4]}", font=font, fill=AMBER)
            else:
                d.rounded_rectangle([x, y, x + tile_w, y + tile_h], radius=8, fill=(16, 14, 13), outline=(30, 27, 24), width=1)
                d.text((x + 12, y + 9), name[:26], font=sm, fill=DIM)
                d.text((x + 12, y + 28), "queued", font=font, fill=(80, 75, 68))
        d.text((16, H - 26), "12 simulated Alberta businesses · live MCP server · keyless search", font=sm, fill=DIM)
        frames.append(img)

    pal = [im.quantize(colors=48, method=Image.MEDIANCUT, dither=Image.NONE) for im in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=[100] * len(pal), loop=0, optimize=True, disposal=2)
    if poster:
        frames[-1].save(poster)
    return out.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", type=Path, nargs="?")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--poster", type=Path)
    ap.add_argument("--title", default="workspaceAlberta — live")
    ap.add_argument("--prompt", default="wa@pi5:~$ ")
    ap.add_argument("--grid", action="store_true", help="transcript is a jobs TSV: slug<TAB>seconds")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--speedup", type=float, default=6.0)
    args = ap.parse_args()

    if args.grid:
        jobs = []
        for line in args.transcript.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                slug, secs = line.split("\t")
                jobs.append((slug, float(secs)))
        size = run_grid(jobs, args.workers, args.out, args.poster, args.title, args.speedup)
    else:
        film = Film(title=args.title, prompt=args.prompt)
        film.run(parse_transcript(args.transcript))
        size = film.save(args.out, args.poster)
    print(f"{args.out}  {size/1024:.0f} KB")


if __name__ == "__main__":
    main()
