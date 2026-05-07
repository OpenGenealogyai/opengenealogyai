# OpenGenealogyAI — Pipeline Resume State
**Last updated:** 2026-05-06 (all code written — ready to launch)
**Status:** ALL CODE WRITTEN. Every worker, fetcher, quality guard, and validation tool is in place. Launch when Ollama and Qdrant are confirmed running.

---

## What This Project Is

**OpenGenealogyAI** — embed 50 million genealogy records into a Qdrant vector database
in 60 days, running 24/7 on Garlon's local machine, nearly entirely on local AI models.

- **Code root:** `C:\Users\stock\dev\opengenealogyai\`
- **Data root:** `D:\ai\companies\open-genealogical-ai\rawdata\`
- **Owner:** Garlon Maxwell (garlonmaxwell@gmail.com)
- **Target:** 50M records in Qdrant by Day 60
- **Embedding model:** nomic-embed-text (local, Ollama, GPU)
- **Extraction model:** llava_13b (local, Ollama, GPU)
- **Council models:** gemma3:12b + qwen2.5vl:7b (local) + claude-haiku (API, tiebreaker only)
- **Daily reviewer:** `claude -p` via Claude Code CLI (your $100/mo plan, no extra charge)

---

## Every File That Exists

### Pipeline core (all written)
| File | What it does |
|------|-------------|
| `pipeline/ORCHESTRATOR.md` | Agent constitution — all rules, sources, escalation, recovery |
| `pipeline/paths.py` | All paths via env vars — single source of truth |
| `pipeline/orchestrator.py` | Main launcher — starts all 7 processes, watchdog restarts any that die |
| `pipeline/checker.py` | Every 10 min: health check, logs to checker.jsonl, triggers DIY recovery |
| `pipeline/reporter.py` | Every 60 min: Slack report to #pipeline-status |
| `pipeline/reviewer.py` | Every 4 hrs: calls `claude -p` for daily review, updates this file, posts recs to Slack |
| `pipeline/council.py` | 3-model council: gemma3 + qwen2.5 + haiku, 2/3 majority, falls back to local-only if API paused |
| `pipeline/api_guard.py` | Wraps ALL Claude API calls, pauses at 90% token window, posts Slack on pause/resume |
| `start_pipeline.bat` | Double-click to start — auto-restarts forever if pipeline stops |
| `start_pipeline.ps1` | PowerShell version — logs restarts, crash-loop protection |

### Workers and fetchers (all written)
| File | What it does |
|------|-------------|
| `pipeline/workers/gpu_worker.py` | nomic-embed-text batching + Qdrant upsert + GPU heartbeat |
| `pipeline/workers/cpu_worker.py` | spaCy NER + RawRecord schema conversion, 10-process pool |
| `pipeline/workers/lora_train.py` | LoRA fine-tuning on llava_13b, scheduler + benchmark + adopt/rollback |
| `pipeline/fetchers/wikidata.py` | Wikidata bulk dump downloader + parser (Priority 1 source) |
| `pipeline/fetchers/chronicling.py` | Chronicling America bulk fetcher (Priority 2) |
| `pipeline/fetchers/internet_archive.py` | IA polite scraper, 1 req/sec (Priority 3) |
| `pipeline/fetchers/blm.py` | BLM Land Patents, 3 req/min (Priority 4) |
| `pipeline/fetchers/trove.py` | Trove API, 40 req/min, ingest-only license (Priority 5) |
| `pipeline/quality_guard.py` | Anti-hallucination + quality scoring for all extracted records |
| `scripts/validate_submission.py` | Quality gate for incoming contributor submissions |
| `docs/AGENT_EXTRACTION_RULES.md` | Mandatory rules every AI worker must follow |
| `catalog/STATUS.md` | GitHub checkout board — live contributor status page |

---

## How the Pipeline Works (the full plan)

### Four autonomous systems running simultaneously

**1. Pipeline Workers** (CPU + GPU)
- Scraper Pool: one async process per source (Wikidata, Chronicling America, IA, BLM, Trove)
- CPU Worker Pool: 10 ProcessPoolExecutor processes — spaCy NER → RawRecord JSON → D: drive
- GPU Worker: reads queue from CPU workers → batches 32 records → nomic-embed-text → Qdrant upsert
- Writes GPU heartbeat to `_logs/gpu_heartbeat.json` every embed

**2. Checker** (every 10 minutes)
- Counts embedded records in SQLite checkpoint DB
- Checks GPU heartbeat (< 3 min ago = alive)
- Checks Ollama is responding
- Checks disk space (warn 200GB, pause 50GB)
- Checks active source folders (modified in last 15 min)
- Computes error rate from last 2 entries
- Writes one-line JSON to `_logs/checker.jsonl`
- Triggers DIY recovery: restarts Ollama if GPU stalled, writes PAUSE_DOWNLOADS if disk critical
- Includes Claude API guard status in every entry

**3. Three-Model Council** (called on ambiguity, target < 10/day)
- gemma3:12b (Ollama) + qwen2.5vl:7b (Ollama) + claude-haiku (API tiebreaker)
- 2/3 majority wins; if all disagree → claude-sonnet resolves
- If API is paused → local-only mode (gemma3 wins split by seniority)
- Used for: quality threshold calls, source priority, recovery decisions, LoRA scheduling

**4. Reporter** (every 60 minutes)
- Reads last 6 checker entries
- Builds plain-English Slack message with records, pace, ETA, issues
- Escalates with ⚠️ header if CRITICAL/ERROR found
- Includes Claude API status line

**5. Daily Reviewer** (every 4 hours, fires once/day)
- Gathers 24h of all logs into one summary dict
- Calls `claude -p "..."` (your Claude Code subscription — no API charge)
- Gets back JSON: health, accomplishments, problems, up to 5 recommendations
- Saves to `_logs/pending_review.json`
- Rewrites this RESUME.md with current state
- Posts full report + recommendations to #pipeline-status Slack
- Garlon approves by telling Claude Code "approve the pipeline recommendations"

### Claude API guard (api_guard.py)
- Wraps every `anthropic` call (council haiku/sonnet only)
- Reads `anthropic-ratelimit-tokens-remaining` from response headers
- Pauses at 90% usage — writes `_logs/PAUSE_CLAUDE_API` with reset timestamp
- Posts Slack: "Claude API paused — resumes at HH:MM"
- Checker auto-clears flag when reset time passes
- Posts Slack: "Claude API resumed"
- Daily cost cap: $5/day (env: `CLAUDE_DAILY_LIMIT_USD`)

### Self-healing (DIY mode)
- Any error → log → retry 3x with exponential backoff → council → alert Garlon
- Pipeline NEVER fully stops — only the broken source pauses
- Ollama restart attempted automatically on GPU stall
- Disk critical → writes PAUSE_DOWNLOADS flag → scrapers check for it

### Self-learning (LoRA protocol)
- Day 16-17: LoRA fine-tuning run on llava_13b (10pm-6am window)
- Day 43-44: Second LoRA run
- Uses synthetic training data auto-generated from Wikidata structured records
- Benchmarks on 500 held-out records before/after; adopts if improved, rolls back if not
- Posts result to Slack

---

## Data Sources (priority order)

| # | Source | Folder | Rate | License |
|---|--------|--------|------|---------|
| 1 | Wikidata bulk dump | `wikidata/` | Download once | CC0 |
| 2 | Chronicling America | `chronicling_america/` | Bulk download | Public domain |
| 3 | Internet Archive | `internet_archive/` | 1 req/sec | Per-item |
| 4 | BLM Land Patents | `blm_land_patents/` | 3→6 req/min | Public domain |
| 5 | Trove (Australia) | `trove/` | 40 req/min (API key) | Embeddings + URI only |
| 6 | SSDI | `ssdi/` | Pending | TBD |
| 7 | Ellis Island | `ellis_island/` | HOLD — awaiting permission | TBD |
| 8 | FamilySearch | `familysearch/` | Internal enrichment only | Store embeddings + URI only |

User-Agent: `OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)`

---

## Quality Thresholds

| Score | Action |
|-------|--------|
| ≥ 0.75 | Embed immediately |
| 0.55–0.74 | Embed, flag quality=medium |
| 0.35–0.54 | Call council once per batch |
| < 0.35 | Skip → `_checkpoints/low_quality/` for post-LoRA retry |

---

## Escalation — when to alert Garlon via Slack

- Disk < 50 GB
- Daily API cost > $5
- All sources failed simultaneously
- Quality score < 0.40 for > 2 hours
- Any source returns 403
- LoRA run rolled back (quality degraded)

---

## Pending Recommendations

None — pipeline not yet started.

**To approve:** Tell Claude Code "approve the pipeline recommendations" in a new session.

---

## Launch Checklist

- [x] Write `pipeline/workers/gpu_worker.py`
- [x] Write `pipeline/workers/cpu_worker.py`
- [x] Write `pipeline/workers/lora_train.py`
- [x] Write `pipeline/fetchers/wikidata.py`
- [x] Write `pipeline/fetchers/chronicling.py`
- [x] Write `pipeline/fetchers/internet_archive.py`
- [x] Write `pipeline/fetchers/blm.py`
- [x] Write `pipeline/fetchers/trove.py`
- [x] Write `pipeline/quality_guard.py`
- [x] Write `scripts/validate_submission.py`
- [x] Write `docs/AGENT_EXTRACTION_RULES.md`
- [x] Build contributor checkout system (`pipeline/checkout.py` + `catalog/STATUS.md`)
- [ ] **Add `TROVE_API_KEY` to `.env`** (get free key at trove.nla.gov.au/about/get-api-key)
- [ ] **Confirm `.env` has `SLACK_BOT_TOKEN` and `ANTHROPIC_API_KEY`**
- [ ] **Confirm Ollama is running** (`ollama list` — need: gemma3:12b, qwen2.5vl:7b, nomic-embed-text, llava:13b)
- [ ] **Double-click `start_pipeline.bat`**
- [ ] Watch first Slack message arrive in #pipeline-status
