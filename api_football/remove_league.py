"""
remove_league.py

Search for and remove a specific competition from leagues_config.json —
so it's no longer included in future pull_data.py runs.

USAGE:
    python remove_league.py "search text"

    Searches both country names and competition names (case-insensitive).
    Shows matches, lets you pick which to remove. Optionally also deletes
    the already-pulled CSV files for that competition, if you want a
    fully clean removal rather than just stopping future updates.
"""

import json
import os
import sys
import glob
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")


def main():
    if len(sys.argv) < 2:
        print('Usage: python remove_league.py "search text"')
        return

    query = " ".join(sys.argv[1:]).lower()

    if not os.path.exists(CONFIG_PATH):
        print(f"{CONFIG_PATH} not found.")
        return

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    matches = []
    for country, comps in config.items():
        for i, comp in enumerate(comps):
            if query in country.lower() or query in comp.get("name", "").lower():
                matches.append((country, i, comp))

    if not matches:
        print(f"No competitions found matching '{query}'.")
        return

    print(f"{len(matches)} match(es):\n")
    for idx, (country, i, comp) in enumerate(matches, 1):
        seasons = comp.get("seasons", comp.get("season"))
        print(f"  [{idx}] {country} — {comp.get('name')} (id {comp['league_id']}, seasons: {seasons})")

    choice = input("\nPick number to remove, or Enter to cancel: ").strip()
    if not (choice.isdigit() and 1 <= int(choice) <= len(matches)):
        print("Cancelled — nothing removed.")
        return

    country, i, comp = matches[int(choice) - 1]
    league_id = comp["league_id"]
    name = comp.get("name")

    config[country].pop(i)
    if not config[country]:
        del config[country]

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nRemoved: {country} — {name} (id {league_id})")
    print(f"Saved to {CONFIG_PATH}")
    print("It will no longer be included in future pull_data.py runs.")

    # Match filenames where league_id appears as an EXACT token — i.e.
    # "..._91_2025.csv" — not as a substring of a longer id like "391" or
    # "991". A loose glob (*91_*.csv) would match both and risk deleting
    # completely unrelated leagues' data.
    id_pattern = re.compile(rf"(^|_){re.escape(str(league_id))}_\d{{4}}\.csv$")
    existing_files = []
    for folder in ("standings", "fixtures"):
        for path in glob.glob(os.path.join(SCRIPT_DIR, "data", folder, "*.csv")):
            if id_pattern.search(os.path.basename(path)):
                existing_files.append(path)

    if existing_files:
        print(f"\nFound {len(existing_files)} already-pulled file(s) for this competition:")
        for f in existing_files:
            print(f"  {f}")
        confirm = input("Delete these too, for a fully clean removal? (y/n): ").strip().lower()
        if confirm == "y":
            for f in existing_files:
                os.remove(f)
            print(f"Deleted {len(existing_files)} file(s).")
        else:
            print("Left in place — they just won't be updated on future runs.")


if __name__ == "__main__":
    main()
