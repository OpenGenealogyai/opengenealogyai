"""
OpenGenealogyAI — Daily Goal Reporter (Goal #15)
Posts a Block Kit Slack message every morning summarizing pipeline status,
CRM counts, top goal activity, and recommended next actions.

Usage:
    python scripts/daily_goal_reporter.py            # post to Slack (or print if no webhook)
    python scripts/daily_goal_reporter.py --dry-run  # always print, never post
"""

import argparse
import datetime
import io
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

# Force UTF-8 output on Windows so emoji don't crash the console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
ENV_PATH    = ROOT / ".env"
BIG_GOALS   = ROOT / "BIG-GOALS.md"
RESUME_MD   = ROOT / "RESUME.md"
DB_PATH     = ROOT / "db" / "staging.db"          # primary DB
CRM_DB_PATH = ROOT / "data" / "crm.db"            # optional CRM DB
CHECKER_LOG = ROOT / "_logs" / "checker.jsonl"
LOGS_DIR    = ROOT / "_logs"
LAST_REPORT = LOGS_DIR / "last_daily_report.json"


# ── Env loader ─────────────────────────────────────────────────────────────────
def load_env() -> dict:
    env = {}
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    except Exception:
        pass
    return env


# ── Big Goals parser ───────────────────────────────────────────────────────────
def parse_goals(md_path: Path) -> list[dict]:
    """Return list of {num, title, body} from BIG-GOALS.md."""
    goals = []
    if not md_path.exists():
        return goals
    text = md_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^### (\d+)\. (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        goals.append({"num": int(m.group(1)), "title": m.group(2).strip(), "body": body})
    return goals


# ── RESUME.md reader ───────────────────────────────────────────────────────────
def read_resume(md_path: Path) -> dict:
    """Pull key status lines from RESUME.md."""
    info = {
        "status": "No status available",
        "target": "50M records",
        "last_updated": "unknown",
        "pending_recs": [],
        "launch_done": 0,
        "launch_total": 0,
    }
    if not md_path.exists():
        return info

    text = md_path.read_text(encoding="utf-8")

    # Status line
    m = re.search(r"\*\*Status:\*\*\s*(.+)", text)
    if m:
        info["status"] = m.group(1).strip()

    # Last updated
    m = re.search(r"\*\*Last updated:\*\*\s*(.+)", text)
    if m:
        info["last_updated"] = m.group(1).strip()

    # Target
    m = re.search(r"\*\*Target:\*\*\s*(.+)", text)
    if m:
        info["target"] = m.group(1).strip()

    # Pending recommendations
    recs_section = re.search(r"## Pending Recommendations\s*(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if recs_section:
        recs_text = recs_section.group(1).strip()
        if "none" not in recs_text.lower():
            for line in recs_text.splitlines():
                line = line.strip("- *").strip()
                if line and not line.startswith("**To approve"):
                    info["pending_recs"].append(line)

    # Launch checklist progress
    done = len(re.findall(r"- \[x\]", text, re.IGNORECASE))
    todo = len(re.findall(r"- \[ \]", text))
    info["launch_done"] = done
    info["launch_total"] = done + todo

    return info


# ── DB stats reader ────────────────────────────────────────────────────────────
def read_db_stats(db_path: Path) -> dict | None:
    """Read record counts from staging DB. Returns None if DB missing."""
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        total_records = cur.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0]
        total_persons = cur.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        approved      = cur.execute("SELECT COUNT(*) FROM persons WHERE judge_approved=1").fetchone()[0]
        today = datetime.date.today().isoformat()
        embedded_today = cur.execute(
            "SELECT COUNT(*) FROM raw_records WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]

        conn.close()
        return {
            "total_records": total_records,
            "total_persons": total_persons,
            "approved_persons": approved,
            "embedded_today": embedded_today,
        }
    except Exception as e:
        return {"error": str(e)}


def read_crm_stats(crm_path: Path) -> dict | None:
    """Read CRM counts if crm.db exists. Returns None if missing."""
    if not crm_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(crm_path))
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

        stats = {"tables": tables}
        # Try common table names
        for table in ["contacts", "persons", "users"]:
            if table in tables:
                stats["total_contacts"] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                break

        for table in ["reports", "ancestor_reports"]:
            if table in tables:
                stats["total_reports"] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                today = datetime.date.today().isoformat()
                stats["delivered_today"] = cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE created_at LIKE ?", (f"{today}%",)
                ).fetchone()[0]
                break

        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}


