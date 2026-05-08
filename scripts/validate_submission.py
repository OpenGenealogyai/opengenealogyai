"""
Contributor Submission Validator — quality gate for incoming JSONL submissions.

Run this against a contributor's submission file before accepting records into
the embedding queue.

Usage:
    python scripts/validate_submission.py <submission.jsonl> [--collection-id <id>]
    python scripts/validate_submission.py --help

Output:
    Summary printed to stdout.
    Accepted records written to _checkpoints/embed_queue/ (ready for GPU worker).
    Rejected records written to _checkpoints/rejected/submission_{timestamp}.jsonl
    Report written to _logs/submission_reports/{timestamp}_{collection_id}.json

Exit codes:
    0 — submission accepted (pass rate >= 60%)
    1 — submission rejected (pass rate < 60%)
    2 — usage error
"""

import argparse, datetime, json, sys
from pathlib import Path
import uuid

# Allow running as a script from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.quality_guard import check_record, batch_stats, QualityResult
from pipeline.paths import CHECKPOINTS, LOGS

EMBED_QUEUE_DIR  = CHECKPOINTS / "embed_queue"
REJECTED_DIR     = CHECKPOINTS / "rejected"
REPORTS_DIR      = LOGS / "submission_reports"

MIN_PASS_RATE    = 0.60   # reject entire submission if < 60% pass
MAX_HALLUC_RATE  = 0.05   # reject if > 5% hallucination rate
MIN_RECORDS      = 5      # submission must have at least 5 records


# ── Validation helpers ────────────────────────────────────────────────────────────

def _load_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    """Load a JSONL file. Returns (records, parse_errors)."""
    records = []
    errors  = []
    for line_num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            errors.append(f"Line {line_num}: {e}")
    return records, errors


def _extract_source_text(record: dict) -> str:
    """Pull the source text field from wherever it lives in the record."""
    return (
        record.get("source_text")
        or record.get("transcription")
        or record.get("text")
        or record.get("ocr_text")
        or ""
    )


def _validate_contributor_fields(record: dict) -> list[str]:
    """Check required contributor metadata fields."""
    issues = []
    if not record.get("embedded_by"):
        issues.append("missing 'embedded_by' (contributor name)")
    if not record.get("source_url") and not record.get("url"):
        issues.append("missing 'source_url' or 'url'")
    if not record.get("collection_id"):
        issues.append("missing 'collection_id'")
    return issues


def _check_license_compliance(record: dict, redistribution_license: str) -> list[str]:
    """Verify record respects its collection's license."""
    issues = []
    if redistribution_license in ("ingest-only", "store-uri-only"):
        if record.get("transcription") and record["transcription"] is not None:
            issues.append(
                f"transcription must be null for {redistribution_license} collections"
            )
    if redistribution_license == "pending":
        issues.append("collection is on HOLD (license=pending) — do not submit yet")
    return issues


# ── Main validation run ───────────────────────────────────────────────────────────

