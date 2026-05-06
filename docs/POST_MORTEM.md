# Project Post-Mortem — OpenGenealogyAI 4-Week Agentic Build

**Date:** 2026-05-05
**Build duration:** ~4 sessions (context-window constrained)
**Total commits:** 25
**Human involvement:** Garlon Maxwell — approximately 2 hours (task initiation, review)

---

## What We Set Out to Do

Build the core infrastructure of OpenGenealogyAI — an open probabilistic genealogy standard — using autonomous AI agents with minimal human involvement. The stated goal: "I don't want to have to do really anything myself."

---

## What Got Built

### Schemas (3 JSON Schema 2020-12 standards)
- **RawRecord**: 18 record types, privacy fields, confidence, provenance — 20 AJV fixtures
- **Person**: probabilistic identity, parent_assertions with relationship_type + confidence, judge_approved gate — 22 fixtures
- **TaskQueue**: 10 task types, dependency chains, cost caps — 20 fixtures
- **Total test fixtures**: 62 passing AJV validations

### Agent Infrastructure
- **Judge agent**: 5-check validation pipeline (schema, confidence, source credibility, privacy gate, relationship consistency) — 10/10 tests
- **Queue manager**: atomic claim via os.rename, retry/dead-letter logic, cost cap enforcement — 6/6 tests
- **Internet Archive fetcher**: 22 curated genealogy collections, conversion to RawRecord, batch Qdrant ingest — 23/23 tests
- **Privacy middleware**: living-person 404 gate, tier2-private blocking, audit logging — 15/15 tests
- **FamilySearch OAuth**: PKCE stub, tier2 enforced at the fetcher level
- **Tree builder**: probabilistic ancestry from seed person, depth-N generation, SQLite persistence, judge queue — 19/19 tests
- **8 agent definitions**: orchestrator, extractor, validator, critic, integrator, conflict-resolver, marketing, community
- **7 JSON agent contracts**: cost caps, allowed tools, forbidden actions, escalation paths

### Data Infrastructure
- SQLite staging.db: 4 tables, WAL mode, append-only assertions, confidence CHECK constraint
- Qdrant setup: persons_v01 + raw_records_v01 (1536-dim, Soundex + 3-gram hybrid, on_disk=true)
- File-based queue: inbox/processing/done/failed/dead with atomic rename
- Daily cost report: Haiku/Sonnet/Opus breakdown, $50 cap enforcement, Slack posting

### Protocols and Documentation
- CONFLICT_PROTOCOL.md: 3-tier resolution (auto / Opus / human gate HG-7)
- COORDINATION_PROTOCOL.md: queue semantics, heartbeat, cost enforcement at 90%/100%
- VECTOR_DB_ARCHITECTURE.md: embedding strategy, payload indexes, migration path to Qdrant Cloud
- HUMAN_GATES.md: 7 defined gates (HG-1 through HG-7) with specific approval criteria
- BRAINSTORM_SYNTHESIS.md: GPT-4o + Grok on 5 strategic questions
- BRAND_CHECK.md: domain status, GitHub org, trademark analysis

### Marketing / Community (Draft, HG-6 Required)
- Landing page HTML with confidence score demo
- HN + Reddit post drafts
- 3 email outreach templates (societies, libraries, researchers)
- Logo brief
- Contributor onboarding guide
- Adopt a Collection task board (20 collections)
- Contributor leaderboard template

### Automation
- Windows Task Scheduler: 30-min autopilot resume + daily cost report
- Cost reporting to Slack #opengenealogyai-cost
- Privacy block audit log

---

## Test Coverage Summary

| Test file | Tests | Passed | Skipped |
|-----------|-------|--------|---------|
| test_judge.py | 10 | 10 | 0 |
| test_queue.py | 6 | 6 | 0 |
| test_ia_fetcher.py | 23 | 23 | 0 |
| test_privacy_middleware.py | 15 | 15 | 0 |
| test_tree_builder.py | 19 | 19 | 0 |
| test_integration_pipeline.py | 12 | 12 | 0 |
| test_qdrant_verify.py | 18 | 15 | 3 (Qdrant offline) |
| test_cost_report.py | 11 | 11 | 0 |
| **Total** | **114** | **111** | **3** |

