"""
qwen_consult.py — Consult Qwen 3 (local Ollama) before major decisions.

Usage:
    python scripts/qwen_consult.py "Should we use SQLite or PostgreSQL for the MVP?"
    python scripts/qwen_consult.py --task ".2" "Review this schema design approach..."
    python scripts/qwen_consult.py --review "path/to/file.json"

Returns Qwen's analysis to stdout. Claude reads it and incorporates the feedback.
"""
import sys, json, urllib.request, urllib.error, argparse, textwrap
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:14b"

SYSTEM_PROMPT = """You are a senior software architect and genealogy domain expert consulting on
the OpenGenealogyAI project — an open-source, AI-native genealogy standard using probabilistic
relationships. Every relationship carries a confidence score (0.0-1.0). Multiple possible parents
are the norm. No fact is ever overwritten.

When reviewing decisions, schemas, or code:
1. Flag any design flaws or missing edge cases
2. Suggest specific improvements with rationale
3. Note any genealogy domain issues (privacy, date uncertainty, naming conventions)
4. Be direct and concise. No hedging.
5. If something looks good, say so briefly and move on.

Project context:
- Three JSON schemas: RawRecord, Person, TaskQueue
- Six agents: Orchestrator, Extractor, Validator, Critic, Judge, Integrator
- Judge-agent is the sole gatekeeper before any DB writes
- Free tier: browse public trees. Paid tier ($9/mo): agents auto-build your tree in 30 min
- Stack: SQLite + Qdrant, Internet Archive (Tier-1), FamilySearch OAuth (Tier-2, private only)"""

def consult(question: str, context: str = "") -> str:
    prompt = question
    if context:
        prompt = f"Context:\n{context}\n\nQuestion: {question}"

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 1024}
    }).encode()

    try:
        req = urllib.request.Request(OLLAMA_URL, data=payload,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except Exception as e:
        return f"[Qwen consultation failed: {e}]"

def main():
    parser = argparse.ArgumentParser(description="Consult Qwen 3 on OpenGenealogyAI decisions")
    parser.add_argument("question", nargs="+", help="Question or decision to review")
    parser.add_argument("--review", help="Path to a file to review")
    parser.add_argument("--task", help="Task ID for context (e.g. .2)")
    args = parser.parse_args()

    question = " ".join(args.question)
    context = ""

    if args.review:
        path = Path(args.review)
        if path.exists():
            context = f"File: {path.name}\n\n{path.read_text(encoding='utf-8', errors='replace')[:4000]}"

    print(f"\n=== Qwen 3 Consultation ===")
    print(f"Q: {question[:120]}{'...' if len(question)>120 else ''}")
    if args.task:
        print(f"Task: {args.task}")
    print("=" * 40)

    response = consult(question, context)
    print(response)
    print("=" * 40 + "\n")
    return response

if __name__ == "__main__":
    main()
