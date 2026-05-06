"""
Query Qdrant for person records using fuzzy name + optional geographic/date filters.
Usage: python scripts/query_qdrant.py --name "Abraham Lincoln" --year-range 1740 1760 --country US
"""
import argparse, json, sys, os
from pathlib import Path

def soundex(name: str) -> str:
    """Simple Soundex implementation."""
    name = name.upper().strip()
    if not name:
        return "0000"
    codes = {'BFPV': '1', 'CGJKQSXYZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
    result = name[0]
    prev = ''
    for c in name[1:]:
        code = ''
        for letters, digit in codes.items():
            if c in letters:
                code = digit
                break
        if code and code != prev:
            result += code
        prev = code
        if len(result) == 4:
            break
    return result.ljust(4, '0')

def name_to_ngrams(name: str, n: int = 3) -> list[str]:
    name = name.lower().strip()
    if len(name) < n:
        return [name]
    return [name[i:i+n] for i in range(len(name) - n + 1)]

def main():
    parser = argparse.ArgumentParser(description="Query OpenGenealogyAI Qdrant")
    parser.add_argument("--name", required=True)
    parser.add_argument("--year-range", nargs=2, type=int, metavar=("MIN", "MAX"))
    parser.add_argument("--country", help="ISO 2-letter country code")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    args = parser.parse_args()

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
    except ImportError:
        print("ERROR: qdrant-client not installed. Run: pip install qdrant-client")
        sys.exit(1)

    try:
        from openai import OpenAI
        openai_key = None
        env_path = Path(__file__).parent.parent / ".env"
        with open(env_path) as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    openai_key = line.strip().split("=", 1)[1]
        client_openai = OpenAI(api_key=openai_key)
    except ImportError:
        print("ERROR: openai not installed. Run: pip install openai")
        sys.exit(1)

    # Build query embedding from n-grams
    ngrams = " ".join(name_to_ngrams(args.name))
    try:
        emb = client_openai.embeddings.create(input=ngrams, model="text-embedding-3-small")
        query_vector = emb.data[0].embedding
    except Exception as e:
        print(f"ERROR: Could not generate embedding: {e}")
        sys.exit(1)

    # Build Qdrant filter
    must_conditions = [
        FieldCondition(key="name_soundex", match=MatchValue(value=soundex(args.name))),
        FieldCondition(key="is_living", match=MatchValue(value=False)),
        FieldCondition(key="judge_approved", match=MatchValue(value=True)),
    ]
    if args.year_range:
        must_conditions.append(
            FieldCondition(key="birth_year_min", range=Range(gte=args.year_range[0]))
        )
        must_conditions.append(
            FieldCondition(key="birth_year_max", range=Range(lte=args.year_range[1]))
        )
    if args.country:
        must_conditions.append(
            FieldCondition(key="country_code", match=MatchValue(value=args.country))
        )

    qdrant = QdrantClient(url=args.qdrant_url)
    try:
        results = qdrant.search(
            collection_name="persons_v01",
            query_vector=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=args.limit,
            with_payload=True
        )
        print(f"Results for '{args.name}' (Soundex: {soundex(args.name)}):")
        for r in results:
            print(f"  [{r.score:.4f}] {r.payload.get('person_id')} - {r.payload.get('name')}")
            print(f"           born ~{r.payload.get('birth_year_min')} | confidence {r.payload.get('composite_confidence', '?')}")
    except Exception as e:
        print(f"Query error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
