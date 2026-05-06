"""Initialize OpenGenealogyAI SQLite staging database."""
import sqlite3, sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "staging.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def init():
    if DB_PATH.exists():
        print(f"Database already exists: {DB_PATH}")
        print("To reinitialize, delete the file first.")
        return

    print(f"Creating database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    # Verify
    conn = sqlite3.connect(DB_PATH)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    print(f"Tables created: {[t[0] for t in tables]}")
    print("Database ready.")

if __name__ == "__main__":
    init()
