# Pipeline Monitor — Session Lessons

**Session:** pipeline-monitor
**Owner:** this Claude Code session
**Distinct from:** `~/.claude/skills/agent-deon/LESSONS.md` (domain-specific genealogy research lessons live there)

This file captures **operational lessons** from running the embedding pipeline,
diagnosing crashes, and coordinating with parallel sessions. Append-only.

Each lesson:
```
## YYYY-MM-DD — [short title]
**Context:** what we were trying to do
**What happened:** the actual lesson
**Apply when:** condition under which this lesson kicks in
```

---

## 2026-05-07 — Windows cp1252 stdout breaks unicode print()
**Context:** Wrote pipeline/monitor.py (and later pipeline/bulk/downloader.py).
Both crashed on first run with UnicodeEncodeError because print statements
contained unicode characters (em-dash, arrow, ✅, ⚠️).
**What happened:** Windows console default codec is cp1252; can't encode many
common unicode chars. The print line crashes the entire process. The same
bug recurred in TWO scripts before I learned to add the fix preemptively.
**Apply when:** ANY Python script written for Windows. Add at top:
```python
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
```
Or stick to ASCII (->, OK, WARN) in print() statements. File writes with
encoding='utf-8' are unaffected.

## 2026-05-07 — Don't preempt a working-but-degraded process
**Context:** GPU worker producing small batches (17–47 records vs 256).
Concluded "trajectory points to crash, kill it preemptively."
**What happened:** Killed PID 42880; replacement PID 588 immediately
consumed 31 GB RAM with ZERO output for 20 minutes. Strictly worse than
the degraded but functioning original. Lost real progress.
**Apply when:** Any time you see degraded-but-still-producing output.
Wait for actual stop. A working process beats a fresh process with
unknown state.

## 2026-05-07 — "Stuck" requires proof, not just absence of progress
**Context:** PID 588 had GPU at 100%, RAM at 31 GB, no heartbeat for 5+ min.
Concluded "stuck" without verifying.
**What happened:** Could have been first-batch initialization (model load +
CUDA kernel pick + first encode + first upsert can take 60-90s for fresh
worker). Killed it; never knew if it was actually stuck.
**Apply when:** Define stuck as: CPU rate near zero AND no I/O AND
identical thread state for 10+ minutes. Heartbeat absence alone is not
stuck. Sample CPU usage delta over 5s before concluding hung.

## 2026-05-07 — Verify code change is actually loaded before assuming it is
**Context:** Edited gpu_worker.py adding race-condition fix; assumed orchestrator's
spawned children would re-import fresh.
**What happened:** Python's bytecode cache (`.pyc` in `__pycache__/`) was older
than the source but somehow the multiprocessing-spawned children kept using
old code. Had to manually delete the .pyc file to force recompile.
**Apply when:** After any edit to a worker module, bump a `BUILD_TAG` constant
and print it at startup. After restart, verify the new tag appears in stdout.
If it doesn't, delete `__pycache__/<module>.cpython-XYZ.pyc` and restart again.

## 2026-05-08 — Check parallel-session edits BEFORE deep diagnosis
**Context:** Pipeline failing with 'url' KeyError on every Qdrant upsert.
Spent 30 minutes investigating: sampled 10,000 records, all valid; tested
upsert manually, worked; tested SQL, worked. Couldn't reproduce.
**What happened:** ANOTHER Claude Code session was actively modifying pipeline
files in parallel (added `pipeline/throttle.py`, modified `gpu_worker.py`).
The edit conflicts created an unstable state in the running worker. The fix
was simply killing the worker and letting watchdog respawn.
**Apply when:** Before deep-diagnosing a mysterious bug, run
`find . -mmin -60 -type f -name "*.py"` to see what was modified recently.
If files outside your declared ownership were modified, suspect
parallel-session conflict. Try clean restart before further diagnosis.

## 2026-05-08 — Multiprocessing children have separate stdout buffering
**Context:** GPU worker (spawned by orchestrator via `multiprocessing.Process`)
appeared to not be running new code because its BUILD_TAG line wasn't
visible in stdout.
**What happened:** Windows multiprocessing children get their own stdout
buffer, separate from parent's. Even with `python -u` on the parent, child
prints can sit in a buffer for minutes until flushed. The new code WAS
running; the proof print was just stuck in buffer.
**Apply when:** Any worker spawned via multiprocessing on Windows. Use
`print(..., flush=True)` for any line you care about seeing immediately.
Don't conclude "code didn't load" from stdout absence alone.

## 2026-05-08 — One throttle system per repo, not per session
**Context:** I built `pipeline/bulk/queue_throttle.py` (1-dial, 1-10 scale,
text file) while the parallel session built `pipeline/throttle.py`
(2-dial, 1-10 scale, JSON file). Same feature, two implementations.
**What happened:** Both ran simultaneously, neither sufficient on its own,
and merging took ~30 minutes of refactoring. We could have avoided this
entirely by having either session check what the other was building first.
**Apply when:** Before building any new infrastructure capability (throttle,
locking, scheduling, etc.), search the repo for existing implementations.
Read other session locks. If you find an active one, ASK before duplicating.

## 2026-05-08 — Track misdiagnoses + errors explicitly per session
**Context:** Garlon asked the session to count its own mistakes as a
quality metric.
**What happened:** Two distinct counters proved useful:
- **Misdiagnosis** = wrong reasoning that led to action (or near-action)
  on wrong info
- **Error** = code/config bug we shipped that broke something
Tracking both publicly creates accountability and reveals patterns.
**Apply when:** Any non-trivial session. Maintain running counters in
session-summary blocks. Don't gloss over errors as "just a small thing."
The pattern matters more than any single mistake.
