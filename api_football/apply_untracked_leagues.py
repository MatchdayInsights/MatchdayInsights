"""
apply_untracked_leagues.py

Combines your filled-in untracked_leagues.csv (tier depth per league)
with the automatically-generated untracked_clubs.json (which club is in
which league) into team_id -> tier_depth_below_deepest_tracked, written
to untracked_club_tiers.json - the file run_ratings.py's
get_starting_position() reads to give a precisely-tiered placeholder
rating instead of the generic "always one level down" assumption.

Validates every row has a tier depth filled in (a positive integer)
before writing anything, listing every problem at once.

Usage:
    python apply_untracked_leagues.py
"""

import csv
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEAGUES_CSV_PATH = os.path.join(SCRIPT_DIR, "untracked_leagues.csv")
CLUBS_JSON_PATH = os.path.join(SCRIPT_DIR, "untracked_clubs.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "untracked_club_tiers.json")


def main():
    with open(LEAGUES_CSV_PATH, encoding="utf-8-sig") as f:
        league_rows = list(csv.DictReader(f))

    errors = []
    league_depth = {}  # league_id (str) -> depth (int)
    for i, row in enumerate(league_rows, start=2):
        league_id = row["league_id"].strip()
        depth = row["tier_depth_below_deepest_tracked"].strip()
        if not depth:
            errors.append(f"  Row {i} ({row['country']} / {row['league_name']}): "
                           f"tier_depth_below_deepest_tracked is blank")
            continue
        if not depth.isdigit() or int(depth) < 1:
            errors.append(f"  Row {i} ({row['country']} / {row['league_name']}): "
                           f"'{depth}' is not a positive whole number")
            continue
        league_depth[league_id] = int(depth)

    if errors:
        print(f"{len(errors)} issue(s) found - fix these in untracked_leagues.csv and re-run:\n")
        for e in errors:
            print(e)
        return

    with open(CLUBS_JSON_PATH, encoding="utf-8") as f:
        club_rows = json.load(f)

    result = {}
    unmatched = 0
    for club in club_rows:
        league_id = str(club["league_id"])
        depth = league_depth.get(league_id)
        if depth is None:
            unmatched += 1
            continue
        result[str(club["team_id"])] = {
            "country": club["country"],
            "league_id": club["league_id"],
            "league_name": club["league_name"],
            "tier_depth_below_deepest_tracked": depth,
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {len(result)} clubs to {OUTPUT_PATH}")
    if unmatched:
        print(f"WARNING: {unmatched} clubs in untracked_clubs.json belonged to a league_id "
              f"not found in untracked_leagues.csv - check nothing got deleted/mismatched between the two files.")


if __name__ == "__main__":
    main()
