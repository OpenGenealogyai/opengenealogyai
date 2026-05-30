"""
maxgen_to_gedcom — Export a MAXGEN MaxPerson collection to GEDCOM 5.5.1.

Privacy rules honored:
- Persons with is_living=true are SKIPPED (or replaced with "Living" stub if
  include_living=False) — per docs/DNA_ARCHITECTURE.md
- Persons whose redistribution_license is 'tier2-private' are SKIPPED unless
  caller_is_owner=True
- DNA fields never exported (separate channel, separate consent)
"""
from __future__ import annotations
from typing import Iterable
import re


def _best(arr: list, key: str = "confidence") -> dict | None:
    if not arr:
        return None
    return max(arr, key=lambda a: a.get(key, 0))


def _ged_date(d: dict | None) -> str | None:
    if not d:
        return None
    y_min = d.get("year_min")
    y_max = d.get("year_max")
    month = d.get("month")
    day = d.get("day")
    date_type = d.get("date_type") or "exact"
    MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
    if not y_min:
        return None
    # GEDCOM date patterns
    if y_max and y_max != y_min:
        return f"BET {y_min} AND {y_max}"
    if date_type == "estimated":
        return f"ABT {y_min}"
    if date_type == "calculated":
        return f"CAL {y_min}"
    parts = []
    if day:
        parts.append(str(day))
    if month and 1 <= month <= 12:
        parts.append(MONTHS[month - 1])
    parts.append(str(y_min))
    return " ".join(parts)


def _ged_id(pid: str, prefix: str = "I") -> str:
    """Generate a stable GEDCOM xref id from a UUID."""
    if not pid:
        return f"@{prefix}0@"
    safe = re.sub(r"[^a-zA-Z0-9]", "", pid)[:10].upper() or "X"
    return f"@{prefix}{safe}@"


