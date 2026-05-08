# Pipeline Monitor — Errors Shipped

**Session:** pipeline-monitor
**Counter:** 3 errors shipped (all fixed)

An error = code or config bug I introduced that broke something.
Different from a misdiagnosis (wrong reasoning).

---

## #1 — 2026-05-07 — pipeline/monitor.py crashed on first hourly write

**Bug:** `print(f"[MONITOR] Wrote report at {ts} ({mark})")` where `mark` was `✅` or `⚠️`.
Windows console default codec is cp1252; can't encode unicode emoji. Process died.

**Severity:** Medium. The hourly_reports.md file write succeeded (UTF-8 file), so no data loss. But the monitor process died after one report and we had no monitoring until I noticed and fixed it.

**Fix:** Added `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at top + replaced unicode chars in print() with ASCII (`OK` / `WARN`). Also wrapped print in `safe_print()` helper to never crash on encoding.

**Recovered:** Yes. Restarted monitor; it's been writing hourly reports cleanly since.

---

## #2 — 2026-05-07 — gpu_worker.py PermissionError race condition (CPU vs GPU)

**Bug:** `_collect_batch()` called `f.unlink(missing_ok=True)` inside an except clause for json parse errors. When CPU worker still held the file open (mid-write), Windows raised `PermissionError [WinError 32]` on unlink. The exception propagated past the `missing_ok=True` flag (which only suppresses FileNotFoundError) and killed the worker with exit=1.

**Severity:** Medium. The orchestrator's watchdog auto-restarted the worker, so the pipeline self-healed. But each crash cost ~30s of model reload time and produced misleading log spam.

**Fix:** Added `_safe_unlink()` helper that catches PermissionError and OSError separately. Applied to all 3 unlink call sites in gpu_worker.py.

**Recovered:** Yes. Race condition no longer crashes the worker.

---

## #3 — 2026-05-08 — pipeline/bulk/downloader.py crashed on first run

**Bug:** Same Windows cp1252 unicode bug as Error #1, but in a NEW file (downloader.py). Used `print(f"[DL] GET {url}  →  {out_path}")` with em-dash arrow.

**Severity:** Low. Failed immediately on first run, so caught fast. No data damage.

**Fix:** Replaced unicode arrow with ASCII `->` AND added `sys.stdout.reconfigure(...)` at top of file.

**Recovered:** Yes. Download succeeded on retry.

**Lesson:** I had already learned this exact pattern in Error #1 and STILL repeated it in Error #3. Added a permanent reminder in LESSONS.md to add the stdout reconfigure to every Windows-targeted Python script as a default.

---

## Pattern Across Errors

All three errors are about **shipping code that wasn't tested in its target environment**. I'd been writing code that "should work" without running it once before declaring done. Better practice: every Python script gets a `python -c "import <module>; print('OK')"` smoke test before being put into production.
