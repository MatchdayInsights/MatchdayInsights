"""
apply_competition_classification.py

Reads your filled-in competition_classification.csv and merges the
type/tier answers back into leagues_config.json, adding "type" and
"tier" keys to each competition entry so get_competition_info() in
run_ratings.py can read them directly instead of guessing from names.

Validates as it goes: flags any row you left blank, any type value
that isn't one of the five allowed values, and any league-type row
missing a tier - prints all issues at once rather than stopping at the
first one, so you can fix everything in one pass rather than
discovering problems one at a time across repeated runs.

Usage:
    python apply_competition_classification.py
"""

import csv
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
CSV_PATH = os.path.join(SCRIPT_DIR, "competition_classification.csv")

VALID_TYPES = {"league", "cup", "supercup", "continental", "global", "remove"}


def main():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    errors = []
    for i, row in enumerate(rows, start=2):  # start=2: row 1 is the header
        comp_type = row["type"].strip().lower()
        tier = row["tier"].strip()

        if not comp_type:
            errors.append(f"  Row {i} ({row['country']} / {row['name']}): 'type' is blank")
            continue

        if comp_type not in VALID_TYPES:
            errors.append(
                f"  Row {i} ({row['country']} / {row['name']}): "
                f"'type'={comp_type!r} is not one of {sorted(VALID_TYPES)}"
            )
            continue

        if comp_type == "league" and not tier:
            errors.append(f"  Row {i} ({row['country']} / {row['name']}): type=league but 'tier' is blank")
        elif comp_type not in ("league", "remove") and tier:
            errors.append(
                f"  Row {i} ({row['country']} / {row['name']}): "
                f"type={comp_type} but 'tier'={tier!r} is set - tier should only be filled for type=league"
            )
        elif tier and not tier.isdigit():
            errors.append(f"  Row {i} ({row['country']} / {row['name']}): 'tier'={tier!r} is not a number")

    if errors:
        print(f"{len(errors)} issue(s) found - fix these in competition_classification.csv and re-run:\n")
        for e in errors:
            print(e)
        return

    with open(CONFIG_PATH, encoding="utf-8") as f:
        leagues = json.load(f)

    lookup = {int(row["league_id"]): row for row in rows}

    updated = 0
    removed = []
    for country in list(leagues.keys()):
        kept_comps = []
        for comp in leagues[country]:
            row = lookup.get(comp["league_id"])
            if row is None:
                print(f"  WARNING: {country} / {comp['name']} (league_id={comp['league_id']}) "
                      f"not found in classification CSV - left unclassified.")
                kept_comps.append(comp)
                continue

            comp_type = row["type"].strip().lower()
            if comp_type == "remove":
                removed.append(f"{country} / {comp['name']} (league_id={comp['league_id']})")
                continue  # dropped entirely - not added back to kept_comps

            comp["type"] = comp_type
            if comp["type"] == "league":
                comp["tier"] = int(row["tier"].strip())
            kept_comps.append(comp)
            updated += 1

        leagues[country] = kept_comps

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(leagues, f, indent=2, ensure_ascii=False)

    print(f"\nUpdated {updated} competition entries in {CONFIG_PATH} with type/tier.")
    if removed:
        print(f"Removed {len(removed)} competition(s) entirely:")
        for r in removed:
            print(f"  - {r}")


if __name__ == "__main__":
    main()
