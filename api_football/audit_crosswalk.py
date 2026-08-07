"""
audit_crosswalk.py

Checks every ALREADY-DECIDED entry in crosswalk.json against the current
api_football_names.json. Flags anything that was resolved to a plain
string (the old format) where that name is now known to be shared by
MULTIPLE real teams — meaning it was decided before the ambiguity fix
existed, and there's no way to know which specific team was actually
intended (the old code had no team_id to record).

This does NOT try to guess which team was meant — it can't, since that
information was never captured. Instead it offers to remove flagged
entries from crosswalk.json so they go back into the normal review queue
in build_crosswalk.py, where you'll now see the real, correctly-labeled
candidates and can make an informed choice.

Entries already in the new {"name":..., "team_id":...} format are
skipped — those are already properly disambiguated regardless of when
they were decided.

USAGE:
    python audit_crosswalk.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_NAMES_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")


def main():
    if not os.path.exists(API_NAMES_PATH):
        print(f"{API_NAMES_PATH} not found. Run collect_api_names.py first.")
        return
    if not os.path.exists(CROSSWALK_PATH):
        print(f"{CROSSWALK_PATH} not found. Nothing to audit yet.")
        return

    with open(API_NAMES_PATH, encoding="utf-8") as f:
        api_data = json.load(f)
    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)

    flagged = []

    for old_name, value in crosswalk.items():
        if value is None:
            continue  # marked unmatched, not relevant
        if isinstance(value, dict):
            continue  # already properly disambiguated with a team_id, safe regardless of when decided
        entries = api_data.get(value, [])
        if len(entries) > 1:
            flagged.append((old_name, value, entries))

    if not flagged:
        print("Nothing flagged — every plain-string entry in crosswalk.json maps to an unambiguous name.")
        print(f"Checked {len(crosswalk)} total entries.")
        return

    print(f"Checked {len(crosswalk)} total entries.")
    print(f"\n{len(flagged)} entry(ies) were resolved BEFORE the ambiguity fix existed, "
          f"to a name that's actually shared by multiple real teams:\n")

    for old_name, matched_name, entries in flagged:
        print(f"  '{old_name}' -> '{matched_name}'  ({len(entries)} real teams share this name)")
        for e in entries:
            league_str = ", ".join(e["leagues"][:2])
            print(f"      - team_id {e['team_id']}: {league_str}")

    print(f"\nThere's no way to know which specific team was originally intended — "
          f"the old format didn't record team_id.")
    confirm = input(
        f"\nRemove these {len(flagged)} entries from crosswalk.json so they go back into "
        f"the review queue (build_crosswalk.py will show the real, correctly-labeled options)? (y/n): "
    ).strip().lower()

    if confirm == "y":
        for old_name, _, _ in flagged:
            del crosswalk[old_name]
        with open(CROSSWALK_PATH, "w", encoding="utf-8") as f:
            json.dump(crosswalk, f, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"\nRemoved {len(flagged)} entries. Run build_crosswalk.py to re-review them "
              f"with the real candidates now visible.")
    else:
        print("\nNo changes made.")


if __name__ == "__main__":
    main()
