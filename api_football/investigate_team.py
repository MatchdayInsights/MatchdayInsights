"""
investigate_team.py

Diagnostic tool for exactly the kind of question that came up with 'Al
Shorta' (team_id=5242, showing up under both Sudan and Iraq): is this
really the SAME club with a genuine cross-border situation, or has
API-Football reused the same numeric team_id for two totally unrelated
real-world clubs?

Give it a team_id and it prints every fixture involving that ID, grouped
by which competition/country it came from, with match counts - a club
genuinely playing in two places will usually show a lopsided distribution
(a handful of guest appearances vs. a full season elsewhere) or a
sensible time pattern; two unrelated clubs sharing an ID by coincidence
will often show two roughly-equal, unrelated-looking blocks of matches
with no plausible connection between them.

Usage:
    python investigate_team.py 5242
"""

import csv
import glob
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(SCRIPT_DIR, "data", "fixtures")
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")


def main():
    if len(sys.argv) != 2:
        print("Usage: python investigate_team.py <team_id>")
        sys.exit(1)
    target_id = sys.argv[1]

    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)
    league_lookup = {}
    for country, comps in leagues_config.items():
        for comp in comps:
            league_lookup[str(comp["league_id"])] = {
                "country": country, "name": comp["name"], "type": comp.get("type", "?"),
            }

    matches = []
    for path in glob.glob(os.path.join(FIXTURES_DIR, "*.csv")):
        filename = os.path.basename(path)
        parts = filename.replace(".csv", "").split("_")
        if len(parts) < 2 or not parts[-2].isdigit():
            continue
        league_id, season = parts[-2], parts[-1]

        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["played"] != "True":
                    continue
                if row["home_team_id"] == target_id or row["away_team_id"] == target_id:
                    is_home = row["home_team_id"] == target_id
                    matches.append({
                        "date": row["date"],
                        "season": season,
                        "league_id": league_id,
                        "opponent": row["away_team"] if is_home else row["home_team"],
                        "home_or_away": "home" if is_home else "away",
                        "score": f"{row['home_score']}-{row['away_score']}",
                        "round": row.get("round", ""),
                    })

    if not matches:
        print(f"No matches found for team_id={target_id} in data/fixtures/.")
        return

    matches.sort(key=lambda m: m["date"])

    # Group by (country, competition_name) for the summary
    from collections import defaultdict
    by_group = defaultdict(list)
    club_name_seen = set()
    for m in matches:
        entry = league_lookup.get(m["league_id"], {"country": "?", "name": f"league_id={m['league_id']}", "type": "?"})
        key = (entry["country"], entry["name"], entry["type"])
        by_group[key].append(m)

    print(f"team_id={target_id}: {len(matches)} total matches across {len(by_group)} competition(s)\n")

    for (country, comp_name, comp_type), group_matches in sorted(by_group.items(), key=lambda x: -len(x[1])):
        dates = sorted(m["date"] for m in group_matches)
        print(f"  {country} / {comp_name} ({comp_type}): {len(group_matches)} matches, "
              f"{dates[0][:10]} to {dates[-1][:10]}")

    print("\nFull chronological match list:")
    for m in matches:
        entry = league_lookup.get(m["league_id"], {"country": "?", "name": f"league_id={m['league_id']}"})
        print(f"  {m['date'][:10]}  {entry['country']:20} {entry['name']:30} "
              f"vs {m['opponent']:25} ({m['home_or_away']}, {m['score']})")


if __name__ == "__main__":
    main()
