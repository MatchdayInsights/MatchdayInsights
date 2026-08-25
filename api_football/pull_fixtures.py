"""
pull_fixtures.py

General-purpose fixture puller for any competition/season combo. Same
proven fetch logic as the earlier one-off scripts (no "page" param -
that was the bug that broke the very first version of this).

USAGE:
  1. pip install requests
  2. export API_FOOTBALL_KEY="ff088abc91c859625de9b4d1aee11136"  (or set on Windows: set API_FOOTBALL_KEY=...)
  3. Edit the COMPETITIONS list below with whatever you need to pull.
  4. Adjust OUTPUT_DIR if needed.
  5. Run: python pull_fixtures.py

HOW TO FIND A league_id AND country NAME:
  Use API-Football's own leagues browser/dashboard (same tool you used
  for the UEFA and New Zealand IDs) - search the competition, note its
  numeric ID. The "country" value below must exactly match how that
  country appears as a key in leagues_config.json (e.g. "New-Zealand"
  with a hyphen, "World" for continental competitions) - check
  leagues_config.json if unsure of the exact spelling/casing.
"""

import csv
import os
import time
import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY")
USE_RAPIDAPI = False  # flip to True if you're on the RapidAPI-hosted version

if USE_RAPIDAPI:
    BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
    HEADERS = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": "api-football-v1.p.rapidapi.com"}
else:
    BASE_URL = "https://v3.football.api-sports.io"
    HEADERS = {"x-apisports-key": API_KEY}

OUTPUT_DIR = "./data/fixtures"  # <-- point this at your real fixtures folder
SLEEP_SECONDS = 6.5  # ~9 requests/minute, safely under a 10/min cap

# ============================================================
# EDIT THIS for whatever you need to pull. Each entry:
#   (country_name_for_filename, competition_name_for_filename, league_id, [seasons])
# country_name and competition_name become part of the output filename -
# spaces become hyphens automatically, no need to type them yourself.
# ============================================================
COMPETITIONS = [
    ("Australia", "A-League", 188, [2026]),
    # ("Some-Country", "Some Competition", 123, [2025, 2026]),
]
# ============================================================


def slugify(name: str) -> str:
    return name.replace(" ", "-")


def fetch_fixtures(league_id: int, season: int) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/fixtures",
        headers=HEADERS,
        params={"league": league_id, "season": season},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
        resp.raise_for_status()

    data = resp.json()
    errors = data.get("errors")
    if errors:
        print(f"  API error for league={league_id} season={season}: {errors}")

    response_field = data.get("response", [])
    print(f"  [debug] results={data.get('results')} response_len={len(response_field)}")
    return response_field


def fixture_to_row(fx: dict) -> dict:
    fixture = fx["fixture"]
    teams = fx["teams"]
    goals = fx["goals"]
    league = fx["league"]

    status_short = fixture["status"]["short"]
    played = status_short in ("FT", "AET", "PEN")

    return {
        "fixture_id": fixture["id"],
        "date": fixture["date"],
        "status": status_short,
        "round": league["round"],
        "home_team": teams["home"]["name"],
        "home_team_id": teams["home"]["id"],
        "away_team": teams["away"]["name"],
        "away_team_id": teams["away"]["id"],
        "home_score": goals["home"] if goals["home"] is not None else "",
        "away_score": goals["away"] if goals["away"] is not None else "",
        "played": played,
        "venue_id": fixture.get("venue", {}).get("id") or "",
    }


def write_csv(rows: list[dict], path: str):
    fieldnames = ["fixture_id", "date", "status", "round", "home_team",
                  "home_team_id", "away_team", "away_team_id",
                  "home_score", "away_score", "played", "venue_id"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not API_KEY:
        raise SystemExit("Set API_FOOTBALL_KEY environment variable first.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for country, comp_name, league_id, seasons in COMPETITIONS:
        for season in seasons:
            print(f"Pulling {country} {comp_name} {season} (league_id={league_id})...")
            fixtures = fetch_fixtures(league_id, season)
            if not fixtures:
                print(f"  No fixtures returned - check the [debug]/error line "
                      f"above (wrong league_id? competition didn't exist that "
                      f"season?) - skipping.")
                continue
            rows = [fixture_to_row(fx) for fx in fixtures]
            filename = f"{slugify(country)}_{slugify(comp_name)}_{league_id}_{season}.csv"
            path = os.path.join(OUTPUT_DIR, filename)
            write_csv(rows, path)
            print(f"  Wrote {len(rows)} fixtures to {filename}")
            time.sleep(SLEEP_SECONDS)

    print("\nDone. Re-run run_ratings.py to pick up the new data.")


if __name__ == "__main__":
    main()
