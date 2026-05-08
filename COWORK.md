# Multi-Session Cowork Protocol — OpenGenealogyAI Repo

This repo is being worked on by multiple Claude Code sessions in parallel.
Without coordination, two sessions can simultaneously edit the same file, build
duplicate features, and create wedge-shaped runtime states. This document is
the rules of the road.

## Active Sessions

Each active session writes a lock file at `_session_locks/<session-name>.json`
declaring what it owns. Read all locks before editing.

```
_session_locks/
├── pipeline-monitor.json                    # this session
└── build-genealogy-open-source-ai.json      # the other session
```

## Lock File Schema

```json
{
  "session_name": "<name shown in user's CC tab>",
  "session_role": "<one-line description of the session's job>",
  "claimed_at": "<ISO8601 UTC>",
  "ttl_minutes": <integer>,
  "owns": ["<path or glob>", ...],
  "reads_only_doesnt_modify": ["<path>", ...],
  "active_tasks": ["<short description>", ...],
  "contact": "<short note about how to coordinate>"
}
```

A lock is **stale** if `claimed_at + ttl_minutes < now`. Stale locks are
ignored; the session may have ended.

## Rules

### 1. Before any edit, scan all locks
```python
# pseudo:
for lock in _session_locks/*.json:
    if file_I_am_editing matches lock.owns and lock is fresh:
        STOP — this is owned by another session
```

### 2. Before claiming territory, write your own lock
On session startup or when starting a new task, append/update your lock.
Be explicit about every directory or file pattern you'll modify.

### 3. Refresh your lock every ~30 minutes
Bump `claimed_at`. If you leave the project area for >TTL minutes, your
lock auto-expires and others can claim it.

### 4. Read-only paths are fine to read; never write to them
The `reads_only_doesnt_modify` list is honesty about what we look at but
don't touch.

### 5. If you find a duplicate feature was built in parallel
- Stop further work on it
- Convene Three-Brain on which version wins
- One session refactors to use the canonical version
- The losing version's file is deleted (not commented out)
- Both sessions update their lock files

### 6. Never modify another session's lock file
If a lock is stale and you want the territory, write your OWN lock claiming
it. Don't edit theirs.

### 7. Special files
- **`pipeline/throttle.py`** — canonical throttle module.
  Owned by **build-genealogy-open-source-ai** session. Do not modify schema
  or function signatures without coordination. Adding fields is OK if
  backward-compatible.
- **`pipeline/orchestrator.py`** — restart impacts every session. Coordinate
  before restarting.
- **`D:\AI\Companies\open-genealogical-ai\rawdata\`** — shared data root.
  All sessions read/write here.
- **`_throttle/throttle.json`** — controls all worker throttles. Either
  session can write it (it's a control file, not code), but think before
  flipping levels.

## How to bring up a NEW session

If the user starts a third Claude Code session in this repo:
1. New session reads this `COWORK.md` first.
2. Reads existing lock files in `_session_locks/`.
3. Writes its own lock claiming whatever territory it needs.
4. Asks the user to confirm if its planned work overlaps with another
   session's claim.

## What to do when conflicts emerge anyway

They will. When you notice:
- A file you didn't edit has changed mid-session
- Imports you added were modified
- A duplicate of your feature exists elsewhere

**Stop. Read the system-reminder for the file change message. Read the other
session's lock. Convene Three-Brain on the merge.** Do not silently overwrite.
