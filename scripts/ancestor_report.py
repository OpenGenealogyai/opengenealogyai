"""
ancestor_report.py — OpenGenealogyAI free ancestor report endpoint.

POST /api/report  →  generate AI report, email it, log submission.
Run with: python ancestor_report.py  (listens on port 8080)
"""

import json
import os
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

import crm

# ── Load environment ──────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_FROM = "garlonmaxwell@gmail.com"
LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "report_submissions.json"

openai_client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_prompt(data: dict) -> str:
    ancestor_name = data.get("ancestor_name", "Unknown")
    spouse = data.get("spouse_name", "")
    birth_year = data.get("birth_year", "")
    death_year = data.get("death_year", "")
    birthplace = data.get("birthplace", "")
    town_county = data.get("town_county", "")
    last_address = data.get("last_address", "")
    children = data.get("children", "")
    extra_info = data.get("extra_info", "")

    context_lines = []
    if ancestor_name:
        context_lines.append(f"- Full name: {ancestor_name}")
    if spouse:
        context_lines.append(f"- Spouse / wife: {spouse}")
    if birth_year:
        context_lines.append(f"- Birth year: {birth_year}")
    if birthplace:
        context_lines.append(f"- Birthplace: {birthplace}")
    if death_year:
        context_lines.append(f"- Death year: {death_year}")
    if town_county:
        context_lines.append(f"- Town / county lived in: {town_county}")
    if last_address:
        context_lines.append(f"- Last known address: {last_address}")
    if children:
        context_lines.append(f"- Children's names: {children}")
    if extra_info:
        context_lines.append(f"- Additional information: {extra_info}")

    context_block = "\n".join(context_lines) if context_lines else "(no details provided)"

    return f"""You are a professional genealogy researcher writing a free ancestry report for a client.

Here is what the client has told us about their ancestor:

{context_block}

Write a 400–600 word genealogy research report with the following sections:

1. **Summary of What Is Known**
   Summarize the key biographical facts provided. Note which details are solid anchors (specific dates/places) versus approximate (decade ranges, vague regions). Assign a confidence level (HIGH / MEDIUM / LOW) to each key fact.

2. **3–5 Specific Next Research Steps**
   Based on the time period and location, list 3–5 specific archives, record collections, or record types that would be most productive to search next. Be specific: name the actual collection (e.g., "FamilySearch — Tennessee Death Records 1908–1958", "U.S. Federal Census 1880 — Giles County, Tennessee", "Ancestry — Civil War Draft Registration Cards"). For each, briefly explain what it might reveal.

3. **Open Research Questions**
   List 2–3 key unanswered questions this research would try to resolve.

4. **A Note on Confidence**
   One short paragraph explaining the confidence levels used and reminding the reader that genealogy involves uncertainty — our platform preserves all leads rather than forcing a single answer.

5. **Your Next Step**
   Mention that full AI-powered research — with confidence scoring, competing hypotheses, and a live Confidence Map — is available via Research Actions on OpenGenealogyAI.org.

Sign off as:
OpenGenealogyAI Research Team
opengenealogyai.org

Keep the tone warm, professional, and encouraging. Do not invent facts. If a detail is missing or uncertain, say so explicitly."""


def generate_report(data: dict) -> str:
    prompt = build_prompt(data)
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional genealogy researcher. Write clear, accurate, "
                    "encouraging research reports based only on information provided."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=900,
        temperature=0.6,
    )
    return response.choices[0].message.content.strip()


def report_to_html(report_text: str, ancestor_name: str) -> str:
    # Convert markdown-ish bold to HTML, preserve line breaks
    import re
    html_body = report_text
    # Bold **text** → <strong>text</strong>
    html_body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_body)
    # Numbered headers like "1. **Title**" → styled divs
    html_body = html_body.replace("\n\n", "</p><p>")
    html_body = html_body.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Your OpenGenealogyAI Ancestor Report</title>
