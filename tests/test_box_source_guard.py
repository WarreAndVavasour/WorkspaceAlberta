"""Fail if forbidden update/API hosts reappear in shipped Box source."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [ROOT / "box", ROOT / "desktop"]
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__"}
FORBIDDEN_HOSTS = (
    "dshdesktop.cn",
    "api.deepseek.com",
)
CHROME_RELATIVE = (
    Path("src") / "branding.mjs",
    Path("src") / "electron-main.mjs",
    Path("src") / "ui-server.mjs",
    Path("ui") / "index.html",
    Path("ui") / "app.js",
    Path("ui") / "styles.css",
    Path("icons") / "wa-mark.svg",
    Path("package.json"),
)


def iter_shipped_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


class BoxSourceGuardTest(unittest.TestCase):
    def test_forbidden_hosts_absent_from_box_source(self) -> None:
        hits: list[str] = []
        scanned = 0
        for root in SCAN_ROOTS:
            for path in iter_shipped_files(root):
                scanned += 1
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                lowered = text.lower()
                for host in FORBIDDEN_HOSTS:
                    if host in lowered:
                        rel = path.relative_to(ROOT)
                        hits.append(f"{rel}: {host}")
        self.assertGreater(scanned, 0, "expected to scan box/ source files")
        self.assertEqual(hits, [], "forbidden hosts must not appear in shipped Box source")

    def test_product_chrome_has_no_third_party_wordmark(self) -> None:
        wordmark = "deep" + "seek"
        box = ROOT / "box"
        self.assertTrue(box.is_dir())
        for relative in CHROME_RELATIVE:
            path = box / relative
            self.assertTrue(path.is_file(), f"missing chrome file: {relative}")
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(wordmark, text.lower(), f"{relative} must not contain the third-party wordmark")

        named = (
            box / "src" / "branding.mjs",
            box / "ui" / "index.html",
            box / "package.json",
        )
        for path in named:
            self.assertIn("WorkspaceAlberta Box", path.read_text(encoding="utf-8"))
