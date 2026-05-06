"""
Internet Archive fetcher for OpenGenealogyAI.
Fetches metadata and text content for a given IA identifier.
Produces a raw content dict suitable for ia_to_rawrecord.py.
"""
import json, re, urllib.request, urllib.parse, sys, datetime
from pathlib import Path

IA_BASE = "https://archive.org"
IA_METADATA = f"{IA_BASE}/metadata"
IA_DOWNLOAD = f"{IA_BASE}/download"

def fetch_metadata(identifier: str) -> dict:
    url = f"{IA_METADATA}/{identifier}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def fetch_text(identifier: str) -> str | None:
    """Try to fetch the OCR text or plain text version of the item."""
    meta = fetch_metadata(identifier)
    files = meta.get("files", [])

    # Prefer _djvu.txt (OCR), then _fulltext.txt, then .txt
    for suffix in ["_djvu.txt", "_fulltext.txt", ".txt"]:
        for f in files:
            name = f.get("name", "")
            if name.endswith(suffix):
                url = f"{IA_DOWNLOAD}/{identifier}/{urllib.parse.quote(name)}"
                try:
                    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        text = resp.read().decode("utf-8", errors="replace")
                        return text[:50000]  # Limit to 50KB
                except Exception:
                    continue
    return None

def fetch_collection_items(collection_id: str, max_items: int = 50) -> list[dict]:
    """
    Search Internet Archive for items in a collection.
    Returns list of {identifier, title, description, year, source_url}.
    """
    query = urllib.parse.urlencode({
        "q": f"collection:{collection_id}",
        "fl": "identifier,title,description,date,subject",
        "rows": max_items,
        "output": "json"
    })
    url = f"{IA_BASE}/advancedsearch.php?{query}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        docs = data.get("response", {}).get("docs", [])
        return [
            {
                "identifier": d.get("identifier", ""),
                "title": d.get("title", ""),
                "description": str(d.get("description", "")),
                "date": d.get("date", ""),
                "subject": d.get("subject", []),
                "source_url": f"{IA_BASE}/details/{d.get('identifier', '')}",
            }
            for d in docs if d.get("identifier")
        ]
    except Exception as e:
        print(f"  Collection fetch error: {e}", file=sys.stderr)
        return []

def main():
    if len(sys.argv) < 2:
        print("Usage: python ia_fetcher.py <ia-identifier>")
        print("       python ia_fetcher.py --collection <collection-id> [--max N]")
        sys.exit(1)

    if sys.argv[1] == "--collection":
        col_id = sys.argv[2]
        max_items = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--max" else 20
        items = fetch_collection_items(col_id, max_items)
        print(json.dumps(items, indent=2))
    else:
        identifier = sys.argv[1]
        try:
            meta = fetch_metadata(identifier)
            text = fetch_text(identifier)
            result = {
                "identifier": identifier,
                "title": meta.get("metadata", {}).get("title", ""),
                "creator": meta.get("metadata", {}).get("creator", ""),
                "date": meta.get("metadata", {}).get("date", ""),
                "source_url": f"{IA_BASE}/details/{identifier}",
                "text_preview": text[:500] if text else None,
                "has_text": text is not None,
            }
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
