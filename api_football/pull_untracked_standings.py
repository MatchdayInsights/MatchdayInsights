"""
pull_untracked_standings.py

One-time pull: for every country, finds every league API-Football has
that ISN'T already in your leagues_config.json, and pulls that league's
current standings (club names + final positions) - enough to identify
which real clubs live in each untracked league, without the added cost
of pulling full team rosters.

This is the raw material for building a "clubs outside the ranking"
database: once you know which club names sit in which untracked
leagues, you fill in a tier-depth CSV (how many levels below the
country's deepest TRACKED tier that league sits), and that becomes a
lookup run_ratings.py can use instead of falling back to the generic
"one level below deepest tracked tier" placeholder assumption for every
untracked club uniformly.

COST WARNING: this is one request per untracked league (standings),
plus one request per country (to enumerate its leagues) - potentially
a large number depending on how much of API-Football's total coverage
sits outside your ~585 tracked competitions. This script counts
everything up FIRST and asks for confirmation before spending any
standings-pull requests, so you don't blow through your daily quota
by surprise.

Usage:
    python pull_untracked_standings.py
"""

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
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
OUT_PATH = os.path.join(SCRIPT_DIR, "untracked_leagues_standings.csv")
os.makedirs(CACHE_DIR, exist_ok=True)

CURRENT_SEASON = 2025  # adjust if you want a different season's standings


def api_get(endpoint, params):
    cache_key = endpoint.strip("/") + "_" + "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    cache_path = os.path.join(CACHE_DIR, cache_key + ".json")
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=30)
    if not resp.ok:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        raise requests.exceptions.HTTPError(f"{resp.status_code} {resp.reason} — {body}", response=resp)

    data = resp.json()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(0.3)
    return data


def get_all_countries():
    """Every country API-Football knows about."""
    data = api_get("countries", {})
    return [c["name"] for c in data.get("response", [])]


def get_leagues_for_country(country_name):
    data = api_get("leagues", {"country": country_name})
    return data.get("response", [])


def main():
    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)

    tracked_league_ids = set()
    for country, comps in leagues_config.items():
        for comp in comps:
            tracked_league_ids.add(comp["league_id"])

    print("Enumerating every country's leagues from API-Football (1 request per country)...")
    all_countries = get_all_countries()
    print(f"  {len(all_countries)} countries found")

    untracked_leagues = []  # (country, league_id, league_name)
    for i, country in enumerate(all_countries, 1):
        print(f"  [{i}/{len(all_countries)}] {country}")
        try:
            leagues = get_leagues_for_country(country)
        except requests.exceptions.HTTPError as e:
            print(f"    ERROR: {e}")
            continue
        for entry in leagues:
            league_id = entry["league"]["id"]
            league_name = entry["league"]["name"]
            if league_id not in tracked_league_ids:
                untracked_leagues.append((country, league_id, league_name))

    print(f"\n{len(untracked_leagues)} untracked leagues found across {len(all_countries)} countries.")
    print(f"Pulling standings for all of these will cost approximately {len(untracked_leagues)} "
          f"additional API requests (cached afterward, so a re-run costs nothing).")
    confirm = input("Proceed with pulling standings for all of these? [y/n]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Stopped before spending any standings-pull requests. "
              "Untracked league list NOT saved - re-run when ready.")
        return

    import csv
    league_rows = []       # one row per LEAGUE - you fill in tier_depth for this
    club_rows = []          # one row per CLUB - fully automatic, no input needed

    for i, (country, league_id, league_name) in enumerate(untracked_leagues, 1):
        print(f"  [{i}/{len(untracked_leagues)}] {country} / {league_name}")
        data = api_get("standings", {"league": league_id, "season": CURRENT_SEASON})
        if data.get("errors") or not data.get("response"):
            league_rows.append({
                "country": country, "league_id": league_id, "league_name": league_name,
                "sample_clubs": "(no standings data - league may not have started, "
                                 "wrong season, or is a cup format without a table)",
                "tier_depth_below_deepest_tracked": "",
            })
            continue
        try:
            groups = data["response"][0]["league"]["standings"]
            clubs = [(r["team"]["id"], r["team"]["name"]) for group in groups for r in group]
        except (IndexError, KeyError):
            clubs = []

        for team_id, team_name in clubs:
            club_rows.append({
                "team_id": team_id, "team_name": team_name,
                "country": country, "league_id": league_id, "league_name": league_name,
            })

        sample_names = "; ".join(name for _, name in clubs[:5])
        if len(clubs) > 5:
            sample_names += f"; ... ({len(clubs)} total)"
        league_rows.append({
            "country": country, "league_id": league_id, "league_name": league_name,
            "sample_clubs": sample_names,
            "tier_depth_below_deepest_tracked": "",  # <- fill in: how many levels
                                                       #    below this country's
                                                       #    deepest TRACKED tier
        })

    league_csv_path = os.path.join(SCRIPT_DIR, "untracked_leagues.csv")
    with open(league_csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "league_id", "league_name",
                                                 "sample_clubs", "tier_depth_below_deepest_tracked"])
        writer.writeheader()
        writer.writerows(league_rows)

    clubs_json_path = os.path.join(SCRIPT_DIR, "untracked_clubs.json")
    with open(clubs_json_path, "w", encoding="utf-8") as f:
        json.dump(club_rows, f, indent=2)

    print(f"\nWrote {len(league_rows)} leagues to {league_csv_path} - "
          f"fill in 'tier_depth_below_deepest_tracked' for each (1 = one level below your "
          f"deepest tracked tier for that country, 2 = two levels below, etc.)")
    print(f"Wrote {len(club_rows)} individual clubs to {clubs_json_path} - "
          f"this one's fully automatic, nothing to fill in.")
    print("Once untracked_leagues.csv is filled in, run apply_untracked_leagues.py.")


if __name__ == "__main__":
    main()
