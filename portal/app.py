"""
OpenGenealogyAI — Paid User Portal
Goal #21: Private dashboard for paying users.

Run: python portal/app.py
Port: 8082
"""

import os
import sqlite3
import json
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_from_directory)
try:
    from flask_cors import CORS
    _has_cors = True
except ImportError:
    _has_cors = False

# ── optional search dependencies ───────────────────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    _has_qdrant = True
except ImportError:
    _has_qdrant = False

import urllib.request as _urllib
import time
import threading

# ── paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
PORTAL_DB  = DATA_DIR / "portal.db"

# ── search config ──────────────────────────────────────────────────────────────
QDRANT_HOST      = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT      = int(os.environ.get("QDRANT_PORT", 6333))
# OLLAMA_HOST env var may be "0.0.0.0" (Ollama bind address) — normalize to a real URL
_raw_ollama = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not _raw_ollama.startswith("http"):
    # Strip bare IP/hostname — replace 0.0.0.0 with 127.0.0.1 for client use
    _ollama_ip = _raw_ollama if _raw_ollama != "0.0.0.0" else "127.0.0.1"
    OLLAMA_HOST = f"http://{_ollama_ip}:11434"
else:
    OLLAMA_HOST = _raw_ollama
EMBED_MODEL      = os.environ.get("EMBED_MODEL", "nomic-embed-text")
SEARCH_LIMIT     = 10          # results per query
RATE_LIMIT_RPM   = 20          # max searches per minute per IP (free tier)

# Simple in-memory rate limiter — resets on restart, good enough for launch
_rate_lock   = threading.Lock()
_rate_hits   = {}   # ip -> [timestamps]
UPLOAD_DIR = DATA_DIR / "user_docs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("PORTAL_SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# Allow the public static site (any origin) to call the public API endpoints
if _has_cors:
    CORS(app, resources={r"/api/directory/*": {"origins": "*"}})

