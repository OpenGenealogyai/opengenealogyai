# Vector Database Architecture

**Product**: OpenGenealogyAI  
**Version**: 0.1  
**DB**: Qdrant (self-hosted on Omen, RTX 5080 + 128GB RAM)

---

## Why Qdrant

- Self-hosted, free, no data leaves the machine during development
- Native hybrid search (dense + sparse vectors in one query)
- Payload filtering: filter by country, year range, record_type before vector similarity
- Strong Python client, active maintenance
- Migration path: qdrant-client works identically against Qdrant Cloud
- RTX 5080 can accelerate embedding inference via Ollama (avoids OpenAI API cost at scale)

---

## Collections

### `persons_v01` (primary)

Stores Person entities for semantic search and genealogy tree building.

| Parameter | Value |
|-----------|-------|
| vector_size | 1536 (text-embedding-3-small) |
| distance | Cosine |
| on_disk | true (128GB RAM, keep vectors on disk for large datasets) |

**Payload fields (indexed for filtering):**

| Field | Type | Index | Purpose |
|-------|------|-------|---------|
| person_id | keyword | yes | UUID lookup |
| country_code | keyword | yes | Filter by country |
| birth_year_min | integer | yes | Date range filter |
| birth_year_max | integer | yes | Date range filter |
| redistribution_license | keyword | yes | Tier-1 vs Tier-2 gate |
| is_living | bool | yes | Privacy gate |
| composite_confidence | float | no | Post-filter ranking |
| name_soundex | keyword | yes | Phonetic pre-filter |
| judge_approved | bool | yes | Only show approved |

### `raw_records_v01` (secondary)

Full-text search on RawRecord transcriptions.

| Parameter | Value |
|-----------|-------|
| vector_size | 1536 |
| distance | Cosine |

**Payload:** record_id, record_type, country_code, year_min, year_max, redistribution_license, is_living_flag

---

## Embedding Strategy

### Name Fields (character n-gram hybrid)

Generic text embeddings fail on historical genealogy names:
- "Lincoln" vs "Linkon" vs "Linkhorn" vs "Lincklaen" — all the same family
- "Bathsheba" — rare name, not in typical embedding training data

**Solution**: character 3-gram embedding + phonetic code stored in payload.

```python
def name_to_ngrams(name: str, n: int = 3) -> str:
    name = name.lower().strip()
    if len(name) < n:
        return name
    return " ".join(name[i:i+n] for i in range(len(name) - n + 1))

# "Lincoln" -> "lin inc nco col col oln"
# Embed this string, not "Lincoln" directly
```

**Soundex payload field**: stored alongside embedding for pre-filtering. Query must match Soundex code before cosine similarity is computed.

### Text Fields (transcription)

Standard text-embedding-3-small (1536-dim) on:
- `transcription` field of RawRecord
- Concatenation of name + place + date for Person entities

### Date Fields

NOT embedded. Use Qdrant payload filters only:
```python
filter = Filter(must=[
    FieldCondition(key="birth_year_min", range=Range(gte=1740, lte=1750))
])
```

---

## Search Patterns

### Pattern 1: Fuzzy name search

```python
# Step 1: Soundex pre-filter (fast, eliminates wrong names)
soundex_filter = FieldCondition(key="name_soundex", match=MatchValue(value=soundex("Lincoln")))

# Step 2: n-gram cosine similarity (catches spelling variants)
query_vec = embed(name_to_ngrams("Linkhorn"))
results = client.search("persons_v01", query_vec, query_filter=soundex_filter, limit=20)

# Step 3: Jaro-Winkler tiebreaker on top-20 results
from jellyfish import jaro_winkler_similarity
results.sort(key=lambda r: jaro_winkler_similarity("Linkhorn", r.payload["name"]), reverse=True)
```

### Pattern 2: Geographic + date + name

```python
results = client.search("persons_v01",
    query_vector=embed(name_to_ngrams("Abraham Lincoln")),
    query_filter=Filter(must=[
        FieldCondition(key="country_code", match=MatchValue(value="US")),
        FieldCondition(key="birth_year_min", range=Range(gte=1740, lte=1760)),
        FieldCondition(key="is_living", match=MatchValue(value=False)),
        FieldCondition(key="judge_approved", match=MatchValue(value=True)),
    ]),
    limit=10
)
```

---

## Local Setup

Qdrant runs in Docker on Omen:

```bash
docker pull qdrant/qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v C:/Users/stock/dev/opengenealogyai/db/qdrant:/qdrant/storage \
  qdrant/qdrant
```

Verify: `curl http://localhost:6333/healthz` returns `{"title":"qdrant - vector search engine","version":"..."}`

Python client: `pip install qdrant-client`

---

## Migration to Qdrant Cloud

When local Omen storage or throughput is insufficient:

1. Create collection on Qdrant Cloud (free tier: 1GB)
2. Change `QDRANT_URL` env var from `http://localhost:6333` to cloud URL
3. Add `QDRANT_API_KEY` to .env
4. No code changes required — qdrant-client is API-compatible

---

## Scaling Estimates

| Records | Storage (1536-dim float32) | RAM needed | Notes |
|---------|--------------------------|-----------|-------|
| 1,000 | ~6MB | fits in RAM | MVP target |
| 100,000 | ~600MB | fits in RAM | Phase 2 |
| 10M | ~60GB | needs on_disk=true | Production |
| 100M | ~600GB | Qdrant Cloud | Future |

Omen: 128GB RAM. on_disk=true is default from the start so we never need to re-index.
