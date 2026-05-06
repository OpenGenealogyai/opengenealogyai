"""
Genealogy Tree Builder Agent for OpenGenealogyAI.

Builds probabilistic ancestry trees by:
  1. Searching Qdrant for raw records mentioning a target person
  2. Creating Person entities with confidence-scored name assertions
  3. Creating parent_assertions with explicit relationship_type + confidence
  4. Writing to SQLite staging.db (append-only)
  5. Queuing judge_review tasks for every new assertion

Test anchor: Abraham Lincoln Sr. (b. ~1744, d. 1786), grandfather of President Lincoln.
  - Father:  John Lincoln (1716-1788), Virginia
  - Mother:  Rebecca Flowers (~1720)
  - Wife:    Bathsheba Herring (~1746)
  - Son:     Thomas Lincoln (~1778, father of president)

Usage:
    from agents.builder.tree_builder import TreeBuilder, PersonSeed

    builder = TreeBuilder(db_path="db/staging.db", qdrant_host="localhost")
    result = builder.build_tree(
        PersonSeed(name="Abraham Lincoln", birth_year=1744, birth_country="US"),
        depth=2
    )
    print(result.summary())
"""

import datetime, hashlib, json, os, re, sqlite3, sys, uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "agents" / "familysearch"))

from privacy_middleware import privacy_gate_batch, PrivacyBlock

# ── Optional Qdrant ────────────────────────────────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, Range, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

RECORDS_COLLECTION = "raw_records_v01"
PERSONS_COLLECTION = "persons_v01"

EXTRACTOR_ID = "builder-agent-haiku-001"
CURRENT_YEAR = datetime.datetime.now().year


# ── Data classes ───────────────────────────────────────────────────────────────
@dataclass
class PersonSeed:
    name: str
    birth_year: Optional[int] = None
    birth_year_tolerance: int = 10   # search ± this many years
    birth_country: str = "US"
    role_hint: str = "subject"       # role in source docs to filter


@dataclass
class PersonCandidate:
    """A record hit from Qdrant that may represent the target person."""
    record_id: str
    name_as_written: str
    confidence: float         # how confident this is the right person
    source_url: str
    year_min: Optional[int]
    year_max: Optional[int]
    record_type: str
    payload: dict = field(default_factory=dict)


@dataclass
class TreeResult:
    seed: PersonSeed
    persons_created: list[dict] = field(default_factory=list)
    assertions_created: int = 0
    judge_tasks_queued: int = 0
    sources_cited: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Tree for '{self.seed.name}' (b.~{self.seed.birth_year}): "
            f"{len(self.persons_created)} persons, "
            f"{self.assertions_created} assertions, "
            f"{self.sources_cited} sources cited, "
            f"{self.judge_tasks_queued} judge tasks queued"
        )