---

## What Worked Well

**Judge-agent-first rule:** Building the judge before any producer agent was the right call. It forced us to define what "valid" means before anything writes data. The 5-check pipeline caught design issues early (0.0 confidence, circular parents, FamilySearch without tier2).

**Append-only assertion model (Option B):** Qwen 3 consultation recommended full provenance per assertion rather than a simple array. This proved correct — the resulting schema naturally handles "two competing fathers" without any special-case code.

**Privacy triple-redundancy:** The living-person gate at three levels (RawRecord field, Person field, license field) means a single missing flag doesn't expose data. The 404-not-403 pattern eliminates existence confirmation.

**File-based queue with atomic rename:** Using `os.rename()` for atomic claim from inbox to processing avoided all distributed locking complexity. No Redis, no coordination service.

**Mocked network tests:** All 111 passing tests run offline. The test suite is CI-safe without any API keys or running services.

**Qwen 3 consultation system:** Valuable for schema design decisions. Timed out on long prompts but useful on focused questions.

---

## What Didn't Work / Known Gaps

**GitHub PAT scope:** The PAT lacks `repo:write` — all 25 commits are local only. Garlon must upgrade at github.com/settings/tokens before any push. This blocked the soft launch gate.

**Internet Archive reachability:** IA is unreachable from this machine (WinError 10060). All IA-dependent code is validated with mocks. Real ingest requires running from a machine with IA access, or using a VPN.

**Qdrant not running:** Docker not installed / Qdrant not started. The 3 live Qdrant tests correctly skip. Setup is documented and tested (`scripts/setup_qdrant.py`).

**FamilySearch app registration:** The OAuth PKCE stub is built but requires a real FamilySearch developer app registration to use. This is a human-gate item (HG-4).

**No actual records ingested:** The batch ingest pipeline is complete and tested but has run zero records into a live Qdrant because IA is unreachable. The 1,000-record R5 criterion is "infrastructure complete, execution pending."

**Web viewer empty:** The `viewer/` directory exists but has no implementation. The landing page is static HTML only.

---

## Confidence Calibration on the Build Itself

| Assertion | Confidence | Evidence |
|-----------|-----------|---------|
| Schema standard is production-ready | 0.85 | 62 fixtures, AJV 2020-12, reviewed architecture |
| Judge agent is correct | 0.90 | 10 targeted test cases, explicit check enumeration |
| Privacy gate is correct | 0.95 | 15 tests including audit log content verification |
| Cost infrastructure works | 0.80 | 11 tests, live Task Scheduler verified |
| Real genealogy tree will build correctly | 0.60 | Mocked tests only — needs live IA + Qdrant run |
| 1,000 records will ingest without issues | 0.55 | Pipeline complete, not exercised live |

---

## Recommended Next Session

1. **Garlon upgrades PAT** → agent pushes to GitHub → repo goes public
2. **Start Docker + Qdrant** (`python scripts/setup_qdrant.py`)
3. **Run batch ingest from a machine with IA access** (`python scripts/ia_batch_ingest.py --max-per-collection 50`)
4. **Register FamilySearch developer app** — gives OAuth client_id for `fs_oauth.py`
5. **HG-6 review of marketing content** → approve landing page + HN post for publishing
6. **Post HN** → watch for researcher feedback on the probabilistic model

---

## Lessons for Future Agentic Builds

1. **Define the judge before any writer.** If you can't specify what "valid" looks like, you can't safely write data.
2. **Mock everything at the boundary.** IA unreachable? Qdrant offline? Tests still pass. CI never depends on external services.
3. **Triple-gate the scary stuff.** Privacy, cost caps, and living-person detection all need redundant enforcement — one missed check is one lawsuit.
4. **Append-only is simpler than it sounds.** No merge conflicts, no version history, no "who changed this" — just assertions with timestamps.
5. **Soundex alone is not enough.** Historical name variants (Lincoln/Linkhorn) don't always share Soundex codes. Always pair with character n-grams and a tiebreaker metric.
