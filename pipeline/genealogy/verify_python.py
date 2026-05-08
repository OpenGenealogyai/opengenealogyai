"""
Verity — Python-layer hallucination check (deterministic).

Takes a fact and a source-text blob; returns whether the fact's literal
strings appear in the source (with reasonable fuzzy/format flexibility).

This is the FAST layer of Verity. The model layer (verify_model.py) does
contextual checks the Python layer can't.

API:
    result = verify_fact_python(fact: dict, source_text: str) -> Verdict

Verdict.kind ∈ {"PASS", "PARTIAL", "FAIL"}
Verdict.detail explains why.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

# ─── Verdict type ─────────────────────────────────────────────────────────────

@dataclass
class Verdict:
    kind: str                                # "PASS" | "PARTIAL" | "FAIL"
    detail: str                              # human-readable reason
    matched_fields: list[str] = field(default_factory=list)
    failed_fields:  list[str] = field(default_factory=list)


# ─── Helpers ──────────────────────────────────────────────────────────────────

_NAME_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]{2,}")
_YEAR_RE       = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")          # 1500–2029
_MONTH_NAMES   = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics-style punctuation noise, collapse whitespace."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[\s ]+", " ", s)
    return s.strip()


def _name_tokens(name: str) -> list[str]:
    """Split a name into significant tokens (skip 1-letter initials in match)."""
    return [t.lower() for t in _NAME_TOKEN_RE.findall(name or "") if len(t) >= 2]


def fuzzy_name_in_text(name: str, source_text: str) -> bool:
    """
    Returns True if the name appears in the source with reasonable flexibility:
    - Initials OK ("Wm. B. Maxwell" matches "William Bailey Maxwell" if SURNAME exact)
    - Order: tokens of the name must appear in order in the text (within a sliding window)
    - Last token (surname) must match exactly (case-insensitive)
    """
    if not name or not source_text:
        return False
    src = _normalize(source_text)
    tokens = _name_tokens(name)
    if not tokens:
        return False

    surname = tokens[-1]
    # Surname must appear at least once
    if surname not in src:
        return False
    # If just a single name (e.g., "Maxwell"), surname presence is enough
    if len(tokens) == 1:
        return True

    # Find each surname occurrence; check that earlier tokens appear within a 60-char window before
    for m in re.finditer(re.escape(surname), src):
        end = m.start()
        start = max(0, end - 200)
        window = src[start:end]
        prior_tokens_found = 0
        for t in tokens[:-1]:
            # Allow first letter only ("w" matches "william" or "wm")
            if t in window or re.search(r"\b" + re.escape(t[0]) + r"[.\s]", window):
                prior_tokens_found += 1
        # Require at least half the prior tokens present
        if prior_tokens_found >= max(1, (len(tokens) - 1) // 2):
            return True
    return False


def parse_year(s: str) -> Optional[int]:
    """Pull a year out of a string. Returns int or None."""
    if not s:
        return None
    m = _YEAR_RE.search(str(s))
    return int(m.group(1)) if m else None


def date_in_text(date_str: str, source_text: str, allow_year_only: bool = True) -> bool:
    """
    Check if a date appears in the source text with format flexibility:
    - "1843" / "August 30, 1843" / "1843-08-30" / "8/30/1843" / "30 August 1843" all match
    - Returns True if AT LEAST the year matches; if month or day are also in fact, prefer match
    """
    if not date_str or not source_text:
        return False
    src = _normalize(source_text)
    year = parse_year(date_str)
    if not year:
        return False
    # Year must be in source
    if str(year) not in src:
        return False
    if allow_year_only:
        return True
    # Try harder for month-day match
    fact_norm = _normalize(date_str)
    for mname, mnum in _MONTH_NAMES.items():
        if mname in fact_norm:
            if mname in src or f"{mnum}/" in src or f"-{mnum:02d}-" in src:
                return True
    return False


def place_in_text(place_str: str, source_text: str) -> bool:
    """Substring match on the most distinctive part of the place name."""
    if not place_str or not source_text:
        return False
    src = _normalize(source_text)
    place_norm = _normalize(place_str)
    # Try whole place
    if place_norm and place_norm in src:
        return True
    # Try the most distinctive token (typically the city)
    tokens = [t.strip() for t in re.split(r"[,\s]+", place_norm) if t.strip()]
    if not tokens:
        return False
    distinctive = max(tokens, key=len)
    return distinctive in src


# ─── Main API ─────────────────────────────────────────────────────────────────

def verify_fact_python(fact: dict, source_text: str) -> Verdict:
    """
    Verify a fact dict against source text using deterministic checks.

    fact schema (any subset; only present fields are checked):
        {
            "kind":    "person" | "birth" | "death" | "marriage" | ...
            "name":    "James Bailey Maxwell"
            "birth_year": 1843,
            "death_year": 1876,
            "birth_place": "Shawneetown, Illinois"
            "death_place": "Panguitch, Garfield County, Utah"
            "spouse":  "Elizabeth Rebecca DeGraw"
            "father":  "William Bailey Maxwell"
            "mother":  "Lucretia Charlotte Bracken"
        }

    source_text: the full text of the source page that allegedly contains
    these facts.
    """
    matched = []
    failed = []

    def check(field_name: str, present_value, check_fn) -> None:
        if not present_value:
            return
        if check_fn(present_value, source_text):
            matched.append(field_name)
        else:
            failed.append(field_name)

    check("name",        fact.get("name"),        fuzzy_name_in_text)
    check("birth_year",  fact.get("birth_year"),  date_in_text)
    check("death_year",  fact.get("death_year"),  date_in_text)
    check("birth_place", fact.get("birth_place"), place_in_text)
    check("death_place", fact.get("death_place"), place_in_text)
    check("spouse",      fact.get("spouse"),      fuzzy_name_in_text)
    check("father",      fact.get("father"),      fuzzy_name_in_text)
    check("mother",      fact.get("mother"),      fuzzy_name_in_text)

    if not matched and not failed:
        return Verdict("FAIL", "No checkable fields present in fact dict.")

    if failed and not matched:
        return Verdict("FAIL", f"All checked fields missing from source: {failed}",
                       matched_fields=matched, failed_fields=failed)

    if failed:
        return Verdict("PARTIAL",
                       f"Some fields verified, some missing in source: matched={matched}, "
                       f"failed={failed}",
                       matched_fields=matched, failed_fields=failed)

    return Verdict("PASS", f"All checked fields verified: {matched}",
                   matched_fields=matched, failed_fields=failed)
