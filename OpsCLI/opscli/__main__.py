"""OpsCLI: an intentionally small, standard-library telecom operations CLI."""
import argparse
import json
import os
from pathlib import Path

DATA = Path(os.environ.get("OPSCLI_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))


def load(filename):
    return json.loads((DATA / filename).read_text(encoding="utf-8"))


def save(filename, records):
    (DATA / filename).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def emit(obj):
    print(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(prog="opscli", description="Local telecom operations CLI; JSON output")
    sub = p.add_subparsers(dest="command", required=True)
    specs = {
        "get-incident": [("id", {})],
        "list-incidents": [("--status", {"default": None})],
        "search-incidents": [("query", {})],
        "create-incident": [("--category", {"required": True}), ("--description", {"required": True})],
        "update-status": [("id", {}), ("--status", {"required": True, "choices": ["Open", "In Progress", "Resolved"]})],
        "assign-incident": [("id", {}), ("--owner", {"required": True})],
        "add-note": [("id", {}), ("--text", {"required": True})],
        "search-defects": [("query", {})],
        "incident-stats": [],
        "health": [],
    }
    for name, arguments in specs.items():
        s = sub.add_parser(name)
        for flag, options in arguments:
            s.add_argument(flag, **options)
    a = p.parse_args()
    incidents = load("incidents.json")
    cmd = a.command
    if cmd == "health":
        return emit({"ok": True, "source": "local JSON", "tools": len(specs)})
    if cmd == "search-defects":
        q = a.query.lower()
        return emit([x for x in load("defects.json") if q in (x["key"] + " " + x["summary"]).lower()])
    if cmd == "list-incidents":
        return emit([x for x in incidents if a.status is None or x["status"].lower() == a.status.lower()])
    if cmd == "search-incidents":
        q = a.query.lower()
        return emit([x for x in incidents if q in (x["id"] + " " + x["category"] + " " + x["description"]).lower()])
    if cmd == "incident-stats":
        counts = {}
        for x in incidents:
            counts[x["status"]] = counts.get(x["status"], 0) + 1
        return emit({"total": len(incidents), "by_status": counts})
    if cmd == "create-incident":
        new_id = f"INC{max([int(x['id'][3:]) for x in incidents if x['id'].startswith('INC') and x['id'][3:].isdigit()] or [1000]) + 1}"
        record = {"id": new_id, "category": a.category, "description": a.description, "status": "Open", "assigned_to": "Unassigned", "notes": []}
        incidents.append(record)
        save("incidents.json", incidents)
        return emit(record)
    record = next((x for x in incidents if x["id"].lower() == a.id.lower()), None)
    if record is None:
        emit({"error": "Incident not found", "id": a.id})
        return 1
    if cmd == "get-incident":
        return emit(record)
    if cmd == "update-status":
        record["status"] = a.status
    elif cmd == "assign-incident":
        record["assigned_to"] = a.owner
    elif cmd == "add-note":
        record["notes"].append(a.text)
    save("incidents.json", incidents)
    emit(record)


if __name__ == "__main__":
    raise SystemExit(main())
