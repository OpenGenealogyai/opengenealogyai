"""
Streaming ingester for OpenLibrary tab-separated gz dump files.

Each line of the OpenLibrary dump is:
  type \t key \t revision \t modified \t json

We parse the JSON, extract author/work/edition info, build a record in the
format the existing GPU embedder expects (text + url + payload), and write
each as a separate .json file into _checkpoints/embed_queue/.

Throttled by canonical pipeline.throttle: when internet_level <= 2, we
PAUSE feeding the queue. The GPU embedder is unaffected and keeps draining
whatever is already in queue.

Usage:
  python -m pipeline.bulk.openlibrary_ingest <gz_path> <kind: authors|works|editions>
"""

import gzip, json, sys, time, uuid
from pathlib import Path

# Reconfigure stdout to UTF-8 — Windows console default is cp1252
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pipeline.bulk.throttle import internet_level, status_line, read_throttle, _invalidate_cache

CHECKPOINTS = Path("D:/AI/Companies/open-genealogical-ai/rawdata/_checkpoints")
EMBED_QUEUE = CHECKPOINTS / "embed_queue"
EMBED_QUEUE.mkdir(parents=True, exist_ok=True)

PROGRESS_EVERY = 5000                         # print a status line every N records
INGEST_PAUSE_THRESHOLD = 2                    # internet_level <= this → pause ingest
PAUSE_POLL_S = 2.0


def _check_pause():
    """Block while internet_level is at or below the pause threshold."""
    if internet_level() > INGEST_PAUSE_THRESHOLD:
        return
    print(f"[ING] PAUSED — internet_level={internet_level()} (threshold={INGEST_PAUSE_THRESHOLD}). "
          f"GPU keeps draining queue.", flush=True)
    while internet_level() <= INGEST_PAUSE_THRESHOLD:
        time.sleep(PAUSE_POLL_S)
        _invalidate_cache()
    print(f"[ING] RESUMED — internet_level={internet_level()}", flush=True)


def _build_text_for_author(rec: dict) -> str:
    parts = []
    name = rec.get("personal_name") or rec.get("name") or ""
    if name:
        parts.append(name)
    birth = rec.get("birth_date") or ""
    death = rec.get("death_date") or ""
    if birth or death:
        parts.append(f"({birth}-{death})".replace("(-", "(b. ").replace("-)", ")"))
    bio = rec.get("bio") or ""
    if isinstance(bio, dict):
        bio = bio.get("value", "")
    if bio:
        parts.append(str(bio)[:2000])
    alts = rec.get("alternate_names") or []
    if alts and isinstance(alts, list):
        parts.append("Also known as: " + ", ".join(str(a) for a in alts[:5]))
    return ". ".join(parts)


def _build_text_for_work(rec: dict) -> str:
    parts = []
    title = rec.get("title") or ""
    if title: parts.append(title)
    sub = rec.get("subtitle") or ""
    if sub: parts.append(sub)
    desc = rec.get("description") or ""
    if isinstance(desc, dict):
        desc = desc.get("value", "")
    if desc: parts.append(str(desc)[:2000])
    subjects = rec.get("subjects") or []
    if subjects and isinstance(subjects, list):
        parts.append("Subjects: " + ", ".join(str(s) for s in subjects[:8]))
    return ". ".join(parts)


def _build_text_for_edition(rec: dict) -> str:
    parts = []
    title = rec.get("title") or ""
    if title: parts.append(title)
    sub = rec.get("subtitle") or ""
    if sub: parts.append(sub)
    publisher = rec.get("publishers") or []
    if publisher and isinstance(publisher, list):
        parts.append("Publisher: " + ", ".join(str(p) for p in publisher[:3]))
    pubdate = rec.get("publish_date") or ""
    if pubdate: parts.append(f"Published: {pubdate}")
    return ". ".join(parts)


def _record_to_pipeline_format(rec: dict, kind: str) -> dict | None:
    key = rec.get("key", "")
    if not key:
        return None
    url = f"https://openlibrary.org{key}"

    if kind == "authors":
        text = _build_text_for_author(rec)
        record_type = "person"
    elif kind == "works":
        text = _build_text_for_work(rec)
        record_type = "other"
    else:  # editions
        text = _build_text_for_edition(rec)
        record_type = "other"

    if len(text) < 20:
        return None

    return {
        "_verdict": "PASS",
        "url": url,
        "source": "open_library",
        "text": text[:5000],
        "quality": 0.6,
        "record_type": record_type,
        "payload": {
            "title": rec.get("name") or rec.get("title") or "",
            "year": rec.get("birth_date") or rec.get("publish_date") or rec.get("death_date") or None,
            "names": [rec.get("name") or rec.get("personal_name")] if (rec.get("name") or rec.get("personal_name")) else [],
            "dates": [d for d in [rec.get("birth_date"), rec.get("death_date"), rec.get("publish_date")] if d],
            "locations": [],
            "source_file": f"openlibrary_{kind}_dump",
            "ingest_kind": "bulk_dump",
        },
    }


def ingest(gz_path: Path, kind: str):
    if kind not in ("authors", "works", "editions"):
        print(f"[ING] Unknown kind: {kind}", flush=True)
        sys.exit(1)

    print(f"[ING] Ingesting {gz_path.name} as {kind}", flush=True)
    print(f"[ING] {status_line()}", flush=True)

    # Block at start if user has already set a pause
    _check_pause()

    started = time.time()
    parsed = written = skipped = 0
    last_progress = started
    last_pause_check = 0.0

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                skipped += 1
                continue
            try:
                rec = json.loads(parts[4])
            except json.JSONDecodeError:
                skipped += 1
                continue
            parsed += 1

            pipeline_rec = _record_to_pipeline_format(rec, kind)
            if pipeline_rec is None:
                skipped += 1
                continue

            # Periodic pause check (every ~5 sec — don't read file every record)
            now = time.time()
            if now - last_pause_check > 5:
                _check_pause()
                last_pause_check = now

            # Atomic write
            out = EMBED_QUEUE / f"{uuid.uuid4().hex}.json"
            tmp = out.with_suffix(".tmp")
            tmp.write_text(json.dumps(pipeline_rec, ensure_ascii=False), encoding="utf-8")
            tmp.replace(out)
            written += 1

            if written % PROGRESS_EVERY == 0 or (now - last_progress) > 30:
                elapsed = now - started
                rpm = written / elapsed * 60 if elapsed > 0 else 0
                print(f"[ING] parsed={parsed:,} written={written:,} skipped={skipped:,} "
                      f"@ {rpm:.0f} rec/min  internet_level={internet_level()}", flush=True)
                last_progress = now

    elapsed = time.time() - started
    print(f"[ING] DONE — parsed={parsed:,} written={written:,} skipped={skipped:,}", flush=True)
    print(f"[ING] Time: {elapsed:.0f}s  ({written/elapsed*60:.0f} rec/min avg)", flush=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m pipeline.bulk.openlibrary_ingest <gz_path> <authors|works|editions>", flush=True)
        sys.exit(1)
    ingest(Path(sys.argv[1]), sys.argv[2])


if __name__ == "__main__":
    main()