<style>
  body {{ font-family: Georgia, serif; background: #f0ede4; color: #1a1a18; margin: 0; padding: 0; }}
  .wrapper {{ max-width: 640px; margin: 0 auto; background: #fff; }}
  .header {{ background: #1a1a18; color: #f0ede4; padding: 2rem; text-align: center; }}
  .header h1 {{ font-size: 1.3rem; margin: 0 0 0.25rem; letter-spacing: 0.04em; }}
  .header .sub {{ font-family: sans-serif; font-size: 0.8rem; opacity: 0.6; }}
  .gold {{ color: #b5873d; }}
  .body {{ padding: 2rem 2.5rem; }}
  .body h2 {{ font-size: 1.1rem; color: #2a5a2a; margin-bottom: 0.5rem; }}
  .body p {{ line-height: 1.8; margin: 0 0 1rem; font-size: 0.95rem; }}
  .cta-block {{ background: #f0ede4; border-radius: 6px; padding: 1.5rem; text-align: center; margin: 1.5rem 0; }}
  .cta-block p {{ margin: 0 0 1rem; font-family: sans-serif; font-size: 0.9rem; }}
  .btn {{ display: inline-block; background: #b5873d; color: #fff; padding: 0.75rem 2rem;
          border-radius: 4px; text-decoration: none; font-family: sans-serif;
          font-weight: bold; font-size: 0.95rem; }}
  .footer {{ background: #1a1a18; color: #f0ede4; text-align: center; padding: 1.5rem;
             font-family: sans-serif; font-size: 0.78rem; opacity: 0.8; }}
  .footer a {{ color: #b5873d; text-decoration: none; }}
  .divider {{ border: none; border-top: 1px solid #e0ddd4; margin: 1.5rem 0; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>OpenGenealogyAI</h1>
    <div class="sub">Your Free Ancestor Report</div>
    <div style="margin-top:0.75rem;font-size:1.1rem;" class="gold">{ancestor_name}</div>
  </div>

  <div class="body">
    <h2>Your Research Report</h2>
    <p>{html_body}</p>

    <hr class="divider">

    <div class="cta-block">
      <p>Ready for deeper research? Our AI agents can search millions of records,
      score every lead, and build a live Confidence Map of your family tree.</p>
      <a class="btn" href="https://opengenealogyai.org">Start Full Research →</a>
    </div>
  </div>

  <div class="footer">
    <p>OpenGenealogyAI — We Don't Guess. We Measure.</p>
    <p style="margin-top:0.5rem"><a href="https://opengenealogyai.org">opengenealogyai.org</a></p>
    <p style="margin-top:0.5rem;opacity:0.5">You received this because you requested a free ancestor report. No spam, ever.</p>
  </div>
</div>
</body>
</html>"""


def report_to_plaintext(report_text: str, ancestor_name: str) -> str:
    return f"""OpenGenealogyAI — Free Ancestor Report
Ancestor: {ancestor_name}
{'=' * 60}

{report_text}

{'=' * 60}
Ready for deeper research? Visit https://opengenealogyai.org
to start full AI-powered genealogy with confidence scoring.

OpenGenealogyAI — We Don't Guess. We Measure.
opengenealogyai.org
"""


def send_email(to_address: str, ancestor_name: str, report_text: str) -> None:
    subject = f"Your OpenGenealogyAI Ancestor Report — {ancestor_name}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"OpenGenealogyAI <{GMAIL_FROM}>"
    msg["To"] = to_address

    plain = report_to_plaintext(report_text, ancestor_name)
    html = report_to_html(report_text, ancestor_name)

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_FROM, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_FROM, to_address, msg.as_string())


def log_submission(data: dict, success: bool, error: str = "") -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    submissions = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                submissions = json.load(f)
        except (json.JSONDecodeError, OSError):
            submissions = []

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "success": success,
        "email": data.get("email", ""),
        "ancestor_name": data.get("ancestor_name", ""),
        "birth_year": data.get("birth_year", ""),
        "birthplace": data.get("birthplace", ""),
        "town_county": data.get("town_county", ""),
        "error": error,
    }
    submissions.append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(submissions, f, indent=2, ensure_ascii=False)


# ── Route ─────────────────────────────────────────────────────────────────────

@app.route("/api/report", methods=["POST", "OPTIONS"])
def api_report():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        data = request.get_json(force=True, silent=True) or {}

        # Validate required fields
        email = (data.get("email") or "").strip()
        ancestor_name = (data.get("ancestor_name") or "").strip()

        if not email:
            return jsonify({"error": "Email address is required."}), 400
        if not ancestor_name:
            return jsonify({"error": "Ancestor name is required."}), 400

        # Log to CRM before generating (captures every submission attempt)
        requester_name = (data.get("requester_name") or "").strip()
        crm_request_id = crm.log_report_request(email, requester_name, ancestor_name)

        # Generate report
        report_text = generate_report(data)

        # Send email
        send_email(email, ancestor_name, report_text)

        # Mark delivered in CRM
        crm.mark_report_delivered(crm_request_id)

        # Log success
        log_submission(data, success=True)

        return jsonify({"success": True, "message": "Report sent! Check your inbox within a few minutes."})

    except Exception as exc:
        err_msg = str(exc)
        traceback.print_exc()
        try:
            log_submission(data if "data" in dir() else {}, success=False, error=err_msg)
        except Exception:
            pass
        return jsonify({"error": f"Something went wrong: {err_msg}"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ancestor_report"})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("OpenGenealogyAI Ancestor Report API — http://localhost:8080")
    print(f"Logging to: {LOG_FILE}")
    app.run(host="0.0.0.0", port=8080, debug=False)
