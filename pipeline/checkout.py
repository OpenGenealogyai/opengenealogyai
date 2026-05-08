"""
Genealogy Embeddings Checkout System

Usage:
  python -m pipeline.checkout list                          # show available collections
  python -m pipeline.checkout list --mine                   # show your checkouts
  python -m pipeline.checkout list --all                    # show everything including completed
  python -m pipeline.checkout claim <id> [<id2> ...]        # claim one or more collections
  python -m pipeline.checkout status                        # show all active checkouts
  python -m pipeline.checkout progress <id> <pct>          # update % complete (0-100)
  python -m pipeline.checkout submit <id>                   # mark as submitted
  python -m pipeline.checkout release <id>                  # release without completing
  python -m pipeline.checkout info <id>                     # full detail on one collection

Contributor identity is set via .env:
  CONTRIBUTOR_NAME=Garlon Maxwell
  CONTRIBUTOR_EMAIL=garlonmaxwell@gmail.com
  CONTRIBUTOR_URL=https://opengenealogyai.org
"""

import json, os, sys, datetime, argparse
from pathlib import Path

CATALOG_FILE   = Path(__file__).parent.parent / "catalog" / "collections.json"
CHECKOUT_FILE  = Path(__file__).parent.parent / "catalog" / "checkouts.json"
CHECKOUT_DAYS  = int(os.environ.get("CHECKOUT_DAYS", "30"))

CONTRIBUTOR_NAME  = os.environ.get("CONTRIBUTOR_NAME",  "Anonymous")
CONTRIBUTOR_EMAIL = os.environ.get("CONTRIBUTOR_EMAIL", "")
CONTRIBUTOR_URL   = os.environ.get("CONTRIBUTOR_URL",   "")


# ── File I/O ───────────────────────────────────────────────────────────────────

def _load_catalog() -> list[dict]:
    return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))


def _load_checkouts() -> list[dict]:
    if not CHECKOUT_FILE.exists():
        return []
    return json.loads(CHECKOUT_FILE.read_text(encoding="utf-8"))


def _save_checkouts(checkouts: list[dict]):
    CHECKOUT_FILE.parent.mkdir(exist_ok=True)
    CHECKOUT_FILE.write_text(json.dumps(checkouts, indent=2), encoding="utf-8")


def _save_catalog(catalog: list[dict]):
    CATALOG_FILE.write_text(json.dumps(catalog, indent=2), encoding="utf-8")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.date.today().isoformat()


def _expiry(days: int = CHECKOUT_DAYS) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _is_expired(checkout: dict) -> bool:
    exp = checkout.get("expires", "")
    if not exp:
        return False
    return datetime.date.today().isoformat() > exp


def _resource_icon(rtype: str) -> str:
    return {"gpu_intensive": "[GPU]   ", "cpu_scraping": "[Scrape]",
            "cpu_processing": "[CPU]   ", "lightweight": "[Light] "}.get(rtype, rtype)


def _status_icon(status: str) -> str:
    return {"available": "[AVAIL]", "checked_out": "[OUT]  ", "completed": "[DONE] ",
            "hold": "[HOLD] ", "partial": "[PART] "}.get(status, "[?]    ")


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list(args):
    catalog   = _load_catalog()
    checkouts = _load_checkouts()
    checked_ids = {c["collection_id"] for c in checkouts if c.get("status") == "active"}

    show_mine = getattr(args, "mine", False)
    show_all  = getattr(args, "all",  False)

    print(f"\n{'-'*80}")
    print(f"  OpenGenealogyAI -- Collection Catalog")
    print(f"  Contributor: {CONTRIBUTOR_NAME} <{CONTRIBUTOR_EMAIL}>")
    print(f"{'-'*80}\n")

    groups: dict[str, list] = {}
    for col in catalog:
        parent = col.get("parent", col["id"])
        groups.setdefault(parent, []).append(col)

    for parent, cols in groups.items():
        for col in cols:
            status = col.get("status", "available")
            if show_mine:
                co = next((c for c in checkouts if c["collection_id"] == col["id"]
                           and c.get("contributor_name") == CONTRIBUTOR_NAME), None)
                if not co:
                    continue
            elif not show_all and status not in ("available",):
                continue

            icon   = _status_icon(status)
            rtype  = _resource_icon(col.get("resource_type", ""))
            recs   = f"{col.get('estimated_records', 0):,}"
            hrs    = col.get("estimated_hours", "?")
            chunk  = f"  [chunk {col['chunk_number']}/{col['chunk_total']}]" if col.get("chunk_number") else ""

            checked_by = ""
            if status == "checked_out":
                co = next((c for c in checkouts if c["collection_id"] == col["id"]), None)
                if co:
                    checked_by = f"  → {co['contributor_name']} (expires {co['expires']})"

            print(f"  {icon} {col['id']:<40} {rtype:<14} ~{recs:>12} records  ~{hrs}h{chunk}")
            print(f"       {col['name']}")
            if checked_by:
                print(f"       {checked_by}")
            if col.get("notes"):
                print(f"       NOTE:  {col['notes']}")
            print()

    total_available = sum(1 for c in catalog if c.get("status") == "available")
    total_checked   = sum(1 for c in catalog if c.get("status") == "checked_out")
    total_done      = sum(1 for c in catalog if c.get("status") == "completed")
    print(f"{'-'*80}")
    print(f"  {total_available} available  |  {total_checked} checked out  |  {total_done} completed\n")


