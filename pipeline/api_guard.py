"""
Claude API Rate-Limit Guard

Wraps every Anthropic API call. After each call it reads the rate-limit
headers and writes a pause flag when usage >= PAUSE_THRESHOLD (90%).
The flag includes the exact reset timestamp so callers know how long to wait.

Callers do:
    from pipeline.api_guard import guarded_claude_call, is_paused, pause_reason
    result = guarded_claude_call(model, messages, max_tokens)

The pause flag file is checked before every call. If paused, the call is
skipped and None is returned — the caller must handle None gracefully.

Local Ollama models are never paused.
"""

import json, os, datetime, time
from pathlib import Path

import anthropic
import requests as _requests

from pipeline.paths import LOGS

PAUSE_FLAG      = LOGS / "PAUSE_CLAUDE_API"
GUARD_LOG       = LOGS / "api_guard.jsonl"
COST_LOG        = LOGS / "cost_tracking.jsonl"
PAUSE_THRESHOLD = 0.90   # pause when 90% of window tokens used

SLACK_TOKEN   = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = "#pipeline-status"
SLACK_URL     = "https://slack.com/api/chat.postMessage"


def _slack(msg: str):
    if not SLACK_TOKEN:
        print(f"[API GUARD SLACK] {msg}")
        return
    try:
        _requests.post(SLACK_URL, headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        }, json={"channel": SLACK_CHANNEL, "text": msg}, timeout=10)
    except Exception:
        pass

# Approximate token costs (USD per 1K tokens, input/output blended)
COST_PER_1K = {
    "claude-haiku-4-5-20251001": 0.001,   # ~$0.80/M input, $4/M output — blended
    "claude-sonnet-4-6":         0.009,   # ~$3/M input, $15/M output — blended
    "claude-opus-4-7":           0.045,   # ~$15/M input, $75/M output — blended
}
DAILY_LIMIT_USD   = float(os.environ.get("CLAUDE_DAILY_LIMIT_USD",  "5.00"))
MONTHLY_LIMIT_USD = float(os.environ.get("CLAUDE_MONTHLY_LIMIT_USD","100.00"))


# ── Pause flag helpers ─────────────────────────────────────────────────────────

def is_paused() -> bool:
    """Return True if the Claude API pause flag is active and not yet expired."""
    if not PAUSE_FLAG.exists():
        return False
    try:
        data = json.loads(PAUSE_FLAG.read_text())
        reset_str = data.get("reset_at")
        if not reset_str:
            return True
        reset_dt = datetime.datetime.fromisoformat(reset_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        if now >= reset_dt:
            PAUSE_FLAG.unlink(missing_ok=True)
            _log_guard("auto_resume", {"reset_at": reset_str})
            print(f"[API GUARD] Rate-limit window reset — resuming Claude API calls")
            _slack(":white_check_mark: *Claude API resumed* — rate-limit window reset. "
                   "Council back to 3-model mode.")
            return False
        return True
    except Exception:
        return PAUSE_FLAG.exists()


def pause_reason() -> str:
    """Human-readable explanation of why calls are paused."""
    if not PAUSE_FLAG.exists():
        return ""
    try:
        data = json.loads(PAUSE_FLAG.read_text())
        used_pct = data.get("tokens_used_pct", 0)
        reset_at = data.get("reset_at", "unknown")
        return f"{used_pct:.0f}% of token window used — paused until {reset_at}"
    except Exception:
        return "API pause flag set (unknown reason)"


def _set_pause(tokens_used_pct: float, tokens_remaining: int,
               tokens_limit: int, reset_at: str):
    PAUSE_FLAG.parent.mkdir(exist_ok=True)
    PAUSE_FLAG.write_text(json.dumps({
        "set_at":           datetime.datetime.utcnow().isoformat() + "Z",
        "tokens_used_pct":  round(tokens_used_pct * 100, 1),
        "tokens_remaining": tokens_remaining,
        "tokens_limit":     tokens_limit,
        "reset_at":         reset_at,
    }))
    print(f"[API GUARD] PAUSED — {tokens_used_pct*100:.0f}% of Claude token window used. "
          f"Resumes at {reset_at}")
    _slack(
        f":hourglass_flowing_sand: *Claude API paused* — "
        f"{tokens_used_pct*100:.0f}% of token window used.\n"
        f"Resumes automatically at `{reset_at}`\n"
        f"Pipeline continues: scrapers, embedding, Qdrant unaffected.\n"
        f"Council switching to local-only mode (gemma3 + qwen2.5)."
    )


def _clear_pause():
    PAUSE_FLAG.unlink(missing_ok=True)


# ── Logging ────────────────────────────────────────────────────────────────────

def _log_guard(event: str, extra: dict = None):
    GUARD_LOG.parent.mkdir(exist_ok=True)
    entry = {"ts": datetime.datetime.utcnow().isoformat() + "Z", "event": event}
    if extra:
        entry.update(extra)
    with open(GUARD_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _log_cost(model: str, input_tokens: int, output_tokens: int):
    total_tokens = input_tokens + output_tokens
    cost_usd = (total_tokens / 1000) * COST_PER_1K.get(model, 0.009)
    COST_LOG.parent.mkdir(exist_ok=True)
    with open(COST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts":           datetime.datetime.utcnow().isoformat() + "Z",
            "model":        model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd":     round(cost_usd, 6),
        }) + "\n")
    return cost_usd


