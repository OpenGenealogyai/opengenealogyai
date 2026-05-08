# Pipeline Monitor — Misdiagnoses

**Session:** pipeline-monitor
**Counter:** 2 confirmed misdiagnoses

A misdiagnosis = wrong reasoning that led to (or nearly led to) acting on wrong info.
Different from an error (code/config bug). Different from a near-miss (caught before acting).

---

## #1 — 2026-05-07 — Variance vs. average in sentence-transformer leak prediction

**Predicted:** "Real text might be slightly less leak-y than synthetic since real text tokenizes more efficiently."

**Actually true:** Real text was DRAMATICALLY worse. Phase 2a's first batch hit 22 GB CUDA reserved (vs synthetic which took 10 batches to reach 20 GB). Why: sentence-transformers pads ALL sequences in a batch to the longest one. Real queue had wider variance (mean 320 chars but max 3,899 chars). One outlier in the batch forced 256 sequences to be padded to its length, exploding attention matrices.

**Why I got it wrong:** Thought about average tokenization efficiency, not variance. With batch-padding, the worst text in the batch determines memory usage for all 256.

**Cost:** Phase 2a tripped the RSS cap after 1 batch instead of the expected ~5-10. Not catastrophic — the diagnostic still produced the answer.

---

## #2 — 2026-05-08 — Wasted ~30 min on 'url' KeyError when problem was parallel-session conflict

**Concluded:** "There must be queue records missing the 'url' field — let me find them."

**Actually true:** Records were fine (sampled 10,000, all valid). The 'url' KeyError was triggered by an unstable runtime state caused by another Claude Code session simultaneously editing `pipeline/throttle.py` and `pipeline/workers/gpu_worker.py`. The fix was simply killing the worker and letting watchdog respawn.

**Why I got it wrong:** Didn't check `find . -mmin -60` first. Didn't notice the system reminder telling me files had been modified by another agent until later. Assumed the bug was in MY records.

**Cost:** ~30 minutes of investigation that produced nothing. Pipeline kept running but with errors during that window.

---

## Pattern Across Misdiagnoses

Both misdiagnoses came from **insufficient hypothesis space**: I picked the most obvious explanation and didn't enumerate alternatives. Lesson: when the obvious explanation doesn't pan out in 5 minutes, STOP and brainstorm at least 3 other possible causes before continuing.
