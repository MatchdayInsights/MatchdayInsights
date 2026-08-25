"""
pull_cross_confederation_friendlies.py

Pulls club friendlies since 2020 and keeps only the ones that are
CROSS-CONFEDERATION (the two clubs' home countries map to different
confederations via confederation_mapping.json) - a much richer sample
for gauging relative confederation strength than the sparse set of
official cross-confederation competitions (2025 Club World Cup, the
annual Intercontinental Cup/playoff).

This is a SEPARATE, standalone data pull - it does NOT feed into
run_ratings.py's rating engine, and output is written outside
data/fixtures/ specifically so it can never accidentally get swept into
the main pipeline. Whether/how to actually use friendly results in
ratings (weakened lineups, no real stakes, big squad-rotation noise)
is a separate methodology decision - this tool is for REVIEWING the
cross-confederation picture first, not for feeding it into Elo.

THREE STEPS, each costing real API quota - you'll be asked to confirm
before each one:

  1. DISCOVER the "Friendlies Clubs" competition's league_id via a name
     search (never hardcoded/assumed - confirm it's the right one).
  2. PULL every fixture for that league_id, season by season, 2020-2026.
  3. RESOLVE each participating club's country - reusing what's already
     known locally (your existing fixture data + team_country_overrides.json)
     first, and only calling the API for genuinely unknown clubs (friendly-
     only participants that never show up in any tracked competition).

Usage:
    python pull_cross_confederation_friendlies.py
"""

import csv
import glob
import json
import os
import time

import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
if not API_KEY:
    raise SystemExit("Set the API_FOOTBALL_KEY environment variable before running this script.")
BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
FIXTURES_GLOB = os.path.join(SCRIPT_DIR, "data", "fixtures", "*.csv")
CONFEDERATION_MAPPING_PATH = os.path.join(SCRIPT_DIR, "confederation_mapping.json")
COUNTRY_CODE_MAPPING_PATH = os.path.join(SCRIPT_DIR, "country_code_mapping.json")
TEAM_COUNTRY_OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
TEAM_COUNTRY_CACHE_PATH = os.path.join(SCRIPT_DIR, "friendly_team_country_cache.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "cross_confederation_friendlies.json")

SEASONS = list(range(2020, 2027))

os.makedirs(CACHE_DIR, exist_ok=True)


def api_get(endpoint, params, use_cache=True):
    cache_key = endpoint.strip("/") + "_" + "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    cache_path = os.path.join(CACHE_DIR, cache_key + ".json")

    if use_cache and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=30)
    if not resp.ok:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        raise requests.exceptions.HTTPError(f"{resp.status_code} {resp.reason} - API response: {body}", response=resp)

    data = resp.json()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    remaining = resp.headers.get("x-ratelimit-requests-remaining")
    if remaining:
        print(f"    (requests remaining today: {remaining})")
    time.sleep(0.3)
    return data


def discover_friendlies_league_id():
    print("Searching API-Football for the 'Friendlies' club competition by name...")
    data = api_get("leagues", {"search": "Friendlies"}, use_cache=False)
    results = data.get("response", [])
    if not results:
        raise SystemExit("No leagues found matching 'Friendlies' - search may need a "
                          "different term, or check your API plan covers this endpoint.")

    club_results = [r for r in results if r.get("league", {}).get("type") == "Cup"
                     or "club" in r.get("league", {}).get("name", "").lower()]
    candidates = club_results or results

    print(f"\nFound {len(candidates)} candidate(s) - confirm which is the real CLUB "
          f"friendlies competition (not national-team friendlies):")
    for r in candidates:
        league = r["league"]
        print(f"  league_id={league['id']}: {league['name']} (type={league.get('type')})")

    chosen = input("\nEnter the league_id to use: ").strip()
    if not chosen.isdigit():
        raise SystemExit("No valid league_id entered - aborting.")
    return int(chosen)