# ── Header parsing ─────────────────────────────────────────────────────────────

def _parse_rate_limit_headers(headers) -> dict:
    """Extract rate-limit info from Anthropic response headers."""
    def _int(key):
        try:
            return int(headers.get(key, 0))
        except (ValueError, TypeError):
            return 0

    def _str(key):
        return headers.get(key, "") or ""

    return {
        "tokens_limit":     _int("anthropic-ratelimit-tokens-limit"),
        "tokens_remaining": _int("anthropic-ratelimit-tokens-remaining"),
        "tokens_reset":     _str("anthropic-ratelimit-tokens-reset"),
        "requests_limit":   _int("anthropic-ratelimit-requests-limit"),
        "requests_remaining": _int("anthropic-ratelimit-requests-remaining"),
        "requests_reset":   _str("anthropic-ratelimit-requests-reset"),
        "retry_after":      _str("retry-after"),
    }


# ── Daily / monthly cost check ─────────────────────────────────────────────────

def _daily_spend_usd() -> float:
    """Sum today's costs from cost_tracking.jsonl."""
    if not COST_LOG.exists():
        return 0.0
    today = datetime.date.today().isoformat()
    total = 0.0
    try:
        for line in COST_LOG.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("ts", "").startswith(today):
                total += entry.get("cost_usd", 0.0)
    except Exception:
        pass
    return total


# ── Main call wrapper ──────────────────────────────────────────────────────────