def cmd_claim(args):
    ids       = args.ids
    catalog   = _load_catalog()
    checkouts = _load_checkouts()

    if not CONTRIBUTOR_NAME or CONTRIBUTOR_NAME == "Anonymous":
        print("ERROR: Set CONTRIBUTOR_NAME in your .env file before claiming.")
        print("  CONTRIBUTOR_NAME=Your Full Name")
        sys.exit(1)

    claimed = []
    for col_id in ids:
        col = next((c for c in catalog if c["id"] == col_id), None)
        if not col:
            print(f"  SKIP '{col_id}' not found in catalog")
            continue
        if col.get("status") == "hold":
            print(f"  SKIP '{col_id}' is on HOLD — {col.get('notes','')}")
            continue
        if col.get("status") == "checked_out":
            co = next((c for c in checkouts if c["collection_id"] == col_id
                       and c.get("status") == "active"), None)
            if co and not _is_expired(co):
                print(f"  SKIP '{col_id}' already checked out by {co['contributor_name']} until {co['expires']}")
                continue
        if col.get("status") == "completed":
            print(f"  SKIP '{col_id}' already completed")
            continue

        expiry = _expiry()
        col["status"]          = "checked_out"
        col["checked_out_by"]  = CONTRIBUTOR_NAME
        col["checked_out_date"] = _today()
        col["expires"]         = expiry
        col["records_completed"] = 0

        checkouts.append({
            "collection_id":    col_id,
            "collection_name":  col["name"],
            "contributor_name": CONTRIBUTOR_NAME,
            "contributor_email": CONTRIBUTOR_EMAIL,
            "contributor_url":  CONTRIBUTOR_URL,
            "checked_out_date": _today(),
            "expires":          expiry,
            "status":           "active",
            "progress_pct":     0,
            "resource_type":    col.get("resource_type"),
            "estimated_records": col.get("estimated_records"),
            "notes":            "",
        })
        claimed.append(col)
        print(f"  OK   Claimed: {col_id}")
        print(f"     {col['name']}")
        print(f"     Expires: {expiry}  |  {_resource_icon(col.get('resource_type',''))}  |  ~{col.get('estimated_hours','?')}h")
        if col.get("notes"):
            print(f"     NOTE:  {col['notes']}")
        print()

    if claimed:
        _save_catalog(catalog)
        _save_checkouts(checkouts)
        print(f"  {len(claimed)} collection(s) checked out to {CONTRIBUTOR_NAME}")
        print(f"  Registry saved to: {CHECKOUT_FILE}")
        print()
        print("  NEXT STEP: Run the pipeline pointed at your checked-out collections.")
        print("  See RESUME.md for launch instructions.")


