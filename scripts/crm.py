"""
crm.py — OpenGenealogyAI CRM module.

SQLite-backed contact and report tracking.
Database lives at: data/crm.db (relative to project root)
"""

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# ── Database path ─────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "crm.db"


# ── Connection helper ─────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    name         TEXT,
    source       TEXT    NOT NULL DEFAULT 'free_report',
    created_at   TEXT    NOT NULL,
    last_seen_at TEXT    NOT NULL,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS report_requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id    INTEGER NOT NULL REFERENCES contacts(id),
    ancestor_name TEXT    NOT NULL,
    submitted_at  TEXT    NOT NULL,
    delivered_at  TEXT,
    status        TEXT    NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    tier       TEXT    NOT NULL DEFAULT 'starter',
    started_at TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS interactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    type       TEXT    NOT NULL,
    occurred_at TEXT   NOT NULL,
    notes      TEXT
);
"""


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript(SCHEMA_SQL)


# ── Core functions ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_contact(email: str, name: str = "", source: str = "free_report") -> int:
    """
    Create a new contact or update last_seen_at if one already exists.
    Returns the contact_id (int).
    """
    init_db()
    now = _now_iso()
    email = email.strip().lower()
    name = (name or "").strip()

    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM contacts WHERE email = ?", (email,)
        ).fetchone()

        if row:
            contact_id = row["id"]
            conn.execute(
                "UPDATE contacts SET last_seen_at = ?, name = COALESCE(NULLIF(?, ''), name) WHERE id = ?",
                (now, name, contact_id),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO contacts (email, name, source, created_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email, name, source, now, now),
            )
            contact_id = cur.lastrowid

    return contact_id


def log_report_request(email: str, name: str, ancestor_name: str) -> int:
    """
    Upsert the contact and insert a pending report_request row.
    Returns the new request_id (int).
    """
    contact_id = upsert_contact(email, name, source="free_report")
    now = _now_iso()

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO report_requests (contact_id, ancestor_name, submitted_at, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (contact_id, ancestor_name.strip(), now),
        )
        request_id = cur.lastrowid

    log_interaction(contact_id, "report_requested", f"Ancestor: {ancestor_name}")
    return request_id


def mark_report_delivered(request_id: int) -> None:
    """
    Set delivered_at = now and status = 'sent' on a report_request row.
    Also logs a report_delivered interaction.
    """
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_requests
            SET delivered_at = ?, status = 'sent'
            WHERE id = ?
            """,
            (now, request_id),
        )
        row = conn.execute(
            "SELECT contact_id, ancestor_name FROM report_requests WHERE id = ?",
            (request_id,),
        ).fetchone()

    if row:
        log_interaction(
            row["contact_id"],
            "report_delivered",
            f"Request #{request_id} — {row['ancestor_name']}",
        )


def log_interaction(contact_id: int, type: str, notes: str = "") -> int:
    """
    Append an interaction row for a contact.
    Common types: email_sent, report_delivered, upgrade_prompt, report_requested
    Returns the new interaction_id.
    """
    init_db()
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO interactions (contact_id, type, occurred_at, notes)
            VALUES (?, ?, ?, ?)
            """,
            (contact_id, type, now, notes),
        )
        return cur.lastrowid


def get_pending_reports() -> list[dict]:
    """
    Return all report_requests with status='pending', joined with contact email.
    Each item is a dict with keys: id, contact_id, email, ancestor_name, submitted_at
    """
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT rr.id, rr.contact_id, c.email, c.name,
                   rr.ancestor_name, rr.submitted_at
            FROM report_requests rr
            JOIN contacts c ON c.id = rr.contact_id
            WHERE rr.status = 'pending'
            ORDER BY rr.submitted_at ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_contacts_for_followup(days_since: int = 7) -> list[dict]:
    """
    Return contacts whose last_seen_at is older than days_since days.
    Each item is a dict with keys: id, email, name, source, last_seen_at
    """
    init_db()
    cutoff = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, email, name, source, last_seen_at
            FROM contacts
            WHERE datetime(last_seen_at) <= datetime(?, '-' || ? || ' days')
            ORDER BY last_seen_at ASC
            """,
            (cutoff, days_since),
        ).fetchall()
    return [dict(r) for r in rows]


def export_csv(filepath: str) -> int:
    """
    Dump all contacts to a CSV file.
    Returns the number of rows written.
    """
    init_db()
    out = Path(filepath)
    out.parent.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, email, name, source, created_at, last_seen_at, notes FROM contacts ORDER BY id"
        ).fetchall()

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "email", "name", "source", "created_at", "last_seen_at", "notes"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    return len(rows)
