"""
Slack posting utility for OpenGenealogyAI agents.
Claude writes the message. This script just sends it.

Usage:
  python slack_post.py "Your message here"
  python slack_post.py --file path/to/message.txt
"""

import sys
import os
import json
import urllib.request
from pathlib import Path

WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")

def post(text: str) -> bool:
    if not WEBHOOK:
        print("[slack_post] SLACK_WEBHOOK_URL not set. Message:\n")
        print(text)
        return False
    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"[slack_post] Failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python slack_post.py 'message' OR python slack_post.py --file message.txt")
        sys.exit(1)

    if sys.argv[1] == "--file":
        text = Path(sys.argv[2]).read_text(encoding="utf-8")
    else:
        text = " ".join(sys.argv[1:])

    success = post(text)
    sys.exit(0 if success else 1)
