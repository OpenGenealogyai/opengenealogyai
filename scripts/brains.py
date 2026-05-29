"""
brains.py — Real three-brain / six-brain council infrastructure.

Loads API keys from C:\\Users\\stock\\Dropbox\\Claude Cowork\\.env and exposes
clean callables for Claude (Anthropic Sonnet 4.5), GPT (OpenAI), Gemini, and a
council orchestrator.

CLI usage:
    python scripts/brains.py verify              # health check on all three
    python scripts/brains.py council "<q>"       # ask the three-brain panel
    python scripts/brains.py six "<question>"    # six-brain (two passes)

Library usage:
    from brains import ask_claude, ask_gpt, ask_gemini, council, six_brain
"""

from __future__ import annotations
import os, sys, json, time, textwrap
from pathlib import Path
import urllib.request, urllib.error

# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------
_ENV_PATH = Path(r"C:\Users\stock\Dropbox\Claude Cowork\.env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            # OVERWRITE — Claude Code injects its own ANTHROPIC_API_KEY into the
            # env which is scoped to this client and won't authenticate against
            # the public Anthropic API. The .env value is what we want here.
            os.environ[_k.strip()] = _v.strip()

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY", "")
GEMINI_KEY    = os.environ.get("GEMINI_API_KEY", "")

# Default models — confirmed live 2026-05-17
CLAUDE_MODEL  = "claude-sonnet-4-5"
GPT_MODEL     = "gpt-4o"
GEMINI_MODEL  = "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------
def _post(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} from {url}: {body[:300]}")


# ---------------------------------------------------------------------------
# Per-provider callables
# ---------------------------------------------------------------------------
def ask_claude(prompt: str, system: str | None = None,
               model: str = CLAUDE_MODEL, max_tokens: int = 4096) -> str:
    msgs = [{"role": "user", "content": prompt}]
    body = {"model": model, "max_tokens": max_tokens, "messages": msgs}
    if system:
        body["system"] = system
    data = _post(
        "https://api.anthropic.com/v1/messages", body,
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    return data["content"][0]["text"]


def ask_gpt(prompt: str, system: str | None = None,
            model: str = GPT_MODEL, max_tokens: int = 4096) -> str:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    data = _post(
        "https://api.openai.com/v1/chat/completions",
        {"model": model, "messages": msgs, "max_tokens": max_tokens},
        headers={
            "Authorization": "Bearer " + OPENAI_KEY,
            "content-type": "application/json",
        },
    )
    return data["choices"][0]["message"]["content"]


def ask_gemini(prompt: str, system: str | None = None,
               model: str = GEMINI_MODEL, max_tokens: int = 4096) -> str:
    contents = [{"parts": [{"text": prompt}]}]
    # Gemini 2.5 spends some tokens on internal "thinking" — give it slack
    # so the visible response isn't starved when caller asks for small max.
    effective_max = max(max_tokens, 512)
    body = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": effective_max},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
    data = _post(url, body, headers={"content-type": "application/json"})
    # Gemini 2.5 uses thinking tokens; sometimes parts is absent if budget too small
    cand = data["candidates"][0]
    if "content" not in cand or "parts" not in cand["content"]:
        return f"[gemini returned no parts; finishReason={cand.get('finishReason')}]"
    return cand["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# Council orchestrators
# ---------------------------------------------------------------------------
_ENGINEER_SYS = (
    "You are Judge-GPT, the Engineer judge on a decision council. Score the "
    "options on PRAGMATIC EXECUTION: which is easiest to build right now with "
    "the fewest moving parts? Output a one-line verdict (PROCEED / PROCEED WITH "
    "CAUTION / DO NOT PROCEED), 2-3 sentences of reasoning, and pick the option "
    "letter you favor. Be concise."
)
_STRATEGIST_SYS = (
    "You are Judge-Gemini, the Strategist judge on a decision council. Score "
    "the options on LONG-TERM FIT: which has the lowest lock-in, best "
    "generalizes, leaves the most doors open? Output a one-line verdict "
    "(PROCEED / PROCEED WITH CAUTION / DO NOT PROCEED), 2-3 sentences of "
    "reasoning, and pick the option letter you favor. Be concise."
)
_OPERATOR_SYS = (
    "You are Judge-Opus, the Operator judge on a decision council. Score the "
    "options on BLAST RADIUS: which has the smallest downside if wrong, the "
    "easiest rollback, the safest defaults? Output a one-line verdict (PROCEED "
    "/ PROCEED WITH CAUTION / DO NOT PROCEED), 2-3 sentences of reasoning, and "
    "pick the option letter you favor. Be concise."
)
_DESIGNER_SYS = (
    "You are Judge-Designer, a senior UX/product designer on this council "
    "(20+ years building consumer software). Score the options on USER "
    "EXPERIENCE QUALITY: which produces the cleanest, most learnable, most "
    "trust-building interface for non-technical genealogists? Output a "
    "one-line verdict, 2-3 sentences of reasoning, and pick the option letter "
    "you favor. Be concise."
)


def council(question: str, options: str, designer: bool = False) -> dict:
    """Three-brain panel (optionally +designer = four-brain). One pass."""
    full = f"DECISION: {question}\n\nOPTIONS:\n{options}\n"
    out = {}
    # Gemini 2.5 Pro burns ~1000 tokens on internal "thinking" before output —
    # generous budget keeps visible reply from being truncated.
    out["engineer"]   = ask_gpt(full,    system=_ENGINEER_SYS,   max_tokens=600)
    out["strategist"] = ask_gemini(full, system=_STRATEGIST_SYS, max_tokens=2048)
    out["operator"]   = ask_claude(full, system=_OPERATOR_SYS,   max_tokens=600)
    if designer:
        out["designer"] = ask_gpt(full, system=_DESIGNER_SYS, max_tokens=600)
    return out


def six_brain(question: str, options: str, designer: bool = False) -> dict:
    """Two-pass adversarial. Pass 2 sees Pass 1 and must argue against own view."""
    pass1 = council(question, options, designer=designer)

    p1_summary = "\n\n".join(
        f"--- {name.upper()} (Pass 1) ---\n{text}"
        for name, text in pass1.items()
    )

    adversarial_template = (
        "PASS 2 — ADVERSARIAL.\n\n"
        "Below are the Pass-1 verdicts of all judges on this question:\n\n"
        f"{p1_summary}\n\n"
        "Now: argue AGAINST your own Pass-1 position. Look for the strongest "
        "case against your prior view, given the others' arguments. Then "
        "re-verdict with PROCEED / PROCEED WITH CAUTION / DO NOT PROCEED and "
        "your final option letter. If you change your mind, flag it explicitly. "
        "Be concise.\n\nORIGINAL DECISION:\n" + question + "\n\nOPTIONS:\n" + options
    )

    pass2 = {}
    pass2["engineer"]   = ask_gpt(adversarial_template,    system=_ENGINEER_SYS,   max_tokens=500)
    pass2["strategist"] = ask_gemini(adversarial_template, system=_STRATEGIST_SYS, max_tokens=500)
    pass2["operator"]   = ask_claude(adversarial_template, system=_OPERATOR_SYS,   max_tokens=500)
    if designer:
        pass2["designer"] = ask_gpt(adversarial_template, system=_DESIGNER_SYS, max_tokens=500)

    return {"pass1": pass1, "pass2": pass2}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _verify():
    print(f"{'Provider':12} {'Status':6} {'Latency':8} {'Model':30} Reply")
    print("-" * 90)
    for name, fn, model in [
        ("anthropic", ask_claude, CLAUDE_MODEL),
        ("openai",    ask_gpt,    GPT_MODEL),
        ("gemini",    ask_gemini, GEMINI_MODEL),
    ]:
        t = time.time()
        try:
            reply = fn("Reply with exactly the two characters: OK", max_tokens=128)
            ms = round(time.time() - t, 2)
            print(f"{name:12} {'OK':6} {str(ms)+'s':8} {model:30} {reply.strip()[:40]}")
        except Exception as e:
            print(f"{name:12} {'FAIL':6} {'-':8} {model:30} {str(e)[:80]}")


def _main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "verify":
        _verify()
    elif cmd in ("council", "six"):
        if len(sys.argv) < 3:
            print("Provide a question + options on stdin or as args.")
            return
        question = sys.argv[2]
        options = sys.stdin.read() if not sys.stdin.isatty() else "(no options provided)"
        fn = council if cmd == "council" else six_brain
        result = fn(question, options, designer=("--designer" in sys.argv))
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    _main()