def maxperson_to_gedcom(
    persons: Iterable[dict],
    *,
    include_living: bool = False,
    caller_is_owner: bool = False,
    submitter_name: str = "OpenGenealogyAI",
) -> str:
    """
    Convert an iterable of MaxPerson dicts to a GEDCOM 5.5.1 string.

    Family records are inferred from parent_assertions: a child links to its
    parents via FAMC/FAMS edges.
    """
    persons = list(persons)
    out: list[str] = []

    # Header
    out.append("0 HEAD")
    out.append("1 SOUR OpenGenealogyAI")
    out.append("2 VERS 1.4")
    out.append("2 NAME OpenGenealogyAI MAXGEN exporter")
    out.append("1 GEDC")
    out.append("2 VERS 5.5.1")
    out.append("2 FORM LINEAGE-LINKED")
    out.append("1 CHAR UTF-8")
    out.append(f"1 SUBM @SUB1@")

    out.append("0 @SUB1@ SUBM")
    out.append(f"1 NAME {submitter_name}")

    # Filter by privacy first
    visible = []
    for p in persons:
        if p.get("is_living") and not include_living:
            continue
        if p.get("redistribution_license") == "tier2-private" and not caller_is_owner:
            continue
        # Skip merged-away unless caller wants the full history
        if p.get("merge_status") == "merged_away":
            continue
        visible.append(p)

    # Build family records: for each child with a parent, create/find a FAM
    families: dict[tuple, dict] = {}  # (father_id, mother_id) -> {family_id, children}
    fam_counter = 1
    for p in visible:
        father_id = None
        mother_id = None
        for pa in p.get("parent_assertions", []):
            if pa.get("parent_role") == "father":
                father_id = pa.get("parent_person_id")
            elif pa.get("parent_role") == "mother":
                mother_id = pa.get("parent_person_id")
        if father_id or mother_id:
            key = (father_id, mother_id)
            if key not in families:
                families[key] = {
                    "family_id": f"@F{fam_counter}@",
                    "father_id": father_id,
                    "mother_id": mother_id,
                    "children": [],
                }
                fam_counter += 1
            families[key]["children"].append(p["person_id"])

    # Person → family memberships (FAMC links)
    famc_lookup: dict[str, list[str]] = {}  # person_id -> [family xref ids]
    for fam in families.values():
        for ch in fam["children"]:
            famc_lookup.setdefault(ch, []).append(fam["family_id"])

    # Person → spouse-family memberships (FAMS links)
    fams_lookup: dict[str, list[str]] = {}
    for fam in families.values():
        if fam["father_id"]:
            fams_lookup.setdefault(fam["father_id"], []).append(fam["family_id"])
        if fam["mother_id"]:
            fams_lookup.setdefault(fam["mother_id"], []).append(fam["family_id"])
    # Spouse_assertions also create families
    spouse_fams = {}  # (a_id, b_id sorted) -> family
    for p in visible:
        for sa in p.get("spouse_assertions", []):
            sp_id = sa.get("spouse_person_id")
            if not sp_id:
                continue
            key = tuple(sorted([p["person_id"], sp_id]))
            if key in spouse_fams:
                continue
            fam_id = f"@F{fam_counter}@"
            fam_counter += 1
            spouse_fams[key] = {
                "family_id": fam_id,
                "spouses": list(key),
                "marriage": sa,
            }
            for spid in key:
                fams_lookup.setdefault(spid, []).append(fam_id)

    # Emit INDI records
    for p in visible:
        pid = _ged_id(p["person_id"])
        out.append(f"0 {pid} INDI")
        name = _best(p.get("name_assertions"))
        if name:
            # NAME line: given /surname/
            given = name.get("given_name", "")
            surname = name.get("surname", "")
            if surname:
                out.append(f"1 NAME {given} /{surname}/".strip())
            else:
                out.append(f"1 NAME {name.get('name_as_written', '')}")
        birth = _best(p.get("birth_assertions"))
        if birth:
            out.append("1 BIRT")
            bd = _ged_date(birth)
            if bd:
                out.append(f"2 DATE {bd}")
            if birth.get("place_as_written"):
                out.append(f"2 PLAC {birth['place_as_written']}")
        death = _best(p.get("death_assertions"))
        if death:
            out.append("1 DEAT")
            dd = _ged_date(death)
            if dd:
                out.append(f"2 DATE {dd}")
            if death.get("place_as_written"):
                out.append(f"2 PLAC {death['place_as_written']}")
            if death.get("cause_as_written"):
                out.append(f"2 CAUS {death['cause_as_written']}")
        # Occupations
        for occ in p.get("occupation_assertions", []) or []:
            out.append("1 OCCU " + (occ.get("occupation_as_written", "")))
        # Family memberships
        for f in famc_lookup.get(p["person_id"], []):
            out.append(f"1 FAMC {f}")
        for f in fams_lookup.get(p["person_id"], []):
            out.append(f"1 FAMS {f}")
        # Notes for any conflict_flags or merge_history (auditability)
        if p.get("merge_history"):
            out.append("1 NOTE MAXGEN merge_history: " + str(len(p["merge_history"])) + " absorbed entities (see MAXGEN export for full provenance)")

    # Emit FAM records
    for key, fam in families.items():
        out.append(f"0 {fam['family_id']} FAM")
        if fam["father_id"]:
            out.append(f"1 HUSB {_ged_id(fam['father_id'])}")
        if fam["mother_id"]:
            out.append(f"1 WIFE {_ged_id(fam['mother_id'])}")
        for ch in fam["children"]:
            out.append(f"1 CHIL {_ged_id(ch)}")
    for key, fam in spouse_fams.items():
        out.append(f"0 {fam['family_id']} FAM")
        out.append(f"1 HUSB {_ged_id(fam['spouses'][0])}")
        out.append(f"1 WIFE {_ged_id(fam['spouses'][1])}")
        marr = fam["marriage"]
        out.append("1 MARR")
        if marr.get("marriage_year_min"):
            md = {
                "year_min": marr["marriage_year_min"],
                "year_max": marr.get("marriage_year_max"),
                "date_type": "exact",
            }
            gd = _ged_date(md)
            if gd:
                out.append(f"2 DATE {gd}")
        if marr.get("marriage_place_as_written"):
            out.append(f"2 PLAC {marr['marriage_place_as_written']}")

    out.append("0 TRLR")
    return "\n".join(out) + "\n"
