"""
detect_relegations.py

Pulls standings for EVERY tracked league-type competition, across every
season it was genuinely included per season_inclusion.json (not just the
latest season) - the full-history extension of the original single-season
version, needed for the Standard-case Starting Position formula to work
correctly for any mid-history promotion, not just the most recent one.

Parses each team's `description` field to determine relegation status and
computes a weighted relegated_count per (code, season).

WORKFLOW:
  Run this whenever you want to (re)build the full historical relegation
  dataset, or just the newest season after your annual review. It:
    1. Counts every (league, season) pull needed and shows you the cost
       BEFORE spending anything - confirm to proceed.
    2. Caches every raw API response to disk, so re-running costs nothing
       for anything already pulled.
    3. Writes two outputs:
         relegation_counts.json  - {code: {season: {...}}} - ready to use
         relegation_review.txt   - anything it couldn't confidently
                                    classify, for you to check by hand

  Nothing here silently guesses. If a description doesn't match a known
  pattern (default OR country override), it goes to the review file
  instead of being counted.

  As you resolve review-flagged items, add a rule to COUNTRY_OVERRIDES
  (see Germany example below) so the same wording is handled
  automatically next time, for every season, not just the one you're
  looking at right now.

Usage:
    python detect_relegations.py

Requires:
    API_FOOTBALL_KEY environment variable.
    leagues_config.json, country_code_mapping.json, and (optionally, but
    strongly recommended to avoid wasted pulls) season_inclusion.json all
    present in this folder.
"""

import os
import re
import json
import time
import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
if not API_KEY:
    raise SystemExit("Set the API_FOOTBALL_KEY environment variable before running this script.")

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
COUNTRY_CODE_MAPPING_PATH = os.path.join(SCRIPT_DIR, "country_code_mapping.json")
SEASON_INCLUSION_PATH = os.path.join(SCRIPT_DIR, "season_inclusion.json")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

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

    if "releg" in desc_l:
        return "unrecognized"

    return "none"


def fetch_standings(league_id, season):
    cache_key = f"standings_desc_league{league_id}_season{season}"
    cache_path = os.path.join(CACHE_DIR, cache_key + ".json")
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(
        f"{BASE_URL}/standings",
        headers=HEADERS,
        params={"league": league_id, "season": season},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(0.3)
    return data


def build_pull_list():
    """
    Returns a list of {code, league_id, season, country_code} for every
    type=="league" competition, for every season it was genuinely
    included per season_inclusion.json. Falls back to every season in
    the competition's own "seasons" list (with a warning) if
    season_inclusion.json isn't available.
    """
    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)
    with open(COUNTRY_CODE_MAPPING_PATH, encoding="utf-8") as f:
        country_code_mapping = json.load(f)

    season_inclusion = None
    if os.path.exists(SEASON_INCLUSION_PATH):
        with open(SEASON_INCLUSION_PATH, encoding="utf-8") as f:
            season_inclusion = json.load(f)
    else:
        print("WARNING: season_inclusion.json not found - will pull EVERY season in each "
              "competition's 'seasons' list, including seasons where the tier may not have "
              "actually been tracked. Strongly recommend running extract_season_inclusion.py first.")

    pull_list = []
    for country, comps in leagues_config.items():
        code_base = country_code_mapping.get(country)
        if code_base is None:
            continue  # no code mapping (e.g. deliberately excluded country) - skip

        for comp in comps:
            if comp.get("type") != "league":
                continue  # relegation only applies to real league divisions

            tier = comp.get("tier", 1)
            code = code_base if tier == 1 else f"{code_base}_{tier}"

            for season in comp.get("seasons", []):
                season_str = str(season)
                if season_inclusion is not None:
                    if code not in season_inclusion.get(season_str, []):
                        continue  # this tier wasn't actually tracked this season - skip
                pull_list.append({
                    "code": code, "league_id": comp["league_id"],
                    "season": season, "country_code": code_base,
                })

    return pull_list


def main():
    pull_list = build_pull_list()

    # Filter out anything already cached, to give an accurate "what will
    # this ACTUALLY cost" number rather than counting free re-pulls.
    to_fetch = []
    already_cached = 0
    for entry in pull_list:
        cache_path = os.path.join(
            CACHE_DIR, f"standings_desc_league{entry['league_id']}_season{entry['season']}.json"
        )
        if os.path.exists(cache_path):
            already_cached += 1
        else:
            to_fetch.append(entry)

    print(f"{len(pull_list)} total (league, season) combos to process.")
    print(f"  {already_cached} already cached (free)")
    print(f"  {len(to_fetch)} will require a new API request")

    if to_fetch:
        confirm = input(f"Proceed with {len(to_fetch)} new API requests? [y/n]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Stopped before spending any new requests.")
            return

    results = {}
    review_lines = []

    for i, entry in enumerate(pull_list, 1):
        code = entry["code"]
        season = entry["season"]
        country_code = entry["country_code"]
        print(f"[{i}/{len(pull_list)}] {code} season {season} (league_id={entry['league_id']})")

        try:
            data = fetch_standings(entry["league_id"], season)
        except Exception as e:
            review_lines.append(f"{code} / {season}: FETCH ERROR - {e}")
            continue

        response = data.get("response", [])
        if not response:
            review_lines.append(f"{code} / {season}: NO STANDINGS DATA RETURNED")
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
                        f"{code} / {season}: UNRECOGNIZED - {team!r} description={desc!r}"
                    )

        results.setdefault(code, {})[str(season)] = {
            "total_clubs": total_clubs,
            "relegated_count": weighted_total,
            "confirmed_relegated": confirmed_teams,
            "playoff_relegated": playoff_teams,
        }

        print(f"    -> relegated_count = {weighted_total} "
              f"(confirmed: {len(confirmed_teams)}, playoff: {len(playoff_teams)})")

    with open(os.path.join(SCRIPT_DIR, "relegation_counts.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    print(f"\nWrote relegation_counts.json - {len(results)} leagues, "
          f"{sum(len(v) for v in results.values())} league-seasons total")

    if review_lines:
        with open(os.path.join(SCRIPT_DIR, "relegation_review.txt"), "w") as f:
            f.write("\n".join(review_lines))
        print(f"Wrote relegation_review.txt ({len(review_lines)} items need manual review)")
    else:
        print("No items flagged for review.")


if __name__ == "__main__":
    main()
