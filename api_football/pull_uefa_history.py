"""
pull_uefa_history.py

Pulls historical UEFA competition fixtures from API-Football and writes
them in the exact same CSV format/filename convention as your existing
data/fixtures/ files, so run_ratings.py can read them with zero changes.

Fills the gap: UEFA Champions League / Europa League / Europa Conference
League only have 2024-2026 pulled so far; domestic leagues go back to
2020. This pulls 2020-2023 for all three.

SETUP:
  1. pip install requests
  2. Set your API key as an environment variable:
       export API_FOOTBALL_KEY="your-key-here"
     (This script uses the official v3.football.api-sports.io host. If
     you're on the RapidAPI-hosted version instead, see the
     USE_RAPIDAPI flag below.)
  3. Adjust OUTPUT_DIR to point at your actual data/fixtures/ folder.
  4. Run: python3 pull_uefa_history.py

Rate limits: API-Football's free/lower tiers are commonly capped around
10 requests/minute. This script sleeps between calls - adjust
SLEEP_SECONDS if your plan allows faster pulls, or lower it and watch
for 429 responses.
"""

import csv
import json
import os
import time
import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY")
USE_RAPIDAPI = False  # flip to True if you're on the RapidAPI-hosted version instead

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
UEFA_COMPETITIONS = [
    ("UEFA-Champions-League", 2),
    ("UEFA-Europa-League", 3),
    ("UEFA-Europa-Conference-League", 848),
]
SEASONS = [2020, 2021, 2022, 2023]  # 2024-2026 already exist - don't re-pull those


def fetch_fixtures(league_id: int, season: int) -> list[dict]:
    """
    /fixtures returns the full season's results in one call - it doesn't
    accept a "page" parameter at all (that's specific to a few other
    API-Football endpoints, e.g. odds/predictions). Sending "page" here
    causes their validator to reject the whole request with
    {"page": "The Page field do not exist."}, which is why the first
    version of this script got empty results for every single call.
    """
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
    """Maps one API-Football fixture object to our CSV row schema."""
    fixture = fx["fixture"]
    teams = fx["teams"]
    goals = fx["goals"]
    league = fx["league"]

    status_short = fixture["status"]["short"]  # e.g. FT, AET, PEN, NS, PST
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

    for comp_name, league_id in UEFA_COMPETITIONS:
        for season in SEASONS:
            print(f"Pulling {comp_name} {season}...")
            fixtures = fetch_fixtures(league_id, season)
            if not fixtures:
                print(f"  No fixtures returned - check the [debug]/error lines "
                      f"above for why (plan restriction, rate limit, etc.) - "
                      f"skipping.")
                continue
            rows = [fixture_to_row(fx) for fx in fixtures]
            filename = f"World_{comp_name}_{league_id}_{season}.csv"
            path = os.path.join(OUTPUT_DIR, filename)
            write_csv(rows, path)
            print(f"  Wrote {len(rows)} fixtures to {filename}")
            time.sleep(SLEEP_SECONDS)

    print("\nDone. Re-run run_ratings.py to pick up the new historical data.")


if __name__ == "__main__":
    main()
