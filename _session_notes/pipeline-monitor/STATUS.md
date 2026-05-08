# Pipeline Monitor — Current Status

**Session:** pipeline-monitor
**Last update:** 2026-05-08 ~10:10 MDT

## Active Work

| Track | Status | Notes |
|-------|--------|-------|
| Embedding pipeline | ✅ RUNNING | GPU embedding ~1.6k–3k/min |
| Hourly monitor | ✅ RUNNING | Writes `hourly_reports.md` every hour |
| OpenLibrary authors-dump ingest | ⏸️ PAUSED | Pre-loaded ~1M records into queue; paused via throttle while user works |
| Maxwell genealogy research (Deon) | ⏸️ PAUSED | Session 1 done (10 logbook entries, 4 confirmed ancestors); waiting for user trigger to resume |
| Verity QA agent | 📋 SPEC ONLY | SKILL.md drafted; runner not yet built |

## Counters (running totals)

- **Misdiagnoses shipped:** 2
- **Errors shipped:** 3 (all fixed)
- **Sessions coordinated with:** 1 (`build-genealogy-open-source-ai`)

## Pipeline Numbers (rough)

- Total embedded: ~1.4M+ records
- Qdrant points: ~1.65M+
- Queue backlog: ~1M+ files (from OpenLibrary trial)
- Heartbeat: fresh

## What's blocked / waiting

- **Throttle skill v3** integration in my bulk modules: I'm currently using `wait_for_internet()` from canonical `pipeline/throttle.py`. v3 added `cpu` and `claude` dials and switched to 0-10 scale. My code uses `internet_level() <= 2` as pause threshold, which still works with the new scale (level 0/1/2 all pause my ingester). Compatible — no change required from me unless the canonical module's function signatures change.
- **Starlink + secondary computer** plan: deferred until user finishes setup later today.
- **FamilySearch developer API** application: status unknown; biggest single-source unlock if approved.

## My Territory (per session lock)

Owned (write access):
- `pipeline/bulk/**`
- `pipeline/monitor.py`
- `pipeline/workers/gpu_worker.py` (coordinate via lock; the other session reads only)
- `diagnostics/**`
- `_session_notes/pipeline-monitor/**` (this folder)

Reads-only:
- `pipeline/throttle.py` (canonical — owned by `build-genealogy-open-source-ai`)
- `pipeline/orchestrator.py` (restart impacts everyone)
- `_throttle/throttle.json`
- `data/**` (other session's work area)

## Next Actions When User Is Free

1. Verify hour-9 hourly report shows healthy embedding rate
2. Pick next OpenLibrary dump to download (works.txt.gz at 2.9 GB)
3. Consider FamilySearch app follow-up
4. Build Verity Python runner (to pair with Deon)
5. Build Deon Python runner (scheduled task for genealogy research)
