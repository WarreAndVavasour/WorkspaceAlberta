import unittest

from fastapi.testclient import TestClient
from tests.test_procurement_http_app import app


class ListingIconTest(unittest.TestCase):
    def test_icon_set_is_served_with_image_types(self):
        expected = {
            "/icon.svg": ("image/svg+xml", b"<svg"),
            "/icon.png": ("image/png", b"\x89PNG"),
            "/icon-192.png": ("image/png", b"\x89PNG"),
            "/favicon-32.png": ("image/png", b"\x89PNG"),
            "/apple-touch-icon.png": ("image/png", b"\x89PNG"),
            "/favicon.ico": ("image/x-icon", b"\x00\x00\x01\x00"),
        }
        with TestClient(app) as client:
            for path, (media_type, magic) in expected.items():
                response = client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertTrue(response.headers["content-type"].startswith(media_type), path)
                self.assertTrue(response.content.startswith(magic), path)

    def test_svg_mark_does_not_depend_on_installed_fonts(self):
        with TestClient(app) as client:
            svg = client.get("/icon.svg").text
        self.assertIn("<path", svg)
        self.assertNotIn("<text", svg)
        self.assertNotIn("font-family", svg)

    def test_icon_routes_ignore_query_parameters(self):
        with TestClient(app) as client:
            plain = client.get("/favicon.ico").content
            probed = client.get("/favicon.ico", params={"name": "../server_http.py", "path": "/etc/passwd"})
        self.assertEqual(probed.status_code, 200)
        self.assertEqual(probed.content, plain)

    def test_html_pages_declare_icons(self):
        with TestClient(app) as client:
            for path in ("/", "/privacy", "/support", "/blog"):
                page = client.get(path).text
                self.assertIn('rel="icon" href="/favicon.ico"', page, path)
                self.assertIn('rel="apple-touch-icon"', page, path)


if __name__ == "__main__":
    unittest.main()
