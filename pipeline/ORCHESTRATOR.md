# OpenGenealogyAI — Orchestrator Agent Constitution
**Version:** 1.0  
**Owner:** Garlon Maxwell (garlonmaxwell@gmail.com)  
**Project:** OpenGenealogyAI — 50 million genealogy records in 60 days  
**Data root:** `D:\ai\companies\open-genealogical-ai\rawdata\`  
**Code root:** `C:\Users\stock\dev\opengenealogyai\`  
**Slack channel:** Post reports to `#pipeline-status` via bot token in `.env`

---

## Mission

Run the OpenGenealogyAI data pipeline autonomously for 60 days without human intervention. Fetch, extract, embed, and index genealogy records from multiple sources simultaneously. Keep the CPU and GPU busy at all times. Report progress to Garlon every hour. Fix problems without waking him up unless truly necessary.

**Target:** 50 million records embedded in Qdrant by Day 60.  
**Launch date:** To be set when Garlon starts the pipeline.

---

## Operating Modes

### DIY Mode (default)
The pipeline fixes its own problems. On any error:
1. Log the error with full context
2. Try the built-in recovery procedure (see Recovery section)
3. Retry up to 3 times with exponential backoff
4. If still failing after 3 retries → escalate to Council
5. If Council cannot resolve → alert Garlon via Slack and pause that source only (never the whole pipeline)

**The pipeline never fully stops. Only the affected source pauses.**

### Autopilot Mode (always on)
The Orchestrator makes all decisions within defined parameters without asking Garlon:
- Prioritize sources dynamically based on throughput
- Skip records below quality threshold 0.55 (log them for later retry)
- Throttle scrapers automatically on 429 responses
- Schedule LoRA fine-tuning runs during low-activity overnight windows
- Expand to backup sources if primary source stalls

Garlon is notified but not required to act unless an **ESCALATION** flag is raised.

---

## The Four Running Systems

### 1. Pipeline Workers
- **Scraper Pool** (CPU, asyncio): fetches raw data from all sources simultaneously
- **CPU Worker Pool** (CPU, 10 processes): decompresses, runs spaCy NER, converts to RawRecord JSON, writes to D: drive
- **GPU Worker** (dedicated process): batch-embeds with nomic-embed-text, upserts to Qdrant

### 2. Checker (runs every 10 minutes)
The Checker is a separate lightweight process. Every 10 minutes it:
1. Counts records processed since last check (reads SQLite checkpoint DB)
2. Checks GPU worker heartbeat (last embed timestamp < 2 min ago?)
3. Checks CPU worker pool (are all 10 workers alive?)
4. Checks scraper pool (are active sources responding?)
5. Checks disk space (warn at 200GB remaining, pause new downloads at 50GB)
6. Checks Qdrant collection size (actual embedded count)
7. Checks error rate (errors in last 10 min / records attempted)
8. Writes a one-line health entry to `_logs/checker.jsonl`
9. If any check fails: logs WARN or ERROR, triggers DIY recovery

**Checker health entry format:**
```json
{
  "ts": "2026-05-06T14:30:00Z",
  "records_last_10m": 8450,
  "total_embedded": 4820000,
  "gpu_alive": true,
  "cpu_workers_alive": 10,
  "active_sources": ["wikidata", "chronicling_america"],
  "disk_gb_free": 1840,
  "error_rate_pct": 0.8,
  "status": "OK"
}
```

### 3. Three-Model Council
Called when a decision needs more than one opinion. Used for:
- Quality threshold decisions ("is 0.53 good enough to embed?")
- Source priority ("Chronicling America is slow — switch to IA or wait?")
- Recovery choices ("retry this batch or skip it?")
- LoRA training decisions ("has quality improved enough to justify another run?")

**Council members:**
- **Model A (Fast):** `gemma3:12b` via Ollama — fastest reliable local model (0.660 quality, 100% JSON)
- **Model B (Balanced):** `qwen2.5vl:7b` via Ollama — best JSON reliability (0.627, 98% JSON)
- **Model C (Resolver):** `claude-haiku-4-5-20251001` via Anthropic API — tiebreaker, costs ~$0.001/call

**Council protocol:**
1. Pose the question as a structured prompt to all three models simultaneously
2. Each model returns: `{"decision": "A|B|C", "confidence": 0.0-1.0, "reason": "..."}`
3. If 2 of 3 agree → that decision wins
4. If all three disagree → escalate to Claude Sonnet (costs ~$0.01, use sparingly)
5. Log every council decision with all three votes to `_logs/council.jsonl`

**Council is never called for routine operations** — only genuine ambiguity. Target: < 10 council calls per day.

### 4. Reporter (runs every hour)
The Reporter reads the last 6 Checker entries (60 minutes of data) and sends a human-readable Slack message to `#pipeline-status`.

