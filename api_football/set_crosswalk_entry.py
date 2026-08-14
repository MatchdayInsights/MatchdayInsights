"""
set_crosswalk_entry.py

Resolves ONE club directly from the command line — no need to step
through the interactive build_crosswalk.py review to reach it. Supports
one OR MULTIPLE linked identities (for clubs that changed team_id due to
rebrand/refounding, e.g. Reggina) in a single command.

USAGE:
    Single identity:
        python set_crosswalk_entry.py "Some Club" "Exact API Name"

    Multiple linked identities (e.g. Reggina's bankruptcy/refounding):
        python set_crosswalk_entry.py "Reggina 1914" "La Fenice Amaranto" "Reggina"

Each name is looked up in api_football_names.json. If a name matches more
than one real team, you'll be asked which one, right in the terminal.
If an already-resolved (non-null) entry exists for this club, you'll be
asked to confirm before it gets overwritten.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_NAMES_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")


def resolve_one(query, api_data):
    matches = {n: e for n, e in api_data.items() if query.lower() == n.lower()}

    if not matches:
        substring_matches = [n for n in api_data if query.lower() in n.lower()]
        if not substring_matches:
            print(f"  No name matching '{query}' found in api_football_names.json at all.")
            return None
        print(f"  No exact match for '{query}'. Did you mean one of these?")
        for i, n in enumerate(substring_matches[:10], 1):
            print(f"    [{i}] {n}")
        choice = input("  Pick a number, or Enter to cancel: ").strip()
        if not (choice.isdigit() and 1 <= int(choice) <= len(substring_matches[:10])):
            print("  Cancelled.")
            return None
        exact_name = substring_matches[int(choice) - 1]
    else:
        exact_name = list(matches.keys())[0]

    entries = api_data.get(exact_name, [])
    if len(entries) == 1:
        return {"name": exact_name, "team_id": entries[0]["team_id"]}

    print(f"  '{exact_name}' matches {len(entries)} different real teams — which one?")
    for i, e in enumerate(entries, 1):
        league_str = ", ".join(e["leagues"][:2])
        print(f"    [{i}] {exact_name}  — {league_str}")
    choice = input("  Pick a number, or Enter to cancel: ").strip()
    if not (choice.isdigit() and 1 <= int(choice) <= len(entries)):
        print("  Cancelled.")
        return None
    return {"name": exact_name, "team_id": entries[int(choice) - 1]["team_id"]}


def main():
    if len(sys.argv) < 3:
        print('Usage: python set_crosswalk_entry.py "Existing Club Name" "Identity 1" ["Identity 2" ...]')
        return

    old_name = sys.argv[1]
    identity_queries = sys.argv[2:]

    if not os.path.exists(API_NAMES_PATH):
        print(f"{API_NAMES_PATH} not found. Run collect_api_names.py first.")
        return

    with open(API_NAMES_PATH, encoding="utf-8") as f:
        api_data = json.load(f)

    crosswalk = {}
    if os.path.exists(CROSSWALK_PATH):
        with open(CROSSWALK_PATH, encoding="utf-8") as f:
            crosswalk = json.load(f)

    if old_name in crosswalk and crosswalk[old_name] is not None:
        print(f"'{old_name}' already has a value in crosswalk.json:")
        print(f"  {crosswalk[old_name]}")
        confirm = input("Overwrite it? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled — nothing changed.")
            return

    resolved = []
    for q in identity_queries:
        print(f"\nResolving '{q}'...")
        r = resolve_one(q, api_data)
        if r is None:
            print(f"\nCouldn't resolve '{q}' — nothing saved.")
            return
        resolved.append(r)
        print(f"  -> {r['name']} (team_id: {r['team_id']})")

    crosswalk[old_name] = resolved if len(resolved) > 1 else resolved[0]

    with open(CROSSWALK_PATH, "w", encoding="utf-8") as f:
        json.dump(crosswalk, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\nSaved '{old_name}' with {len(resolved)} identity(ies) to {CROSSWALK_PATH}")


if __name__ == "__main__":
    main()