# ── database ───────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(str(PORTAL_DB))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    UNIQUE NOT NULL,
            pw_hash     TEXT    NOT NULL,
            name        TEXT,
            plan        TEXT    DEFAULT 'free',
            actions_remaining INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now')),
            last_login  TEXT,
            stripe_customer_id TEXT,
            verified    INTEGER DEFAULT 0,
            verify_token TEXT
        );

        CREATE TABLE IF NOT EXISTS trees (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            name        TEXT    DEFAULT 'My Family Tree',
            root_name   TEXT,
            root_birth  TEXT,
            generations_found INTEGER DEFAULT 0,
            last_updated TEXT   DEFAULT (datetime('now')),
            share_token TEXT    UNIQUE,
            share_enabled INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS persons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tree_id     INTEGER NOT NULL REFERENCES trees(id),
            wikidata_id TEXT,
            given_name  TEXT,
            surname     TEXT,
            birth_year  INTEGER,
            birth_place TEXT,
            death_year  INTEGER,
            death_place TEXT,
            generation  INTEGER DEFAULT 0,
            parent1_id  INTEGER REFERENCES persons(id),
            parent2_id  INTEGER REFERENCES persons(id),
            confidence  REAL    DEFAULT 1.0,
            sources     TEXT    DEFAULT '[]',
            notes       TEXT,
            added_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            person_id   INTEGER REFERENCES persons(id),
            filename    TEXT    NOT NULL,
            stored_name TEXT    NOT NULL,
            doc_type    TEXT    DEFAULT 'other',
            size_bytes  INTEGER,
            uploaded_at TEXT    DEFAULT (datetime('now')),
            description TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_persons_tree ON persons(tree_id);
        CREATE INDEX IF NOT EXISTS idx_docs_user ON documents(user_id);

        CREATE TABLE IF NOT EXISTS directory_listings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tree_name    TEXT    NOT NULL,
            tree_url     TEXT    NOT NULL,
            format       TEXT    NOT NULL DEFAULT 'other',
            surnames     TEXT,
            geo_era      TEXT,
            description  TEXT,
            submitter_email TEXT,
            record_count INTEGER DEFAULT 0,
            status       TEXT    DEFAULT 'pending',  -- pending|approved|rejected
            verified_maxgen INTEGER DEFAULT 0,
            submitted_at TEXT    DEFAULT (datetime('now')),
            approved_at  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_listings_status ON directory_listings(status);
        """)
    print(f"[portal] Database ready: {PORTAL_DB}")


# ── auth helpers ───────────────────────────────────────────────────────────────
def hash_password(pw):
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest()
    return f"{salt}:{h}"


def check_password(pw, stored):
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest() == h
    except Exception:
        return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


# ── auth routes ────────────────────────────────────────────────────────────────
@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name  = request.form.get("name", "").strip()
        pw    = request.form.get("password", "")
        pw2   = request.form.get("password2", "")

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Please enter a valid email address.", "error")
            return render_template("signup.html")
        if len(pw) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("signup.html")
        if pw != pw2:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        try:
            with get_db() as db:
                cur = db.execute(
                    "INSERT INTO users (email, pw_hash, name) VALUES (?,?,?)",
                    (email, hash_password(pw), name)
                )
                uid = cur.lastrowid
                db.execute("INSERT INTO trees (user_id, name) VALUES (?,?)",
                           (uid, "My Family Tree"))
            session.permanent = True
            session["user_id"] = uid
            session["user_name"] = name or email.split("@")[0]
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("signup.html")

        flash("Welcome! Your account is ready.", "success")
        return redirect(url_for("dashboard"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw    = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user or not check_password(pw, user["pw_hash"]):
            flash("Invalid email or password.", "error")
            return render_template("login.html")
        with get_db() as db:
            db.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user["id"],))
        session.permanent = True
        session["user_id"] = user["id"]
        session["user_name"] = user["name"] or email.split("@")[0]
        return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ── dashboard ──────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    with get_db() as db:
        trees = db.execute(
            "SELECT * FROM trees WHERE user_id=? ORDER BY last_updated DESC",
            (user["id"],)).fetchall()
        doc_count = db.execute(
            "SELECT COUNT(*) FROM documents WHERE user_id=?", (user["id"],)).fetchone()[0]
    return render_template("dashboard.html", user=user, trees=trees, doc_count=doc_count)


# ── tree / pedigree ────────────────────────────────────────────────────────────
@app.route("/tree/<int:tree_id>")
@login_required
def tree_view(tree_id):
    user = current_user()
    with get_db() as db:
        tree = db.execute(
            "SELECT * FROM trees WHERE id=? AND user_id=?", (tree_id, user["id"])).fetchone()
        if not tree:
            flash("Tree not found.", "error")
            return redirect(url_for("dashboard"))
        persons = db.execute(
            "SELECT * FROM persons WHERE tree_id=? ORDER BY generation, id", (tree_id,)).fetchall()
    return render_template("tree.html", user=user, tree=tree, persons=persons)


@app.route("/api/tree/<int:tree_id>/data")
@login_required
def tree_data(tree_id):
    user = current_user()
    with get_db() as db:
        tree = db.execute(
            "SELECT * FROM trees WHERE id=? AND user_id=?", (tree_id, user["id"])).fetchone()
        if not tree:
            return jsonify({"error": "not found"}), 404
        persons = db.execute(
            "SELECT * FROM persons WHERE tree_id=? ORDER BY generation, id", (tree_id,)).fetchall()
    nodes = [{
        "id": p["id"],
        "name": f"{p['given_name'] or ''} {p['surname'] or ''}".strip() or "Unknown",
        "birth_year": p["birth_year"],
        "death_year": p["death_year"],
        "birth_place": p["birth_place"],
        "generation": p["generation"],
        "parent1_id": p["parent1_id"],
        "parent2_id": p["parent2_id"],
        "confidence": p["confidence"],
        "sources": json.loads(p["sources"] or "[]"),
    } for p in persons]
    return jsonify({"tree": dict(tree), "nodes": nodes})


@app.route("/api/tree/<int:tree_id>/person", methods=["POST"])
@login_required
def add_person(tree_id):
    user = current_user()
    with get_db() as db:
        if not db.execute("SELECT id FROM trees WHERE id=? AND user_id=?",
                          (tree_id, user["id"])).fetchone():
            return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO persons
              (tree_id, given_name, surname, birth_year, birth_place,
               death_year, death_place, generation, parent1_id, parent2_id,
               confidence, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (tree_id, data.get("given_name"), data.get("surname"),
              data.get("birth_year"), data.get("birth_place"),
              data.get("death_year"), data.get("death_place"),
              data.get("generation", 0), data.get("parent1_id"),
              data.get("parent2_id"), data.get("confidence", 1.0),
              data.get("notes")))
        db.execute(
            "UPDATE trees SET last_updated=datetime('now'), "
            "generations_found=MAX(generations_found,?) WHERE id=?",
            (data.get("generation", 0), tree_id))
    return jsonify({"id": cur.lastrowid, "ok": True})


# ── family group sheets ────────────────────────────────────────────────────────
@app.route("/tree/<int:tree_id>/sheets")
@login_required
def family_sheets(tree_id):
    user = current_user()
    with get_db() as db:
        tree = db.execute(
            "SELECT * FROM trees WHERE id=? AND user_id=?", (tree_id, user["id"])).fetchone()
        if not tree:
            flash("Tree not found.", "error")
            return redirect(url_for("dashboard"))
        persons = db.execute(
            "SELECT * FROM persons WHERE tree_id=? ORDER BY generation, surname, given_name",
            (tree_id,)).fetchall()

    person_map = {p["id"]: dict(p) for p in persons}
    families = {}
    for p in persons:
        pd = dict(p)
        for pk in ("parent1_id", "parent2_id"):
            pid = pd.get(pk)
            if pid and pid in person_map:
                if pid not in families:
                    families[pid] = {"parent": person_map[pid], "children": []}
                families[pid]["children"].append(pd)
    roots = [dict(p) for p in persons if not p["parent1_id"] and not p["parent2_id"]]
    return render_template("sheets.html", user=user, tree=tree,
                           families=list(families.values()), roots=roots,
                           person_map=person_map)


# ── document library ───────────────────────────────────────────────────────────
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".mp3", ".mp4",
               ".mov", ".heic", ".tif", ".tiff", ".doc", ".docx", ".txt"}

PLAN_DOC_LIMITS = {"free": 0, "starter": 1000, "pro": 5000, "premium": 20000}


@app.route("/documents")
@login_required
def document_library():
    user = current_user()
    with get_db() as db:
        docs = db.execute("""
            SELECT d.*, p.given_name, p.surname
            FROM documents d
            LEFT JOIN persons p ON p.id = d.person_id
            WHERE d.user_id=?
            ORDER BY d.uploaded_at DESC
        """, (user["id"],)).fetchall()
    return render_template("documents.html", user=user, docs=docs,
                           doc_count=len(docs),
                           doc_limit=PLAN_DOC_LIMITS.get(user["plan"], 0))


@app.route("/documents/upload", methods=["POST"])
@login_required
def upload_document():
    user = current_user()
    if user["plan"] == "free":
        return jsonify({"error": "Document storage requires a paid plan."}), 403

    with get_db() as db:
        doc_count = db.execute(
            "SELECT COUNT(*) FROM documents WHERE user_id=?", (user["id"],)).fetchone()[0]

    limit = PLAN_DOC_LIMITS.get(user["plan"], 0)
    if doc_count >= limit:
        return jsonify({"error": f"Storage limit reached ({limit} docs). Upgrade to store more."}), 403

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file provided."}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"File type {ext} not allowed."}), 400

    stored_name = f"{user['id']}_{secrets.token_hex(8)}{ext}"
    user_dir = UPLOAD_DIR / str(user["id"])
    user_dir.mkdir(exist_ok=True)
    save_path = user_dir / stored_name
    file.save(str(save_path))

    with get_db() as db:
        cur = db.execute("""
            INSERT INTO documents (user_id, person_id, filename, stored_name, doc_type, size_bytes, description)
            VALUES (?,?,?,?,?,?,?)
        """, (user["id"], request.form.get("person_id") or None,
              file.filename, stored_name,
              request.form.get("doc_type", "other"),
              save_path.stat().st_size,
              request.form.get("description", "")))
    return jsonify({"id": cur.lastrowid, "ok": True, "filename": file.filename})


@app.route("/documents/view/<int:doc_id>")
@login_required
def view_document(doc_id):
    user = current_user()
    with get_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id=? AND user_id=?", (doc_id, user["id"])).fetchone()
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("document_library"))
    return send_from_directory(str(UPLOAD_DIR / str(user["id"])),
                               doc["stored_name"], download_name=doc["filename"])


# ── tree sharing ───────────────────────────────────────────────────────────────
@app.route("/share/<token>")
def shared_tree(token):
    with get_db() as db:
        tree = db.execute(
            "SELECT * FROM trees WHERE share_token=? AND share_enabled=1", (token,)).fetchone()
        if not tree:
            return render_template("404.html"), 404
        persons = db.execute(
            "SELECT * FROM persons WHERE tree_id=? ORDER BY generation, id",
            (tree["id"],)).fetchall()
    nodes = [{
        "id": p["id"],
        "name": f"{p['given_name'] or ''} {p['surname'] or ''}".strip() or "Unknown",
        "birth_year": p["birth_year"], "death_year": p["death_year"],
        "birth_place": p["birth_place"], "generation": p["generation"],
        "parent1_id": p["parent1_id"], "parent2_id": p["parent2_id"],
        "confidence": p["confidence"],
    } for p in persons]
    return render_template("shared_tree.html", tree=tree, nodes=nodes)


@app.route("/api/tree/<int:tree_id>/share", methods=["POST"])
@login_required
def toggle_sharing(tree_id):
    user = current_user()
    with get_db() as db:
        tree = db.execute(
            "SELECT * FROM trees WHERE id=? AND user_id=?", (tree_id, user["id"])).fetchone()
        if not tree:
            return jsonify({"error": "not found"}), 404
        if not tree["share_token"]:
            token = secrets.token_urlsafe(16)
            db.execute("UPDATE trees SET share_token=?, share_enabled=1 WHERE id=?", (token, tree_id))
        else:
            db.execute("UPDATE trees SET share_enabled=? WHERE id=?",
                       (0 if tree["share_enabled"] else 1, tree_id))
        updated = db.execute("SELECT * FROM trees WHERE id=?", (tree_id,)).fetchone()
    url = (url_for("shared_tree", token=updated["share_token"], _external=True)
           if updated["share_enabled"] else None)
    return jsonify({"enabled": bool(updated["share_enabled"]), "url": url})


# ── account ────────────────────────────────────────────────────────────────────
@app.route("/account")
@login_required
def account():
    return render_template("account.html", user=current_user())


@app.route("/account/update", methods=["POST"])
@login_required
def update_account():
    user = current_user()
    name = request.form.get("name", "").strip()
    with get_db() as db:
        db.execute("UPDATE users SET name=? WHERE id=?", (name, user["id"]))
    session["user_name"] = name
    flash("Account updated.", "success")
    return redirect(url_for("account"))


# ── demo seed ──────────────────────────────────────────────────────────────────
@app.route("/demo/seed")
@login_required
def seed_demo_data():
    """Load Lincoln family demo data into the user's first tree."""
    user = current_user()
    with get_db() as db:
        tree = db.execute("SELECT * FROM trees WHERE user_id=? LIMIT 1", (user["id"],)).fetchone()
        if not tree:
            return "No tree found", 404
        tree_id = tree["id"]
        if db.execute("SELECT COUNT(*) FROM persons WHERE tree_id=?", (tree_id,)).fetchone()[0] > 0:
            flash("Demo data already loaded.", "info")
            return redirect(url_for("tree_view", tree_id=tree_id))

        ps = [
            dict(given_name="Abraham", surname="Lincoln", birth_year=1809,
                 birth_place="Hardin County, Kentucky", death_year=1865,
                 death_place="Washington, D.C.", generation=0, confidence=1.0,
                 sources='["Wikidata Q91","1860 US Census"]'),
            dict(given_name="Thomas", surname="Lincoln", birth_year=1778,
                 birth_place="Rockingham County, Virginia", death_year=1851,
                 death_place="Coles County, Illinois", generation=1, confidence=0.99,
                 sources='["Wikidata Q1124178"]'),
            dict(given_name="Nancy", surname="Hanks", birth_year=1784,
                 birth_place="Hampshire County, Virginia", death_year=1818,
                 death_place="Spencer County, Indiana", generation=1, confidence=0.97,
                 sources='["Wikidata Q233592"]'),
            dict(given_name="Abraham", surname="Lincoln", birth_year=1744,
                 birth_place="Berks County, Pennsylvania", death_year=1786,
                 death_place="Jefferson County, Kentucky", generation=2, confidence=0.95,
                 sources='["Wikidata Q4666050"]'),
            dict(given_name="Bathsheba", surname="Herring", birth_year=1742,
                 birth_place="Virginia", death_year=1836,
                 death_place="Washington County, Kentucky", generation=2, confidence=0.90,
                 sources='["Lincoln family records"]'),
            dict(given_name="James", surname="Hanks", birth_year=1750,
                 birth_place="Virginia", death_year=1793,
                 death_place="Virginia", generation=2, confidence=0.72,
                 sources='["Disputed — multiple candidates"]'),
            dict(given_name="Lucy", surname="Shipley", birth_year=1752,
                 birth_place="Virginia", death_year=None, death_place=None,
                 generation=2, confidence=0.65,
                 sources='["Estimated — not confirmed"]'),
        ]
        ids = []
        for p in ps:
            cur = db.execute("""
                INSERT INTO persons
                  (tree_id,given_name,surname,birth_year,birth_place,
                   death_year,death_place,generation,confidence,sources)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (tree_id, p["given_name"], p["surname"], p["birth_year"],
                  p["birth_place"], p["death_year"], p["death_place"],
                  p["generation"], p["confidence"], p["sources"]))
            ids.append(cur.lastrowid)

        db.execute("UPDATE persons SET parent1_id=?, parent2_id=? WHERE id=?",
                   (ids[1], ids[2], ids[0]))
        db.execute("UPDATE persons SET parent1_id=?, parent2_id=? WHERE id=?",
                   (ids[3], ids[4], ids[1]))
        db.execute("UPDATE persons SET parent1_id=?, parent2_id=? WHERE id=?",
                   (ids[5], ids[6], ids[2]))
        db.execute("UPDATE trees SET root_name='Abraham Lincoln', "
                   "generations_found=2, last_updated=datetime('now') WHERE id=?", (tree_id,))

    flash("Lincoln family demo loaded — 3 generations, 7 people.", "success")
    return redirect(url_for("tree_view", tree_id=tree_id))


# ── community directory API ────────────────────────────────────────────────────

@app.route("/api/directory/submit", methods=["POST"])
def submit_directory_listing():
    """Accept a community tree listing submission."""
    data = request.get_json() or request.form.to_dict()

    tree_name = (data.get("tree_name") or data.get("treeName") or "").strip()
    tree_url  = (data.get("tree_url")  or data.get("treeUrl")  or "").strip()
    fmt       = (data.get("format")    or "other").strip().lower()

    if not tree_name or not tree_url:
        return jsonify({"error": "Tree name and URL are required."}), 400
    if not re.match(r"https?://", tree_url):
        return jsonify({"error": "Tree URL must start with http:// or https://"}), 400

    with get_db() as db:
        cur = db.execute("""
            INSERT INTO directory_listings
              (tree_name, tree_url, format, surnames, geo_era, description, submitter_email)
            VALUES (?,?,?,?,?,?,?)
        """, (
            tree_name, tree_url, fmt,
            (data.get("surnames") or "").strip(),
            (data.get("geo_era")  or data.get("geoEra") or "").strip(),
            (data.get("description") or "").strip()[:1000],
            (data.get("email") or data.get("submitter_email") or "").strip().lower(),
        ))
        listing_id = cur.lastrowid

    return jsonify({
        "ok": True,
        "id": listing_id,
        "message": "Thank you! Your listing is under review and will appear in the directory within 48 hours."
    })


@app.route("/api/directory/listings")
def get_directory_listings():
    """Return approved directory listings with optional search/filter."""
    q      = request.args.get("q", "").strip().lower()
    fmt    = request.args.get("format", "").strip().lower()
    limit  = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    where = ["status = 'approved'"]
    params = []

    if fmt:
        where.append("format = ?")
        params.append(fmt)
    if q:
        where.append("(LOWER(tree_name) LIKE ? OR LOWER(surnames) LIKE ? OR LOWER(geo_era) LIKE ? OR LOWER(description) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])

    sql = f"SELECT * FROM directory_listings WHERE {' AND '.join(where)} ORDER BY approved_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    count_sql = f"SELECT COUNT(*) FROM directory_listings WHERE {' AND '.join(where)}"

    with get_db() as db:
        rows  = db.execute(sql, params).fetchall()
        total = db.execute(count_sql, params[:-2]).fetchone()[0]

    listings = [dict(r) for r in rows]
    for l in listings:
        l.pop("submitter_email", None)   # never expose email publicly

    return jsonify({"listings": listings, "total": total, "offset": offset})


@app.route("/api/directory/stats")
def directory_stats():
    """Live stats for the directory hero section."""
    with get_db() as db:
        total_trees   = db.execute("SELECT COUNT(*) FROM directory_listings WHERE status='approved'").fetchone()[0]
        total_records = db.execute("SELECT COALESCE(SUM(record_count),0) FROM directory_listings WHERE status='approved'").fetchone()[0]
        famous_count  = 0
        try:
            import os
            fp = Path(__file__).parent.parent / "data" / "famous_people"
            if fp.exists():
                famous_count = sum(1 for f in fp.iterdir() if f.suffix == ".json" and not f.name.startswith("_"))
        except Exception:
            pass

    return jsonify({
        "trees_listed": total_trees,
        "records_linked": total_records,
        "famous_people_indexed": famous_count,
    })


# ── search helpers ────────────────────────────────────────────────────────────

def _rate_ok(ip: str) -> bool:
    """Return True if this IP is under the rate limit."""
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_hits.get(ip, []) if now - t < 60]
        if len(hits) >= RATE_LIMIT_RPM:
            return False
        hits.append(now)
        _rate_hits[ip] = hits
    return True


def _embed(text: str) -> list | None:
    """Embed text via Ollama nomic-embed-text. Returns vector or None on error."""
    import sys
    url = f"{OLLAMA_HOST}/api/embeddings"
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    try:
        req = _urllib.Request(url, data=payload,
                              headers={"Content-Type": "application/json"})
        # Disable proxy lookup — Windows urllib hangs on localhost without this
        opener = _urllib.build_opener(_urllib.ProxyHandler({}))
        with opener.open(req, timeout=30) as resp:
            result = json.loads(resp.read())
            emb = result.get("embedding")
            print(f"[search] embed OK: {len(emb) if emb else 'None'} dims", flush=True)
            return emb
    except Exception as e:
        print(f"[search] embed error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return None


def _qdrant() -> "QdrantClient | None":
    if not _has_qdrant:
        return None
    try:
        return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=5)
    except Exception:
        return None


def _format_result(hit) -> dict:
    """Convert a Qdrant ScoredPoint to a clean result dict."""
    p = hit.payload or {}
    name_parts = [p.get("given_name", ""), p.get("surname", "")]
    name = " ".join(x for x in name_parts if x).strip() or p.get("name", "Unknown")

    birth = p.get("birth_year") or p.get("birth_year_min")
    death = p.get("death_year") or p.get("death_year_min")
    place = p.get("birth_place", "")

    sources = p.get("source_record_ids") or []
    source_url = p.get("source_url", "")
    ia_url = source_url if "archive.org" in source_url else ""
    wikidata_qid = (p.get("external_ids") or {}).get("wikidata_qid", "")
    wikidata_url = f"https://www.wikidata.org/wiki/{wikidata_qid}" if wikidata_qid else ""

    return {
        "id":           str(hit.id),
        "score":        round(hit.score, 3),
        "name":         name,
        "birth_year":   birth,
        "death_year":   death,
        "birth_place":  place,
        "death_place":  p.get("death_place", ""),
        "occupation":   p.get("occupation", ""),
        "father":       p.get("father", ""),
        "mother":       p.get("mother", ""),
        "spouse":       p.get("spouse", ""),
        "source_count": len(sources),
        "source_url":   source_url,
        "ia_url":       ia_url,
        "wikidata_url": wikidata_url,
        "collection":   getattr(hit, "_collection", "people"),
    }


# ── search routes ──────────────────────────────────────────────────────────────

@app.route("/search")
def search_page():
    """Public search page — no login required."""
    query = request.args.get("q", "").strip()
    results = []
    error = None
    searched = False

    if query:
        searched = True
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        if not _rate_ok(ip):
            error = "Too many searches — please wait a moment and try again."
        elif not _has_qdrant:
            error = "Search index not available yet — check back soon."
        else:
            vector = _embed(
                f"search_query: {query}"
            )
            if vector is None:
                error = "Search engine is warming up — try again in a few seconds."
            else:
                client = _qdrant()
                if client is None:
                    error = "Search database is starting up — check back soon."
                else:
                    try:
                        # Search people collection
                        resp = client.query_points(
                            collection_name="people",
                            query=vector,
                            limit=SEARCH_LIMIT,
                            with_payload=True,
                        )
                        results = [_format_result(h) for h in resp.points]
                    except Exception as e:
                        print(f"[search] qdrant error: {e}")
                        error = "Search is unavailable — the index may still be loading."

    return render_template("search.html",
                           query=query,
                           results=results,
                           error=error,
                           searched=searched,
                           result_count=len(results))


@app.route("/api/search")
def api_search():
    """JSON search API — public, rate limited."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q parameter required"}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if not _rate_ok(ip):
        return jsonify({"error": "rate_limit", "message": "Too many requests"}), 429

    if not _has_qdrant:
        return jsonify({"error": "search_unavailable", "message": "Qdrant not installed"}), 503

    vector = _embed(f"search_query: {query}")
    if vector is None:
        return jsonify({"error": "embed_failed", "message": "Embedding service unavailable"}), 503

    client = _qdrant()
    if client is None:
        return jsonify({"error": "db_unavailable", "message": "Search database unavailable"}), 503

    try:
        resp = client.query_points(
            collection_name="people",
            query=vector,
            limit=SEARCH_LIMIT,
            with_payload=True,
        )
        results = [_format_result(h) for h in resp.points]
        return jsonify({"query": query, "results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": "search_error", "message": str(e)}), 500


@app.route("/api/status")
def api_status():
    """Health check — shows what's online."""
    status = {
        "portal": "ok",
        "qdrant": "offline",
        "ollama": "offline",
        "people_count": 0,
    }
    if _has_qdrant:
        try:
            client = _qdrant()
            if client:
                info = client.get_collection("people")
                status["qdrant"] = "ok"
                status["people_count"] = info.points_count
        except Exception:
            pass
    try:
        req = _urllib.Request(f"{OLLAMA_HOST}/api/tags")
        with _urllib.urlopen(req, timeout=3):
            status["ollama"] = "ok"
    except Exception:
        pass
    return jsonify(status)


# ── jinja2 filters ────────────────────────────────────────────────────────────
@app.template_filter("from_json")
def from_json_filter(s):
    try:
        return json.loads(s)
    except Exception:
        return []


# ── dev / demo routes ──────────────────────────────────────────────────────────

# Path to canonical Maxwell family tree photos (OMEN pipeline session output)
_FAMILY_TREE_ROOT = r"D:\AI\Companies\open-genealogical-ai\family_tree"

@app.route("/family-photos/<ancestor_slug>/<filename>")
def family_photos(ancestor_slug, filename):
    """Serve photos from the Maxwell family tree archive.
    Read-only; only allows files inside the family_tree dir.
    """
    safe_slug = "".join(c for c in ancestor_slug if c.isalnum() or c in "-_")
    safe_name = "".join(c for c in filename if c.isalnum() or c in "-_.")
    folder = os.path.join(_FAMILY_TREE_ROOT, safe_slug)
    full = os.path.join(folder, safe_name)
    if not os.path.isfile(full):
        return "Not found", 404
    if not os.path.abspath(full).startswith(os.path.abspath(_FAMILY_TREE_ROOT)):
        return "Forbidden", 403
    from flask import send_file
    return send_file(full)


@app.route("/dev/components")
def dev_components():
    """Storybook-lite: render every <maxgen-*> with example data."""
    return render_template("dev_components.html")


@app.route("/dev/family-group-sheet")
def dev_family_group_sheet():
    """Live demo: William Bailey Maxwell + Lucretia Bracken + their children.
    Uses real data from the OMEN family_tree archive.
    """
    return render_template("dev_family_group_sheet.html")


@app.route("/dev/tokens")
def dev_tokens():
    """Visual swatch page for design tokens."""
    return render_template("dev_tokens.html")


@app.route("/dev/person")
def dev_person():
    """Live demo: William Bailey Maxwell's profile page."""
    return render_template("dev_person_profile.html")


@app.route("/dev/pedigree")
def dev_pedigree():
    """Live demo: Garlon's full Maxwell patriline back to Scotland (5 generations)."""
    return render_template("dev_pedigree.html")


@app.route("/dev/fan")
def dev_fan():
    """Live demo: fan chart + DNA-evidence noisy-OR boost."""
    return render_template("dev_fan.html")


@app.route("/dev/tools")
def dev_tools():
    """Live demo: relationship calculator + merge UI + GEDCOM export."""
    return render_template("dev_tools.html")


@app.route("/dev/gedcom-export")
def dev_gedcom_export():
    """Export Garlon's Maxwell patriline as GEDCOM 5.5.1."""
    from maxgen_to_gedcom import maxperson_to_gedcom
    from flask import Response

    # Real patriline data (matching the pedigree demo)
    NOW = "2026-05-17T00:00:00Z"
    def mkP(pid, name, given, surname, by=None, dy=None, bp=None, parents=None, conf=0.85):
        p = {
            "person_id": pid, "schema_version": "1.4", "is_living": False,
            "composite_confidence": conf,
            "name_assertions": [{
                "name_as_written": name, "given_name": given, "surname": surname,
                "name_type": "birth", "confidence": conf,
                "source_record_id": f"fag-{pid}", "asserted_by": "omen", "asserted_at": NOW,
            }],
            "birth_assertions": [], "death_assertions": [],
            "parent_assertions": parents or [],
            "asserted_by": "omen", "asserted_at": NOW,
        }
        if by:
            p["birth_assertions"].append({
                "year_min": by, "year_max": by, "date_type": "exact",
                "place_as_written": bp,
                "confidence": conf, "source_record_id": f"fag-{pid}",
                "asserted_by": "omen", "asserted_at": NOW,
            })
        if dy:
            p["death_assertions"].append({
                "year_min": dy, "year_max": dy, "date_type": "exact",
                "confidence": conf, "source_record_id": f"fag-{pid}",
                "asserted_by": "omen", "asserted_at": NOW,
            })
        return p

    persons = [
        mkP("william-1740", "William Maxwell (Scottish immigrant)", "William", "Maxwell", 1740, 1810, conf=0.85),
        mkP("richard-1774", "Richard Maxwell", "Richard", "Maxwell", 1774, 1845, "Bourbon Co KY",
            parents=[{"parent_role":"father", "parent_person_id":"william-1740", "parent_name":"William Maxwell", "confidence":0.88, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW}],
            conf=0.88),
        mkP("richard-1796", "Richard Maxwell", "Richard", "Maxwell", 1796, 1821, "Shawneetown IL",
            parents=[{"parent_role":"father", "parent_person_id":"richard-1774", "parent_name":"Richard Maxwell", "confidence":0.90, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW}],
            conf=0.90),
        mkP("ruth-hodge", "Ruth Hodge Barnett", "Ruth", "Hodge Barnett", 1800, 1875, conf=0.82),
        mkP("lucretia", "Lucretia Charlotte Bracken", "Lucretia Charlotte", "Bracken", 1823, 1893, conf=0.85),
        mkP("william-bailey-1821", "William Bailey Maxwell", "William Bailey", "Maxwell", 1821, 1895, "Shawneetown IL",
            parents=[
                {"parent_role":"father", "parent_person_id":"richard-1796", "parent_name":"Richard Maxwell", "confidence":0.88, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW},
                {"parent_role":"mother", "parent_person_id":"ruth-hodge", "parent_name":"Ruth Hodge Barnett", "confidence":0.85, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW},
            ], conf=0.95),
        mkP("james-1843", "James Bailey Maxwell", "James Bailey", "Maxwell", 1843, 1876, "Lee Co IA",
            parents=[
                {"parent_role":"father", "parent_person_id":"william-bailey-1821", "parent_name":"William Bailey Maxwell", "confidence":0.95, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW},
                {"parent_role":"mother", "parent_person_id":"lucretia", "parent_name":"Lucretia Charlotte Bracken", "confidence":0.95, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW},
            ], conf=0.95),
        mkP("james-1870", "James Bailey Maxwell (Jr.)", "James Bailey", "Maxwell", 1870, 1942, "Lincoln Co NV",
            parents=[{"parent_role":"father", "parent_person_id":"james-1843", "parent_name":"James Bailey Maxwell", "confidence":0.92, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW}],
            conf=0.92),
        mkP("horace", "Horace William Maxwell", "Horace William", "Maxwell", 1898, 1980, "Glendale UT",
            parents=[{"parent_role":"father", "parent_person_id":"james-1870", "parent_name":"James Bailey Maxwell (Jr.)", "confidence":0.95, "relationship_type":"biological", "source_record_id":"fag", "asserted_by":"omen", "asserted_at":NOW}],
            conf=0.95),
    ]

    ged = maxperson_to_gedcom(persons, include_living=False, caller_is_owner=True,
                              submitter_name="Garlon Maxwell")
    return Response(ged, mimetype="application/x-gedcom",
                    headers={"Content-Disposition": "attachment; filename=maxwell-line.ged"})


# ── run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORTAL_PORT", 8082))
    print(f"[portal] Running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
