# Scenario 1: Marketing Content Generation

**Business Type:** Marketing agency, solo marketer, or small business marketing team

**Inspired by:** IG Group achieving triple-digit speed-to-market improvements with AI-assisted content creation

---

## The Scenario

Sarah runs a 3-person marketing agency. They manage social media for 8 small business clients. Every week, the team:

1. Writes blog posts in Google Docs
2. Manually creates social variations for LinkedIn, Twitter, and Facebook
3. Copies content into Buffer to schedule
4. Tracks performance in spreadsheets
5. Sends weekly reports via Mailchimp

**Time spent:** ~12 hours/week on content repurposing and reporting alone

---

## The Pain Point

> "I wish AI could take a blog post we write and automatically create social media variations for each platform, then help me understand which posts actually drove traffic."

---

## Tool Stack

```
Google Drive
Slack
Buffer
Mailchimp
Google Analytics
Calendly
```

---

## Generator Command

```bash
python -m generator.generator google_drive slack buffer mailchimp google_analytics calendly
```

---

## What AI Can Do With These Tools Connected

With MCP servers connecting these tools, the AI assistant can:

1. **Read blog drafts** from Google Drive
2. **Generate platform-specific variations** (Twitter thread, LinkedIn post, Facebook caption)
3. **Schedule content** via Buffer
4. **Pull analytics** to show which content performs best
5. **Draft performance summaries** for client emails via Mailchimp
6. **Post updates** to team Slack channels

---

## Example Workflow Prompt

Once workspace is set up, ask the AI:

> "Read the latest blog post in our 'Client - Acme' folder, create 3 social variations optimized for LinkedIn, and schedule them for Tuesday, Thursday, and Saturday at 9am."
