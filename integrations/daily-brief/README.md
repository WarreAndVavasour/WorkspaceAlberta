# Native Daily Government Tenders Brief (Zero Dependencies)

Run a weekday morning tender brief straight from `POST https://elbowsupknivesout.warreandvavasour.com/brief` using only standard Python 3 — **no n8n, no Zapier, no third-party automation SaaS, no API key required.**

## Run Once

```bash
python integrations/daily-brief/daily_brief.py \
  --company "Red Deer Steel" \
  --location "Red Deer, Alberta" \
  --description "CWB structural steel fabrication and mobile welding" \
  --days 30
```

Save to a Markdown file or push to Slack / Microsoft Teams / Discord:

```bash
WEBHOOK_URL="https://hooks.slack.com/services/..." \
python integrations/daily-brief/daily_brief.py \
  --company "Red Deer Steel" \
  --location "Red Deer, Alberta" \
  --description "CWB structural steel fabrication and mobile welding" \
  --out "briefs/$(date +%F).md"
```

## Schedule Natively (No Third-Party Tools)

### Windows Task Scheduler (Weekdays at 7:00 AM)
```powershell
schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 07:00 `
  /TN "WorkspaceAlbertaDailyBrief" `
  /TR "python C:\path\to\daily_brief.py --location \"Red Deer, Alberta\" --description \"CWB welding and steel fabrication\" --out C:\briefs\latest.md"
```

### macOS / Linux `cron` (Weekdays at 7:00 AM)
```cron
0 7 * * 1-5 python3 /path/to/daily_brief.py --location "Red Deer, Alberta" --description "CWB welding and steel fabrication" --out /path/to/briefs/latest.md
```

### Or Use Inside Claude / ChatGPT / Cursor Directly
Connect the MCP endpoint for interactive search, Historical Contract Awards (`get_buyer_award_history`), and interactive RFP Requirements Boards (`classify_tender`):

```text
https://elbowsupknivesout.warreandvavasour.com/mcp
```