def load_known_country_lookup():
    """Reuses whatever's already resolvable locally - existing pulled
    fixture data (scanned the same lightweight way preview_rankings.py
    does) plus team_country_overrides.json, which always wins. This is
    NOT the full precision of run_ratings.py's real
    build_team_country_lookup (no league-vs-cup priority weighting) -
    good enough for a first pass to minimize new API calls; genuinely
    ambiguous cases will just fall through to a live lookup instead."""
    lookup = {}
    for path in glob.glob(FIXTURES_GLOB):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for side in ("home", "away"):
                    tid = row.get(f"{side}_team_id")
                    if tid:
                        country_guess = os.path.basename(path).split("_")[0]
                        if country_guess != "World":
                            lookup[str(tid)] = country_guess

    if os.path.exists(TEAM_COUNTRY_OVERRIDES_PATH):
        with open(TEAM_COUNTRY_OVERRIDES_PATH, encoding="utf-8") as f:
            lookup.update(json.load(f))

    return lookup


def resolve_team_country_live(team_id: str) -> str | None:
    data = api_get("teams", {"id": team_id})
    response = data.get("response", [])
    if not response:
        return None
    return response[0].get("team", {}).get("country")


def main():
    with open(CONFEDERATION_MAPPING_PATH, encoding="utf-8") as f:
        confederation_mapping = json.load(f)
    with open(COUNTRY_CODE_MAPPING_PATH, encoding="utf-8") as f:
        country_code_mapping = json.load(f)

    league_id = discover_friendlies_league_id()

    print(f"\nPulling fixtures for league_id={league_id}, seasons {SEASONS[0]}-{SEASONS[-1]}...")
    print(f"This costs 1 API request per season not already cached ({len(SEASONS)} max).")
    if input("Proceed? (y/n): ").strip().lower() != "y":
        return

    all_fixtures = []
    for season in SEASONS:
        print(f"  Season {season}...")
        data = api_get("fixtures", {"league": league_id, "season": season})
        response = data.get("response", [])
        for m in response:
            if m["fixture"]["status"]["short"] != "FT":
                continue
            all_fixtures.append({
                "date": m["fixture"]["date"],
                "home_team": m["teams"]["home"]["name"],
                "home_team_id": str(m["teams"]["home"]["id"]),
                "away_team": m["teams"]["away"]["name"],
                "away_team_id": str(m["teams"]["away"]["id"]),
                "home_score": m["goals"]["home"],
                "away_score": m["goals"]["away"],
                "season": season,
            })
    print(f"\nPulled {len(all_fixtures)} played friendly fixtures total.")

    known_country = load_known_country_lookup()
    team_country_cache = {}
    if os.path.exists(TEAM_COUNTRY_CACHE_PATH):
        with open(TEAM_COUNTRY_CACHE_PATH, encoding="utf-8") as f:
            team_country_cache = json.load(f)

    unresolved_ids = set()
    for m in all_fixtures:
        for tid in (m["home_team_id"], m["away_team_id"]):
            if tid not in known_country and tid not in team_country_cache:
                unresolved_ids.add(tid)

    if unresolved_ids:
        print(f"\n{len(unresolved_ids)} club(s) in these friendlies aren't resolvable from "
              f"existing local data - this costs 1 API request each to look up directly.")
        if input(f"Proceed with {len(unresolved_ids)} lookups? (y/n): ").strip().lower() == "y":
            for i, tid in enumerate(sorted(unresolved_ids), 1):
                print(f"  [{i}/{len(unresolved_ids)}] team_id={tid}...")
                country = resolve_team_country_live(tid)
                team_country_cache[tid] = country
            with open(TEAM_COUNTRY_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(team_country_cache, f, indent=2, sort_keys=True)

    def resolve_confederation(team_id: str) -> str | None:
        country = known_country.get(team_id) or team_country_cache.get(team_id)
        if country is None:
            return None
        base_code = country_code_mapping.get(country, country)
        return confederation_mapping.get(base_code)

    cross_confed = []
    same_confed_count = 0
    unresolved_count = 0
    for m in all_fixtures:
        home_confed = resolve_confederation(m["home_team_id"])
        away_confed = resolve_confederation(m["away_team_id"])
        if home_confed is None or away_confed is None:
            unresolved_count += 1
            continue
        if home_confed == away_confed:
            same_confed_count += 1
            continue
        m["home_confederation"] = home_confed
        m["away_confederation"] = away_confed
        cross_confed.append(m)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cross_confed, f, indent=2)

    print(f"\nWrote {len(cross_confed)} cross-confederation friendlies to {OUTPUT_PATH}")
    print(f"  ({same_confed_count} same-confederation friendlies excluded, "
          f"{unresolved_count} excluded for unresolvable club country)")


if __name__ == "__main__":
    main()
