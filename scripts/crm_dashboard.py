"""
crm_dashboard.py — OpenGenealogyAI CRM CLI dashboard.

Usage: python scripts/crm_dashboard.py
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root or scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crm

DB_PATH = crm.DB_PATH


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print("No CRM database found yet. No contacts recorded.")
        sys.exit(0)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _section(title: str) -> None:
    print(f"\n{'-' * 50}")
    print(f"  {title}")
    print(f"{'-' * 50}")


def main() -> None:
    crm.init_db()  # ensure schema exists even if DB is fresh
    conn = _connect()

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.date().isoformat()                    # e.g. 2026-05-07
    week_start = now_utc.strftime("%Y-%W")                    # ISO year-week

    print("\n" + "=" * 50)
    print("  OpenGenealogyAI CRM Dashboard")
    print(f"  {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    # ── Total contacts ────────────────────────────────────────────────────────
    _section("Contacts")
    total = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    print(f"  Total contacts:          {total}")

    # ── Contacts by source ────────────────────────────────────────────────────
    _section("Contacts by Source")
    rows = conn.execute(
        "SELECT source, COUNT(*) AS cnt FROM contacts GROUP BY source ORDER BY cnt DESC"
    ).fetchall()
    if rows:
        for row in rows:
            print(f"  {row['source']:<25} {row['cnt']}")
    else:
        print("  (none)")

    # ── Pending reports ───────────────────────────────────────────────────────
    _section("Pending Reports (not yet delivered)")
    pending = conn.execute(
        """
        SELECT rr.id, c.email, rr.ancestor_name, rr.submitted_at
        FROM report_requests rr
        JOIN contacts c ON c.id = rr.contact_id
        WHERE rr.status = 'pending'
        ORDER BY rr.submitted_at ASC
        """
    ).fetchall()
    if pending:
        print(f"  {'ID':<6} {'Email':<30} {'Ancestor':<25} Submitted")
        print(f"  {'--':<6} {'-----':<30} {'--------':<25} ---------")
        for r in pending:
            submitted = r["submitted_at"][:16].replace("T", " ")
            print(f"  {r['id']:<6} {r['email']:<30} {r['ancestor_name']:<25} {submitted}")
    else:
        print("  (none - all clear!)")

    # ── Reports delivered today ───────────────────────────────────────────────
    _section("Reports Delivered")
    today_count = conn.execute(
        "SELECT COUNT(*) FROM report_requests WHERE status = 'sent' AND delivered_at LIKE ?",
        (f"{today_str}%",),
    ).fetchone()[0]

    # This week: delivered_at starts with YYYY-Www — use date arithmetic instead
    week_count = conn.execute(
        """
        SELECT COUNT(*) FROM report_requests
        WHERE status = 'sent'
          AND strftime('%Y-%W', delivered_at) = strftime('%Y-%W', 'now')
        """
    ).fetchone()[0]

    total_delivered = conn.execute(
        "SELECT COUNT(*) FROM report_requests WHERE status = 'sent'"
    ).fetchone()[0]

    print(f"  Delivered today:         {today_count}")
    print(f"  Delivered this week:     {week_count}")
    print(f"  Delivered all time:      {total_delivered}")

    # ── Failed reports ────────────────────────────────────────────────────────
    failed = conn.execute(
        "SELECT COUNT(*) FROM report_requests WHERE status = 'failed'"
    ).fetchone()[0]
    if failed:
        print(f"\n  Failed / error:          {failed}")

    # ── Follow-up candidates ──────────────────────────────────────────────────
    stale_7 = conn.execute(
        """
        SELECT COUNT(*) FROM contacts
        WHERE datetime(last_seen_at) <= datetime('now', '-7 days')
        """
    ).fetchone()[0]
    _section("Follow-up Queue")
    print(f"  Not seen in 7+ days:     {stale_7}")

    print("\n" + "=" * 50 + "\n")
    conn.close()


if __name__ == "__main__":
    main()
