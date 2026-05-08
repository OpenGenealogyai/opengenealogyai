"""
Three-Model Council — consensus decision-making for the pipeline.

Called when the pipeline faces genuine ambiguity:
  - Quality threshold calls
  - Source prioritization when resources contend
  - Recovery decisions
  - LoRA run scheduling

Never called for routine operations. Target: < 10 calls/day.
"""

import json, time, datetime, os, re
from pathlib import Path
from typing import Any
import requests

from pipeline.paths import LOGS
from pipeline.api_guard import guarded_claude_call, is_paused, pause_reason

COUNCIL_LOG = LOGS / "council.jsonl"

# Council members (in priority order)
MODEL_A = {"id": "gemma3_12b",  "backend": "ollama", "name": "gemma3:12b"}
MODEL_B = {"id": "qwen25vl_7b", "backend": "ollama", "name": "qwen2.5vl:7b"}
MODEL_C = {"id": "claude_haiku","backend": "claude", "name": "claude-haiku-4-5-20251001"}
RESOLVER = {"id": "claude_sonnet", "backend": "claude", "name": "claude-sonnet-4-6"}

OLLAMA_URL = "http://localhost:11434"

COUNCIL_PROMPT_TEMPLATE = """\
You are a member of a three-model decision council for an autonomous genealogy data pipeline.
A decision is needed. Answer with ONLY a valid JSON object — no explanation.

Question: {question}

Options:
{options}

Context:
{context}

Return this JSON:
{{
  "decision": "<exact option key>",
  "confidence": <0.0-1.0>,
  "reason": "<one sentence>"
}}
"""


def _call_ollama(model_name: str, prompt: str, timeout: int = 30) -> dict | None:
    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": model_name, "prompt": prompt,
            "stream": False, "options": {"temperature": 0.1, "num_predict": 200}
        }, timeout=timeout)
        r.raise_for_status()
        text = r.json().get("response", "")
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"  [council] {model_name} failed: {e}")
    return None


def _call_claude(model_name: str, prompt: str) -> dict | None:
    if is_paused():
        print(f"  [council] {model_name} skipped — {pause_reason()}")
        return None
    try:
        result = guarded_claude_call(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        if result is None:
            return None
        text = result["text"]
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"  [council] {model_name} failed: {e}")
    return None


def _ask_model(model_cfg: dict, prompt: str) -> dict | None:
    if model_cfg["backend"] == "ollama":
        return _call_ollama(model_cfg["name"], prompt)
    return _call_claude(model_cfg["name"], prompt)


def _log(entry: dict):
    COUNCIL_LOG.parent.mkdir(exist_ok=True)
    with open(COUNCIL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def vote(question: str, options: dict[str, str], context: str = "") -> tuple[str, float, list]:
    """
    Ask the three-model council a question.

    Returns (decision_key, confidence, votes_list).

    Recovery mode: if Claude API is paused, automatically drops to local-only
    voting (MODEL_A + MODEL_B). Requires unanimous agreement; if they split,
    MODEL_A wins by seniority. Claude is never called while paused.
    """
    options_text = "\n".join(f"  {k}: {v}" for k, v in options.items())
    prompt = COUNCIL_PROMPT_TEMPLATE.format(
        question=question, options=options_text, context=context or "No additional context."
    )

    api_paused = is_paused()
    if api_paused:
        members = [MODEL_A, MODEL_B]       # local-only — no Claude
        print(f"\n[COUNCIL] LOCAL-ONLY MODE — {pause_reason()}")
        print(f"[COUNCIL] Question: {question[:80]}")
    else:
        members = [MODEL_A, MODEL_B, MODEL_C]
        print(f"\n[COUNCIL] Question: {question[:80]}")

    votes = []
    for m in members:
        result = _ask_model(m, prompt)
        vote_entry = {
            "model_id": m["id"],
            "decision": result.get("decision") if result else None,
            "confidence": result.get("confidence", 0) if result else 0,
            "reason": result.get("reason", "no response") if result else "model failed",
        }
        votes.append(vote_entry)
        print(f"  {m['id']}: {vote_entry['decision']} ({vote_entry['confidence']:.2f}) — {vote_entry['reason'][:60]}")

    # Tally
    tally: dict[str, list] = {}
    for v in votes:
        d = v["decision"]
        if d:
            tally.setdefault(d, []).append(v)

    # Majority threshold: 2/3 normal, unanimous (2/2) in local-only mode
    needed = 2
    winner = None
    winner_confidence = 0.0
    for decision, supporting in tally.items():
        if len(supporting) >= needed:
            winner = decision
            winner_confidence = sum(v["confidence"] for v in supporting) / len(supporting)
            break

    if not winner and api_paused:
        # Split between two local models — MODEL_A wins by seniority
        a_vote = next((v for v in votes if v["model_id"] == MODEL_A["id"] and v["decision"]), None)
        if a_vote:
            winner = a_vote["decision"]
            winner_confidence = a_vote["confidence"] * 0.6  # discount for no consensus
            print(f"  [COUNCIL] Local split — MODEL_A ({MODEL_A['id']}) decides: {winner}")
        else:
            winner = list(options.keys())[0]
            winner_confidence = 0.0
            print(f"  [COUNCIL] Both local models failed — defaulting to first option: {winner}")

    elif not winner:
        # Normal mode: no majority → call resolver
        print(f"  [COUNCIL] No majority — escalating to resolver ({RESOLVER['id']})")
        resolver_result = _ask_model(RESOLVER, prompt)
        if resolver_result:
            winner = resolver_result.get("decision")
            winner_confidence = resolver_result.get("confidence", 0.5)
            votes.append({
                "model_id": RESOLVER["id"], "decision": winner,
                "confidence": winner_confidence,
                "reason": resolver_result.get("reason", ""),
            })

    if not winner and options:
        winner = list(options.keys())[0]
        winner_confidence = 0.0
        print(f"  [COUNCIL] All models failed — defaulting to first option: {winner}")

    log_entry = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "question": question,
        "options": options,
        "context": context[:500] if context else "",
        "votes": votes,
        "decision": winner,
        "confidence": round(winner_confidence, 3),
    }
    _log(log_entry)
    print(f"  [COUNCIL] DECIDED: {winner} (confidence {winner_confidence:.2f})\n")
    return winner, winner_confidence, votes
