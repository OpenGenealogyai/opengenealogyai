"""
Resumable HTTP downloader, throttled by canonical pipeline.throttle.

Reads internet level from _throttle/throttle.json. Calls wait_for_internet()
once at start and periodically during long downloads.

Usage:
  python -m pipeline.bulk.downloader <url> <output_path>

Resumes from partial file if interrupted (uses HTTP Range).
"""

import os, sys, time
from pathlib import Path

# Reconfigure stdout to UTF-8 so any unicode in URLs/paths doesn't crash
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests

from pipeline.bulk.throttle import wait_for_internet, internet_level, status_line

CHUNK_SIZE = 64 * 1024            # 64 KB chunks
CHECK_THROTTLE_EVERY_N_CHUNKS = 256  # ~16 MB between throttle checks
PROGRESS_EVERY_S = 5


def download(url: str, out_path: Path) -> bool:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    resume_pos = 0
    if out_path.exists():
        resume_pos = out_path.stat().st_size

    headers = {}
    if resume_pos > 0:
        headers["Range"] = f"bytes={resume_pos}-"
        print(f"[DL] Resuming from {resume_pos:,} bytes", flush=True)

    print(f"[DL] GET {url}  ->  {out_path}", flush=True)
    print(f"[DL] {status_line()}", flush=True)

    # Block until internet is not paused
    wait_for_internet()

    started = time.time()
    last_progress = started
    bytes_this_run = 0
    chunks_seen = 0

    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = resume_pos + int(r.headers.get("content-length", 0))
        mode = "ab" if resume_pos > 0 else "wb"
        with open(out_path, mode) as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                bytes_this_run += len(chunk)
                chunks_seen += 1

                # Periodic throttle check — picks up level changes mid-download
                if chunks_seen % CHECK_THROTTLE_EVERY_N_CHUNKS == 0:
                    wait_for_internet()

                # Progress output
                now = time.time()
                if now - last_progress > PROGRESS_EVERY_S:
                    elapsed = now - started
                    pct = (resume_pos + bytes_this_run) / total_size * 100 if total_size else 0
                    rate_mbps = bytes_this_run / elapsed / 125_000 if elapsed > 0 else 0
                    print(f"[DL] {(resume_pos+bytes_this_run)/1024/1024:.1f}/{total_size/1024/1024:.1f} MB "
                          f"({pct:.0f}%) @ {rate_mbps:.1f} Mbps  internet_level={internet_level()}", flush=True)
                    last_progress = now

    final_size = out_path.stat().st_size
    elapsed = time.time() - started
    avg_mbps = bytes_this_run / elapsed / 125_000 if elapsed > 0 else 0
    print(f"[DL] DONE — {final_size/1024/1024:.1f} MB in {elapsed:.0f}s "
          f"(avg {avg_mbps:.1f} Mbps for this session)", flush=True)
    return True


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m pipeline.bulk.downloader <url> <output_path>", flush=True)
        sys.exit(1)
    url = sys.argv[1]
    out = Path(sys.argv[2])
    try:
        ok = download(url, out)
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"[DL] FAILED: {e}", flush=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
