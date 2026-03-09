# Scenario 2: Customer Support Automation

**Business Type:** E-commerce store, online retailer, DTC brand

**Inspired by:** Companies building knowledge-base-aware support bots that pull order info automatically

---

## The Scenario

Mike runs an online kitchenware store with ~500 orders/month. He handles customer support himself with help from one part-time assistant. Common support requests:

1. "Where's my order?" (40% of tickets)
2. "I received the wrong item" (20%)
3. "How do I return this?" (15%)
4. "Is this item in stock?" (10%)
5. Other questions (15%)

**Current process:** Open Zendesk ticket → Search customer email in Shopify → Find order → Copy order details → Write response → Send

**Time per ticket:** 5-8 minutes
**Tickets per day:** 15-25

---

## The Pain Point

> "Every support ticket requires me to manually look up order info in Shopify before I can respond. I wish the AI could see both the ticket and the order history so it could draft a response for me."

---

## Tool Stack

```
Shopify
Zendesk
Stripe
Slack
Google Drive
```

---

## Generator Command

```bash
python -m generator.generator shopify zendesk stripe slack google_drive
```

---

## What AI Can Do With These Tools Connected

With MCP servers connecting these tools, the AI assistant can:

1. **Read incoming tickets** from Zendesk
2. **Look up customer orders** in Shopify by email
3. **Check payment status** in Stripe
4. **Draft contextual responses** with order details included
5. **Escalate complex issues** to Slack
6. **Access return policies** stored in Google Drive

---

## Example Workflow Prompt

Once workspace is set up, ask the AI:

> "Show me today's open Zendesk tickets. For each 'where's my order' ticket, look up their most recent Shopify order and draft a response with the tracking number."

---

## Expected Time Savings

| Task | Before | After |
|------|--------|-------|
| Order lookup | 2-3 min | Instant |
| Response drafting | 3-5 min | 30 sec review |
| Total per ticket | 5-8 min | 1-2 min |
| Daily (20 tickets) | 2-3 hours | 30-40 min |
