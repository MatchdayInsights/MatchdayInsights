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


def add_team(teams_by_id, team_id, name, label, source):
    """teams_by_id: {team_id: {"names": set(...), "leagues": set(...), "standings_leagues": set(...)}}
    Tracks EVERY name variant seen for this team_id, AND tracks which
    league labels came from STANDINGS specifically (source='standings')
    vs any appearance at all including fixtures (source='fixtures').

    Why this distinction matters: a fixtures file for a league can include
    cross-tier matches (e.g. a promotion/relegation playoff between a top-
    flight club and a lower-tier club) tagged under the top-flight
    league_id. That means a lower-tier club can get incorrectly labeled
    as e.g. "Albania - Superliga" just for having played ONE playoff match
    against a Superliga side, even though it was never a genuine member of
    that table. Standings membership doesn't have this problem — a team
    only appears in a competition's standings if it was a real participant
    that season. standings_leagues is the accurate one for "was this team
    really part of this competition" checks; leagues (the fuller set) is
    still useful for name-matching/search purposes.
    """
    if team_id not in teams_by_id:
        teams_by_id[team_id] = {"names": set(), "leagues": set(), "standings_leagues": set()}
    teams_by_id[team_id]["leagues"].add(label)
    teams_by_id[team_id]["names"].add(name)
    if source == "standings":
        teams_by_id[team_id]["standings_leagues"].add(label)


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
                add_team(teams_by_id, team_id, name, label, source="standings")


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
                    add_team(teams_by_id, team_id, name, label, source="fixtures")


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

    # Build name -> [list of distinct teams sharing that name]. A team that
    # appeared under MULTIPLE names (see add_team's docstring) gets an entry
    # under EACH of its names, all pointing to the same team_id/leagues —
    # so searching by any name variant correctly finds it.
    by_name = {}
    multi_named_teams = []
    for team_id, info in teams_by_id.items():
        names = info["names"]
        if len(names) > 1:
            multi_named_teams.append((team_id, sorted(names)))
        for name in names:
            by_name.setdefault(name, []).append({
                "team_id": team_id,
                "leagues": sorted(info["leagues"]),
                "standings_leagues": sorted(info["standings_leagues"]),
            })

    output = {name: entries for name, entries in sorted(by_name.items())}

    ambiguous = {name: entries for name, entries in output.items() if len(entries) > 1}

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nFound {len(teams_by_id)} distinct teams under {len(output)} unique names.")

    if multi_named_teams:
        print(f"\n{len(multi_named_teams)} team(s) appeared under MORE THAN ONE name across your files "
              f"(genuine rename, or an inconsistency between standings/fixtures data) — "
              f"all name variants are searchable and point to the same team:")
        for team_id, names in multi_named_teams[:15]:
            print(f"  team_id {team_id}: {' / '.join(names)}")
        if len(multi_named_teams) > 15:
            print(f"  ... and {len(multi_named_teams)-15} more")

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
