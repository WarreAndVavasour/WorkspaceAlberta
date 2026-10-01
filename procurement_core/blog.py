"""Repo-authored announcements, shipped with the existing Cloud Run service."""
from __future__ import annotations

import calendar
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import formatdate
from html import escape
from pathlib import Path
from string import Template
from xml.etree import ElementTree as ET

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from markdown_it import MarkdownIt

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "content" / "blog"
BLOG_URL = "https://elbowsupknivesout.warreandvavasour.com/blog"
SHELL = Template((ROOT / "templates" / "blog.html").read_text(encoding="utf-8"))
MARKDOWN = MarkdownIt("commonmark", {"html": False})


@dataclass(frozen=True)
class Post:
    slug: str
    title: str
    summary: str
    author: str
    category: str
    published_at: date
    body: str

    @property
    def url(self) -> str:
        return f"{BLOG_URL}/{self.slug}"


def load_posts(directory: Path = POSTS_DIR, *, today: date | None = None) -> list[Post]:
    """Only explicitly published, non-future posts are reachable or syndicated.

    JSON front matter is also valid YAML; no YAML execution or raw HTML is
    accepted. Slugs come from validated filenames, never from a request path.
    """
    today = today or datetime.now(timezone.utc).date()
    posts = []
    for path in sorted(directory.glob("*.md")):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", path.stem):
            raise ValueError(f"Invalid blog slug: {path.name}")
        source = path.read_text(encoding="utf-8")
        if not source.startswith("---\n"):
            raise ValueError(f"Missing blog metadata: {path.name}")
        metadata, body = source[4:].split("\n---\n", 1)
        meta = json.loads(metadata)
        if meta.get("status") not in {"draft", "published"}:
            raise ValueError(f"Invalid publication status: {path.name}")
        published_at = date.fromisoformat(meta["date"])
        # Validate drafts too, so mistakes fail review rather than a later release.
        for key in ("title", "summary", "author", "category"):
            if not isinstance(meta.get(key), str) or not meta[key].strip():
                raise ValueError(f"Missing {key}: {path.name}")
        if not body.strip():
            raise ValueError(f"Empty post: {path.name}")
        if meta["status"] == "draft" or published_at > today:
            continue
        posts.append(Post(path.stem, meta["title"], meta["summary"], meta["author"],
                          meta["category"], published_at, MARKDOWN.render(body)))
    return sorted(posts, key=lambda p: (p.published_at, p.slug), reverse=True)


def _date(post: Post) -> str:
    return f'<time datetime="{post.published_at.isoformat()}">{post.published_at.strftime("%B")} {post.published_at.day}, {post.published_at.year}</time>'


def _page(title: str, summary: str, url: str, content: str) -> str:
    return SHELL.substitute(title=escape(title), summary=escape(summary),
                            canonical=escape(url, quote=True), content=content)


def render_index(posts: list[Post]) -> str:
    cards = "".join(
        f'<article class="post-card"><div class="post-meta">{_date(p)} · {escape(p.category)}</div>'
        f'<h2><a href="/blog/{p.slug}">{escape(p.title)}</a></h2><p>{escape(p.summary)}</p>'
        f'<a class="read-more" href="/blog/{p.slug}">Read the announcement <span aria-hidden="true">↗</span></a></article>'
        for p in posts
    ) or '<p class="empty">Something good is taking shape. Our first update is on its way.</p>'
    content = f'''<section class="hero"><div class="hero-copy"><p class="eyebrow">The workspaceAlberta journal</p>
    <h1>Public work.<br><em>New possibilities.</em></h1><p class="intro">Wouldn’t it be great if the next opportunity was easier to find?</p>
    <p class="hero-note">News, practical notes and small steps forward for Canadian businesses.</p></div>
    <figure class="hero-art"><img src="/assets/archive/plate-rocky-mountains.webp" width="560" height="354"
    alt="A hand-coloured view of the Rocky Mountains by Henry J. Warre"><figcaption>Henry J. Warre · The Rocky Mountains · 1848</figcaption></figure></section>
    <section class="posts" aria-labelledby="latest"><div class="section-heading"><h2 id="latest">Latest from the workspace</h2><a href="/blog/feed.xml">RSS feed ↗</a></div>{cards}</section>'''
    return _page("News and notes · workspaceAlberta", "News and practical notes from workspaceAlberta.", BLOG_URL, content)


def render_post(post: Post) -> str:
    content = f'''<article class="story"><a class="back-link" href="/blog">← All news and notes</a>
    <header><p class="eyebrow">{escape(post.category)}</p><h1>{escape(post.title)}</h1>
    <p class="standfirst">{escape(post.summary)}</p><div class="post-meta">{_date(post)} · {escape(post.author)}</div></header>
    <div class="story-body">{post.body}</div><aside class="connect-note"><p>Find your next possibility.</p>
    <a href="/support">Connect workspaceAlberta <span aria-hidden="true">↗</span></a></aside></article>'''
    return _page(f"{post.title} · workspaceAlberta", post.summary, post.url, content)


def render_feed(posts: list[Post]) -> bytes:
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    for key, value in {"title": "workspaceAlberta — news and notes", "link": BLOG_URL,
                       "description": "Public work. New possibilities.", "language": "en-ca"}.items():
        ET.SubElement(channel, key).text = value
    for post in posts:
        item = ET.SubElement(channel, "item")
        for key, value in {"title": post.title, "link": post.url, "guid": post.url,
                           "description": post.summary, "category": post.category,
                           "pubDate": formatdate(calendar.timegm(post.published_at.timetuple()), usegmt=True)}.items():
            ET.SubElement(item, key).text = value
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def register_blog_routes(app: FastAPI) -> None:
    @app.get("/assets/brand/{filename}", include_in_schema=False)
    async def blog_font(filename: str):
        allowed = {"fonts.css", "fraunces-normal.woff2", "fraunces-italic.woff2",
                   "inter-tight-normal.woff2", "jetbrains-mono-normal.woff2"}
        if filename not in allowed:
            return Response(status_code=404)
        return FileResponse(ROOT / "assets" / "brand" / filename,
                            media_type="text/css" if filename == "fonts.css" else "font/woff2",
                            headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/assets/blog.css", include_in_schema=False)
    async def blog_styles():
        return FileResponse(ROOT / "assets" / "blog.css", media_type="text/css",
                            headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/blog", include_in_schema=False)
    async def blog_index():
        return HTMLResponse(render_index(load_posts()))

    @app.get("/blog/feed.xml", include_in_schema=False)
    async def blog_feed():
        return Response(render_feed(load_posts()), media_type="application/rss+xml")

    @app.get("/blog/{slug}", include_in_schema=False)
    async def blog_post(slug: str):
        post = next((p for p in load_posts() if p.slug == slug), None)
        if post is None:
            return HTMLResponse(_page("Page not found · workspaceAlberta", "Page not found", BLOG_URL,
                                '<section class="story"><h1>Nothing here yet.</h1><p><a href="/blog">Back to news and notes</a></p></section>'), status_code=404)
        return HTMLResponse(render_post(post))
