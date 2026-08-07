"""
migrate_config.py

ONE-TIME script. Upgrades any old-format entries in leagues_config.json
(single "season": 2025) to the new format ("seasons": [2024, 2025]) by
looking up each league's real season dates in leagues_master.json and
recomputing which seasons cover 1/1/2025 through today.

Does NOT touch entries that are already in the new "seasons" format —
safe to run even if your config is a mix of old and new entries.

USAGE:
    python migrate_config.py
"""

import json
import os
from build_config import seasons_covering_range  # reuse the exact same logic

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")


def main():
    with open(MASTER_PATH, encoding="utf-8") as f:
        master = json.load(f)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    # Index master list by league_id for fast lookup
    by_id = {entry["league"]["id"]: entry for entry in master}

    upgraded = 0
    already_new = 0
    not_found = 0

    for country, comps in config.items():
        for comp in comps:
            if "seasons" in comp:
                already_new += 1
                continue

            league_id = comp["league_id"]
            master_entry = by_id.get(league_id)
            if not master_entry:
                print(f"  WARNING: league_id {league_id} ({comp.get('name')}) not found in leagues_master.json — leaving as-is")
                not_found += 1
                continue

            new_seasons = seasons_covering_range(master_entry.get("seasons", []))
            old_season = comp.pop("season")
            comp["seasons"] = new_seasons if new_seasons else [old_season]
            upgraded += 1

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nUpgraded: {upgraded}")
    print(f"Already new format: {already_new}")
    print(f"Not found in master list (left unchanged): {not_found}")
    print(f"Saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
