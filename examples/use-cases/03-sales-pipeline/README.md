# Scenario 3: Sales Pipeline Intelligence

**Business Type:** B2B services company, consulting firm, agency

**Inspired by:** Analytics teams saving 70 hours weekly by automating data analysis and reporting

---

## The Scenario

Lisa runs a 12-person digital consulting firm. Her sales team of 3 manages ~60 active opportunities across different stages. Current challenges:

1. Leads sit in HubSpot but follow-up timing is inconsistent
2. Meeting notes live in Google Docs, disconnected from CRM
3. Pipeline reports are manually built in Google Sheets every Monday
4. No clear signal on which deals need attention

**Lost revenue:** Estimated 2-3 deals/quarter slip through due to missed follow-ups

---

## The Pain Point

> "I wish AI could look at our pipeline and tell me which deals are at risk of going cold, then automatically schedule follow-ups for leads we haven't contacted in over a week."

---

## Tool Stack

```
HubSpot
Google Drive
Google Sheets
Slack
Calendly
Stripe
```

---

## Generator Command

```bash
npx ts-node generator/generator.ts hubspot google_drive google_sheets slack calendly stripe
```

---

## What AI Can Do With These Tools Connected

With MCP servers connecting these tools, the AI assistant can:

1. **Analyze pipeline health** from HubSpot deals
2. **Identify stale opportunities** (no activity in 7+ days)
3. **Pull meeting notes** from Google Drive for context
4. **Update pipeline spreadsheets** automatically
5. **Send Slack alerts** for deals needing attention
6. **Check payment history** in Stripe for existing customers
7. **Suggest Calendly links** for scheduling follow-ups

---

## Example Workflow Prompt

Once workspace is set up, ask the AI:

> "Show me all HubSpot deals over $10k that haven't had activity in the last 7 days. For each one, find any meeting notes in our 'Sales Notes' Drive folder and draft a follow-up email."

---

## Pipeline Intelligence Examples

| Query | What AI Does |
|-------|--------------|
| "Which deals are at risk?" | Scans HubSpot for deals with no recent activity, flags by value |
| "Prep me for my call with Acme Corp" | Pulls deal history, past emails, meeting notes, payment history |
| "Update the Monday pipeline report" | Reads HubSpot data, updates Google Sheet, posts summary to Slack |
| "Who should I call today?" | Prioritizes leads by deal size, recency, and close date |
