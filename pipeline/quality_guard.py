"""
Quality Guard — anti-hallucination and minimum quality enforcement.

Every extracted record passes through here before it is allowed into the
embedding queue. Records that fail are routed to:
  - _checkpoints/rejected/     (hallucination or invalid)
  - _checkpoints/low_quality/  (valid but below threshold, retry after LoRA)
  - _checkpoints/needs_review/ (uncertain — human or verification agent reviews)

Call from cpu_worker.py after extraction:
    from pipeline.quality_guard import check_record
    result = check_record(record, source_text)
    if result.action == "embed":
        queue.put(record)
    elif result.action == "reject":
        write_to_rejected(record, result.reasons)
"""

import re, json, datetime
from dataclasses import dataclass, field
from pathlib import Path
from pipeline.paths import CHECKPOINTS, LOGS

REJECTED_DIR     = CHECKPOINTS / "rejected"
LOW_QUALITY_DIR  = CHECKPOINTS / "low_quality"
NEEDS_REVIEW_DIR = CHECKPOINTS / "needs_review"
QUALITY_LOG      = LOGS / "quality_guard.jsonl"

# ── Thresholds ─────────────────────────────────────────────────────────────────
EMBED_THRESHOLD        = 0.55   # minimum quality score to embed
REVIEW_THRESHOLD       = 0.35   # below this goes to needs_review
MIN_NAME_LENGTH        = 2
MAX_NAME_LENGTH        = 80     # longer = likely OCR artifact
PLAUSIBLE_BIRTH_MIN    = 1400
PLAUSIBLE_BIRTH_MAX    = 2005
PLAUSIBLE_DEATH_MAX    = 2025
MAX_AGE_AT_DEATH       = 130
MIN_MARRIAGE_AGE       = 12
MAX_RECORDS_FROM_PAGE  = 50     # >50 persons from one page = suspect extraction

# Known OCR/hallucination garbage patterns
GARBAGE_PATTERNS = [
    r"^\s*$",                          # empty
    r"[^\x00-\x7F]{5,}",              # long runs of non-ASCII
    r"\b(lorem|ipsum|dolor|sit amet)\b",  # placeholder text
    r"(\w)\1{4,}",                    # aaaaa-type repetition
    r"^[^a-zA-Z]+$",                  # no letters at all
]
GARBAGE_RE = [re.compile(p, re.I) for p in GARBAGE_PATTERNS]


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class QualityResult:
    action: str          # "embed" | "flag_medium" | "needs_review" | "reject"
    score:  float        # 0.0 – 1.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Individual checks ──────────────────────────────────────────────────────────

def _check_garbage(text: str) -> str | None:
    """Return a reason string if text looks like garbage, else None."""
    for pat in GARBAGE_RE:
        if pat.search(text):
            return f"garbage pattern matched: {pat.pattern[:40]}"
    return None


def _check_name_in_source(name: str, source_text: str) -> bool:
    """
    At least one word from the name (surname or given) must appear in the
    source text. Prevents fully hallucinated names.
    """
    if not source_text:
        return True  # can't verify, give benefit of doubt
    name_clean = re.sub(r"[^a-zA-Z ]", "", name).strip()
    words = [w for w in name_clean.split() if len(w) >= 3]
    if not words:
        return True
    src_lower = source_text.lower()
    return any(w.lower() in src_lower for w in words)


