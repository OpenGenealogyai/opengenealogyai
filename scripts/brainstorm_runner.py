"""
OpenGenealogyAI Multi-Model Brainstorm Runner
Queries Claude (Anthropic SDK) + GPT-4o (OpenAI SDK) with 5 hard strategic questions.
Appends results to docs/BRAINSTORM_SYNTHESIS.md and docs/brainstorm-raw.json.
"""
import os
import sys
import json
import datetime

# ── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = r"C:\Users\stock\dev\opengenealogyai"
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
SYNTHESIS_PATH = os.path.join(PROJECT_ROOT, "docs", "BRAINSTORM_SYNTHESIS.md")
RAW_PATH = os.path.join(PROJECT_ROOT, "docs", "brainstorm-raw.json")

TODAY = datetime.date.today().isoformat()  # 2026-05-07

# ── Load .env ────────────────────────────────────────────────────────────────
env_keys = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env_keys[k.strip()] = v.strip()

def get_key(name):
    """Check .env first, then os.environ."""
    return env_keys.get(name) or os.environ.get(name, "")

ANTHROPIC_KEY = get_key("ANTHROPIC_API_KEY")
OPENAI_KEY = get_key("OPENAI_API_KEY")

# ── Context injected into every question ─────────────────────────────────────
SYSTEM_CONTEXT = """You are a strategic advisor for OpenGenealogyAI, an open-source AI-native genealogy platform.

Core facts:
- Probabilistic genealogy: every relationship, date, and name carries a confidence score (0.0–1.0)
- Multiple possible parents are the norm — no fact is ever overwritten, new evidence creates new assertions
- 50M records being embedded into Qdrant vector DB over 60 days on local GPU hardware
- Business model: freemium. Free tier = browse public probabilistic family trees. Paid tier = agent labor (auto-tree building, research actions)
- Pricing under consideration: $0.12 per Research Action (pay-as-you-go) OR bundles (100 actions/$9, 500 actions/$35, 1000 actions/$60) OR flat $9/mo
- Nine growth ideas ranked by prior brainstorm: DNA+AI Matching (#1), Adopt a Collection (#2), One-Click Publish (#3), AI Ghostwriter (#4), Living Memory (#5), Global Translation, Corporate Heritage, School Curriculum, AI Debate Mode
- Tech stack: Qdrant, SQLite staging, Ollama (local GPU), spaCy NER, LoRA fine-tuning, three-model council for quality decisions
- Data sources: Wikidata, Chronicling America, Internet Archive, BLM Land Patents, Trove (Australia)
- Differentiator: confidence-first, immutable assertion log, open standard, append-only (no edit wars)
- Target users: genealogy researchers first, then casual hobbyists

Answer with strategic depth. Be direct and opinionated. Avoid vague generalities."""

QUESTIONS = [
    "What's the biggest risk to OpenGenealogyAI's business model in year 1? Be specific about what could kill the project before it gains traction.",
    "Which of the 9 growth ideas (AI Ghostwriter, One-Click Publish, Living Memory, DNA+AI Matching, Adopt a Collection, Global Translation, Corporate Heritage, School Curriculum, AI Debate Mode) should be built first and why? Give a concrete build sequence for the first 6 months.",
    "How should OpenGenealogyAI price its services differently to maximize adoption among genealogy hobbyists vs serious researchers? Are the current pricing options ($0.12/action, bundles, or $9/mo flat) well-suited to both segments?",
    "What's the fastest path to 1,000 paying users from zero? What specific channels, partnerships, or tactics would work for this niche?",
    "What technical architecture decisions made now will be hardest to undo later? Which of the current choices (Qdrant, confidence scores on every assertion, append-only log, local GPU pipeline, SQLite staging) creates the most lock-in risk?"
]

# ── Claude (Anthropic SDK) ───────────────────────────────────────────────────
def query_claude(question):
    try:
        import anthropic
    except ImportError:
        return "[SKIP: anthropic package not installed — run: pip install anthropic]"

    if not ANTHROPIC_KEY:
        return "[SKIP: ANTHROPIC_API_KEY not found in .env or environment]"

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=SYSTEM_CONTEXT,
            messages=[{"role": "user", "content": question}]
        )
        # Extract text blocks only (skip thinking blocks)
        text_parts = [
            block.text for block in response.content
            if hasattr(block, "text")
        ]
        return "\n\n".join(text_parts).strip()
    except Exception as e:
        return f"[ERROR: {e}]"


# ── GPT-4o (OpenAI SDK) ──────────────────────────────────────────────────────
def query_openai(question):
    try:
        from openai import OpenAI
    except ImportError:
        return "[SKIP: openai package not installed — run: pip install openai]"

    if not OPENAI_KEY:
        return "[SKIP: OPENAI_API_KEY not found in .env or environment]"

    try:
        client = OpenAI(api_key=OPENAI_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_CONTEXT},
                {"role": "user", "content": question}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR: {e}]"


