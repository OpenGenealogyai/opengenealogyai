"""
Daily Pipeline Reviewer — calls `claude -p` (Claude Code CLI) to analyse the
last 24 hours, write recommendations, update RESUME.md, and post to Slack.

Uses your Claude Code subscription ($100/mo plan) — no ANTHROPIC_API_KEY charge.
Whatever model you have selected in Claude Code is what runs the review.

Runs every 4 hours (checks whether a daily report is due).
Posts a full daily report once per calendar day.

Garlon approves changes by telling Claude Code "approve the pipeline
recommendations" in a new session.
"""

import json, os, datetime, time, subprocess, shutil
from pathlib import Path

from pipeline.paths import LOGS

REVIEWER_LOG     = LOGS / "reviewer.jsonl"
PENDING_FILE     = LOGS / "pending_review.json"
LAST_REVIEW_FILE = LOGS / "last_review_date.txt"
RESUME_MD        = Path(__file__).parent.parent / "RESUME.md"

CLAUDE_CMD    = shutil.which("claude") or "claude"   # Claude Code CLI
SLACK_TOKEN   = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = "#pipeline-status"
SLACK_URL     = "https://slack.com/api/chat.postMessage"

TARGET_RECORDS  = 50_000_000
TARGET_DAYS     = 60


# ── Log helpers ────────────────────────────────────────────────────────────────

def _log(event: str, extra: dict = None):
    REVIEWER_LOG.parent.mkdir(exist_ok=True)
    entry = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "event": event}
    if extra:
        entry.update(extra)
    with open(REVIEWER_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _slack(msg: str):
    if not SLACK_TOKEN:
        print(f"[REVIEWER SLACK]\n{msg}")
        return
    try:
        import requests
        requests.post(SLACK_URL, headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        }, json={"channel": SLACK_CHANNEL, "text": msg}, timeout=15)
    except Exception as e:
        print(f"[REVIEWER] Slack failed: {e}")


# ── Data gathering ─────────────────────────────────────────────────────────────

def _read_last_n_jsonl(path: Path, hours: int = 24) -> list[dict]:
    """Read log entries from the last N hours."""
    if not path.exists():
        return []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                ts_str = e.get("ts", "")
                if ts_str:
                    ts = datetime.datetime.fromisoformat(ts_str.replace("Z", ""))
                    if ts >= cutoff:
                        entries.append(e)
            except Exception:
                pass
    except Exception:
        pass
    return entries


def _pipeline_hour() -> int:
    start_file = LOGS / "pipeline_start.txt"
    if not start_file.exists():
        return 0
    try:
        start = datetime.datetime.fromisoformat(start_file.read_text().strip())
        return int((datetime.datetime.utcnow() - start).total_seconds() / 3600)
    except Exception:
        return 0


