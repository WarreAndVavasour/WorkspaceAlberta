import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch

from fastapi.testclient import TestClient
from tests.test_procurement_http_app import app
from procurement_core import blog


class BlogTest(unittest.TestCase):
    def test_announcement_and_feed_are_served_by_existing_app(self):
        with TestClient(app) as client:
            index = client.get("/blog")
            self.assertEqual(index.status_code, 200)
            self.assertIn("A new connection for Canadian public work", index.text)
            post = client.get("/blog/workspacealberta-community-connector-approved")
            self.assertEqual(post.status_code, 200)
            self.assertIn("community connector", post.text)
            self.assertIn("Publication is the next step", post.text)
            self.assertIn('rel="canonical"', post.text)
            feed = client.get("/blog/feed.xml")
            self.assertEqual(feed.status_code, 200)
            self.assertEqual(len(ET.fromstring(feed.content).findall("channel/item")), 1)
            self.assertEqual(client.get("/assets/blog.css").status_code, 200)
            self.assertEqual(client.get("/assets/archive/plate-rocky-mountains.webp").status_code, 200)
            self.assertEqual(client.get("/blog/nonexistent").status_code, 404)
            self.assertIn('href="/blog"', client.get("/").text)
            privacy = client.get("/privacy").text
            self.assertIn("Cohere and E2B are subprocessors", privacy)
            self.assertIn("US-Central", privacy)
            self.assertIn("us-west1", privacy)

    def test_drafts_future_posts_and_unsafe_html_cannot_be_published_by_accident(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for slug, status, day in (("draft", "draft", "2026-10-01"),
                                       ("future", "published", "2099-01-01"),
                                       ("ready", "published", "2026-10-01")):
                meta = {"title": "<script>alert(1)</script>", "summary": "A & B", "author": "Test",
                        "category": "News", "date": day, "status": status}
                (directory / f"{slug}.md").write_text("---\n" + json.dumps(meta) + "\n---\n\n<script>alert(1)</script>\n\n[bad](javascript:alert(1))", encoding="utf-8")
            posts = blog.load_posts(directory, today=date(2026, 10, 1))
            self.assertEqual([p.slug for p in posts], ["ready"])
            self.assertNotIn("<script>", blog.render_post(posts[0]))
            self.assertNotIn('href="javascript:', posts[0].body)
            self.assertEqual(ET.fromstring(blog.render_feed(posts)).findtext("channel/item/description"), "A & B")
            with patch.object(blog, "load_posts", return_value=posts), TestClient(app) as client:
                self.assertEqual(client.get("/blog/draft").status_code, 404)
                self.assertEqual(client.get("/blog/future").status_code, 404)


if __name__ == "__main__":
    unittest.main()
