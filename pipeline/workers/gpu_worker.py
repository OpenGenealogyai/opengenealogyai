"""
GPU Worker — sentence-transformers direct inference + Qdrant upsert.

Replaces the Ollama HTTP approach with direct sentence-transformers model
inference, eliminating per-batch HTTP overhead and running the RTX 5080 at
full utilization.

Model: nomic-ai/nomic-embed-text-v1.5 (768-dim, matches existing collection)
Batch: BATCH_SIZE records encoded in one model.encode() call
Throughput: ~10-50x vs Ollama HTTP at equivalent GPU load
"""

import gc, json, datetime, time, sqlite3, uuid, threading
from collections import deque
from pathlib import Path

import requests
import torch                                  # imported at top so empty_cache is always available
from sentence_transformers import SentenceTransformer

from pipeline.paths import LOGS, CHECKPOINTS
from pipeline.throttle import wait_for_gpu, gpu_level, status_line

# Build sentinel — printed at startup so we can confirm new code is running after a restart
BUILD_TAG = "2026-05-08-trace-upsert-error"


def _safe_unlink(p: Path) -> bool:
    """Delete p; tolerate Windows PermissionError when CPU worker still holds a handle.

    Returns True if deleted (or never existed). Returns False if a permission
    error means another process still has the file open — caller should leave
    the file alone for next batch. NEVER raises: prevents the WinError 32 race
    that crashed the worker after queue drained at the 5h mark.
    """
    try:
        p.unlink(missing_ok=True)
        return True
    except (PermissionError, OSError) as e:
        # Don't log every miss — would flood stdout. Counter is sampled in batch metrics.
        return False

QDRANT_URL  = "http://localhost:6333"
COLLECTION  = "raw_records_v01"
EMBED_MODEL = "nomic-ai/nomic-embed-text-v1.5"
BATCH_SIZE     = 256    # Reduced from 512 — keeps VRAM well under 16 GB ceiling
TEXT_TRUNCATE  = 1000   # Truncate input texts. Controls peak attention memory per batch.
                        # Without this, one outlier 4k-char record forces all 256 in batch
                        # to be padded to that length → 22 GB CUDA reservation → OOM.
QDRANT_CHUNK   = 200    # points per Qdrant upsert request

HEARTBEAT_FILE  = LOGS / "gpu_heartbeat.json"
EMBED_QUEUE_DIR = CHECKPOINTS / "embed_queue"
CHECKPOINT_DB   = CHECKPOINTS / "pipeline.db"

CONTRIBUTOR_NAME = "Garlon Maxwell"
CONTRIBUTOR_URL  = "https://opengenealogyai.org"

_db_lock = threading.Lock()

# In-memory path deque — avoids re-scanning a 200k-file directory every batch.
# Refilled from disk when it drops below REFILL_THRESHOLD.
_path_deque: deque = deque()
_REFILL_THRESHOLD = BATCH_SIZE * 8   # refill when fewer than 8 batches remain


_REFILL_LOAD_CAP = 10_000   # max new paths to add per refill call

def _refill_deque():
    """Scan the embed queue dir and append up to _REFILL_LOAD_CAP new paths.

    Capping per-call load prevents a single glob scan of a 300k-file directory
    from blocking the embedding loop for minutes on Windows NTFS.
    """
    known = set(_path_deque)
    added = 0
    for f in EMBED_QUEUE_DIR.glob("*.json"):
        if f not in known:
            _path_deque.append(f)
            added += 1
            if added >= _REFILL_LOAD_CAP:
                break