def gather_24h_summary() -> dict:
    """Collect all pipeline data from the last 24 hours into one dict."""
    checks  = _read_last_n_jsonl(LOGS / "checker.jsonl",       hours=24)
    council = _read_last_n_jsonl(LOGS / "council.jsonl",        hours=24)
    costs   = _read_last_n_jsonl(LOGS / "cost_tracking.jsonl",  hours=24)
    reports = _read_last_n_jsonl(LOGS / "reporter.jsonl",       hours=24)
    guards  = _read_last_n_jsonl(LOGS / "api_guard.jsonl",      hours=24)

    if not checks:
        return {"error": "no checker data"}

    latest = checks[-1]
    first  = checks[0]

    total_embedded  = latest.get("total_embedded", 0)
    start_embedded  = first.get("total_embedded", 0)
    records_24h     = total_embedded - start_embedded
    pipeline_hour   = _pipeline_hour()

    # Pace
    avg_per_10m = (sum(c.get("records_last_10m", 0) for c in checks)
                   / max(len(checks), 1))
    records_per_hr = avg_per_10m * 6
    remaining = max(0, TARGET_RECORDS - total_embedded)
    eta_days = round(remaining / records_per_hr / 24, 1) if records_per_hr > 0 else None

    # Source activity
    all_sources: set = set()
    stalled_sources: set = set()
    for c in checks:
        srcs = c.get("active_sources", [])
        all_sources.update(srcs)
    # Sources that showed up early but not in last 3 checks = stalled
    recent_sources = set()
    for c in checks[-3:]:
        recent_sources.update(c.get("active_sources", []))
    stalled_sources = all_sources - recent_sources

    # Error rate trends
    high_error_checks = [c for c in checks if c.get("error_rate_pct", 0) > 5.0]

    # GPU health
    gpu_down_checks = [c for c in checks if not c.get("gpu_alive", True)]

    # Status counts
    status_counts: dict[str, int] = {}
    for c in checks:
        s = c.get("status", "OK")
        status_counts[s] = status_counts.get(s, 0) + 1

    # Council decisions
    council_decisions = [
        {"q": e.get("question", "")[:80], "decision": e.get("decision"),
         "confidence": e.get("confidence", 0)}
        for e in council
    ]

    # Cost
    total_cost_usd = sum(e.get("cost_usd", 0) for e in costs)
    api_pause_events = [e for e in guards if e.get("event") in ("auto_resume", "rate_limit_error", "cost_limit_hit")]

    # Disk
    disk_readings = [c.get("disk_gb_free", 0) for c in checks if c.get("disk_gb_free")]
    disk_latest = disk_readings[-1] if disk_readings else 0
    disk_trend = disk_readings[-1] - disk_readings[0] if len(disk_readings) >= 2 else 0

    return {
        "pipeline_hour":     pipeline_hour,
        "total_embedded":    total_embedded,
        "records_24h":       records_24h,
        "records_per_hr":    round(records_per_hr, 0),
        "eta_days":          eta_days,
        "pct_complete":      round(total_embedded / TARGET_RECORDS * 100, 2),
        "active_sources":    sorted(recent_sources),
        "stalled_sources":   sorted(stalled_sources),
        "high_error_periods": len(high_error_checks),
        "gpu_down_periods":   len(gpu_down_checks),
        "status_counts":     status_counts,
        "council_decisions": council_decisions,
        "total_cost_usd":    round(total_cost_usd, 4),
        "api_pause_events":  len(api_pause_events),
        "disk_gb_free":      disk_latest,
        "disk_change_gb":    round(disk_trend, 1),
        "check_count":       len(checks),
    }


# ── Claude Code review (uses your $100/mo plan, not the API key) ───────────────

REVIEW_PROMPT = """\
You are the daily reviewer for the OpenGenealogyAI pipeline.
Your job: analyse the last 24 hours and recommend concrete changes.

Pipeline goal: embed 50,000,000 genealogy records in 60 days using local AI models.
Architecture: Python scrapers → CPU workers (spaCy) → GPU worker (nomic-embed-text) → Qdrant.
Council: gemma3:12b + qwen2.5vl:7b + claude-haiku for decisions.

Last 24 hours of data:
{summary_json}

Respond with a JSON object in this exact format — nothing else, no explanation:
{{
  "overall_health": "GREEN|YELLOW|RED",
  "headline": "one sentence summary of the last 24 hours",
  "accomplishments": ["bullet 1", "bullet 2", "bullet 3"],
  "problems": ["problem 1 if any"],
  "recommendations": [
    {{
      "priority": "HIGH|MEDIUM|LOW",
      "change": "exactly what to change (file, setting, or action)",
      "reason": "why",
      "reversible": true
    }}
  ],
  "pace_assessment": "on_track|ahead|behind",
  "eta_days": <number or null>
}}

Be specific. Only recommend changes that will materially improve throughput, stability, or cost.
Limit to 5 recommendations maximum. Prefer LOW-risk changes.
"""


