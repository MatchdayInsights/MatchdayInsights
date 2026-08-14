"""
test_standings_descriptions.py

Standalone diagnostic script - pulls standings for a handful of test
league/season combos and prints out every team's rank + description field,
so we can see how clean/messy the API's relegation labeling actually is
before deciding how much of promotion/relegation detection to automate.

Usage:
    python test_standings_descriptions.py

Requires:
    API_FOOTBALL_KEY environment variable set, or edit API_KEY below directly.
"""

import os
import requests
import time

API_KEY = os.environ.get("API_FOOTBALL_KEY", "b3d61bb980d740790b311fc3de4da661")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# Edit this list to test whatever league/season combos you want to inspect.
# league = API-Football's numeric league ID (not your ENG_2-style codes).
# You likely already have these IDs mapped from fetch_leagues.py /
# build_config.py output - pull a few from there.
TEST_CASES = [
    {"label": "England Championship 2023-24", "league": 40, "season": 2023},
    {"label": "Germany 2. Bundesliga 2023-24", "league": 79, "season": 2023},
    {"label": "Italy Serie B 2023-24", "league": 136, "season": 2023},
    {"label": "Albania Superliga 2023-24", "league": 310, "season": 2023},
    # Add smaller/lower-tier leagues here once you've confirmed IDs -
    # e.g. Albania Kategoria Superiore, to test data completeness
    # outside the Big 5.
]


def fetch_standings(league_id, season):
    resp = requests.get(
        f"{BASE_URL}/standings",
        headers=HEADERS,
        params={"league": league_id, "season": season},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    for case in TEST_CASES:
        print("=" * 80)
        print(case["label"])
        print("=" * 80)

        try:
            data = fetch_standings(case["league"], case["season"])
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        response = data.get("response", [])
        if not response:
            print("  No standings data returned - check league/season ID.")
            continue

        # standings is a list of groups (usually just one group for a
        # normal league table; multiple for group-stage competitions)
        standings_groups = response[0]["league"]["standings"]

        for group in standings_groups:
            for row in group:
                rank = row.get("rank")
                team = row.get("team", {}).get("name")
                desc = row.get("description")
                print(f"  {rank:>3}  {team:<30}  description: {desc!r}")

        # be polite to the rate limit between calls
        time.sleep(1)


if __name__ == "__main__":
    main()