# ── Checker log reader ─────────────────────────────────────────────────────────
def read_checker_entries(log_path: Path, n: int = 6) -> list[dict]:
    """Return last n entries from checker.jsonl. Empty list if missing."""
    if not log_path.exists():
        return []
    entries = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return entries[-n:]


# ── Goal activity analyzer ─────────────────────────────────────────────────────
def score_goal_activity(goals: list[dict], checker_entries: list[dict], resume: dict) -> list[dict]:
    """
    Score each goal by inferred activity. Heuristic: goals with pipeline/DB
    keywords in body get bumped based on checker health + resume status.
    Returns top 3 most active goals.
    """
    pipeline_active = bool(checker_entries)
    db_has_data = False  # will be set by caller based on db_stats

    active_keywords = {
        17: ["record", "embed", "pipeline", "qdrant", "million"],
        15: ["slack", "daily", "report", "goal review"],
        14: ["agent", "operating system", "five agents"],
        13: ["crm", "contact", "user"],
        9:  ["website", "domain", "landing"],
        10: ["github", "repository"],
        2:  ["free", "ancestor report", "email"],
        1:  ["schema", "maxgen", "standard"],
    }

    scored = []
    for g in goals:
        score = 0
        body_lower = g["body"].lower()

        # Goals known to be actively worked on
        if g["num"] in active_keywords:
            kws = active_keywords[g["num"]]
            hits = sum(1 for kw in kws if kw in body_lower)
            score += hits * 10

        # Pipeline-related goals get boost if checker has entries
        if pipeline_active and g["num"] in [17, 14, 15, 19]:
            score += 20

        # Goal #15 is this very script — always relevant
        if g["num"] == 15:
            score += 30

        # Goal #17 (1M records) always relevant while pipeline running
        if g["num"] == 17:
            score += 25

        scored.append({**g, "activity_score": score})

    return sorted(scored, key=lambda x: x["activity_score"], reverse=True)[:3]


# ── Next actions recommender ───────────────────────────────────────────────────
def build_recommendations(
    resume: dict,
    db_stats: dict | None,
    crm_stats: dict | None,
    checker_entries: list[dict],
) -> list[str]:
    recs = []

    # Check launch checklist
    done = resume.get("launch_done", 0)
    total = resume.get("launch_total", 0)
    if total > 0 and done < total:
        remaining = total - done
        recs.append(
            f"*1. Complete launch checklist* — {done}/{total} items done, "
            f"{remaining} remaining. Next: add TROVE_API_KEY and confirm Ollama models."
        )

    # Pipeline not started
    if not checker_entries:
        recs.append(
            "*2. Start the pipeline* — Double-click `start_pipeline.bat` on the Omen to "
            "begin embedding records. Ollama and Qdrant must be running first."
        )
    else:
        # Pipeline running — check health
        last = checker_entries[-1]
        status = last.get("status", "").upper()
        if status in ("ERROR", "CRITICAL"):
            recs.append(
                f"*2. Investigate pipeline error* — Last checker status: `{status}`. "
                "Run `pipeline/checker.py` manually and check `_logs/checker.jsonl`."
            )
        else:
            records = last.get("embedded_total", 0)
            recs.append(
                f"*2. Monitor embedding pace* — {records:,} records embedded so far. "
                "Target: 50M in 60 days = ~833K/day. Check pace is on track."
            )

    # Slack webhook not set
    recs.append(
        "*3. Set up daily Slack reporting* — Add `SLACK_WEBHOOK_URL` to `.env` "
        "(see `scripts/slack_setup_instructions.md`) so this report posts automatically each morning."
    )

    # CRM not yet populated
    if crm_stats is None or crm_stats.get("total_contacts", 0) == 0:
        recs.append(
            "*4. Seed the CRM* — Goal #13 requires tracking every user from day one. "
            "Set up crm.db or connect to an external CRM before first user arrives."
        )

    # Website not yet live (heuristic: no domain proof)
    recs.append(
        "*5. Launch opengenealogyai.com* — Goal #9: site must be live with free "
        "ancestor report form above the fold before any marketing starts."
    )

    return recs[:3]


