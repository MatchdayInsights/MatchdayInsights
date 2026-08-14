"""
detect_relegations.py

Pulls final-season standings for a set of leagues, parses each team's
`description` field to determine relegation status, and computes a
weighted relegated_count per league-season for use in the Starting
Position formula.

WORKFLOW:
  Run this once a year (or whenever you're doing your annual review of
  leagues in the ranking). It pulls the just-completed season's final
  standings for every league in your config, classifies each team,
  and writes two outputs:

    1. relegation_counts.json  - the clean, ready-to-use results
    2. relegation_review.txt   - anything it couldn't confidently
                                  classify, for you to check by hand

  Nothing here silently guesses. If a description doesn't match a known
  pattern (default OR country override), it goes to the review file
  instead of being counted - better to flag it than get a wrong number
  baked into a Starting Position that every club in that league inherits.

  As you resolve review-flagged items, add a rule to COUNTRY_OVERRIDES
  (see Germany example below) so the same wording is handled
  automatically next time. The system gets more hands-off over time for
  countries you've already seen; brand-new countries or reworded
  formats will still need a first-pass human check.

Usage:
    python detect_relegations.py

Requires:
    API_FOOTBALL_KEY environment variable, or edit API_KEY below.
    LEAGUES config below - replace with your real league IDs/seasons,
    ideally pulled programmatically from your existing league config
    file rather than hardcoded here long-term.
"""

import os
import re
import json
import time
import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "PASTE_YOUR_KEY_HERE")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ---------------------------------------------------------------------------
# CONFIG: which league/season combos to process.
# Replace this with a load from your real league config (build_config.py /
# fetch_leagues.py output) once you're ready to wire this into the pipeline.
# code = your internal league code (ENG_2 style), used in the output file.
# ---------------------------------------------------------------------------
LEAGUES = [
    {"code": "ENG_2", "league_id": 40, "season": 2023},
    {"code": "GER_2", "league_id": 79, "season": 2023},
    {"code": "ITA_2", "league_id": 136, "season": 2023},
    {"code": "ALB", "league_id": 236, "season": 2023},  # verify real ID
]

# ---------------------------------------------------------------------------
# DEFAULT CLASSIFICATION RULES
# Applied to every league unless a country override below takes precedence.
# Order matters: playoff patterns are checked before the plain "relegation"
# pattern, since a playoff description usually also contains "relegation".
# ---------------------------------------------------------------------------
DEFAULT_PLAYOFF_PATTERNS = [
    r"relegation play[\s-]?off",
    r"relegation[\s-]?playout",
]
DEFAULT_CONFIRMED_PATTERNS = [
    r"relegation",
]

# ---------------------------------------------------------------------------
# COUNTRY OVERRIDES
# Add an entry here whenever a country's wording doesn't match the default
# patterns (discovered via the review file). Each override is checked
# BEFORE falling back to the defaults for that country.
#
# Example - Germany's 2. Bundesliga promotion/relegation playoff uses a
# totally different format: "2. Bundesliga (Relegation)" instead of
# "Relegation Play-off". This tags it as the 0.5-weight playoff case.
# ---------------------------------------------------------------------------
COUNTRY_OVERRIDES = {
    "GER": {
        "playoff_patterns": [
            r"\(relegation\)\s*$",       # e.g. "2. Bundesliga (Relegation)"
            r"\(relegation:\s*\)",       # promotion-side mirror, just in case
        ],
        "confirmed_patterns": [
            r"^relegation\s*-",          # e.g. "Relegation - 3. Liga"
        ],
    },
    # Add more as you encounter them, e.g.:
    # "FRA": { "playoff_patterns": [...], "confirmed_patterns": [...] },
}


def classify_description(desc, country_code):
    """
    Returns one of: 'confirmed' (weight 1.0), 'playoff' (weight 0.5),
    'none' (not relegated), or 'unrecognized' (needs manual review).
    """
    if desc is None or desc.strip() == "":
        return "none"

    desc_l = desc.lower()
    rules = COUNTRY_OVERRIDES.get(country_code, {})
    playoff_patterns = rules.get("playoff_patterns", []) + DEFAULT_PLAYOFF_PATTERNS
    confirmed_patterns = rules.get("confirmed_patterns", []) + DEFAULT_CONFIRMED_PATTERNS

    for pat in playoff_patterns:
        if re.search(pat, desc_l):
            return "playoff"

    for pat in confirmed_patterns:
        if re.search(pat, desc_l):
            return "confirmed"

    # Contains "relegat" in some form but didn't match a known pattern -
    # don't guess, flag it.
    if "releg" in desc_l:
        return "unrecognized"

    # Doesn't mention relegation at all (e.g. a promotion description) -
    # not relevant to this calculation.
    return "none"


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
    results = {}
    review_lines = []

    for entry in LEAGUES:
        code = entry["code"]
        country_code = code.split("_")[0]  # ENG_2 -> ENG
        print(f"Processing {code} (league_id={entry['league_id']}, season={entry['season']})...")

        try:
            data = fetch_standings(entry["league_id"], entry["season"])
        except Exception as e:
            review_lines.append(f"{code}: FETCH ERROR - {e}")
            continue

        response = data.get("response", [])
        if not response:
            review_lines.append(f"{code}: NO STANDINGS DATA RETURNED - check league/season ID")
            continue

        standings_groups = response[0]["league"]["standings"]

        weighted_total = 0.0
        total_clubs = 0
        confirmed_teams = []
        playoff_teams = []

        for group in standings_groups:
            for row in group:
                total_clubs += 1
                team = row.get("team", {}).get("name")
                desc = row.get("description")
                classification = classify_description(desc, country_code)

                if classification == "confirmed":
                    weighted_total += 1.0
                    confirmed_teams.append(team)
                elif classification == "playoff":
                    weighted_total += 0.5
                    playoff_teams.append(team)
                elif classification == "unrecognized":
                    review_lines.append(
                        f"{code}: UNRECOGNIZED - {team!r} description={desc!r} "
                        f"(contains 'releg' but matched no known pattern)"
                    )

        results[code] = {
            "season": entry["season"],
            "total_clubs": total_clubs,
            "relegated_count": weighted_total,
            "confirmed_relegated": confirmed_teams,
            "playoff_relegated": playoff_teams,
        }

        print(f"  -> relegated_count = {weighted_total} "
              f"(confirmed: {len(confirmed_teams)}, playoff: {len(playoff_teams)})")

        time.sleep(1)  # be polite to the rate limit

    with open("relegation_counts.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote relegation_counts.json")

    if review_lines:
        with open("relegation_review.txt", "w") as f:
            f.write("\n".join(review_lines))
        print(f"Wrote relegation_review.txt ({len(review_lines)} items need manual review)")
    else:
        print("No items flagged for review.")


if __name__ == "__main__":
    main()
