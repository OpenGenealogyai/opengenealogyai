"""
Daily cost report for OpenGenealogyAI agents.
Reads queue/done/ and queue/dead/ for today tasks, sums by agent type,
checks $50/day cap, posts to Slack.
"""
import json, sys, datetime, os, urllib.request
from pathlib import Path

QUEUE_ROOT = Path(__file__).parent.parent / "queue"
ENV_PATH = Path(__file__).parent.parent / ".env"

def load_env():
    env = {}
    try:
        with open(ENV_PATH) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.strip().partition("=")
                    env[k.strip()] = v.strip()
    except Exception:
        pass
    return env

def get_slack_token():
    return load_env().get("SLACK_BOT_TOKEN", "")

def post_slack(message: str, token: str):
    if not token:
        print("[Slack] No token -- printing to stdout only")
        print(message)
        return
    payload = json.dumps({"channel": "#opengenealogyai-cost", "text": message}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if not result.get("ok"):
                print(f"[Slack] Error: {result.get('error')}")
    except Exception as e:
        print(f"[Slack] Failed: {e}")

def collect_costs(target_date: str) -> dict:
    totals = {
        "haiku": 0.0,
        "sonnet": 0.0,
        "opus": 0.0,
        "unknown": 0.0,
        "tasks_done": 0,
        "tasks_failed": 0,
    }

    for subdir in ["done", "dead", "failed"]:
        for f in (QUEUE_ROOT / subdir).glob("*.json"):
            try:
                task = json.loads(f.read_text(encoding="utf-8"))
                completed = task.get("completed_at", task.get("created_at", ""))
                if not completed.startswith(target_date):
                    continue
                cost = task.get("cost_usd", 0.0)
                assigned = task.get("assigned_to", "")
                status = task.get("status", "")

                if "haiku" in assigned:
                    totals["haiku"] += cost
                elif "sonnet" in assigned or "orchestrator" in assigned or "judge" in assigned:
                    totals["sonnet"] += cost
                elif "opus" in assigned:
                    totals["opus"] += cost
                else:
                    totals["unknown"] += cost

                if status == "done":
                    totals["tasks_done"] += 1
                else:
                    totals["tasks_failed"] += 1
            except Exception:
                continue

    return totals

def format_report(date: str, costs: dict, total: float) -> str:
    cap_pct = (total / 50.0) * 100
    if total >= 50.0:
        status = "[OVER CAP]"
    elif total >= 40.0:
        status = "[WARNING]"
    else:
        status = "[OK]"
    lines = [
        f"*OpenGenealogyAI Daily Cost Report -- {date}*",
        f"{status} Total: ${total:.4f} / $50.00 ({cap_pct:.1f}% of cap)",
        f"  Haiku workers: ${costs['haiku']:.4f}",
        f"  Sonnet (orchestrator/judge/validator): ${costs['sonnet']:.4f}",
        f"  Opus escalations: ${costs['opus']:.4f}",
        f"  Tasks completed: {costs['tasks_done']} | Failed: {costs['tasks_failed']}",
    ]
    if costs['unknown'] > 0:
        lines.append(f"  WARNING Unknown agent costs: ${costs['unknown']:.4f}")
    if total >= 50.0:
        lines.append("ALERT: DAILY CAP EXCEEDED -- STOPPING ALL AGENT TASKS")
    return "\n".join(lines)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    parser.add_argument("--no-slack", action="store_true")
    args = parser.parse_args()

    costs = collect_costs(args.date)
    total = costs["haiku"] + costs["sonnet"] + costs["opus"] + costs["unknown"]
    report = format_report(args.date, costs, total)

    print(report)

    if not args.no_slack:
        token = get_slack_token()
        post_slack(report, token)

    if total >= 50.0:
        print("FATAL: Daily cost cap $50 exceeded. Exiting non-zero.", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