**Hourly report format:**
```
📊 OpenGenealogyAI — Hour 42 Report

Records this hour:    51,200
Total embedded:       4,871,000  (9.7% of 50M target)
Day estimate:         Day 56 at current pace

Active sources:       Wikidata ✓  Chronicling America ✓  BLM ✓
GPU status:           Embedding continuous, 340K rec/hr
CPU status:           10 workers, 98% utilization
Disk free:            1,840 GB

Issues this hour:     None
Last council call:    8 hours ago (source prioritization)
Next LoRA run:        Day 17 (scheduled)

Est. completion:      Day 54 (6 days ahead of target)
```

If any **ESCALATION** flags are active, the report leads with:
```
⚠️  NEEDS YOUR ATTENTION: [reason]
```

---

## Data Sources and Priority Order

Sources run simultaneously. Prioritize in this order when resources contend:

| Priority | Source | Folder | Rate | License |
|----------|--------|--------|------|---------|
| 1 | Wikidata bulk dump | `wikidata/` | Download once | CC0 — fully redistributable |
| 2 | Chronicling America | `chronicling_america/` | Bulk download | Public domain — fully redistributable |
| 3 | Internet Archive | `internet_archive/` | 1 req/sec | Per-item — check license field |
| 4 | BLM Land Patents | `blm_land_patents/` | 3 req/min → ramp to 6 | Public domain — fully redistributable |
| 5 | Trove (Australia) | `trove/` | 40 req/min (API key) | Ingest only — do NOT redistribute raw text |
| 6 | SSDI | `ssdi/` | Pending access | TBD |
| 7 | Ellis Island | `ellis_island/` | HOLD — awaiting permission | TBD |
| 8 | FamilySearch | `familysearch/` | Internal enrichment only | Non-redistributable — store embeddings + URI only |

**User-Agent for all HTTP requests:**
```
OpenGenealogyAI/1.0 (https://opengenealogyai.org; contact@opengenealogyai.org)
```

**robots.txt:** Check before first request to any new domain. Re-check weekly.  
**On 429:** Back off 30 minutes, then resume at half the previous rate.  
**On 403:** Stop that source, log for manual review, alert Garlon.  
**On 3× consecutive 5xx:** Halt that source, alert Garlon.

---

## Quality Thresholds

| Score | Action |
|-------|--------|
| ≥ 0.75 | Embed immediately |
| 0.55 – 0.74 | Embed, flag as `quality=medium` in Qdrant payload |
| 0.35 – 0.54 | Embed only if Council approves (call council once per batch, not per record) |
| < 0.35 | Skip for now, save raw text to `_checkpoints/low_quality/` for retry after next LoRA run |

**JSON validity:** Any record with invalid JSON output is never embedded. It goes to `_checkpoints/retry/` for re-extraction.

---

## GPU Schedule

The GPU runs one task at a time in this priority order:
1. **nomic-embed-text batch embedding** — highest priority, runs continuously
2. **LoRA fine-tuning** — runs 10 PM – 6 AM only, pauses embedding during window
3. **llava_13b extraction** — only for records flagged as `low_quality`, runs when embedding queue is empty

**LoRA training is scheduled, not triggered spontaneously.** Scheduled runs:
- Run 1: Day 16–17 (after Wikidata + Chronicling America processed)
- Run 2: Day 43–44 (mid-pipeline quality check)
- Additional runs: only if Council votes for it AND quality score has degraded > 0.10 from baseline

**LoRA training data source:** Auto-generated from Wikidata structured records (no human labels needed). Script: `pipeline/lora_train.py`.

---

## Self-Learning Protocol

After every LoRA run:
1. Run quality benchmark on 500 held-out records (same set each time, stored in `_checkpoints/benchmark_set.json`)
2. Compare new quality score to previous baseline
3. If new score ≥ old score: adopt new model weights, update baseline
4. If new score < old score: roll back to previous weights, log failure reason
5. Post result to Slack: "LoRA Run 2: quality 0.776 → 0.821 ✓ (adopted)"

After every 10-minute check cycle, the Checker logs which record types have the highest error rates. This feeds the next LoRA training set — broken record types get more synthetic training examples.

---

## Cost Controls

| Item | Limit | Action if exceeded |
|------|-------|-------------------|
| Claude API per day | $5.00 | Pause API calls, use local models only |
| Claude API per month | $100.00 | Alert Garlon, reduce API usage plan |
| OpenAI embedding per month | $20.00 | Switch to nomic-embed-text only |
| Council calls per day | 20 | Use local models only for rest of day |

All API costs logged to `_logs/cost_tracking.jsonl` with timestamp, model, tokens, dollars.

---

## Escalation Rules (when to wake Garlon)