def guarded_claude_call(
    model: str,
    messages: list[dict],
    max_tokens: int = 200,
    system: str | None = None,
) -> dict | None:
    """
    Make a Claude API call with rate-limit and cost guards.

    Returns the parsed JSON response dict, or None if:
      - API is currently paused (rate limit / cost limit hit)
      - API call fails

    Usage:
        result = guarded_claude_call("claude-haiku-4-5-20251001", messages)
        if result is None:
            # use local fallback
    """
    # Pre-call guards
    if is_paused():
        print(f"[API GUARD] Skipping Claude call — {pause_reason()}")
        return None

    daily_spend = _daily_spend_usd()
    if daily_spend >= DAILY_LIMIT_USD:
        tomorrow = (datetime.datetime.utcnow().replace(hour=0, minute=0, second=0)
                    + datetime.timedelta(days=1)).isoformat() + "Z"
        _set_pause(1.0, 0, 0, tomorrow)
        _log_guard("cost_limit_hit", {"daily_spend": daily_spend, "limit": DAILY_LIMIT_USD})
        print(f"[API GUARD] PAUSED — daily cost limit hit (${daily_spend:.2f} / ${DAILY_LIMIT_USD})")
        _slack(
            f":money_with_wings: *Claude API daily cost limit hit* — "
            f"${daily_spend:.2f} spent today (limit ${DAILY_LIMIT_USD}).\n"
            f"Claude paused until midnight UTC. Pipeline continues on local models."
        )
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[API GUARD] No ANTHROPIC_API_KEY — skipping Claude call")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
    if system:
        kwargs["system"] = system

    try:
        # Use with_raw_response to get headers
        raw = client.messages.with_raw_response.create(**kwargs)
        response = raw.parse()
        headers  = raw.headers

        # Parse rate-limit headers
        rl = _parse_rate_limit_headers(headers)
        tokens_limit     = rl["tokens_limit"]
        tokens_remaining = rl["tokens_remaining"]
        tokens_reset     = rl["tokens_reset"]

        # Log usage + cost
        in_tok  = response.usage.input_tokens  if response.usage else 0
        out_tok = response.usage.output_tokens if response.usage else 0
        _log_cost(model, in_tok, out_tok)

        # Evaluate usage fraction
        if tokens_limit > 0:
            used_frac = 1.0 - (tokens_remaining / tokens_limit)
            _log_guard("api_call_ok", {
                "model":            model,
                "tokens_remaining": tokens_remaining,
                "tokens_limit":     tokens_limit,
                "used_pct":         round(used_frac * 100, 1),
                "reset_at":         tokens_reset,
                "in_tokens":        in_tok,
                "out_tokens":       out_tok,
            })

            if used_frac >= PAUSE_THRESHOLD:
                _set_pause(used_frac, tokens_remaining, tokens_limit, tokens_reset)
        else:
            _log_guard("api_call_ok", {"model": model, "in_tokens": in_tok, "out_tokens": out_tok})

        # Return text as dict (caller parses JSON from it)
        text = response.content[0].text if response.content else ""
        return {"text": text, "model": model, "in_tokens": in_tok, "out_tokens": out_tok}

    except anthropic.RateLimitError as e:
        # 429 — extract retry-after if available
        retry_after = getattr(e, "retry_after", None) or 3600
        reset_at = (datetime.datetime.utcnow() + datetime.timedelta(seconds=int(retry_after))).isoformat() + "Z"
        _set_pause(1.0, 0, 0, reset_at)
        _log_guard("rate_limit_error", {"retry_after": retry_after, "error": str(e)})
        print(f"[API GUARD] 429 Rate limit hit — pausing for {retry_after}s")
        return None

    except Exception as e:
        _log_guard("api_call_error", {"model": model, "error": str(e)})
        print(f"[API GUARD] Claude call failed: {e}")
        return None


# ── Status report ──────────────────────────────────────────────────────────────

def status_report() -> dict:
    """Return current API guard status — used by checker and reporter."""
    paused = is_paused()
    daily  = _daily_spend_usd()

    result = {
        "claude_paused":     paused,
        "pause_reason":      pause_reason() if paused else "",
        "daily_spend_usd":   round(daily, 4),
        "daily_limit_usd":   DAILY_LIMIT_USD,
        "daily_pct":         round(daily / DAILY_LIMIT_USD * 100, 1) if DAILY_LIMIT_USD else 0,
    }

    # Last guard log entry for token window info
    if GUARD_LOG.exists():
        try:
            lines = GUARD_LOG.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                entry = json.loads(line)
                if entry.get("event") == "api_call_ok" and "tokens_limit" in entry:
                    result["tokens_limit"]     = entry["tokens_limit"]
                    result["tokens_remaining"] = entry["tokens_remaining"]
                    result["window_used_pct"]  = entry.get("used_pct", 0)
                    result["window_reset_at"]  = entry.get("reset_at", "")
                    break
        except Exception:
            pass

    return result


# ── CLI test ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Claude API Guard — Status ===")
    s = status_report()
    print(f"  Paused:          {s['claude_paused']}")
    if s["claude_paused"]:
        print(f"  Reason:          {s['pause_reason']}")
    print(f"  Daily spend:     ${s['daily_spend_usd']:.4f} / ${s['daily_limit_usd']:.2f}  ({s['daily_pct']:.1f}%)")
    if "window_used_pct" in s:
        print(f"  Token window:    {s['window_used_pct']:.1f}% used  ({s.get('tokens_remaining',0):,} remaining)")
        print(f"  Window resets:   {s.get('window_reset_at','unknown')}")

    print()
    print("Running live test call (requires ANTHROPIC_API_KEY)...")
    result = guarded_claude_call(
        model="claude-haiku-4-5-20251001",
        messages=[{"role": "user", "content": "Reply with exactly: {\"status\": \"ok\"}"}],
        max_tokens=20,
    )
    if result:
        print(f"  Response: {result['text']}")
        print(f"  Tokens:   {result['in_tokens']} in / {result['out_tokens']} out")
        s2 = status_report()
        print(f"\n  After call — window used: {s2.get('window_used_pct','?')}%  remaining: {s2.get('tokens_remaining','?'):,}")
    else:
        print("  Call returned None (paused or no key)")
