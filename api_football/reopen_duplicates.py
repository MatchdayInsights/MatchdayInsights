"""
reopen_duplicates.py

Finds every old_name involved in a DUPLICATE mapping (two different
old_names both pointing at the same real team) and removes them from
crosswalk.json, sending them back into the "needs review" pool — without
touching anything else you've already resolved.

Both names in each duplicate pair get reopened (not just one), so you
have full control to re-decide each independently — keep one as-is and
mark the other 'k', point one at a genuinely different team if it turns
out they're actually different clubs, link them if they really are the
same club worth merging, etc.

After running this, just run build_crosswalk.py normally — since
everything else is already decided, it'll only prompt you for these.

USAGE:
    python reopen_duplicates.py
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
        print(f"{API_NAMES_PATH} not found. Run collect_api_names.py first.")
        return

    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)
    with open(API_NAMES_PATH, encoding="utf-8") as f:
        api_data = json.load(f)

    name_to_id = {}
    for name, entries in api_data.items():
        if len(entries) == 1:
            name_to_id[name] = entries[0]["team_id"]

    team_id_to_old_names = {}
    for old_name, value in crosswalk.items():
        for name, team_id in get_identity_entries(value):
            if not team_id:
                team_id = name_to_id.get(name)
            if team_id:
                team_id_to_old_names.setdefault(team_id, set()).add(old_name)

    duplicates = {tid: names for tid, names in team_id_to_old_names.items() if len(names) > 1}

    if not duplicates:
        print("No duplicates found -- nothing to reopen.")
        return

    to_reopen = sorted(set().union(*duplicates.values()))

    print(f"{len(duplicates)} duplicate team(s), involving {len(to_reopen)} club name(s):\n")
    for tid, names in duplicates.items():
        print(f"  team_id {tid}: {', '.join(sorted(names))}")

    confirm = input(f"\nReopen these {len(to_reopen)} entries for review? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled -- nothing changed.")
        return

    for name in to_reopen:
        del crosswalk[name]

    with open(CROSSWALK_PATH, "w", encoding="utf-8") as f:
        json.dump(crosswalk, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\nRemoved {len(to_reopen)} entries. Run build_crosswalk.py now -- "
          f"it'll only prompt for these, since everything else is already resolved.")


if __name__ == "__main__":
    main()