def _check_date_plausibility(record: dict) -> list[str]:
    issues = []
    rd = record.get("record_date", {}) or {}
    year_min = rd.get("year_min")
    year_max = rd.get("year_max")

    persons = record.get("persons_mentioned", []) or []
    for p in persons:
        birth = p.get("birth_year")
        death = p.get("death_year")
        marriage = p.get("marriage_year")

        if birth is not None:
            if not (PLAUSIBLE_BIRTH_MIN <= birth <= PLAUSIBLE_BIRTH_MAX):
                issues.append(f"implausible birth year {birth} for {p.get('name_as_written','?')}")
        if death is not None:
            if death > PLAUSIBLE_DEATH_MAX:
                issues.append(f"future death year {death}")
            if birth is not None and death < birth:
                issues.append(f"death {death} before birth {birth}")
            if birth is not None and (death - birth) > MAX_AGE_AT_DEATH:
                issues.append(f"age at death {death-birth} exceeds {MAX_AGE_AT_DEATH}")
        if marriage is not None and birth is not None:
            if (marriage - birth) < MIN_MARRIAGE_AGE:
                issues.append(f"marriage age {marriage-birth} below minimum {MIN_MARRIAGE_AGE}")

    return issues


def _check_field_completeness(record: dict) -> tuple[bool, list[str]]:
    """Record must have at minimum: at least one named person OR a meaningful transcription."""
    persons = record.get("persons_mentioned", []) or []
    trans = (record.get("transcription") or "").strip()

    reasons = []
    if not persons and len(trans) < 20:
        reasons.append("no persons and transcription too short (<20 chars)")
        return False, reasons

    for p in persons:
        name = (p.get("name_as_written") or "").strip()
        if len(name) < MIN_NAME_LENGTH:
            reasons.append(f"person has no usable name: '{name}'")
        elif len(name) > MAX_NAME_LENGTH:
            reasons.append(f"name too long ({len(name)} chars) — likely OCR artifact: '{name[:40]}...'")

    return len(reasons) == 0, reasons


def _check_person_count(record: dict, source_text: str) -> list[str]:
    """Flag if extraction claims far more persons than source text plausibly contains."""
    persons = record.get("persons_mentioned", []) or []
    if len(persons) <= MAX_RECORDS_FROM_PAGE:
        return []
    # Rough check: source text has fewer name-like capitalized words than claimed persons
    if source_text:
        cap_words = len(re.findall(r'\b[A-Z][a-z]{2,}\b', source_text))
        if len(persons) > cap_words:
            return [f"claimed {len(persons)} persons but source has only ~{cap_words} capitalized words"]
    return []


def _score_extraction(record: dict, source_text: str) -> float:
    """
    Six-criteria quality score (0.0–1.0), same scale as the benchmark runner.
    valid_json / has_persons / name_in_source / has_event_type / has_date / has_location
    """
    score = 0.0
    weight = 1.0 / 6

    # 1. Valid JSON structure (we already have a dict, so +1)
    score += weight

    # 2. Has at least one named person
    persons = record.get("persons_mentioned", []) or []
    if persons and any((p.get("name_as_written") or "").strip() for p in persons):
        score += weight

    # 3. At least one person name appears in source text
    if persons:
        first_name = (persons[0].get("name_as_written") or "").strip()
        if _check_name_in_source(first_name, source_text):
            score += weight
    elif source_text:
        score += weight  # no persons but source provided — neutral

    # 4. Has event type
    if record.get("record_type") and record["record_type"] != "unknown":
        score += weight

    # 5. Has at least one date
    rd = record.get("record_date", {}) or {}
    if rd.get("year_min") or rd.get("year_max") or rd.get("date_as_written"):
        score += weight
    else:
        for p in persons:
            if p.get("birth_year") or p.get("death_year") or p.get("marriage_year"):
                score += weight
                break

    # 6. Has location
    loc = record.get("location", {}) or {}
    if loc.get("place_name") or loc.get("country_code") or loc.get("state_province"):
        score += weight

    return round(score, 3)


# ── Main entry point ───────────────────────────────────────────────────────────