# ── Run all questions ────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"OpenGenealogyAI Brainstorm Runner — {TODAY}")
print(f"{'='*60}")
print(f"Claude (claude-opus-4-7): {'ENABLED' if ANTHROPIC_KEY else 'DISABLED (no key)'}")
print(f"GPT-4o: {'ENABLED' if OPENAI_KEY else 'DISABLED (no key)'}")
print()

results = []

for i, question in enumerate(QUESTIONS, 1):
    print(f"[Q{i}/5] {question[:80]}...")

    print(f"  >> Querying Claude...", end="", flush=True)
    claude_answer = query_claude(question)
    status = "OK" if not claude_answer.startswith("[") else claude_answer[:50]
    print(f" {status}")

    print(f"  >> Querying GPT-4o...", end="", flush=True)
    gpt_answer = query_openai(question)
    status = "OK" if not gpt_answer.startswith("[") else gpt_answer[:50]
    print(f" {status}")

    results.append({
        "date": TODAY,
        "question_index": i,
        "question": question,
        "claude_opus_4_7": claude_answer,
        "gpt4o": gpt_answer
    })
    print()

print("All questions answered. Writing outputs...\n")

# ── Append to brainstorm-raw.json ────────────────────────────────────────────
existing_raw = []
if os.path.exists(RAW_PATH):
    try:
        with open(RAW_PATH, encoding="utf-8") as f:
            existing_raw = json.load(f)
        if not isinstance(existing_raw, list):
            existing_raw = [existing_raw]
        print(f"  Loaded {len(existing_raw)} existing entries from brainstorm-raw.json")
    except Exception as e:
        print(f"  Warning: could not parse existing raw JSON ({e}), starting fresh list")
        existing_raw = []

existing_raw.extend(results)
with open(RAW_PATH, "w", encoding="utf-8") as f:
    json.dump(existing_raw, f, indent=2, ensure_ascii=False)
print(f"  Saved {len(existing_raw)} total entries -> {RAW_PATH}")

# ── Build synthesis section ───────────────────────────────────────────────────
def extract_agreements(claude_text, gpt_text):
    """Return a placeholder — actual synthesis is written below per question."""
    return ""

section_parts = [f"\n\n---\n\n## Session: {TODAY} — Strategic Deep Dive\n"]
section_parts.append(f"**Models:** Claude Opus 4.7 (adaptive thinking) + GPT-4o  \n")
section_parts.append(f"**Questions:** 5 hard business/architecture questions\n")

for r in results:
    q_num = r["question_index"]
    question = r["question"]
    claude_ans = r["claude_opus_4_7"]
    gpt_ans = r["gpt4o"]

    section_parts.append(f"\n### Q{q_num}: {question}\n")

    section_parts.append(f"**Claude Opus 4.7:**\n\n{claude_ans}\n")
    section_parts.append(f"\n**GPT-4o:**\n\n{gpt_ans}\n")

    # Key agreements heuristic: both skipped -- note that
    claude_skipped = claude_ans.startswith("[SKIP") or claude_ans.startswith("[ERROR")
    gpt_skipped = gpt_ans.startswith("[SKIP") or gpt_ans.startswith("[ERROR")

    if claude_skipped and gpt_skipped:
        section_parts.append(f"\n**Status:** Both models unavailable for this session.\n")
    elif claude_skipped:
        section_parts.append(f"\n**Note:** Claude unavailable — GPT-4o answer only.\n")
    elif gpt_skipped:
        section_parts.append(f"\n**Note:** GPT-4o unavailable — Claude answer only.\n")
    else:
        section_parts.append(f"\n**Key agreements / disagreements:** *(review manually — both models answered)*\n")

section_parts.append(f"\n---\n*End of {TODAY} session*\n")

new_section = "".join(section_parts)

# ── Append to BRAINSTORM_SYNTHESIS.md ───────────────────────────────────────
if os.path.exists(SYNTHESIS_PATH):
    with open(SYNTHESIS_PATH, "r", encoding="utf-8") as f:
        existing_synthesis = f.read()
    print(f"  Appending to existing BRAINSTORM_SYNTHESIS.md ({len(existing_synthesis)} chars)")
    with open(SYNTHESIS_PATH, "a", encoding="utf-8") as f:
        f.write(new_section)
else:
    header = f"# OpenGenealogyAI — Multi-Model Brainstorm Synthesis\n\n**Created:** {TODAY}\n"
    with open(SYNTHESIS_PATH, "w", encoding="utf-8") as f:
        f.write(header + new_section)
    print(f"  Created new BRAINSTORM_SYNTHESIS.md")

print(f"  Synthesis appended -> {SYNTHESIS_PATH}")
print(f"\nDone! Brainstorm complete for {TODAY}.")
