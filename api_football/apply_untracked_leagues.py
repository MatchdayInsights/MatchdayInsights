"""
apply_untracked_leagues.py

Combines your filled-in untracked_leagues.csv (each league's ACTUAL tier
number in that country's pyramid - e.g. 4 for a country's 4th division,
NOT a depth relative to whatever's currently directly tracked, which
would go stale if that changes - or "EXCLUDE" for leagues that shouldn't
feed into ratings at all, e.g. women's/youth/reserve competitions) with
the automatically-generated untracked_clubs.json (which club is in which
league) into team_id -> tier, written to untracked_club_tiers.json - the
file run_ratings.py's get_starting_position() reads to give a
precisely-tiered placeholder rating instead of the generic "always one
level down" assumption.

Validates every row has EITHER a positive-integer tier OR the literal
value "EXCLUDE" or "N/A" filled in (a genuinely blank row is still an
error - forces an explicit decision either way) before writing anything,
listing every problem at once.

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
    excluded_league_ids = set()   # deliberately excluded (e.g. women's/youth)
    no_data_league_ids = set()    # no standings data was ever pulled for this league
    league_tier = {}  # league_id (str) -> tier (int), the league's ACTUAL
                       # tier number in that country's pyramid
    for i, row in enumerate(league_rows, start=2):
        league_id = row["league_id"].strip()
        tier = row["tier"].strip()
        if not tier:
            errors.append(f"  Row {i} ({row['country']} / {row['league_name']}): "
                           f"tier is blank")
            continue
        if tier.upper() == "EXCLUDE":
            excluded_league_ids.add(league_id)
            continue
        if tier.upper() == "N/A":
            no_data_league_ids.add(league_id)
            continue
        if not tier.isdigit() or int(tier) < 1:
            errors.append(f"  Row {i} ({row['country']} / {row['league_name']}): "
                           f"'{tier}' is not a positive whole number (or 'EXCLUDE'/'N/A')")
            continue
        league_tier[league_id] = int(tier)

    if errors:
        print(f"{len(errors)} issue(s) found - fix these in untracked_leagues.csv and re-run:\n")
        for e in errors:
            print(e)
        return

    with open(CLUBS_JSON_PATH, encoding="utf-8") as f:
        club_rows = json.load(f)

    result = {}
    unmatched = 0
    excluded_club_count = 0
    for club in club_rows:
        league_id = str(club["league_id"])
        if league_id in excluded_league_ids or league_id in no_data_league_ids:
            excluded_club_count += 1
            continue
        tier = league_tier.get(league_id)
        if tier is None:
            unmatched += 1
            continue
        result[str(club["team_id"])] = {
            "country": club["country"],
            "league_id": club["league_id"],
            "league_name": club["league_name"],
            "tier": tier,
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {len(result)} clubs to {OUTPUT_PATH}")
    print(f"  ({excluded_club_count} clubs skipped from {len(excluded_league_ids)} "
          f"leagues marked EXCLUDE + {len(no_data_league_ids)} leagues marked N/A)")
    if unmatched:
        print(f"WARNING: {unmatched} clubs in untracked_clubs.json belonged to a league_id "
              f"not found in untracked_leagues.csv - check nothing got deleted/mismatched between the two files.")


if __name__ == "__main__":
    main()