def _init_db() -> sqlite3.Connection:
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS records (
            url         TEXT PRIMARY KEY,
            source      TEXT,
            status      TEXT,
            quality     REAL,
            embedded_at DATETIME
        )
    """)
    con.commit()
    return con


def _ensure_collection(dim: int = 768):
    """Create the Qdrant collection if it does not exist."""
    try:
        r = requests.get(f"{QDRANT_URL}/collections/{COLLECTION}", timeout=5)
        if r.status_code == 404:
            resp = requests.put(
                f"{QDRANT_URL}/collections/{COLLECTION}",
                json={"vectors": {"size": dim, "distance": "Cosine"}},
                timeout=15,
            )
            resp.raise_for_status()
            print(f"[GPU] Created Qdrant collection '{COLLECTION}' ({dim}-dim)")
    except Exception as e:
        print(f"[GPU] Qdrant init warning: {e}")


def _upsert_batch(records: list[dict], embeddings):
    """Upsert records to Qdrant in chunks to stay within payload limits."""
    emb_list = embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)
    for i in range(0, len(records), QDRANT_CHUNK):
        chunk_recs = records[i:i + QDRANT_CHUNK]
        chunk_vecs = emb_list[i:i + QDRANT_CHUNK]
        points = [
            {
                "id":     str(uuid.uuid4()),
                "vector": vec,
                "payload": {
                    **rec.get("payload", {}),
                    "source":          rec.get("source"),
                    "url":             rec.get("url"),
                    "quality":         rec.get("quality", 1.0),
                    "record_type":     rec.get("record_type", "unknown"),
                    "embedded_by":     CONTRIBUTOR_NAME,
                    "contributor_url": CONTRIBUTOR_URL,
                },
            }
            for rec, vec in zip(chunk_recs, chunk_vecs)
        ]
        r = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION}/points",
            json={"points": points},
            timeout=30,
        )
        r.raise_for_status()


def _mark_embedded(con: sqlite3.Connection, records: list[dict]):
    now = datetime.datetime.utcnow().isoformat()
    with _db_lock:
        con.executemany(
            "INSERT OR REPLACE INTO records (url, source, status, quality, embedded_at) "
            "VALUES (?,?,?,?,?)",
            [(r["url"], r["source"], "embedded", r.get("quality", 1.0), now) for r in records],
        )
        con.commit()


def _write_heartbeat(total_embedded: int, rate_per_min: float):
    LOGS.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.write_text(json.dumps({
        "last_embed":       datetime.datetime.utcnow().isoformat(),
        "total_embedded":   total_embedded,
        "rate_per_min":     round(rate_per_min, 1),
        "engine":           "sentence-transformers",
        "model":            EMBED_MODEL,
        "batch_size":       BATCH_SIZE,
        "throttle_gpu":     gpu_level(),
        "throttle_status":  status_line(),
    }))


def _collect_batch(con: sqlite3.Connection) -> list[tuple[Path, dict]]:
    """Pop up to BATCH_SIZE paths from the in-memory deque.

    Refills from disk only when the deque drops below REFILL_THRESHOLD.
    Uses a single bulk DB query to skip records already 'embedded',
    preventing duplicate Qdrant vectors without per-record query overhead.

    Stale-deque detection: if more than 4× as many paths are missing as
    present (and at least 200 misses), the deque is dominated by paths to
    files that have already been deleted.  In that case we clear the deque
    and force an immediate refill so the next batch is full-sized again.
    """
    EMBED_QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    if len(_path_deque) < _REFILL_THRESHOLD:
        _refill_deque()

    if not _path_deque:
        return []

    # Read a larger candidate set so we can filter and still return BATCH_SIZE
    candidates: list[tuple[Path, dict]] = []
    miss_count  = 0
    read_limit  = BATCH_SIZE * 3
    while _path_deque and len(candidates) < read_limit:
        f = _path_deque.popleft()
        if not f.exists():
            miss_count += 1
            continue
        try:
            candidates.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            # File unreadable — could be: corrupted JSON, OR CPU worker mid-write.
            # Try to delete only if we can; if CPU worker still holds it,
            # _safe_unlink returns False and we leave the file for next pass.
            _safe_unlink(f)
            miss_count += 1

    # If the deque was mostly stale, clear it and grab fresh paths from disk
    # so subsequent batches aren't starved by thousands of already-deleted paths.
    hit_count = len(candidates)
    if miss_count > max(hit_count * 4, 200):
        print(f"[GPU] Deque stale ({miss_count} misses / {hit_count} hits) — resetting")
        _path_deque.clear()
        _refill_deque()

    if not candidates:
        return []

    # Bulk-check which URLs are already embedded.
    # SQLite limits IN-clause variables to 999; chunk to stay under that.
    _SQL_CHUNK = 900
    urls = [rec.get("url", "") for _, rec in candidates]
    non_empty = [u for u in urls if u]
    already_embedded: set[str] = set()
    for i in range(0, len(non_empty), _SQL_CHUNK):
        chunk = non_empty[i:i + _SQL_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows = con.execute(
            f"SELECT url FROM records WHERE url IN ({placeholders}) AND status='embedded'",
            chunk,
        ).fetchall()
        already_embedded.update(row[0] for row in rows)

    batch = []
    for f, rec in candidates:
        url = rec.get("url", "")
        if url and url in already_embedded:
            _safe_unlink(f)   # Already embedded; safe to drop. May fail benignly.
            continue
        if len(batch) >= BATCH_SIZE:
            # Push unused candidates back to the front of the deque
            _path_deque.appendleft(f)
        else:
            batch.append((f, rec))

    return batch


def run_loop():
    """Main GPU worker loop — runs forever."""
    print(f"[GPU] Build {BUILD_TAG} — Worker starting")
    print(f"[GPU] Loading model: {EMBED_MODEL}")
    print(f"[GPU] Settings: BATCH_SIZE={BATCH_SIZE} TEXT_TRUNCATE={TEXT_TRUNCATE}")
    EMBED_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    model = SentenceTransformer(EMBED_MODEL, trust_remote_code=True)
    # Warm up: encode a dummy text to load weights onto GPU
    model.encode(["warmup"], batch_size=1, show_progress_bar=False)
    print(f"[GPU] Model loaded")
    print(f"[GPU] {status_line()}")
    print("[GPU] Change throttle: python scripts/throttle.py gpu N  (1=pause, 10=full)")

    con = _init_db()
    _ensure_collection(dim=768)

    total_embedded = 0
    idle_logged    = False
    t_start        = time.time()

    while True:
        batch = _collect_batch(con)

        if not batch:
            if not idle_logged:
                print("[GPU] Queue empty — waiting for CPU worker")
                idle_logged = True
            time.sleep(3)
            continue

        idle_logged = False
        paths   = [p for p, _ in batch]
        records = [r for _, r in batch]
        # Truncate to TEXT_TRUNCATE chars. Variance in text length is the leak
        # mechanism: a single 4k-char outlier forces all 256 sequences in the
        # batch to be padded to that length, blowing CUDA reservation past 22 GB.
        texts   = [(r.get("text", "") or "")[:TEXT_TRUNCATE] for r in records]

        t0 = time.time()
        embeddings = None
        try:
            embeddings = model.encode(
                texts,
                batch_size=BATCH_SIZE,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        except Exception as e:
            print(f"[GPU] Encode error: {e} — skipping batch")
            time.sleep(5)
            continue

        try:
            _upsert_batch(records, embeddings)
            _mark_embedded(con, records)
            for p in paths:
                _safe_unlink(p)   # Tolerate transient Windows file lock
            # Throttle — respects GPU level set by: python scripts/throttle.py gpu N
            wait_for_gpu()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[GPU] Upsert failed: {type(e).__name__}: {e} -- records stay in queue", flush=True)
            print(f"[GPU] Traceback (one-time per error type):\n{tb}", flush=True)
            time.sleep(5)
            continue
        finally:
            # Release peak-batch CUDA blocks back to allocator pool.
            # Verified in Phase 2b: drops cuda_reserved from 7 GB → 0.58 GB
            # between batches, keeping RSS flat instead of climbing 4 GB/batch.
            if embeddings is not None:
                del embeddings
            gc.collect()
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

        elapsed        = time.time() - t0
        total_embedded += len(records)
        elapsed_total  = time.time() - t_start
        rate           = total_embedded / elapsed_total * 60  # records/min

        _write_heartbeat(total_embedded, rate)
        print(
            f"[GPU] {len(records)} embedded in {elapsed:.1f}s "
            f"({len(records)/elapsed:.0f} rec/s) | "
            f"total={total_embedded:,} | rate={rate:.0f}/min"
        )


if __name__ == "__main__":
    run_loop()