def check_record(record: dict, source_text: str = "") -> QualityResult:
    """
    Run all quality checks on an extracted record.

    Parameters
    ----------
    record      : dict  — the extracted RawRecord
    source_text : str   — the original source document text (used for hallucination detection)

    Returns
    -------
    QualityResult with action "embed" | "flag_medium" | "needs_review" | "reject"
    """
    reasons  = []
    warnings = []

    # ── Hard rejects ──────────────────────────────────────────────────────────

    # Garbage transcription
    trans = record.get("transcription") or ""
    g = _check_garbage(trans)
    if g and len(trans) > 10:
        reasons.append(f"transcription garbage: {g}")

    # Field completeness
    complete, completeness_reasons = _check_field_completeness(record)
    if not complete:
        reasons.extend(completeness_reasons)

    # Person count sanity
    count_issues = _check_person_count(record, source_text)
    reasons.extend(count_issues)

    # Date plausibility
    date_issues = _check_date_plausibility(record)
    for issue in date_issues:
        # Implausible dates are warnings unless multiple
        if len(date_issues) >= 3:
            reasons.append(issue)
        else:
            warnings.append(issue)

    # ── Hallucination: name not in source ─────────────────────────────────────
    if source_text:
        persons = record.get("persons_mentioned", []) or []
        hallucinated = []
        for p in persons:
            name = (p.get("name_as_written") or "").strip()
            if name and not _check_name_in_source(name, source_text):
                hallucinated.append(name)
        if hallucinated:
            if len(hallucinated) == len(persons):
                # All names hallucinated — hard reject
                reasons.append(f"ALL {len(hallucinated)} person names absent from source text — hallucination")
            else:
                warnings.append(f"{len(hallucinated)} names not found in source: {hallucinated[:3]}")

    # ── Quality score ──────────────────────────────────────────────────────────
    score = _score_extraction(record, source_text)

    # ── Decide action ──────────────────────────────────────────────────────────
    if reasons:
        action = "reject"
    elif score >= EMBED_THRESHOLD:
        action = "embed" if score >= 0.75 else "flag_medium"
    elif score >= REVIEW_THRESHOLD:
        action = "needs_review"
    else:
        action = "reject"

    return QualityResult(action=action, score=score, reasons=reasons, warnings=warnings)


# ── File routing ───────────────────────────────────────────────────────────────

def route_record(record: dict, result: QualityResult):
    """Write rejected/low-quality/review records to the right checkpoint folder."""
    for d in (REJECTED_DIR, LOW_QUALITY_DIR, NEEDS_REVIEW_DIR):
        d.mkdir(parents=True, exist_ok=True)

    record_id = record.get("record_id", "unknown")
    payload = {**record, "_quality_score": result.score,
               "_reasons": result.reasons, "_warnings": result.warnings}
    line = json.dumps(payload) + "\n"

    if result.action == "reject":
        with open(REJECTED_DIR / "rejected.jsonl", "a", encoding="utf-8") as f:
            f.write(line)
    elif result.action in ("flag_medium", "needs_review"):
        with open(NEEDS_REVIEW_DIR / "review_queue.jsonl", "a", encoding="utf-8") as f:
            f.write(line)

    # Always log the quality decision
    QUALITY_LOG.parent.mkdir(exist_ok=True)
    with open(QUALITY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts":        datetime.datetime.utcnow().isoformat() + "Z",
            "record_id": record_id,
            "action":    result.action,
            "score":     result.score,
            "reasons":   result.reasons,
            "warnings":  result.warnings,
        }) + "\n")


# ── Batch stats ────────────────────────────────────────────────────────────────

def batch_stats(results: list[QualityResult]) -> dict:
    """Summarise quality results for a batch — used by checker and reporter."""
    if not results:
        return {}
    actions = [r.action for r in results]
    scores  = [r.score for r in results]
    return {
        "total":          len(results),
        "embed":          actions.count("embed"),
        "flag_medium":    actions.count("flag_medium"),
        "needs_review":   actions.count("needs_review"),
        "rejected":       actions.count("reject"),
        "pass_rate":      round(actions.count("embed") / len(results), 3),
        "avg_score":      round(sum(scores) / len(scores), 3),
        "min_score":      round(min(scores), 3),
        "hallucinations": sum(1 for r in results if any("hallucination" in x for x in r.reasons)),
    }
