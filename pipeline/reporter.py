"""
Hourly Reporter — reads Checker log, posts to Slack.

Runs every 60 minutes. Reads last 6 checker entries (60 min of data).
Posts a plain-English summary to #pipeline-status.
Escalates to Garlon if any WARN/ERROR/CRITICAL status found.
"""

import json, os, datetime, time
from pathlib import Path
import requests

from pipeline.paths import LOGS

CHECKER_LOG = LOGS / "checker.jsonl"
COUNCIL_LOG = LOGS / "council.jsonl"
REPORTER_LOG = LOGS / "reporter.jsonl"

SLACK_TOKEN   = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = "#pipeline-status"
SLACK_URL     = "https://slack.com/api/chat.postMessage"

START_TIME_FILE = LOGS / "pipeline_start.txt"


def _pipeline_hour() -> int:
    if not START_TIME_FILE.exists():
        return 0
    try:
        start = datetime.datetime.fromisoformat(START_TIME_FILE.read_text().strip())
        return int((datetime.datetime.utcnow() - start).total_seconds() / 3600)
    except Exception:
        return 0


def _last_n_checks(n: int = 6) -> list[dict]:
    if not CHECKER_LOG.exists():
        return []
    lines = CHECKER_LOG.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in reversed(lines):
        try:
            entries.append(json.loads(line))
            if len(entries) >= n:
                break
        except Exception:
            pass
    return list(reversed(entries))


def _last_council_call() -> str:
    if not COUNCIL_LOG.exists():
        return "none yet"
    try:
        lines = COUNCIL_LOG.read_text(encoding="utf-8").splitlines()
        last = json.loads(lines[-1])
        ts = datetime.datetime.fromisoformat(last["ts"].replace("Z", ""))
        hours_ago = int((datetime.datetime.utcnow() - ts).total_seconds() / 3600)
        return f"{hours_ago}h ago ({last.get('question','')[:40]})"
    except Exception:
        return "unknown"


def build_report(checks: list[dict]) -> tuple[str, bool]:
    """
    Build the Slack message. Returns (message_text, needs_escalation).
    """
    if not checks:
        return "No checker data available yet.", False

    latest  = checks[-1]
    total   = latest.get("total_embedded", 0)
    pct     = round(total / 50_000_000 * 100, 1)
    hr_rate = sum(c.get("records_last_10m", 0) for c in checks) * 6 // max(len(checks), 1)

    eta_days = latest.get("eta_days")
    eta_str  = f"Day {60 - int(eta_days)} ahead of target" if eta_days and eta_days < 60 \
               else f"~{eta_days} days remaining" if eta_days else "calculating..."

    sources = latest.get("active_sources", [])
    source_str = "  ".join(f"{s} OK" for s in sources) if sources else "none active"

    disk   = latest.get("disk_gb_free", 0)
    gpu    = "OK" if latest.get("gpu_alive") else "DOWN"
    err    = latest.get("error_rate_pct", 0)
    status = latest.get("status", "UNKNOWN")

    # Claude API guard status
    claude_paused    = latest.get("claude_paused", False)
    claude_day_pct   = latest.get("claude_daily_pct", 0)
    claude_win_pct   = latest.get("claude_window_pct", 0)
    claude_reset     = latest.get("claude_reset_at", "")
    claude_str = (f"PAUSED ({claude_day_pct:.0f}%/day, resets {claude_reset})"
                  if claude_paused
                  else f"OK  ({claude_day_pct:.0f}%/day budget used)")

    issues = []
    needs_escalation = False

    for c in checks:
        s = c.get("status", "OK")
        if s == "CRITICAL":
            issues.append(f"CRITICAL: disk at {c.get('disk_gb_free',0):.0f} GB")
            needs_escalation = True
        elif s == "ERROR":
            issues.append("ERROR: GPU worker down")
            needs_escalation = True
        elif s == "STALLED":
            issues.append("STALLED: no records processed for 10+ min")
        elif s == "WARN_DISK":
            issues.append(f"WARN: disk low ({c.get('disk_gb_free',0):.0f} GB free)")
        elif s == "WARN_ERRORS":
            issues.append(f"WARN: error rate {c.get('error_rate_pct',0):.1f}%")
        if c.get("claude_paused"):
            issues.append(f"Claude API paused ({c.get('claude_day_pct',0):.0f}% of daily budget)")

    issues_str = "\n".join(f"  • {i}" for i in issues) if issues else "  None"

    hour = _pipeline_hour()
    council_str = _last_council_call()

    if needs_escalation:
        header = f":warning:  *NEEDS YOUR ATTENTION*\n{issues_str}\n\n"
    else:
        header = ""

    msg = (
        f"{header}"
        f":bar_chart: *OpenGenealogyAI — Hour {hour} Report*\n\n"
        f"*Records this hour:*   {hr_rate:,}\n"
        f"*Total embedded:*      {total:,}  ({pct}% of 50M target)\n"
        f"*Pace estimate:*       {eta_str}\n"
        f"\n"
        f"*Active sources:*      {source_str}\n"
        f"*GPU status:*          {gpu}  |  *Error rate:* {err:.1f}%\n"
        f"*Disk free:*           {disk:.0f} GB\n"
        f"*Claude API:*          {claude_str}\n"
        f"\n"
        f"*Issues this hour:*\n{issues_str}\n"
        f"*Last council call:*   {council_str}\n"
    )

    return msg, needs_escalation


def post_to_slack(message: str) -> bool:
    if not SLACK_TOKEN:
        print("[REPORTER] No Slack token — printing report instead:")
        print(message)
        return False
    try:
        r = requests.post(SLACK_URL, headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        }, json={"channel": SLACK_CHANNEL, "text": message}, timeout=10)
        data = r.json()
        if data.get("ok"):
            return True
        print(f"[REPORTER] Slack error: {data.get('error')}")
    except Exception as e:
        print(f"[REPORTER] Slack post failed: {e}")
    return False


def run_report():
    checks = _last_n_checks(6)
    message, needs_escalation = build_report(checks)
    sent = post_to_slack(message)

    # Log the report
    REPORTER_LOG.parent.mkdir(exist_ok=True)
    with open(REPORTER_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "sent_to_slack": sent,
            "needs_escalation": needs_escalation,
            "total_embedded": checks[-1].get("total_embedded", 0) if checks else 0,
        }) + "\n")


def run_loop(interval_seconds: int = 3600):
    """Run reporter forever, every interval_seconds."""
    print(f"[REPORTER] Starting — reporting every {interval_seconds//60} minutes")
    while True:
        try:
            run_report()
        except Exception as e:
            print(f"[REPORTER ERROR] {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_loop()
