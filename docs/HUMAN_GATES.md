# HUMAN_GATES.md — OpenGenealogyAI

These are the ONLY actions requiring Garlon Maxwell's personal involvement.
Everything else is handled by agents. Total estimated time: ~2 hours over 4 weeks.

| Gate | ID | Action | Est. Time | Trigger | Status |
|------|----|--------|-----------|---------|--------|
| 1 | HG-1 | Create GitHub org `opengenealogyai` + fine-grained PAT | 15 min | Day 1 | ✅ DONE |
| 2 | HG-2 | Register opengenealogyai.org domain | 5 min | Day 1 | ✅ DONE |
| 3 | HG-3 | Create dev folder at C:\Users\stock\dev\opengenealogyai | 2 min | Day 1 | ✅ DONE |
| 4 | HG-4 | Sign in to GitHub (Google OAuth — agent cannot do OAuth) | 2 min | Before first push | ⏳ PENDING |
| 5 | HG-5 | Sign FamilySearch Compatible Solution Program agreement | 30 min | Day 14 | ⏳ PENDING |
| 6 | HG-6 | Approve merges touching LICENSE, SECURITY.md, or schema $id URLs | 5 min ea | As needed | ⏳ PENDING |
| 7 | HG-7 | Post to HN + send 5 personal emails to genealogy researchers | 45 min | Day 28 | ⏳ PENDING |
| 8 | HG-8 | Resolve judge-agent escalations exceeding Opus confidence threshold | 5 min ea | As needed | ⏳ PENDING |
| 9 | HG-9 | Create Stripe account + paste 3 Payment Link URLs into pricing.html | 20 min | Before first paid user | ⏳ PENDING |
| 10 | HG-10 | Create Slack incoming webhook + paste URL into .env as SLACK_WEBHOOK_URL | 5 min | Before daily reports | ⏳ PENDING |
| 11 | HG-11 | Add FamilySearch credentials to .env (FS_USERNAME + FS_PASSWORD) | 2 min | When API key arrives | ⏳ PENDING |
| 12 | HG-12 | Choose login method for Goal #21 paid portal (Google OAuth vs email/password) | 10 min | Before portal build | ⏳ PENDING |

## Escalation Protocol

If an agent blocks on a decision that requires human judgment:
1. Agent posts BLOCKED status to Slack with reason and context
2. Garlon reviews in Slack and replies with decision
3. Agent resumes

## What Agents Handle Without Human Involvement

- All schema creation, validation, and versioning
- All agent definition writing
- All record extraction, validation, critic scoring, judge approval
- All database operations (SQLite + Qdrant)
- All code writing, testing, and committing
- All marketing asset production (drafts only — Garlon approves before publishing)
- All cost monitoring and reporting
- All contributor onboarding materials