# ── Slack Block Kit builder ────────────────────────────────────────────────────
def build_slack_blocks(
    date_str: str,
    resume: dict,
    db_stats: dict | None,
    crm_stats: dict | None,
    checker_entries: list[dict],
    top_goals: list[dict],
    recommendations: list[str],
) -> list[dict]:
    blocks = []

    # ── Header ────────────────────────────────────────────────────────────────
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"🌳 OpenGenealogyAI Daily Report — {date_str}",
            "emoji": True,
        },
    })

    blocks.append({"type": "divider"})

    # ── Pipeline status ────────────────────────────────────────────────────────
    if checker_entries:
        last = checker_entries[-1]
        status_icon = {
            "ok": "✅", "warning": "⚠️", "error": "🔴", "critical": "🚨"
        }.get(last.get("status", "ok").lower(), "🔵")
        embedded = last.get("embedded_total", 0)
        pace_per_hr = last.get("pace_per_hour", 0)
        gpu_alive = "✅ alive" if last.get("gpu_alive") else "❌ stalled"
        pipeline_text = (
            f"{status_icon} *Pipeline running*\n"
            f"Records embedded: *{embedded:,}* | Pace: *{pace_per_hr:,}/hr*\n"
            f"GPU: {gpu_alive} | Status: `{last.get('status', 'unknown')}`"
        )
    else:
        launch_done = resume.get("launch_done", 0)
        launch_total = resume.get("launch_total", 0)
        pipeline_text = (
            f"🟡 *Pipeline not yet started*\n"
            f"Launch checklist: {launch_done}/{launch_total} complete\n"
            f"Status: {resume.get('status', 'Ready to launch')}"
        )

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*📊 Pipeline Status*\n{pipeline_text}"},
    })

    blocks.append({"type": "divider"})

    # ── CRM / Record counts ────────────────────────────────────────────────────
    crm_lines = []

    if db_stats and "error" not in db_stats:
        crm_lines.append(f"Raw records in DB: *{db_stats['total_records']:,}*")
        crm_lines.append(f"Persons indexed: *{db_stats['total_persons']:,}*")
        crm_lines.append(f"Judge-approved persons: *{db_stats['approved_persons']:,}*")
        crm_lines.append(f"Embedded today: *{db_stats['embedded_today']:,}*")
    elif db_stats is None:
        crm_lines.append("_staging.db not found — pipeline not started yet_")
    else:
        crm_lines.append(f"_DB read error: {db_stats.get('error')}_")

    if crm_stats and "error" not in crm_stats:
        crm_lines.append(f"CRM contacts: *{crm_stats.get('total_contacts', 0):,}*")
        if "total_reports" in crm_stats:
            crm_lines.append(f"Ancestor reports generated: *{crm_stats['total_reports']:,}*")
        if "delivered_today" in crm_stats:
            crm_lines.append(f"Delivered today: *{crm_stats.get('delivered_today', 0):,}*")
    elif crm_stats is None:
        crm_lines.append("_CRM database not found yet (Goal #13 pending)_")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*🗄️ CRM & Record Counts*\n" + "\n".join(crm_lines)},
    })

    blocks.append({"type": "divider"})

    # ── Top 3 active goals ─────────────────────────────────────────────────────
    goal_lines = []
    for g in top_goals:
        # Trim body to one sentence
        first_sentence = g["body"].split(".")[0].strip()
        if len(first_sentence) > 120:
            first_sentence = first_sentence[:117] + "..."
        goal_lines.append(f"*Goal #{g['num']}: {g['title']}*\n_{first_sentence}._")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*🎯 Top 3 Goals — Most Recent Activity*\n\n" + "\n\n".join(goal_lines),
        },
    })

    blocks.append({"type": "divider"})

    # ── Recommendations ────────────────────────────────────────────────────────
    rec_text = "*💡 Recommended Next Actions for Garlon*\n\n" + "\n\n".join(recommendations)
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": rec_text},
    })

    blocks.append({"type": "divider"})

    # ── Footer ─────────────────────────────────────────────────────────────────
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    f"🤖 OpenGenealogyAI Big Goal Agent | {date_str} | "
                    "Reply with a number to approve a recommendation"
                ),
            }
        ],
    })

    return blocks


