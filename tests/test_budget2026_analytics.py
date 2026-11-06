"""Budget 2026 analytics must not keep a PostHog project key in tracked source.

The page reads the key from a meta tag filled at build time. These tests
check the tag and that tracked files do not contain a project key. Failure
messages name the file only.
"""

import html
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "budget2026" / "scripts"))

import build_site  # noqa: E402

# Longer than the phc_test fixture used by server telemetry tests.
PROJECT_KEY = re.compile(r"phc_[A-Za-z0-9]{10,}")
SKIP_DIRS = {".git", "out", "out-preview", "dist", "__pycache__", "node_modules", ".wrangler"}


def _tracked_files():
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for rel in listed.stdout.split(b"\0"):
        if not rel:
            continue
        path = ROOT / rel.decode("utf-8")
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        yield path, data.decode("utf-8", errors="replace")


class NoCommittedPosthogKeyTest(unittest.TestCase):
    def test_tracked_files_have_no_project_key(self):
        offenders = [str(path.relative_to(ROOT)) for path, text in _tracked_files() if PROJECT_KEY.search(text)]
        self.assertEqual(offenders, [])

    def test_site_js_reads_meta_and_skips_without_a_key(self):
        js = (ROOT / "budget2026" / "assets" / "site.js").read_text(encoding="utf-8")
        self.assertIn("meta[name='wv:posthog-key']", js)
        self.assertIn("live && !dnt && KEY", js)
        self.assertFalse(PROJECT_KEY.search(js) is not None, "budget2026/assets/site.js still contains a PostHog project key")


class PosthogMetaTagTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("POSTHOG_PROJECT_KEY", None)

    def page(self):
        return build_site.layout("Budget 2026 Explorer", "A map of the budget.", "/", "<p>Body</p>", page_type="home", slug="budget")

    def test_meta_is_empty_when_unset(self):
        os.environ.pop("POSTHOG_PROJECT_KEY", None)
        page = self.page()
        self.assertIn('<meta name="wv:page-type" content="home">', page)
        self.assertIn('<meta name="wv:slug" content="budget">', page)
        self.assertIn('<meta name="wv:posthog-key" content="">', page)

    def test_meta_is_empty_when_blank(self):
        os.environ["POSTHOG_PROJECT_KEY"] = " \n\t "
        page = self.page()
        self.assertIn('<meta name="wv:posthog-key" content="">', page)

    def test_meta_copies_a_single_token(self):
        os.environ["POSTHOG_PROJECT_KEY"] = "phc_test"
        page = self.page()
        self.assertIn('<meta name="wv:posthog-key" content="phc_test">', page)

    def test_meta_escapes_the_value(self):
        raw = 'phc_test"><script>'
        os.environ["POSTHOG_PROJECT_KEY"] = f"  {raw}  "
        page = self.page()
        escaped = html.escape(raw, quote=True)
        self.assertIn(f'<meta name="wv:posthog-key" content="{escaped}">', page)
        self.assertNotIn(raw, page)
