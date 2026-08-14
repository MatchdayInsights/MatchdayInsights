"""
show_id.py

crosswalk.json only shows club names, not team_ids, which makes it hard
to visually confirm a plain-string entry resolved to the RIGHT team when
a name is shared by multiple real clubs. This resolves and displays the
actual team_id (and full league list) for any entry, regardless of
whether it's stored as a plain string, a disambiguated dict, or a linked
list of multiple identities.

USAGE:
    python show_id.py "search text"

    Searches your crosswalk keys (old names) by substring, shows each
    match's stored value(s) resolved to their real team_id(s) and full
    league list -- so you can visually confirm it's the team you meant.
"""

import json
import os
import sys

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
    if len(sys.argv) < 2:
        print('Usage: python show_id.py "search text"')
        return

    query = " ".join(sys.argv[1:]).lower()

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

    matches = [k for k in crosswalk if query in k.lower()]

    if not matches:
        print(f"No crosswalk entries found containing '{query}'.")
        return

    for old_name in matches:
        value = crosswalk[old_name]
        print(f"\n'{old_name}'")

        if value is None:
            print("  -> marked unmatched")
            continue

        for name, team_id in get_identity_entries(value):
            resolved_id = team_id
            all_leagues_for_name = api_data.get(name, [])

            if resolved_id is None:
                if len(all_leagues_for_name) == 1:
                    resolved_id = all_leagues_for_name[0]["team_id"]
                elif len(all_leagues_for_name) > 1:
                    print(f"  -> '{name}': AMBIGUOUS -- {len(all_leagues_for_name)} different teams "
                          f"share this name, and no team_id is stored. This needs fixing with "
                          f"set_crosswalk_entry.py.")
                    for e in all_leagues_for_name:
                        print(f"       team_id {e['team_id']}: {', '.join(e['leagues'])}")
                    continue
                else:
                    print(f"  -> '{name}': NOT FOUND in api_football_names.json at all "
                          f"(manually-typed, unverified)")
                    continue

            leagues = None
            for e in all_leagues_for_name:
                if str(e["team_id"]) == str(resolved_id):
                    leagues = e["leagues"]
                    break

            print(f"  -> '{name}'  (team_id {resolved_id})")
            if leagues:
                for lg in leagues:
                    print(f"       {lg}")


if __name__ == "__main__":
    main()