# ── Slack poster ───────────────────────────────────────────────────────────────
def post_to_slack(webhook_url: str, blocks: list[dict], fallback_text: str) -> bool:
    payload = json.dumps({
        "text": fallback_text,
        "blocks": blocks,
    }).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            if body.strip() == "ok":
                return True
            print(f"[Slack] Unexpected response: {body}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[Slack] POST failed: {e}", file=sys.stderr)
        return False


# ── Save last report ───────────────────────────────────────────────────────────
def save_last_report(date_str: str, blocks: list[dict], recommendations: list[str]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "date": date_str,
        "blocks": blocks,
        "recommendations": recommendations,
    }
    try:
        LAST_REPORT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Reporter] Could not save last report: {e}", file=sys.stderr)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="OpenGenealogyAI daily Slack reporter")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print message to console instead of posting to Slack",
    )
    args = parser.parse_args()

    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d (%A)")

    env = load_env()
    webhook_url = env.get("SLACK_WEBHOOK_URL", "").strip()

    # ── Gather data ────────────────────────────────────────────────────────────
    goals = parse_goals(BIG_GOALS)
    resume = read_resume(RESUME_MD)
    db_stats = read_db_stats(DB_PATH)
    crm_stats = read_crm_stats(CRM_DB_PATH)
    checker_entries = read_checker_entries(CHECKER_LOG, n=6)

    # Score goal activity
    top_goals = score_goal_activity(goals, checker_entries, resume)

    # Build recommendations
    recommendations = build_recommendations(resume, db_stats, crm_stats, checker_entries)

    # ── Build message ──────────────────────────────────────────────────────────
    blocks = build_slack_blocks(
        date_str=date_str,
        resume=resume,
        db_stats=db_stats,
        crm_stats=crm_stats,
        checker_entries=checker_entries,
        top_goals=top_goals,
        recommendations=recommendations,
    )

    fallback = f"🌳 OpenGenealogyAI Daily Report — {date_str}"

    # ── Save report ────────────────────────────────────────────────────────────
    save_last_report(date_str, blocks, recommendations)

    # ── Output ─────────────────────────────────────────────────────────────────
    dry_run_mode = args.dry_run or not webhook_url

    if dry_run_mode:
        if not webhook_url and not args.dry_run:
            print("[Reporter] SLACK_WEBHOOK_URL not set — printing to console (test mode)")
        else:
            print("[Reporter] --dry-run mode — printing to console")
        print("=" * 70)
        print(f"  {fallback}")
        print("=" * 70)
        for block in blocks:
            btype = block.get("type")
            if btype == "header":
                print(f"\n{'='*60}")
                print(f"  {block['text']['text']}")
                print(f"{'='*60}")
            elif btype == "section":
                text = block.get("text", {}).get("text", "")
                # Strip mrkdwn bold markers for readability (leave underscores alone)
                text = re.sub(r"\*(.+?)\*", r"\1", text)
                print(f"\n{text}")
            elif btype == "context":
                for el in block.get("elements", []):
                    if el.get("type") == "mrkdwn":
                        print(f"\n[{el['text']}]")
            elif btype == "divider":
                print("-" * 60)
        print()
        print(f"[Reporter] Report saved to: {LAST_REPORT}")
    else:
        print(f"[Reporter] Posting to Slack webhook...")
        ok = post_to_slack(webhook_url, blocks, fallback)
        if ok:
            print(f"[Reporter] Posted successfully. Report saved to: {LAST_REPORT}")
        else:
            print(f"[Reporter] Slack post failed — report still saved to: {LAST_REPORT}")
            sys.exit(1)


if __name__ == "__main__":
    main()
