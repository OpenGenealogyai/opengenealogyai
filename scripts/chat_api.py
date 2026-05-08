"""
chat_api.py — OpenGenealogyAI RAG chat API for the "Ada" genealogy expert chatbot.

POST /api/chat          — Ask Ada a genealogy question
POST /api/chat/email    — Capture email after gate at question 3
GET  /api/chat/sample-questions — Return sample questions

Run with: python chat_api.py  (listens on port 8081)
"""

import json
import os
import re
import traceback
from datetime import datetime, timedelta, timezone
from math import log
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

import crm

# ── Load environment ──────────────────────────────────────────────────────────

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

KB_DIR = Path(__file__).resolve().parent.parent / "data" / "kb"
LOG_FILE = Path(__file__).resolve().parent.parent / "_logs" / "chat_log.jsonl"

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://opengenealogyai.org",
        "https://www.opengenealogyai.org",
    ]
}})

# ── Session store (in-memory, expires after 24 hours) ────────────────────────

sessions: dict[str, dict] = {}

SESSION_TTL_HOURS = 24

SAMPLE_QUESTIONS = [
    "What records should I search to find my great-grandmother's immigration details?",
    "How do I find birth records from rural Tennessee in the 1880s?",
    "What is the best way to trace African American ancestry before 1870?",
    "How can I find out where my German ancestors came from before they emigrated?",
    "What genealogy databases have the best coverage for Irish ancestry?",
]

# ── Ada system prompt ─────────────────────────────────────────────────────────

ADA_SYSTEM_TEMPLATE = """\
You are Ada, a friendly and knowledgeable genealogy expert for OpenGenealogyAI.
You help people discover their family history. You are warm, encouraging, and precise.
You always cite what type of records would help and what sources to check.
When you don't know something specific, say so honestly and suggest where to find it.
Keep answers under 200 words. End with one follow-up question to keep the conversation going.

Context from our knowledge base:
{retrieved_context}"""

# ── Knowledge base loading ────────────────────────────────────────────────────

_kb_chunks: list[dict] = []   # [{text, source, tokens}]