def _call_claude_code(prompt: str, timeout: int = 120) -> str | None:
    """
    Call `claude -p` — uses the Claude Code subscription (no API key charge).
    Whatever model is active in Claude Code is what runs.
    """
    if not CLAUDE_CMD:
        print("[REVIEWER] claude CLI not found in PATH")
        return None
    try:
        result = subprocess.run(
            [CLAUDE_CMD, "-p", prompt],
            capture_output=True, text=True,
            timeout=timeout, encoding="utf-8",
        )
        if result.returncode != 0:
            print(f"[REVIEWER] claude -p exited {result.returncode}: {result.stderr[:200]}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"[REVIEWER] claude -p timed out after {timeout}s")
        return None
    except FileNotFoundError:
        print("[REVIEWER] claude CLI not found — is Claude Code installed?")
        return None
    except Exception as e:
        print(f"[REVIEWER] claude -p failed: {e}")
        return None


def run_review() -> dict | None:
    """Run the review via Claude Code CLI. Returns parsed review dict or None."""
    import re

    summary = gather_24h_summary()

    if "error" in summary:
        print(f"[REVIEWER] Cannot review: {summary['error']}")
        return None

    prompt = REVIEW_PROMPT.format(summary_json=json.dumps(summary, indent=2))

    print(f"[REVIEWER] Calling Claude Code CLI for daily review...")
    text = _call_claude_code(prompt)

    if not text:
        print("[REVIEWER] No response from Claude Code")
        return None

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        print("[REVIEWER] Could not parse JSON from review response")
        _log("parse_error", {"raw": text[:500]})
        return None

    try:
        review = json.loads(m.group())
    except json.JSONDecodeError as e:
        print(f"[REVIEWER] JSON parse error: {e}")
        return None

    review["ts"]      = datetime.datetime.utcnow().isoformat() + "Z"
    review["summary"] = summary
    review["model"]   = "claude-code-cli"
    return review


# ── Write outputs ──────────────────────────────────────────────────────────────

def save_pending(review: dict):
    """Save recommendations to pending_review.json for Garlon's approval."""
    PENDING_FILE.parent.mkdir(exist_ok=True)
    PENDING_FILE.write_text(json.dumps(review, indent=2), encoding="utf-8")
    print(f"[REVIEWER] Saved {len(review.get('recommendations', []))} recommendations to {PENDING_FILE}")


def update_resume_md(review: dict):
    """Rewrite RESUME.md so any new Claude Code session can pick up immediately."""
    s = review["summary"]
    recs = review.get("recommendations", [])
    now  = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    rec_lines = ""
    if recs:
        rec_lines = "\n".join(
            f"  {i+1}. [{r['priority']}] {r['change']} — {r['reason']}"
            for i, r in enumerate(recs)
        )
    else:
        rec_lines = "  None — pipeline running well."

    health_icon = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(
        review.get("overall_health", "?"), "⚪"
    )

    content = f"""\
# OpenGenealogyAI — Pipeline Resume State
**Last updated:** {now}
**Updated by:** Daily Reviewer ({"claude-code-cli"})

---

## Current Status  {health_icon} {review.get("overall_health", "UNKNOWN")}

**{review.get("headline", "")}**

- Pipeline hour: {s.get("pipeline_hour", 0)}
- Records embedded: {s.get("total_embedded", 0):,} ({s.get("pct_complete", 0):.1f}% of 50M target)
- Records last 24h: {s.get("records_24h", 0):,}
- Rate: ~{s.get("records_per_hr", 0):,.0f} records/hour
- ETA: {review.get("eta_days") or s.get("eta_days")} days remaining — pace is **{review.get("pace_assessment", "unknown")}**
- Disk free: {s.get("disk_gb_free", 0):.0f} GB
- API cost today: ${s.get("total_cost_usd", 0):.4f}

---

## Accomplishments (last 24h)

{chr(10).join("- " + a for a in review.get("accomplishments", ["No data yet."]))}

## Problems (last 24h)

{chr(10).join("- " + p for p in review.get("problems", [])) or "- None"}

---

## Pending Recommendations  ⏳ AWAITING GARLON APPROVAL

{rec_lines}

**To approve:** Tell Claude Code "approve the pipeline recommendations" in a new session.
**To reject:** Tell Claude Code "reject recommendations" or delete `_logs/pending_review.json`.
**Pending file:** `{PENDING_FILE}`

---

## How to Resume This Session

When you open a new Claude Code session in this project:

1. Read this file (`RESUME.md`) — it has current pipeline state
2. Read `pipeline/ORCHESTRATOR.md` — agent constitution and rules
3. Check if pipeline is running: look for `_logs/orchestrator.pid`
4. Check last health: `_logs/checker.jsonl` (last 6 entries = last hour)
5. Never restart the pipeline automatically — always confirm with Garlon first

**Code root:** `C:\\Users\\stock\\dev\\opengenealogyai\\`
**Data root:** `D:\\ai\\companies\\open-genealogical-ai\\rawdata\\`
**Owner:** Garlon Maxwell (garlonmaxwell@gmail.com)
**Target:** 50M records embedded in Qdrant by Day 60
"""

    RESUME_MD.write_text(content, encoding="utf-8")
    print(f"[REVIEWER] Updated {RESUME_MD}")


def post_slack_report(review: dict):
    """Post the daily review to #pipeline-status."""
    s    = review["summary"]
    recs = review.get("recommendations", [])
    health_icon = {"GREEN": ":large_green_circle:", "YELLOW": ":large_yellow_circle:",
                   "RED": ":red_circle:"}.get(review.get("overall_health", "?"), ":white_circle:")

    accomplishments = "\n".join(f"  • {a}" for a in review.get("accomplishments", []))
    problems        = "\n".join(f"  • {p}" for p in review.get("problems", [])) or "  None"

    if recs:
        rec_lines = "\n".join(
            f"  {i+1}. *[{r['priority']}]* {r['change']}"
            for i, r in enumerate(recs)
        )
        rec_block = f"*Recommendations (pending your approval):*\n{rec_lines}\n\nTell Claude Code: *\"approve the pipeline recommendations\"*"
    else:
        rec_block = "*Recommendations:* None — pipeline running well :white_check_mark:"

    msg = (
        f"{health_icon} *OpenGenealogyAI — Daily Review  (Hour {s.get('pipeline_hour',0)})*\n\n"
        f"*{review.get('headline', '')}*\n\n"
        f"*Records embedded:* {s.get('total_embedded',0):,}  ({s.get('pct_complete',0):.1f}% of 50M)\n"
        f"*Last 24h:* {s.get('records_24h',0):,} records  |  "
        f"*Rate:* {s.get('records_per_hr',0):,.0f}/hr  |  "
        f"*ETA:* {review.get('eta_days') or s.get('eta_days')} days  ({review.get('pace_assessment','?')})\n"
        f"*Active sources:* {', '.join(s.get('active_sources', [])) or 'none'}\n"
        f"*API cost today:* ${s.get('total_cost_usd',0):.4f}\n\n"
        f"*Accomplishments:*\n{accomplishments}\n\n"
        f"*Problems:*\n{problems}\n\n"
        f"{rec_block}"
    )
    _slack(msg)


# ── Scheduler ──────────────────────────────────────────────────────────────────

def _today_str() -> str:
    return datetime.date.today().isoformat()


def _review_done_today() -> bool:
    if not LAST_REVIEW_FILE.exists():
        return False
    return LAST_REVIEW_FILE.read_text().strip() == _today_str()


def _mark_review_done():
    LAST_REVIEW_FILE.parent.mkdir(exist_ok=True)
    LAST_REVIEW_FILE.write_text(_today_str())


def run_review_if_due():
    """Call this every 4 hours. Runs full review once per calendar day."""
    if _review_done_today():
        print(f"[REVIEWER] Already ran today ({_today_str()}) — skipping")
        return

    review = run_review()
    if not review:
        return

    save_pending(review)
    update_resume_md(review)
    post_slack_report(review)
    _mark_review_done()
    _log("daily_review_complete", {
        "health":  review.get("overall_health"),
        "recs":    len(review.get("recommendations", [])),
        "pace":    review.get("pace_assessment"),
        "model":   "claude-code-cli",
    })
    print(f"[REVIEWER] Daily review complete — {review.get('overall_health')} | "
          f"{len(review.get('recommendations',[]))} recommendations posted to Slack")


def run_loop(interval_seconds: int = 14400):
    """Run reviewer forever, checking every interval_seconds (default 4 hours)."""
    print(f"[REVIEWER] Starting — checking every {interval_seconds//3600} hours")
    while True:
        try:
            run_review_if_due()
        except Exception as e:
            print(f"[REVIEWER ERROR] {e}")
        time.sleep(interval_seconds)


# ── Apply approved recommendations ────────────────────────────────────────────

def list_pending() -> list[dict]:
    """Return pending recommendations. Called by Claude Code when Garlon says 'approve'."""
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        return data.get("recommendations", [])
    except Exception:
        return []


def clear_pending():
    """Remove the pending review file after approval or rejection."""
    PENDING_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys
    if "--now" in sys.argv:
        # Force a review right now regardless of schedule
        print("[REVIEWER] Forcing review now...")
        review = run_review()
        if review:
            save_pending(review)
            update_resume_md(review)
            post_slack_report(review)
            print(f"\nReview complete: {review.get('overall_health')}")
            print(f"Recommendations: {len(review.get('recommendations', []))}")
    else:
        run_loop()
