"""
Set up Qdrant locally via Docker and create the persons_v01 and raw_records_v01 collections.
Run once to initialize the development database.
"""
import subprocess, sys, time, json, urllib.request

QDRANT_URL = "http://localhost:6333"
CONTAINER_NAME = "qdrant-opengenealogyai"
STORAGE_PATH = "C:/Users/stock/dev/opengenealogyai/db/qdrant"

def check_docker():
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def start_qdrant():
    # Check if already running
    try:
        with urllib.request.urlopen(f"{QDRANT_URL}/healthz", timeout=3) as resp:
            print("Qdrant already running")
            return True
    except Exception:
        pass

    print("Starting Qdrant via Docker...")
    cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", "6333:6333", "-p", "6334:6334",
        "-v", f"{STORAGE_PATH}:/qdrant/storage",
        "qdrant/qdrant"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if "already in use" in result.stderr:
            subprocess.run(["docker", "start", CONTAINER_NAME], capture_output=True)
        else:
            print(f"Docker error: {result.stderr}")
            return False

    # Wait for Qdrant to be ready
    for i in range(30):
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"{QDRANT_URL}/healthz", timeout=2) as resp:
                print(f"Qdrant ready after {i+1}s")
                return True
        except Exception:
            print(f"  Waiting... {i+1}/30")
    return False

def create_collection(name: str, vector_size: int):
    payload = json.dumps({
        "vectors": {
            "size": vector_size,
            "distance": "Cosine",
            "on_disk": True
        }
    }).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{name}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"  Created collection '{name}': {result}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if "already exists" in body:
            print(f"  Collection '{name}' already exists")
        else:
            print(f"  Error creating '{name}': {body}")

def create_payload_index(collection: str, field: str, field_type: str):
    payload = json.dumps({"field_name": field, "field_schema": field_type}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{collection}/index",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"    Index created: {field} ({field_type})")
    except Exception as e:
        print(f"    Index error {field}: {e}")

def main():
    if not check_docker():
        print("ERROR: Docker not found. Install Docker Desktop.")
        sys.exit(1)

    if not start_qdrant():
        print("ERROR: Could not start Qdrant")
        sys.exit(1)

    print("\nCreating collections...")
    create_collection("persons_v01", 1536)
    create_collection("raw_records_v01", 1536)

    print("\nCreating payload indexes for persons_v01...")
    indexes = [
        ("person_id", "keyword"),
        ("country_code", "keyword"),
        ("birth_year_min", "integer"),
        ("birth_year_max", "integer"),
        ("redistribution_license", "keyword"),
        ("is_living", "bool"),
        ("name_soundex", "keyword"),
        ("judge_approved", "bool"),
    ]
    for field, ftype in indexes:
        create_payload_index("persons_v01", field, ftype)

    print("\nCreating payload indexes for raw_records_v01...")
    for field, ftype in [
        ("record_id", "keyword"),
        ("record_type", "keyword"),
        ("country_code", "keyword"),
        ("year_min", "integer"),
        ("year_max", "integer"),
        ("redistribution_license", "keyword"),
        ("is_living_flag", "bool"),
    ]:
        create_payload_index("raw_records_v01", field, ftype)

    print("\nQdrant setup complete.")
    print(f"Dashboard: http://localhost:6333/dashboard")

if __name__ == "__main__":
    main()