def cmd_status(args):
    checkouts = _load_checkouts()
    catalog   = _load_catalog()
    active    = [c for c in checkouts if c.get("status") == "active"]

    if not active:
        print("\n  No active checkouts.")
        return

    print(f"\n{'-'*80}")
    print(f"  Active Checkouts -- {CONTRIBUTOR_NAME}")
    print(f"{'-'*80}\n")

    total_records = 0
    for co in active:
        expired = _is_expired(co)
        exp_str = f"EXPIRED {co['expires']}" if expired else f"expires {co['expires']}"
        pct     = co.get("progress_pct", 0)
        bar     = "#" * (pct // 10) + "." * (10 - pct // 10)
        rtype   = _resource_icon(co.get("resource_type", ""))
        recs    = co.get("estimated_records", 0)
        total_records += recs
        print(f"  >>   {co['collection_id']}")
        print(f"     {co['collection_name']}")
        print(f"     [{bar}] {pct}%  |  {rtype}  |  ~{recs:,} records  |  {exp_str}")
        print()

    print(f"  Total: {len(active)} collections  |  ~{total_records:,} records\n")


def cmd_progress(args):
    col_id = args.id
    pct    = int(args.pct)
    if not (0 <= pct <= 100):
        print("ERROR: percentage must be 0–100")
        sys.exit(1)

    checkouts = _load_checkouts()
    catalog   = _load_catalog()

    co = next((c for c in checkouts if c["collection_id"] == col_id
               and c.get("status") == "active"), None)
    if not co:
        print(f"  No active checkout found for '{col_id}'")
        sys.exit(1)

    co["progress_pct"] = pct
    col = next((c for c in catalog if c["id"] == col_id), None)
    if col:
        col["records_completed"] = int(col.get("estimated_records", 0) * pct / 100)

    _save_checkouts(checkouts)
    _save_catalog(catalog)
    print(f"  Updated {col_id}: {pct}% complete")


def cmd_submit(args):
    col_id    = args.id
    checkouts = _load_checkouts()
    catalog   = _load_catalog()

    co = next((c for c in checkouts if c["collection_id"] == col_id
               and c.get("status") == "active"), None)
    if not co:
        print(f"  No active checkout for '{col_id}'")
        sys.exit(1)

    co["status"]         = "submitted"
    co["submitted_date"] = _today()
    co["progress_pct"]   = 100

    col = next((c for c in catalog if c["id"] == col_id), None)
    if col:
        col["status"]         = "completed"
        col["submitted_date"] = _today()
        col["records_completed"] = col.get("estimated_records", 0)

    _save_checkouts(checkouts)
    _save_catalog(catalog)
    print(f"  OK   Submitted: {col_id}")
    print(f"     Credited to: {co['contributor_name']}")
    print(f"     Thank you for your contribution to OpenGenealogyAI!")


def cmd_release(args):
    col_id    = args.id
    checkouts = _load_checkouts()
    catalog   = _load_catalog()

    co = next((c for c in checkouts if c["collection_id"] == col_id
               and c.get("status") == "active"), None)
    if not co:
        print(f"  No active checkout for '{col_id}'")
        sys.exit(1)

    pct = co.get("progress_pct", 0)
    if pct > 0:
        co["status"] = "partial"
        col = next((c for c in catalog if c["id"] == col_id), None)
        if col:
            col["status"] = "available"
            col["checked_out_by"]  = None
            col["checked_out_date"] = None
            col["expires"]         = None
        print(f"  Released '{col_id}' at {pct}% — marked partial, returned to available")
    else:
        co["status"] = "released"
        col = next((c for c in catalog if c["id"] == col_id), None)
        if col:
            col["status"] = "available"
            col["checked_out_by"]  = None
            col["checked_out_date"] = None
            col["expires"]         = None
        print(f"  Released '{col_id}' — returned to available")

    _save_checkouts(checkouts)
    _save_catalog(catalog)


def cmd_info(args):
    catalog = _load_catalog()
    col     = next((c for c in catalog if c["id"] == args.id), None)
    if not col:
        print(f"  Collection '{args.id}' not found")
        sys.exit(1)
    print(json.dumps(col, indent=2))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.checkout",
        description="OpenGenealogyAI Collection Checkout System"
    )
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List collections")
    p_list.add_argument("--mine",  action="store_true", help="Show only your checkouts")
    p_list.add_argument("--all",   action="store_true", help="Include completed/held")

    p_claim = sub.add_parser("claim", help="Claim one or more collections")
    p_claim.add_argument("ids", nargs="+", metavar="ID")

    p_status = sub.add_parser("status", help="Show active checkouts")

    p_prog = sub.add_parser("progress", help="Update completion %")
    p_prog.add_argument("id")
    p_prog.add_argument("pct", type=int)

    p_submit = sub.add_parser("submit", help="Mark collection as submitted")
    p_submit.add_argument("id")

    p_release = sub.add_parser("release", help="Release checkout")
    p_release.add_argument("id")

    p_info = sub.add_parser("info", help="Full detail on one collection")
    p_info.add_argument("id")

    sub.add_parser("page", help="Regenerate catalog/STATUS.md for GitHub")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmds = {
        "list": cmd_list, "claim": cmd_claim, "status": cmd_status,
        "progress": cmd_progress, "submit": cmd_submit,
        "release": cmd_release, "info": cmd_info, "page": cmd_page,
    }
    cmds[args.command](args)


