"""Query Grok and GPT-4 with brainstorm questions and save synthesis."""
import os, sys, json, urllib.request, urllib.error

env_path = r"C:\Users\stock\dev\opengenealogyai\.env"
keys = {}
with open(env_path) as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, _, v = line.strip().partition("=")
            keys[k] = v

OPENAI_KEY = keys.get("OPENAI_API_KEY", "")
GROK_KEY = keys.get("GROK_API_KEY", "")

QUESTIONS = [
    "How can OpenGenealogyAI balance free-tier accessibility (public tree browsing) with paid-tier monetization ($9/month auto-tree building for 3+ ancestral generations in 30 minutes) without alienating open-source principles?",
    "What are the 5 biggest technical risks when building a probabilistic genealogy system where multiple possible parents coexist with confidence scores, and no fact is ever overwritten?",
    "How should OpenGenealogyAI differentiate itself from Ancestry.com and FamilySearch, given that those platforms force a single 'correct' answer while OpenGenealogyAI embraces uncertainty?",
    "What are the best growth strategies for an open-source AI genealogy platform? Which of these 9 ideas would you prioritize: AI Ghostwriter, One-Click Publish, Living Memory (voice stories), DNA+AI Matching, Adopt a Collection, Global Translation, Corporate Heritage, School Curriculum, AI Debate Mode?",
    "What could go wrong with an agent-driven genealogy system that builds family trees autonomously from Internet Archive records? What safeguards should be in place to prevent misinformation?",
]

CONTEXT = """OpenGenealogyAI is an open-source, AI-native genealogy standard. Core differentiator: probabilistic genealogy. Every relationship, date, and name carries a confidence score (0.0-1.0). Multiple possible parents are the norm. No fact is ever overwritten - new evidence creates new assertions.

Tech: JSON schemas, Qdrant vector DB, SQLite staging, Internet Archive for public records. Six coordinating agents (Orchestrator, Extractor, Validator, Critic, Judge, Integrator). Free tier: browse public probabilistic family trees. Paid tier ($9/mo): provide name + birth year and within 30 minutes agents auto-build 3+ ancestral generations using only public-domain sources."""

def query_openai(question):
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": CONTEXT},
            {"role": "user", "content": question}
        ],
        "max_tokens": 600,
        "temperature": 0.7
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

def query_grok(question):
    payload = json.dumps({
        "model": "grok-3-latest",
        "messages": [
            {"role": "system", "content": CONTEXT},
            {"role": "user", "content": question}
        ],
        "max_tokens": 600,
        "temperature": 0.7
    }).encode()
    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

results = []
for i, q in enumerate(QUESTIONS):
    print(f"\n=== Question {i+1} ===")
    print(q[:100] + "...")
    
    gpt_answer = ""
    grok_answer = ""
    
    try:
        gpt_answer = query_openai(q)
        print(f"  GPT-4o: OK ({len(gpt_answer)} chars)")
    except Exception as e:
        gpt_answer = f"[ERROR: {e}]"
        print(f"  GPT-4o: FAILED - {e}")
    
    try:
        grok_answer = query_grok(q)
        print(f"  Grok: OK ({len(grok_answer)} chars)")
    except Exception as e:
        grok_answer = f"[ERROR: {e}]"
        print(f"  Grok: FAILED - {e}")
    
    results.append({"question": q, "gpt4o": gpt_answer, "grok": grok_answer})

# Save raw results
out_path = r"C:\Users\stock\dev\opengenealogyai\docs\brainstorm-raw.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nRaw results saved to {out_path}")
