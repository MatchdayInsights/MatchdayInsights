"""
pull_new_zealand.py

Pulls fixtures for the New Zealand National League structure (added to
leagues_config.json 2026-08-25): the three regional groups, the national
playoff phase, and the final. Same proven fetch logic as
pull_uefa_history.py (no "page" param - that was the earlier bug).

SETUP:
  1. pip install requests
  2. export API_FOOTBALL_KEY="your-key-here"
  3. Adjust OUTPUT_DIR to point at your real data/fixtures/ folder.
  4. Run: python3 pull_new_zealand.py
"""

import csv
import json
import os
import time
import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY")
USE_RAPIDAPI = False

if USE_RAPIDAPI:
    BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
    HEADERS = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": "api-football-v1.p.rapidapi.com"}
else:
    BASE_URL = "https://v3.football.api-sports.io"
    HEADERS = {"x-apisports-key": API_KEY}

OUTPUT_DIR = "./data/fixtures"  # <-- point this at your real fixtures folder
SLEEP_SECONDS = 0.25  # API-Football Pro plan: 300 req/min (5/sec) -
                       # 0.25s keeps us at 4/sec, a safety margin under
                       # the real limit rather than the free-tier-level
                       # pace this used to run at.

# (competition_name_for_filename, league_id)
NEW_ZEALAND_COMPETITIONS = [
    ("National-League-Central", 954),
    ("National-League-Northern", 956),
    ("National-League-Southern", 957),
    ("National-League-Championship", 955),
    ("National-League-Final", 1056),
]
SEASONS = [2025, 2026]


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

    # Force UTF-8 decoding of the raw response bytes directly, instead of
    # resp.json() (which relies on requests guessing the encoding from
    # response headers - if the server does not send an explicit
    # charset=utf-8 in its Content-Type, that guess can be wrong, silently
    # mangling accented characters like Bayern MÃ¼nchen instead of München).
    data = json.loads(resp.content.decode("utf-8"))
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
    # Require BOTH goal fields to be genuinely present, not just a
    # played-looking status - API-Football occasionally returns FT/AET/PEN
    # with a null goal (a real data-quality gap on their end), and writing
    # played=True with an empty score field crashes run_ratings.py's
    # int(row["home_score"]) with no useful error. Treating that case as
    # NOT played is the safe choice: run_ratings.py only wants matches it
    # can actually score.
    played = (
        status_short in ("FT", "AET", "PEN")
        and goals["home"] is not None
        and goals["away"] is not None
    )

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

    for comp_name, league_id in NEW_ZEALAND_COMPETITIONS:
        for season in SEASONS:
            print(f"Pulling {comp_name} {season}...")
            fixtures = fetch_fixtures(league_id, season)
            if not fixtures:
                print(f"  No fixtures returned - check the [debug]/error lines "
                      f"above (e.g. this group may not have existed that season) - skipping.")
                continue
            rows = [fixture_to_row(fx) for fx in fixtures]
            filename = f"New-Zealand_{comp_name}_{league_id}_{season}.csv"
            path = os.path.join(OUTPUT_DIR, filename)
            write_csv(rows, path)
            print(f"  Wrote {len(rows)} fixtures to {filename}")
            time.sleep(SLEEP_SECONDS)

    print("\nDone. Re-run run_ratings.py to pick up the new data.")


if __name__ == "__main__":
    main()