def validate_submission(submission_path: Path, collection_id: str = "") -> int:
    """
    Full validation pipeline for a contributor submission.
    Returns exit code: 0=accepted, 1=rejected.
    """
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    col_tag = collection_id or "unknown"
    print(f"[VALIDATE] Submission: {submission_path}")
    print(f"[VALIDATE] Collection: {col_tag}")

    # ── Load collection metadata for license check ─────────────────────────────
    catalog_file = Path(__file__).resolve().parents[1] / "catalog" / "collections.json"
    redistribution_license = "public-domain"  # default
    if catalog_file.exists() and collection_id:
        try:
            catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
            for coll in catalog:
                if coll.get("id") == collection_id:
                    redistribution_license = coll.get("redistribution_license", "public-domain")
                    break
        except Exception:
            pass

    print(f"[VALIDATE] License: {redistribution_license}")

    # ── Load records ──────────────────────────────────────────────────────────
    records, parse_errors = _load_jsonl(submission_path)

    if parse_errors:
        print(f"[VALIDATE] {len(parse_errors)} JSON parse errors:")
        for e in parse_errors[:5]:
            print(f"  - {e}")

    if len(records) < MIN_RECORDS:
        print(f"[VALIDATE] REJECTED — too few records ({len(records)} < {MIN_RECORDS})")
        return 1

    print(f"[VALIDATE] Loaded {len(records)} records — running quality checks...")

    # ── Per-record checks ──────────────────────────────────────────────────────
    results: list[QualityResult] = []
    accepted_records: list[dict] = []
    rejected_records: list[dict] = []
    contributor_issues_count = 0

    for i, record in enumerate(records):
        source_text = _extract_source_text(record)

        # Contributor metadata check
        contrib_issues = _validate_contributor_fields(record)
        if contrib_issues:
            contributor_issues_count += 1

        # License compliance check
        license_issues = _check_license_compliance(record, redistribution_license)

        # Quality guard check
        result = check_record(record, source_text)

        # Merge license issues into hard rejects
        if license_issues:
            result.reasons.extend(license_issues)
            if result.action != "reject":
                result.action = "reject"
                result.score  = min(result.score, 0.3)

        results.append(result)

        if result.action in ("embed", "flag_medium"):
            accepted_records.append(record)
        else:
            rejected_records.append({
                **record,
                "_quality_score": result.score,
                "_reasons":       result.reasons,
                "_warnings":      result.warnings,
            })

    # ── Compute stats ──────────────────────────────────────────────────────────
    stats = batch_stats(results)
    pass_rate   = stats.get("pass_rate", 0)
    halluc_rate = stats.get("hallucinations", 0) / max(len(results), 1)

    print()
    print("=" * 60)
    print(f"  SUBMISSION QUALITY REPORT — {col_tag}")
    print("=" * 60)
    print(f"  Total records:      {stats['total']}")
    print(f"  Accepted (embed):   {stats['embed']}")
    print(f"  Flag medium:        {stats.get('flag_medium', 0)}")
    print(f"  Needs review:       {stats['needs_review']}")
    print(f"  Rejected:           {stats['rejected']}")
    print(f"  Pass rate:          {pass_rate:.1%}")
    print(f"  Avg quality score:  {stats['avg_score']:.3f}")
    print(f"  Hallucinations:     {stats['hallucinations']}  ({halluc_rate:.1%})")
    print(f"  Parse errors:       {len(parse_errors)}")
    print(f"  Contributor issues: {contributor_issues_count}")
    print("=" * 60)

    # ── Decide accept/reject ───────────────────────────────────────────────────
    accepted = True
    reject_reasons = []

    if pass_rate < MIN_PASS_RATE:
        reject_reasons.append(f"pass rate {pass_rate:.1%} < minimum {MIN_PASS_RATE:.0%}")
        accepted = False

    if halluc_rate > MAX_HALLUC_RATE:
        reject_reasons.append(f"hallucination rate {halluc_rate:.1%} > maximum {MAX_HALLUC_RATE:.0%}")
        accepted = False

    if redistribution_license == "pending":
        reject_reasons.append("collection license=pending — cannot accept yet")
        accepted = False

    if accepted:
        print(f"\n  RESULT: ACCEPTED — writing {len(accepted_records)} records to embed queue")
    else:
        print(f"\n  RESULT: REJECTED")
        for r in reject_reasons:
            print(f"    - {r}")

    # ── Write outputs ──────────────────────────────────────────────────────────
    EMBED_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if accepted and accepted_records:
        for rec in accepted_records:
            out = EMBED_QUEUE_DIR / f"{uuid.uuid4().hex}.json"
            out.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    if rejected_records:
        rejected_file = REJECTED_DIR / f"submission_{ts}_{col_tag}.jsonl"
        with open(rejected_file, "w", encoding="utf-8") as f:
            for rec in rejected_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"\n  Rejected records written to: {rejected_file}")

    # Write full JSON report
    report = {
        "ts":                    ts,
        "collection_id":         col_tag,
        "submission_file":       str(submission_path),
        "redistribution_license": redistribution_license,
        "accepted":              accepted,
        "reject_reasons":        reject_reasons,
        "stats":                 stats,
        "contributor_issues":    contributor_issues_count,
        "parse_errors":          len(parse_errors),
    }
    report_file = REPORTS_DIR / f"{ts}_{col_tag}.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  Report written to:   {report_file}")

    return 0 if accepted else 1


# ── CLI ───────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validate a contributor JSONL submission before accepting records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("submission", type=Path, help="Path to the .jsonl submission file")
    parser.add_argument(
        "--collection-id", default="",
        help="Collection ID (e.g. wikidata-chunk-1) — used for license check"
    )
    args = parser.parse_args()

    if not args.submission.exists():
        print(f"ERROR: file not found: {args.submission}", file=sys.stderr)
        sys.exit(2)

    if not args.submission.suffix.lower() == ".jsonl":
        print(f"WARNING: expected a .jsonl file, got: {args.submission.suffix}")

    exit_code = validate_submission(args.submission, args.collection_id)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