Alert Garlon via Slack ONLY for these conditions:

| Condition | Message |
|-----------|---------|
| Disk < 50 GB free | "⚠️ DISK NEARLY FULL — downloads paused. Please free space or add drive." |
| Daily API cost > $5 | "⚠️ API cost limit hit ($X today). Switched to local-only mode." |
| All sources failed simultaneously | "⚠️ PIPELINE STALLED — all sources unreachable. Check internet connection." |
| Quality score drops below 0.40 for > 2 hours | "⚠️ Quality degraded below threshold. May need manual review of recent records." |
| A source returns 403 | "⚠️ [Source] blocked us (403). Check User-Agent or ToS." |
| LoRA run rolls back (quality degraded) | "ℹ️ LoRA Run [N] rolled back — quality did not improve. Previous model retained." |

**Do NOT alert for:** temporary slowdowns, individual record failures, 429 rate limits (handled automatically), or normal overnight low-throughput periods.

---

## Recovery Procedures (DIY)

### Procedure: Source stalled (no new records for 15 min)
1. Check if scraper process is alive → restart if dead
2. Check network connectivity to that source → wait 5 min and retry
3. If source returns 429 → back off 30 min, resume at half rate
4. After 3 failed recoveries → suspend source, continue with others, log for Garlon

### Procedure: GPU worker stalled (no new embeds for 5 min)
1. Check Ollama is running (`http://localhost:11434/api/tags`)
2. If Ollama down → restart it via `ollama serve`
3. Check embed queue depth — if > 1000, GPU may be overwhelmed → reduce batch size to 16
4. After 3 failed recoveries → alert Garlon

### Procedure: CPU worker died
1. ProcessPoolExecutor respawns workers automatically
2. If total alive workers drops below 5 → log WARN, continue
3. If total alive workers drops to 0 → restart CPU pool, alert Garlon

### Procedure: Qdrant write failure
1. Retry with exponential backoff (1s, 2s, 4s)
2. If Qdrant path is full → alert Garlon immediately (disk issue)
3. If Qdrant corrupted → do NOT attempt repair, alert Garlon

### Procedure: Low quality batch (< 0.40 average on last 1000 records)
1. Call Council: "Quality has dropped to X on [source]. Pause and retry, skip batch, or schedule early LoRA run?"
2. Implement Council decision
3. Log quality dip with source + time for LoRA training

---

## Checkpoint and Restart

All progress is stored in SQLite at `_checkpoints/pipeline.db` with schema:
```sql
records(url TEXT PRIMARY KEY, source TEXT, status TEXT, quality REAL, embedded_at DATETIME)
```

On any restart (crash, reboot, manual stop):
1. Read `_checkpoints/pipeline.db`
2. Resume from `WHERE status != 'embedded'`
3. Log restart event with reason if known
4. Send Slack message: "Pipeline restarted. Resuming from [N] embedded records."

**Never reprocess already-embedded records.** The checkpoint DB is the ground truth.

---

## How a New Claude Session Resumes This Project

When a new Claude conversation opens in `C:\Users\stock\dev\opengenealogyai\`:

1. Read this file (ORCHESTRATOR.md) first
2. Read `_logs/checker.jsonl` — last 6 entries show current pipeline state
3. Read `_logs/council.jsonl` — last entry shows last decision made
4. Check if pipeline process is running: `ps aux | grep orchestrator`
5. If running: report status to user, offer to review logs
6. If not running: ask Garlon if he wants to restart, show last known state
7. Never restart automatically — always confirm with Garlon first

---

## File Map

```
pipeline/
  ORCHESTRATOR.md      ← this file (agent constitution)
  __init__.py
  paths.py             ← all path configuration
  orchestrator.py      ← main control loop
  checker.py           ← 10-minute health monitor
  reporter.py          ← hourly Slack reports
  council.py           ← 3-model council implementation
  fetchers/
    wikidata.py        ← Wikidata dump downloader + parser
    chronicling.py     ← Chronicling America bulk fetcher
    internet_archive.py
    trove.py
    blm.py
  workers/
    cpu_worker.py      ← spaCy NER + schema conversion
    gpu_worker.py      ← nomic-embed-text + Qdrant upsert
    lora_train.py      ← LoRA fine-tuning runner
  schema/
    rawrecord.py       ← RawRecord builder
```

---

## Success Criteria

| Milestone | Target |
|-----------|--------|
| Pipeline boots cleanly | Day 1 |
| 1M records embedded | Day 3 |
| 5M records | Day 7 |
| 10M records | Day 12 |
| First LoRA run complete | Day 17 |
| 25M records | Day 28 |
| 50M records | Day 56 |
| Launch announcement | Day 60 |

*Last updated: 2026-05-06*