def _load_kb() -> None:
    """Load all .md files from data/kb/ into memory as searchable chunks."""
    global _kb_chunks
    _kb_chunks = []
    KB_DIR.mkdir(parents=True, exist_ok=True)
    for md_file in sorted(KB_DIR.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8").strip()
            if not text:
                continue
            # Split on double newlines to get paragraph-level chunks
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
            for para in paragraphs:
                _kb_chunks.append({"text": para, "source": md_file.name})
        except OSError:
            pass


_load_kb()


# ── TF-IDF style retrieval ────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]{2,}", text.lower())


def _retrieve_context(query: str, top_k: int = 3) -> str:
    """Return the top_k most relevant KB chunks for query, concatenated."""
    if not _kb_chunks:
        return "(No knowledge base content loaded)"

    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return "(No query tokens)"

    # Simple TF-IDF: score each chunk by term overlap weighted by inverse chunk frequency
    n = len(_kb_chunks)
    scores: list[tuple[float, str]] = []

    # Build document frequency counts across all chunks
    df: dict[str, int] = {}
    for chunk in _kb_chunks:
        chunk_tokens = set(_tokenize(chunk["text"]))
        for t in chunk_tokens:
            df[t] = df.get(t, 0) + 1

    for chunk in _kb_chunks:
        chunk_tokens = _tokenize(chunk["text"])
        chunk_token_set = set(chunk_tokens)
        tf_idf_sum = 0.0
        for t in query_tokens:
            if t in chunk_token_set:
                tf = chunk_tokens.count(t) / max(len(chunk_tokens), 1)
                idf = log((n + 1) / (df.get(t, 0) + 1)) + 1
                tf_idf_sum += tf * idf
        scores.append((tf_idf_sum, chunk["text"]))

    scores.sort(key=lambda x: x[0], reverse=True)
    top = [text for score, text in scores[:top_k] if score > 0]

    if not top:
        return "(No relevant knowledge base content found)"

    return "\n\n---\n\n".join(top)


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm(system_prompt: str, user_message: str) -> str:
    """Call Claude (preferred) → OpenAI (fallback) → static response."""

    # --- Try Anthropic ---
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except Exception:
            pass  # fall through to OpenAI

    # --- Try OpenAI ---
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI
            oa_client = OpenAI(api_key=OPENAI_API_KEY)
            resp = oa_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=512,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass  # fall through to static

    # --- Static fallback ---
    return (
        "I'm Ada, your genealogy guide! I'm temporarily unable to connect to my AI backend. "
        "Here's a general tip: for most genealogy questions, start with FamilySearch.org — "
        "it's free and has billions of indexed records. "
        "What ancestor are you trying to find?"
    )


# ── Session helpers ───────────────────────────────────────────────────────────

def _get_session(session_id: str) -> dict:
    """Return session dict, creating it if new. Prune expired sessions."""
    now = datetime.now(timezone.utc)

    # Prune expired sessions opportunistically
    expired = [
        sid for sid, s in sessions.items()
        if now - s["created_at"] > timedelta(hours=SESSION_TTL_HOURS)
    ]
    for sid in expired:
        del sessions[sid]

    if session_id not in sessions:
        sessions[session_id] = {
            "question_count": 0,
            "email_captured": False,
            "created_at": now,
        }

    return sessions[session_id]


# ── Logging ───────────────────────────────────────────────────────────────────

def _log_chat(session_id: str, message: str, answer: str, status: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": session_id,
        "question": message,
        "answer": answer,
        "status": status,
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def api_chat():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        data = request.get_json(force=True, silent=True) or {}
        message = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "anon").strip()
        # question_number from client is the number OF THE CURRENT question being asked
        question_number = int(data.get("question_number") or 1)

        if not message:
            return jsonify({"error": "message is required"}), 400

        session = _get_session(session_id)

        # Use server-side count as the authoritative state
        # Increment before answering so count reflects this question
        session["question_count"] += 1
        server_q = session["question_count"]

        # --- Paywall: question 7+ ---
        if server_q >= 7:
            _log_chat(session_id, message, "", "paywall")
            return jsonify({
                "answer": None,
                "question_number": server_q + 1,
                "status": "paywall",
                "show_email_gate": False,
                "show_paywall": True,
            })

        # --- Email gate: question 3 (answer + show gate) ---
        # Questions 4-6 are free IF email was captured
        if server_q == 3 and not session["email_captured"]:
            context = _retrieve_context(message)
            system_prompt = ADA_SYSTEM_TEMPLATE.format(retrieved_context=context)
            answer = _call_llm(system_prompt, message)
            _log_chat(session_id, message, answer, "email_gate")
            return jsonify({
                "answer": answer,
                "question_number": server_q + 1,
                "status": "email_gate",
                "show_email_gate": True,
                "show_paywall": False,
            })

        # --- Soft block: questions 4-6 without email ---
        if server_q in (4, 5, 6) and not session["email_captured"]:
            _log_chat(session_id, message, "", "email_gate")
            return jsonify({
                "answer": None,
                "question_number": server_q + 1,
                "status": "email_gate",
                "show_email_gate": True,
                "show_paywall": False,
            })

        # --- Free answer (questions 1-2, or 4-6 after email) ---
        context = _retrieve_context(message)
        system_prompt = ADA_SYSTEM_TEMPLATE.format(retrieved_context=context)
        answer = _call_llm(system_prompt, message)
        _log_chat(session_id, message, answer, "free")

        return jsonify({
            "answer": answer,
            "question_number": server_q + 1,
            "status": "free",
            "show_email_gate": False,
            "show_paywall": False,
        })

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Something went wrong: {exc}"}), 500


@app.route("/api/chat/email", methods=["POST", "OPTIONS"])
def api_chat_email():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        data = request.get_json(force=True, silent=True) or {}
        session_id = (data.get("session_id") or "anon").strip()
        email = (data.get("email") or "").strip().lower()

        if not email:
            return jsonify({"error": "email is required"}), 400

        # Save to CRM
        crm.upsert_contact(email, source="chat_gate")

        # Mark session
        session = _get_session(session_id)
        session["email_captured"] = True

        # Calculate remaining free questions (up to question 6)
        used = session["question_count"]
        remaining = max(0, 6 - used)

        _log_chat(session_id, f"[email captured: {email}]", "", "email_captured")

        return jsonify({"success": True, "questions_remaining": remaining})

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Something went wrong: {exc}"}), 500


@app.route("/api/chat/sample-questions", methods=["GET"])
def api_sample_questions():
    return jsonify({"questions": SAMPLE_QUESTIONS})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "chat_api",
        "kb_chunks": len(_kb_chunks),
        "active_sessions": len(sessions),
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("OpenGenealogyAI Chat API (Ada) — http://localhost:8081")
    print(f"KB directory: {KB_DIR}  ({len(_kb_chunks)} chunks loaded)")
    print(f"Chat log: {LOG_FILE}")
    print(f"LLM backend: {'Anthropic' if ANTHROPIC_API_KEY else 'OpenAI' if OPENAI_API_KEY else 'Static fallback'}")
    app.run(host="0.0.0.0", port=8081, debug=False)
