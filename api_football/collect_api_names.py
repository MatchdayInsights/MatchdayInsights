"""
collect_api_names.py

Scans every CSV in data/standings/ and data/fixtures/ and pulls out every
team API-Football has given you — tracked by team_id, not just name.

WHY team_id matters: two genuinely different real clubs can share an
identical name (e.g. San Marino's "AC Libertas" and an unrelated Croatian
club also called "Libertas"). Tracking by name alone would silently merge
their league labels together, making it look like one club plays in both
countries. Tracking by team_id keeps them correctly separate, while still
letting you search/match by name (the name just now maps to a LIST of
distinct teams, most commonly a list of exactly one).

REQUIRES pull_data.py to have captured team_id/home_team_id/away_team_id
in your CSVs — if yours predate that, re-run pull_data.py first (this
reads from cache, so it won't cost any API quota).

USAGE:
    python collect_api_names.py
"""

import csv
import glob
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")

FILENAME_RE = re.compile(r"(\d+)_(\d{4})\.csv$")


def build_league_lookup():
    if not os.path.exists(CONFIG_PATH):
        print(f"WARNING: {CONFIG_PATH} not found — names will be collected without league context.")
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    lookup = {}
    for country, comps in config.items():
        for comp in comps:
            lookup[comp["league_id"]] = f"{country} - {comp.get('name', comp['league_id'])}"
    return lookup


def league_label_for_file(filename, lookup):
    m = FILENAME_RE.search(os.path.basename(filename))
    if not m:
        return "Unknown competition"
    league_id = int(m.group(1))
    return lookup.get(league_id, f"Unknown competition (league_id {league_id})")


def add_team(teams_by_id, team_id, name, label):
    """teams_by_id: {team_id: {"name": ..., "leagues": set(...)}}"""
    if team_id not in teams_by_id:
        teams_by_id[team_id] = {"name": name, "leagues": set()}
    teams_by_id[team_id]["leagues"].add(label)
    teams_by_id[team_id]["name"] = name


def collect_from_standings(path, label, teams_by_id, missing_id_warned):
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and "team_id" not in reader.fieldnames:
            if path not in missing_id_warned:
                print(f"  WARNING: {os.path.basename(path)} has no team_id column — "
                      f"re-run pull_data.py to regenerate with IDs. Skipping this file.")
                missing_id_warned.add(path)
            return
        for row in reader:
            name = row.get("team", "").strip()
            team_id = row.get("team_id", "").strip()
            if name and team_id:
                add_team(teams_by_id, team_id, name, label)


def collect_from_fixtures(path, label, teams_by_id, missing_id_warned):
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and "home_team_id" not in reader.fieldnames:
            if path not in missing_id_warned:
                print(f"  WARNING: {os.path.basename(path)} has no home_team_id column — "
                      f"re-run pull_data.py to regenerate with IDs. Skipping this file.")
                missing_id_warned.add(path)
            return
        for row in reader:
            for side in ("home", "away"):
                name = row.get(f"{side}_team", "").strip()
                team_id = row.get(f"{side}_team_id", "").strip()
                if name and team_id:
                    add_team(teams_by_id, team_id, name, label)


def main():
    lookup = build_league_lookup()
    teams_by_id = {}
    missing_id_warned = set()

    standings_files = glob.glob(os.path.join(SCRIPT_DIR, "data", "standings", "*.csv"))
    fixtures_files = glob.glob(os.path.join(SCRIPT_DIR, "data", "fixtures", "*.csv"))

    print(f"Scanning {len(standings_files)} standings files and {len(fixtures_files)} fixtures files...")

    for path in standings_files:
        label = league_label_for_file(path, lookup)
        collect_from_standings(path, label, teams_by_id, missing_id_warned)

    for path in fixtures_files:
        label = league_label_for_file(path, lookup)
        collect_from_fixtures(path, label, teams_by_id, missing_id_warned)

    # Build name -> [list of distinct teams sharing that name], each with its
    # own team_id and ONLY its own league labels (no merging across teams).
    by_name = {}
    for team_id, info in teams_by_id.items():
        by_name.setdefault(info["name"], []).append({
            "team_id": team_id,
            "leagues": sorted(info["leagues"]),
        })

    output = {name: entries for name, entries in sorted(by_name.items())}

    ambiguous = {name: entries for name, entries in output.items() if len(entries) > 1}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nFound {len(teams_by_id)} distinct teams under {len(output)} unique names.")
    if ambiguous:
        print(f"\n{len(ambiguous)} name(s) are shared by more than one real team "
              f"(different clubs, same name) — these will show as separate, clearly "
              f"labeled options during matching:")
        for name, entries in list(ambiguous.items())[:15]:
            countries = [e["leagues"][0].split(" - ")[0] for e in entries if e["leagues"]]
            print(f"  '{name}' — {len(entries)} teams: {', '.join(countries)}")
        if len(ambiguous) > 15:
            print(f"  ... and {len(ambiguous)-15} more")

    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
