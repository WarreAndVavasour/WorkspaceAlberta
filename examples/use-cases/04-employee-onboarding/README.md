# Scenario 4: Employee Onboarding Automation

**Business Type:** Growing SMB (15-50 employees), any industry

**Inspired by:** Newfront automating HR support, contract review, and internal knowledge management via AI integrated with Slack and Google Drive

---

## The Scenario

David is the operations manager at a 28-person marketing agency. They hire 1-2 people per month on average. Current onboarding process:

1. Send offer letter via DocuSign
2. Once signed, create employee in Gusto
3. Add to Google Workspace (email, Drive folders)
4. Share onboarding docs from Google Drive
5. Add to Slack channels
6. Schedule orientation meetings
7. Set up 1:1s with manager and team

**Time per new hire:** 3-4 hours across multiple days
**Error rate:** Frequently forget steps, causing delays

---

## The Pain Point

> "Every new hire requires the same 15 manual steps across 5 different systems. I wish AI could handle the checklist and tell me what's done and what's still pending for each person."

---

## Tool Stack

```
Gusto
DocuSign
Google Drive
Slack
Calendly
Notion
```

---

## Generator Command

```bash
npx ts-node generator/generator.ts gusto docusign google_drive slack calendly notion
```

---

## What AI Can Do With These Tools Connected

With MCP servers connecting these tools, the AI assistant can:

1. **Track DocuSign status** - Know when offer letters are signed
2. **Monitor Gusto** - Verify employee setup is complete
3. **Manage Drive folders** - Ensure new hire has access to right docs
4. **Post to Slack** - Announce new hires, add to channels
5. **Schedule via Calendly** - Set up orientation meetings
6. **Update Notion checklist** - Track onboarding progress

---

## Example Workflow Prompt

Once workspace is set up, ask the AI:

> "Check the status of onboarding for everyone who started this month. For each person, tell me which steps are complete and which are still pending. Then draft a Slack message to welcome anyone who hasn't been announced yet."

---

## Onboarding Checklist Automation

| Step | Manual Time | With AI |
|------|-------------|---------|
| Check DocuSign signed | 2 min | Auto-monitored |
| Create in Gusto | 10 min | AI prompts with data |
| Share Drive folders | 5 min | AI handles |
| Add to Slack channels | 3 min | AI handles |
| Schedule orientations | 15 min | AI drafts invites |
| Track all steps | 20 min/week | Real-time dashboard |

---

## HR Query Examples

| Question | What AI Does |
|----------|--------------|
| "Who's starting next week?" | Checks DocuSign for signed offers with start dates |
| "Is Jamie's onboarding complete?" | Cross-references all systems for status |
| "Send the employee handbook to new hires" | Finds doc in Drive, shares via appropriate channel |
| "Schedule a welcome call with the team" | Creates Calendly invite, posts to Slack |
