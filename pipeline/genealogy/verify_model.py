"""
Verity — Model-layer hallucination check (contextual, judgment-based).

Takes a fact and source text. Asks a local Ollama model whether the fact is
contextually correct in the source — catches things the Python layer can't:
- Wrong attribution ("1901 belongs to Horace, not James")
- Logical impossibility ("father died 1876, son born 1880")
- Date format ambiguity ("11/3/1869" — could be Nov 3 or Mar 11)
- Same-name disambiguation
- Cross-document contradiction (when comparing multiple sources)
- Genealogy-specific anachronisms ("Utah" pre-1896 was a Territory, not a state)

Uses local Ollama via HTTP (default qwen2.5:72b — different model family from
whatever extracted the fact, to avoid same-model echo chamber).

Honors the gpu dial in pipeline-monitor's throttle (since Ollama uses GPU).
At gpu=0, falls back to FAIL with reason "GPU paused; cannot verify."
"""

from __future__ import annotations
import json
import sys
from dataclasses import dataclass

import requests

# Reconfigure stdout to UTF-8 — Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pipeline.bulk.throttle import gpu_level

OLLAMA_URL = "http://localhost:11434/api/generate"
# mistral-small:24b — different family from likely-extractor (qwen2.5), fits 16GB VRAM,
# large enough for genealogy reasoning. Falls back gracefully if model isn't installed.
DEFAULT_MODEL = "mistral-small:24b-instruct-2501-q4_K_M"
TIMEOUT_S = 180  # 24b model first-request can take 30-120s for GPU load + first inference

PROMPT_TEMPLATE = """You are Verity, a hallucination-checker for a genealogy researcher.
You receive a single FACT extracted by another agent, plus the SOURCE TEXT it was supposedly extracted from.
Your job: decide whether the fact is correctly attributed to the right person and dates in the source.

Look for these failure modes:
1. Wrong attribution — did the agent confuse two people in the source?
2. Logical impossibility — do the dates make biological sense?
3. Date format ambiguity — is "11/3" Nov 3 or Mar 11?
4. Disambiguation — does the source mention multiple people with this name?
5. Missed context — did the agent miss "first marriage" / "adopted" / etc?
6. Anachronism — does the place/time make sense (e.g., "Utah" pre-1896 was a Territory)?

FACT:
{fact_json}

SOURCE TEXT (truncated to 4000 chars):
---
{source_text}
---

Respond ONLY in this exact JSON format (no commentary):
{{
  "verdict": "PASS" or "PARTIAL" or "FAIL",
  "reason": "one sentence",
  "issue_type": "wrong_attribution" or "impossible_dates" or "ambiguous_date" or "wrong_person_same_name" or "missed_context" or "anachronism" or "none"
}}
"""


@dataclass
class ModelVerdict:
    kind: str        # "PASS" | "PARTIAL" | "FAIL"
    reason: str
    issue_type: str
    raw_response: str = ""
    error: str = ""


def verify_fact_model(fact: dict, source_text: str, model: str = DEFAULT_MODEL) -> ModelVerdict:
    """Run the contextual check via Ollama. Honors the gpu throttle dial."""
    if gpu_level() == 0:
        return ModelVerdict("FAIL", "GPU dial is paused; model verification skipped.",
                             "throttled", error="gpu=0")

    src = (source_text or "")[:4000]
    prompt = PROMPT_TEMPLATE.format(
        fact_json=json.dumps(fact, ensure_ascii=False, indent=2),
        source_text=src,
    )

    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0, "num_ctx": 8192}},
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
        body = r.json()
        raw = body.get("response", "").strip()
    except Exception as e:
        return ModelVerdict("FAIL",
                             f"Ollama call failed; defaulting to FAIL: {e}",
                             "ollama_error", error=str(e))

    # Try to parse JSON from the response
    parsed = _extract_json(raw)
    if parsed is None:
        return ModelVerdict("FAIL",
                             "Could not parse model response as JSON; defaulting to FAIL.",
                             "parse_error", raw_response=raw)

    verdict = parsed.get("verdict", "FAIL").upper()
    if verdict not in ("PASS", "PARTIAL", "FAIL"):
        verdict = "FAIL"
    return ModelVerdict(
        kind=verdict,
        reason=parsed.get("reason", ""),
        issue_type=parsed.get("issue_type", "none"),
        raw_response=raw,
    )


def _extract_json(text: str) -> dict | None:
    """Pull a JSON object out of a string that might have surrounding noise."""
    if not text:
        return None
    # Try whole string first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find first { and last } and try
    start = text.find("{")
    end   = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None