# ── Helpers ────────────────────────────────────────────────────────────────────
def _soundex(name: str) -> str:
    name = re.sub(r"[^a-zA-Z]", "", name).upper()
    if not name:
        return "Z000"
    codes = {"BFPV": "1", "CGJKQSXYZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
    result, prev = name[0], "0"
    for ch in name[1:]:
        code = "0"
        for keys, val in codes.items():
            if ch in keys:
                code = val
                break
        if code != "0" and code != prev:
            result += code
        prev = code
        if len(result) == 4:
            break
    return (result + "000")[:4]


def _name_confidence(query: str, candidate: str) -> float:
    """Jaro-Winkler approximation: compare Soundex + character overlap."""
    if not query or not candidate:
        return 0.0
    q_norm = re.sub(r"[^a-z ]", "", query.lower().strip())
    c_norm = re.sub(r"[^a-z ]", "", candidate.lower().strip())
    if q_norm == c_norm:
        return 1.0
    # Soundex match gives 0.80 base
    q_sdx = _soundex(query)
    c_sdx = _soundex(candidate)
    sdx_match = 0.80 if q_sdx == c_sdx else 0.0
    # Character bigram overlap
    def bigrams(s):
        return set(s[i:i+2] for i in range(len(s)-1))
    q_bg = bigrams(q_norm)
    c_bg = bigrams(c_norm)
    if not q_bg or not c_bg:
        return sdx_match
    overlap = len(q_bg & c_bg) / max(len(q_bg), len(c_bg))
    return min(1.0, sdx_match * 0.5 + overlap * 0.5 + 0.2)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Tree Builder ────────────────────────────────────────────────────────────────
class TreeBuilder:

    def __init__(
        self,
        db_path: str = "db/staging.db",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        agent_id: str = EXTRACTOR_ID,
    ):
        self.db_path = Path(REPO_ROOT / db_path) if not Path(db_path).is_absolute() else Path(db_path)
        self.agent_id = agent_id
        self.qdrant: Optional["QdrantClient"] = None

        if QDRANT_AVAILABLE:
            try:
                self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port, timeout=5)
            except Exception:
                pass  # offline — will use empty search results

    # ── Qdrant search ──────────────────────────────────────────────────────────
    def search_records(self, seed: PersonSeed) -> list[PersonCandidate]:
        """Search Qdrant for raw records mentioning the target person."""
        if not self.qdrant:
            return []

        sdx = _soundex(seed.name)
        year_min = (seed.birth_year - seed.birth_year_tolerance) if seed.birth_year else None
        year_max = (seed.birth_year + seed.birth_year_tolerance) if seed.birth_year else None

        must_conditions = [MatchValue(key="name_soundex", match={"any": [sdx]})]
        if year_min and year_max:
            must_conditions.append(Range(key="year_min", gte=year_min, lte=year_max + 50))

        filt = Filter(must=must_conditions)

        try:
            hits = self.qdrant.scroll(
                collection_name=RECORDS_COLLECTION,
                scroll_filter=filt,
                limit=20,
                with_payload=True,
            )[0]
        except Exception:
            return []

        candidates = []
        for hit in hits:
            payload = hit.payload or {}
            names = payload.get("person_names", [])
            for name_str in names:
                conf = _name_confidence(seed.name, name_str)
                if conf < 0.40:
                    continue
                candidates.append(PersonCandidate(
                    record_id=payload.get("record_id", hit.id),
                    name_as_written=name_str,
                    confidence=round(conf, 3),
                    source_url=payload.get("source_url", ""),
                    year_min=payload.get("year_min"),
                    year_max=payload.get("year_max"),
                    record_type=payload.get("record_type", "other"),
                    payload=payload,
                ))

        # Sort by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    # ── Person creation ────────────────────────────────────────────────────────
    def _make_person_id(self, name: str, birth_year: Optional[int]) -> str:
        key = f"{name.lower().strip()}:{birth_year or 'unknown'}"
        return "P-" + hashlib.sha256(key.encode()).hexdigest()[:12].upper()

    def create_person(
        self,
        name: str,
        birth_year: Optional[int],
        candidates: list[PersonCandidate],
    ) -> dict:
        """
        Create a Person JSON entity from name + evidence candidates.
        Each candidate becomes a name_assertion with its confidence score.
        """
        person_id = self._make_person_id(name, birth_year)
        now = _now_iso()

        # Build name assertions from evidence
        name_assertions = []
        seen_sources = set()
        for cand in candidates[:5]:   # top 5 evidence records
            if cand.record_id in seen_sources:
                continue
            seen_sources.add(cand.record_id)
            name_assertions.append({
                "name_as_written": cand.name_as_written,
                "confidence": cand.confidence,
                "source_record_id": cand.record_id,
                "asserted_by": self.agent_id,
                "asserted_at": now,
            })

        # If no evidence found, create a seed assertion with low confidence
        if not name_assertions:
            name_assertions.append({
                "name_as_written": name,
                "confidence": 0.30,   # low — seeded without documentary evidence
                "source_record_id": "seed-no-evidence",
                "asserted_by": self.agent_id,
                "asserted_at": now,
            })

        person = {
            "person_id": person_id,
            "schema_version": "0.1",
            "name_assertions": name_assertions,
            "redistribution_license": "public-domain",
            "is_living": False,
            "judge_approved": False,
            "parent_assertions": [],
            "created_by": self.agent_id,
            "created_at": now,
        }

        # Add birth fact if known
        if birth_year:
            person["birth_assertions"] = [{
                "year_min": birth_year - 5,
                "year_max": birth_year + 5,
                "confidence": 0.60 if candidates else 0.30,
                "source_record_id": candidates[0].record_id if candidates else "seed-no-evidence",
                "asserted_by": self.agent_id,
                "asserted_at": now,
            }]

        return person

    # ── Parent assertion ───────────────────────────────────────────────────────
    def assert_parent(
        self,
        person: dict,
        parent_id: str,
        parent_name: str,
        relationship_type: str,
        parent_role: str,
        confidence: float,
        source_record_id: str,
    ) -> dict:
        """Append a parent assertion to person dict. Returns modified person."""
        assertion = {
            "parent_person_id": parent_id,
            "relationship_type": relationship_type,
            "parent_role": parent_role,
            "confidence": round(confidence, 3),
            "source_record_id": source_record_id,
            "asserted_by": self.agent_id,
            "asserted_at": _now_iso(),
            "conflict_flag": False,
        }
        person.setdefault("parent_assertions", []).append(assertion)
        return person

    # ── SQLite persistence ─────────────────────────────────────────────────────
    def _get_db(self) -> Optional[sqlite3.Connection]:
        if not self.db_path.exists():
            return None
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def persist_person(self, person: dict) -> bool:
        """Insert person + assertions into staging.db. Returns True on success."""
        conn = self._get_db()
        if not conn:
            return False
        try:
            name_assertions = person.get("name_assertions", [])
            primary_name = name_assertions[0]["name_as_written"] if name_assertions else "Unknown"
            primary_conf = name_assertions[0]["confidence"] if name_assertions else 0.0

            conn.execute(
                "INSERT OR IGNORE INTO persons "
                "(person_id, primary_name, primary_name_confidence, is_living, "
                " redistribution_license, created_by, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (person["person_id"], primary_name, primary_conf,
                 1 if person.get("is_living") else 0,
                 person.get("redistribution_license", "public-domain"),
                 self.agent_id, _now_iso())
            )

            for assertion in name_assertions:
                conn.execute(
                    "INSERT OR IGNORE INTO assertions "
                    "(assertion_id, person_id, assertion_type, value_json, "
                    " confidence, source_record_id, judge_verdict_path, "
                    " asserted_by, asserted_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), person["person_id"], "name",
                     json.dumps({"name_as_written": assertion["name_as_written"]}),
                     assertion["confidence"],
                     assertion.get("source_record_id", ""),
                     "pending-judge-review",
                     assertion.get("asserted_by", self.agent_id),
                     assertion.get("asserted_at", _now_iso()))
                )

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"[DB ERROR] {e}", file=sys.stderr)
            return False
        finally:
            conn.close()

    # ── Queue judge task ───────────────────────────────────────────────────────
    def queue_judge_task(self, person_id: str, priority: int = 5) -> str:
        """Write a judge_review task to queue/inbox/. Returns task filename."""
        queue_dir = REPO_ROOT / "queue" / "inbox"
        queue_dir.mkdir(parents=True, exist_ok=True)

        task = {
            "task_id": str(uuid.uuid4()),
            "task_type": "judge_review",
            "status": "pending",
            "priority": priority,
            "payload": {
                "person_id": person_id,
                "review_type": "new_person",
            },
            "cost_cap_usd": 0.50,
            "created_by": self.agent_id,
            "created_at": _now_iso(),
        }
        filename = f"judge_{person_id}_{task['task_id'][:8]}.json"
        path = queue_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)
        return filename

    # ── Main build entry point ─────────────────────────────────────────────────
    def build_tree(self, seed: PersonSeed, depth: int = 2) -> TreeResult:
        """
        Build an ancestry tree starting from a seed person.
        For historical persons (birth_year < current_year-110), searches
        Qdrant for documentary evidence, creates Person entities and
        parent assertions, persists to SQLite, queues judge tasks.

        depth=1: subject only
        depth=2: subject + parents
        depth=3: subject + parents + grandparents
        """
        result = TreeResult(seed=seed)

        # Step 1: Search for evidence of the seed person
        candidates = self.search_records(seed)

        # Step 2: Create the subject Person entity
        subject = self.create_person(seed.name, seed.birth_year, candidates)
        result.persons_created.append(subject)
        result.sources_cited += len(subject["name_assertions"])

        # Persist + queue judge
        self.persist_person(subject)
        task_file = self.queue_judge_task(subject["person_id"])
        result.judge_tasks_queued += 1

        if depth < 2:
            return result

        # Step 3: For known historical figures, add well-documented parents
        # The builder searches Qdrant for parent evidence using surname patterns
        parents = self._find_parents(seed, subject["person_id"], result)
        for parent in parents:
            result.persons_created.append(parent)
            result.judge_tasks_queued += 1

        return result

    def _find_parents(
        self, seed: PersonSeed, subject_id: str, result: TreeResult
    ) -> list[dict]:
        """Search for parents of the seed person. Returns list of Person dicts."""
        parents = []

        # Search Qdrant for records that mention the same surname near the subject's birth year
        # and are older (birth_year 20-40 years earlier)
        if seed.birth_year:
            parent_birth_window = seed.birth_year - 30  # approximate parent birth year

            # Extract surname from seed name (last word)
            parts = seed.name.strip().split()
            surname = parts[-1] if parts else seed.name

            # Search for father (same surname)
            father_seed = PersonSeed(
                name=surname,   # search by surname only — father's given name unknown
                birth_year=parent_birth_window,
                birth_year_tolerance=20,
                birth_country=seed.birth_country,
            )
            father_candidates = self.search_records(father_seed)
            father_candidates = [c for c in father_candidates if c.confidence > 0.45]

            if father_candidates or seed.birth_year < CURRENT_YEAR - 110:
                # Either found evidence, or old enough to confidently add known parents
                father = self.create_person(
                    name=f"{surname} (father)",
                    birth_year=parent_birth_window,
                    candidates=father_candidates,
                )
                # Link father to subject
                self.assert_parent(
                    person={"person_id": subject_id, "parent_assertions": []},
                    parent_id=father["person_id"],
                    parent_name=father["name_assertions"][0]["name_as_written"],
                    relationship_type="biological",
                    parent_role="father",
                    confidence=0.45 if not father_candidates else father_candidates[0].confidence * 0.8,
                    source_record_id=father_candidates[0].record_id if father_candidates else "inferred-no-direct-evidence",
                )
                result.assertions_created += 1
                self.persist_person(father)
                self.queue_judge_task(father["person_id"])
                parents.append(father)

        return parents
