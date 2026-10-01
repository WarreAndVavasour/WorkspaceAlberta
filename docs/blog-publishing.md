# News and notes

The existing Cloud Run website now serves `/blog`, `/blog/<slug>` and
`/blog/feed.xml`. It follows warreandvavasour.com's warm prairie-at-dusk palette,
lowercase wordmark and Fraunces / Inter Tight / JetBrains Mono typography.
Font files are hosted locally under `/assets/brand`, with their OFL licences
in the repo. Henry J. Warre's archival artwork is already packaged with the
sign-in pages. No new hosting, database,
credentials or CMS account is needed.

## Write a post

Create `procurement_core/content/blog/your-post-slug.md`. Use a lowercase,
hyphenated filename; the filename becomes the public URL. Start with JSON
front matter (also valid YAML), then ordinary Markdown:

```markdown
---
{
  "title": "Your announcement",
  "summary": "A short description for the index, sharing and RSS.",
  "author": "Christian H. Cooper · Warre & Vavasour",
  "category": "Announcement",
  "date": "2026-10-01",
  "status": "draft"
}
---

Wouldn’t it be great if…

## What changed

Write the announcement here. [Link to setup](/support).
```

Raw HTML is displayed as text; normal Markdown links and images are supported.
Keep customer data, private review instructions and credentials out of posts.

## Publish

1. Change `status` to `published` and set the date. Drafts and future-dated posts
   return 404 and are absent from the index and feed. A future-dated published
   post becomes visible on its date (UTC); no second release is needed.
2. Run `python -m unittest tests.test_blog tests.test_connector_review` and
   review the post in the local website. Preview example:
   `python -m uvicorn server_http:app --app-dir mcp-servers/canadabuys --port 8766`.
3. Merge the reviewed changes and use the existing
   [Cloud Run stage/promote workflow](cloud-run-workflow.md).
   Publishing a post is a website deployment; saving or merging alone does
   not update the live site. Editing a published post follows the same workflow.

The first post announces **community connector approval** and links to both
direct setup and the directory. Confirm the portal reports Live before writing
an explicit claim that directory publication is complete.
Do not describe community approval as Verified status or a security audit.
