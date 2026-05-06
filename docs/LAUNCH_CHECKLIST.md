# Soft Launch Checklist — OpenGenealogyAI

**Target:** GitHub repo public + opengenealogyai.org landing page live
**Human Gate:** HG-6 (Garlon approval required before any public action)
**Status:** READY FOR HG-6 REVIEW

---

## Pre-Launch Verification (Completed by Agents)

### Schemas
- [x] RawRecord schema v0.1 — JSON Schema 2020-12 — AJV validated — 20 fixtures passing
- [x] Person schema v0.1 — probabilistic assertions, parent_assertions, judge_approved — 22 fixtures
- [x] TaskQueue schema v0.1 — 10 task types, dependency chains, cost_cap_usd — 20 fixtures

### Agents
- [x] Judge agent — 10/10 tests passing (5 checks: schema, confidence, source, privacy, relationship)
- [x] Queue manager — 6/6 tests passing (claim, complete, fail/retry, dead, cost cap)
- [x] IA fetcher — 23/23 tests passing (mocked network)
- [x] Privacy middleware — 15/15 tests passing (living person + tier2 gate)
- [x] Tree builder — 19/19 tests passing (Abraham Lincoln Sr. anchor fixture)

### Integration
- [x] Integration pipeline — 12/12 tests passing (3 generations, zero living persons, sources cited)
- [x] Cost report — 11/11 tests passing (daily scheduler registered in Windows Task Scheduler)
- [x] Qdrant verification — 15/15 passing (3 skipped pending live Qdrant)

### Content (All DRAFT — HG-6 required before publishing)
- [x] Landing page HTML — docs/marketing/landing-page.html
- [x] HN post draft — docs/marketing/hn-post-draft.md
- [x] Reddit post draft — docs/marketing/reddit-post-draft.md
- [x] Email outreach templates (3) — docs/marketing/email-outreach-template.md
- [x] Logo brief — docs/marketing/logo-brief.md
- [x] Contributor onboarding guide — docs/community/onboarding-guide.md
- [x] Adopt a Collection tasks (20 collections) — docs/community/adopt-a-collection-tasks.md
- [x] Contributor leaderboard template — docs/community/contributor-leaderboard.md

### Infrastructure
- [x] Windows Task Scheduler: OpenGenealogyAI-Autopilot (every 30 min)
- [x] Windows Task Scheduler: OpenGenealogyAI-CostReport (daily 00:05)
- [x] SQLite staging.db schema — 4 tables, WAL mode, foreign keys
- [x] Qdrant collections defined: persons_v01, raw_records_v01 (1536-dim, on_disk=true)
- [x] File-based task queue: queue/{inbox,processing,done,failed,dead}/

---

## Launch Actions (Requires HG-6 Sign-off from Garlon)

### Step 1: Push to GitHub

```bash
cd C:\Users\stock\dev\opengenealogyai

# First: upgrade GitHub PAT at github.com/settings/tokens — add 'repo' scope
git remote add origin https://github.com/opengenealogyai/opengenealogyai.git
git push -u origin master
```

**Why PAT upgrade needed:** Current PAT lacks `repo:write` scope. This is a manual step — Garlon must visit github.com/settings/tokens.

### Step 2: Enable GitHub Pages

In GitHub repo settings → Pages → Source: Deploy from branch `master` → `/docs` folder.
This publishes `docs/marketing/landing-page.html` at opengenealogyai.org once DNS is configured.

**OR** copy `landing-page.html` to repo root as `index.html` for simpler Pages setup.

### Step 3: DNS Configuration

Point opengenealogyai.org to GitHub Pages:
- CNAME record: opengenealogyai.org → opengenealogyai.github.io
- (Done in SiteGround DNS panel — Garlon has credentials)

### Step 4: Post to HN

Use the draft at `docs/marketing/hn-post-draft.md`. Review and customize before posting.
**DO NOT post without HG-6 approval.**

### Step 5: Post to Reddit

Use `docs/marketing/reddit-post-draft.md`. Target r/genealogy first.
**DO NOT post without HG-6 approval.**

---

## Post-Launch Monitoring

- Check Slack #opengenealogyai-cost daily (automated at 00:05)
- Queue status: `python scripts/queue_status.py`
- Cost report (on-demand): `python scripts/cost_report.py --no-slack`
- Privacy audit log: `logs/privacy_blocks.jsonl`
- Batch ingest log: `logs/ia_batch_ingest.jsonl`

---

## Known Gaps (Not Blockers for Soft Launch)

- Qdrant not yet running locally (Docker pull + `python scripts/setup_qdrant.py`)
- GitHub PAT needs repo:write scope for push
- FamilySearch OAuth requires registering a developer app at familysearch.org
- No web UI beyond the static landing page (viewer/ directory exists but is empty)
- DNA match integration deferred to Q3
- Living Memory voice feature deferred to Q4
