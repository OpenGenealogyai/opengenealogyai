"""
Central path configuration for OpenGenealogyAI pipeline.
All scripts import from here — never hardcode paths elsewhere.

Usage:
    from pipeline.paths import RAW, EMBEDDED, LOGS, CHECKPOINTS
    raw_file = RAW.wikidata / "dump_2026.json.gz"
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_BASE = Path(os.environ.get(
    "GENEALOGY_RAW_DIR",
    r"D:\ai\companies\open-genealogical-ai\rawdata"
))


class RawDirs:
    """Subfolder paths for each raw data source."""
    base              = _BASE
    wikidata          = _BASE / "wikidata"
    chronicling       = _BASE / "chronicling_america"
    internet_archive  = _BASE / "internet_archive"
    trove             = _BASE / "trove"
    blm_land_patents  = _BASE / "blm_land_patents"
    nara_catalog      = _BASE / "nara_catalog"
    hathitrust        = _BASE / "hathitrust"
    open_library      = _BASE / "open_library"
    dpla              = _BASE / "dpla"
    ssdi              = _BASE / "ssdi"
    ellis_island      = _BASE / "ellis_island"
    parish_records    = _BASE / "parish_records"
    census            = _BASE / "census"
    military          = _BASE / "military"
    cemetery          = _BASE / "cemetery"
    newspapers        = _BASE / "newspapers"
    birth_certs       = _BASE / "birth_certificates"
    death_certs       = _BASE / "death_certificates"
    immigration       = _BASE / "immigration"
    probate_wills     = _BASE / "probate_wills"
    land_deeds        = _BASE / "land_deeds"
    familysearch      = _BASE / "familysearch"


RAW         = RawDirs()
EMBEDDED    = Path(os.environ.get("GENEALOGY_EMBEDDED_DIR",  _BASE / "_embedded"))
CHECKPOINTS = Path(os.environ.get("GENEALOGY_CHECKPOINTS_DIR", _BASE / "_checkpoints"))
LOGS        = Path(os.environ.get("GENEALOGY_LOGS_DIR",      _BASE / "_logs"))
QDRANT_PATH = Path(os.environ.get("QDRANT_PATH",             EMBEDDED / "qdrant"))

# Ensure all dirs exist at import time
for _d in [
    RAW.wikidata, RAW.chronicling, RAW.internet_archive, RAW.trove,
    RAW.blm_land_patents, RAW.nara_catalog, RAW.hathitrust,
    RAW.open_library, RAW.dpla,
    RAW.ssdi, RAW.ellis_island, RAW.parish_records,
    RAW.census, RAW.military, RAW.cemetery, RAW.newspapers,
    RAW.birth_certs, RAW.death_certs, RAW.immigration,
    RAW.probate_wills, RAW.land_deeds, RAW.familysearch,
    EMBEDDED, CHECKPOINTS, LOGS, QDRANT_PATH,
]:
    _d.mkdir(parents=True, exist_ok=True)
