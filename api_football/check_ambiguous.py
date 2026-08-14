"""
check_ambiguous.py

Scans EVERY entry in crosswalk.json and reports every one that's a plain
string referencing a name shared by MULTIPLE real teams — i.e. genuinely
ambiguous, not yet disambiguated to a specific team_id. This is the bulk
version of show_id.py: instead of checking one name at a time, this finds
everything that needs set_crosswalk_entry.py in one pass.

Separately reports names that don't exist in api_football_names.json at
all (likely a manually-typed name that was never validated) — a
different problem needing a different fix (search for the real spelling,
or confirm the club genuinely isn't covered).

USAGE:
    python check_ambiguous.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")
API_NAMES_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")


def get_identity_entries(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [(value, None)]
    if isinstance(value, dict):
        return [(value.get("name"), value.get("team_id"))]
    if isinstance(value, list):
        return [(v.get("name"), v.get("team_id")) for v in value if isinstance(v, dict)]
    return []


def main():
    if not os.path.exists(CROSSWALK_PATH):
        print(f"{CROSSWALK_PATH} not found.")
        return
    if not os.path.exists(API_NAMES_PATH):
        print(f"{API_NAMES_PATH} not found.")
        return

    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)
    with open(API_NAMES_PATH, encoding="utf-8") as f:
        api_data = json.load(f)

    ambiguous = []
    not_found = []

    for old_name, value in crosswalk.items():
        for name, team_id in get_identity_entries(value):
            if team_id is not None:
                continue
            entries = api_data.get(name, [])
            if len(entries) > 1:
                ambiguous.append((old_name, name, entries))
            elif len(entries) == 0:
                not_found.append((old_name, name))

    print(f"Checked {len(crosswalk)} crosswalk entries.\n")

    if ambiguous:
        print(f"{'='*70}")
        print(f"AMBIGUOUS -- {len(ambiguous)} entry(ies) need set_crosswalk_entry.py")
        print(f"{'='*70}\n")
        for old_name, name, entries in ambiguous:
            print(f"'{old_name}' -> '{name}'  ({len(entries)} teams share this name)")
            for e in entries:
                league_preview = ', '.join(e['leagues'][:3])
                more = ' ...' if len(e['leagues']) > 3 else ''
                print(f"    team_id {e['team_id']}: {league_preview}{more}")
            print(f"    fix: python set_crosswalk_entry.py \"{old_name}\" \"{name}\"")
            print()
    else:
        print("No ambiguous entries found.")

    if not_found:
        print(f"\n{'='*70}")
        print(f"NOT FOUND AT ALL -- {len(not_found)} entry(ies), likely typos or genuinely uncovered clubs")
        print(f"{'='*70}\n")
        for old_name, name in not_found:
            print(f"  '{old_name}' -> '{name}'")

    print(f"\nSummary: {len(ambiguous)} ambiguous, {len(not_found)} not found, "
          f"{len(crosswalk) - len(ambiguous) - len(not_found)} confirmed safe.")


if __name__ == "__main__":
    main()
