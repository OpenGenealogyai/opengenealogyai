"""Validate all MAXGEN schemas + fixtures. Run after any schema change."""
import json, glob, os
import jsonschema

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=== Schema consts ===")
for s in ["raw-record", "person", "task-queue", "dna"]:
    with open(os.path.join(base, "schemas", s + ".schema.json")) as f:
        sc = json.load(f)
    const = sc["properties"]["schema_version"].get("const", "?")
    title = sc["title"]
    print("  %-11s schema_version const = %s" % (title, const))

print("\n=== Metaschema validity ===")
for s in ["raw-record", "person", "task-queue", "dna"]:
    with open(os.path.join(base, "schemas", s + ".schema.json")) as f:
        sc = json.load(f)
    try:
        jsonschema.Draft202012Validator.check_schema(sc)
        print("  %-11s OK" % s)
    except Exception as e:
        print("  %-11s INVALID: %s" % (s, str(e)[:80]))

print("\n=== Fixtures ===")
pairs = [
    ("person", "schemas/person.schema.json"),
    ("raw-record", "schemas/raw-record.schema.json"),
    ("task-queue", "schemas/task-queue.schema.json"),
]
g_ok = g_fail = 0
for fixdir, sp in pairs:
    with open(os.path.join(base, sp)) as f:
        schema = json.load(f)
    files = glob.glob(os.path.join(base, "test", "fixtures", fixdir, "**", "*.json"), recursive=True)
    ok = fail = 0
    for fp in files:
        try:
            with open(fp) as f:
                jsonschema.validate(json.load(f), schema)
            ok += 1
        except Exception as e:
            fail += 1
            print("  FAIL %s: %s" % (os.path.basename(fp), str(e)[:80]))
    print("  %-11s PASS=%d FAIL=%d" % (fixdir, ok, fail))
    g_ok += ok
    g_fail += fail
print("\nTOTAL fixtures: PASS=%d FAIL=%d" % (g_ok, g_fail))
