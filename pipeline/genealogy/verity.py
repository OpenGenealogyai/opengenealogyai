"""
Verity — Hallucination QA agent for genealogy research.

Combines deterministic Python check + contextual model check into a single
verdict. Reads a client's pending facts, verifies each, writes results.

Usage:
    python -m pipeline.genealogy.verity audit <client_folder>
    python -m pipeline.genealogy.verity check-fact <fact_json> <source_file>

Workflow:
1. Read facts pending verification from <client>/pending_facts.jsonl
2. For each fact:
   a. Run verify_fact_python (literal check)
   b. If PASS or PARTIAL, run verify_fact_model (contextual check)
   c. Combined verdict:
      - Python FAIL → final FAIL (no model needed; literal not present)
      - Python PASS + Model PASS → final PASS
      - Python PASS + Model PARTIAL/FAIL → final PARTIAL/FAIL (model wins on judgment)
      - Python PARTIAL + Model PASS → final PARTIAL
      - Python PARTIAL + Model FAIL → final FAIL
3. Write QA report to <client>/qa_reports/<date>.md
4. Append flagged hallucinations to <client>/hallucination_alerts.jsonl
5. Move PASSed facts to <client>/confirmed_facts.jsonl
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Reconfigure stdout to UTF-8 — Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pipeline.genealogy.verify_python import verify_fact_python, Verdict
from pipeline.genealogy.verify_model  import verify_fact_model, ModelVerdict


def combine(py: Verdict, mv: ModelVerdict) -> dict:
    """Combine the two verdicts into a final dict."""
    # Python is the gate: if literal not present, fail outright (don't waste model time)
    if py.kind == "FAIL":
        return {
            "final": "FAIL",
            "reason": f"Python check failed: {py.detail}",
            "python":  {"kind": py.kind, "detail": py.detail,
                         "matched": py.matched_fields, "failed": py.failed_fields},
            "model": None,
        }

    # Both layers consulted; combine
    final_map = {
        ("PASS",    "PASS"):    "PASS",
        ("PASS",    "PARTIAL"): "PARTIAL",
        ("PASS",    "FAIL"):    "FAIL",
        ("PARTIAL", "PASS"):    "PARTIAL",
        ("PARTIAL", "PARTIAL"): "PARTIAL",
        ("PARTIAL", "FAIL"):    "FAIL",
    }
    final = final_map.get((py.kind, mv.kind), "FAIL")

    return {
        "final": final,
        "reason": (f"Python: {py.detail}. Model: {mv.reason}"
                   if mv.kind != "FAIL" else f"Model verdict: {mv.reason}"),
        "python":  {"kind": py.kind, "detail": py.detail,
                     "matched": py.matched_fields, "failed": py.failed_fields},
        "model":   {"kind": mv.kind, "reason": mv.reason, "issue_type": mv.issue_type},
    }


def verify_one(fact: dict, source_text: str) -> dict:
    """Run both layers on a single (fact, source) pair."""
    py = verify_fact_python(fact, source_text)
    if py.kind == "FAIL":
        # Don't spend model time on facts that fail the literal check
        return combine(py, ModelVerdict("FAIL", "skipped (Python failed)", "none"))
    mv = verify_fact_model(fact, source_text)
    return combine(py, mv)


# ─── Audit mode (process pending facts for a client) ─────────────────────────

def audit(client_folder: Path) -> None:
    pending_file   = client_folder / "pending_facts.jsonl"
    confirmed_file = client_folder / "confirmed_facts.jsonl"
    alerts_file    = client_folder / "hallucination_alerts.jsonl"

    if not pending_file.exists():
        print(f"[VERITY] No pending facts at {pending_file} — nothing to audit.", flush=True)
        return

    facts = []
    with open(pending_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                facts.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[VERITY] Skipping malformed line: {e}", flush=True)

    if not facts:
        print(f"[VERITY] {pending_file} is empty.", flush=True)
        return

    print(f"[VERITY] Auditing {len(facts)} pending facts for client {client_folder.name}", flush=True)

    pass_count = partial_count = fail_count = 0
    confirmed_lines = []
    alert_lines = []
    audit_lines = [
        f"# Verity QA Report — {client_folder.name}",
        f"**Date:** {dt.datetime.now().isoformat(timespec='seconds')}",
        f"**Facts audited:** {len(facts)}",
        "",
    ]

    for i, fact in enumerate(facts):
        source_text = fact.pop("__source_text__", "")
        fact_id     = fact.get("__fact_id__", f"f{i}")
        if not source_text:
            print(f"[VERITY] Fact {fact_id} has no __source_text__ field — cannot verify; FAIL.", flush=True)
            verdict = {
                "final": "FAIL",
                "reason": "Source text missing from fact record.",
                "python": None, "model": None,
            }
        else:
            verdict = verify_one(fact, source_text)

        # Tally
        if verdict["final"] == "PASS":     pass_count    += 1
        elif verdict["final"] == "PARTIAL": partial_count += 1
        else:                                fail_count    += 1

        # Audit-report row
        emoji = {"PASS": "OK", "PARTIAL": "WARN", "FAIL": "FAIL"}[verdict["final"]]
        audit_lines.append(f"## {fact_id} — {emoji} {verdict['final']}")
        audit_lines.append(f"**Fact:** `{json.dumps(fact, ensure_ascii=False)}`")
        audit_lines.append(f"**Reason:** {verdict['reason']}")
        if verdict.get("python"):
            audit_lines.append(f"**Python:** matched={verdict['python']['matched']} "
                               f"failed={verdict['python']['failed']}")
        if verdict.get("model"):
            audit_lines.append(f"**Model:** {verdict['model']['kind']} — "
                               f"{verdict['model']['issue_type']}")
        audit_lines.append("")

        # Routing
        record = {**fact, "__fact_id__": fact_id, "__verdict__": verdict,
                  "__verified_at__": dt.datetime.now().isoformat(timespec="seconds")}
        if verdict["final"] == "PASS":
            confirmed_lines.append(json.dumps(record, ensure_ascii=False))
        else:
            alert_lines.append(json.dumps(record, ensure_ascii=False))

    # Write outputs
    audit_dir = client_folder / "qa_reports"
    audit_dir.mkdir(exist_ok=True)
    audit_file = audit_dir / f"{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    audit_file.write_text("\n".join(audit_lines), encoding="utf-8")

    if confirmed_lines:
        with open(confirmed_file, "a", encoding="utf-8") as f:
            for line in confirmed_lines: f.write(line + "\n")
    if alert_lines:
        with open(alerts_file, "a", encoding="utf-8") as f:
            for line in alert_lines: f.write(line + "\n")

    # Clear pending (we processed everything)
    pending_file.write_text("", encoding="utf-8")

    print(f"[VERITY] DONE — PASS:{pass_count} PARTIAL:{partial_count} FAIL:{fail_count}", flush=True)
    print(f"[VERITY] Report: {audit_file}", flush=True)
    if alert_lines:
        print(f"[VERITY] {len(alert_lines)} hallucination alerts -> {alerts_file}", flush=True)


# ─── Single-fact check mode ─────────────────────────────────────────────────

def check_fact_cli(fact_json_str: str, source_file: str) -> None:
    fact = json.loads(fact_json_str)
    source = Path(source_file).read_text(encoding="utf-8", errors="replace")
    verdict = verify_one(fact, source)
    print(json.dumps(verdict, ensure_ascii=False, indent=2), flush=True)


# ─── Entry point ────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Verity — genealogy hallucination QA")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("audit", help="Audit a client's pending_facts.jsonl")
    pa.add_argument("client_folder", type=Path)

    pc = sub.add_parser("check-fact", help="Check one fact against a source file")
    pc.add_argument("fact_json", help="JSON string of the fact")
    pc.add_argument("source_file", type=str)

    args = p.parse_args()

    if args.cmd == "audit":
        audit(args.client_folder)
    elif args.cmd == "check-fact":
        check_fact_cli(args.fact_json, args.source_file)


if __name__ == "__main__":
    main()