def cmd_page(args):
    generate_status_page()


def generate_status_page():
    """Write catalog/STATUS.md — the public GitHub view of the checkout board."""
    catalog   = _load_catalog()
    checkouts = _load_checkouts()
    now       = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    total_records    = sum(c.get("estimated_records", 0) for c in catalog if c.get("status") != "hold")
    completed_records = sum(c.get("records_completed", 0) for c in catalog if c.get("status") == "completed")
    checked_out_count = sum(1 for c in catalog if c.get("status") == "checked_out")
    available_count   = sum(1 for c in catalog if c.get("status") == "available")
    completed_count   = sum(1 for c in catalog if c.get("status") == "completed")
    pct_done = round(completed_records / total_records * 100, 1) if total_records else 0

    bar_filled = int(pct_done / 5)
    progress_bar = "[" + "#" * bar_filled + "." * (20 - bar_filled) + f"] {pct_done}%"

    # Active checkouts table
    active_rows = []
    for co in checkouts:
        if co.get("status") != "active":
            continue
        pct = co.get("progress_pct", 0)
        mini_bar = "#" * (pct // 10) + "." * (10 - pct // 10)
        active_rows.append(
            f"| {co['collection_id']} | {co['contributor_name']} | "
            f"{co['checked_out_date']} | {co['expires']} | "
            f"`[{mini_bar}]` {pct}% |"
        )

    # Available table
    available_rows = []
    for col in catalog:
        if col.get("status") != "available":
            continue
        recs = f"{col.get('estimated_records',0):,}"
        hrs  = col.get("estimated_hours", "?")
        rtype = col.get("resource_type", "").replace("_", " ")
        chunk = f"chunk {col['chunk_number']}/{col['chunk_total']}" if col.get("chunk_number") else "full"
        available_rows.append(
            f"| {col['id']} | {col.get('geography','?')} | {rtype} | ~{recs} | ~{hrs}h | {chunk} |"
        )

    # Completed table
    completed_rows = []
    for col in catalog:
        if col.get("status") != "completed":
            continue
        co = next((c for c in checkouts if c["collection_id"] == col["id"]
                   and c.get("status") == "submitted"), None)
        contributor = co["contributor_name"] if co else "unknown"
        submitted   = col.get("submitted_date", "?")
        recs = f"{col.get('estimated_records',0):,}"
        completed_rows.append(f"| {col['id']} | {contributor} | {submitted} | {recs} |")

    status_md = f"""\
# OpenGenealogyAI — Collection Checkout Board

> Helping build the world's largest open genealogy vector database.
> **{total_records:,} total records** across all collections.

**Last updated:** {now}

---

## Overall Progress

```
{progress_bar}
```

| Metric | Count |
|--------|-------|
| Collections available to claim | {available_count} |
| Currently checked out | {checked_out_count} |
| Completed | {completed_count} |
| Records embedded so far | {completed_records:,} |

---

## How to Contribute

1. Pick a collection from the **Available** table below
2. Read the [Extraction Rules](../docs/AGENT_EXTRACTION_RULES.md) — required before starting
3. Claim it: `python -m pipeline.checkout claim <collection-id>`
4. Run the pipeline on your machine (see [RESUME.md](../RESUME.md) for setup)
5. Submit: `python -m pipeline.checkout submit <collection-id>`

**You get full attribution** — your name appears in every Qdrant record you embed.

---

## Active Checkouts

| Collection | Contributor | Claimed | Expires | Progress |
|-----------|-------------|---------|---------|----------|
{chr(10).join(active_rows) if active_rows else "| *(none currently checked out)* | | | | |"}

---

## Available — Claim One

| Collection ID | Geography | Type | Records | Est. Time | Chunk |
|--------------|-----------|------|---------|-----------|-------|
{chr(10).join(available_rows) if available_rows else "| *(all collections claimed)* | | | | | |"}

---

## Completed

| Collection | Contributor | Submitted | Records |
|-----------|-------------|-----------|---------|
{chr(10).join(completed_rows) if completed_rows else "| *(none completed yet)* | | | |"}

---

*This file is auto-generated by `python -m pipeline.checkout page`. Do not edit manually.*
"""

    out = Path(__file__).parent.parent / "catalog" / "STATUS.md"
    out.write_text(status_md, encoding="utf-8")
    print(f"Status page written to: {out}")
    print(f"  {available_count} available  |  {checked_out_count} checked out  |  {completed_count} completed")


if __name__ == "__main__":
    main()
