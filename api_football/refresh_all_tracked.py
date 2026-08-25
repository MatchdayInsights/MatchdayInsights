"""
refresh_all_tracked.py

Pulls fresh fixtures for every competition relevant to the site's
currently-tracked universe - not the FULL leagues_config.json (which
includes hundreds of untracked tiers, youth/women's leagues, and noise
like the giant "Friendlies Clubs" bucket, league_id 667, that would burn
API quota on data the site never uses).

SCOPE: for every country that has at least one currently-tracked club
(from club_metadata.json) plus "World" (continental competitions), pulls
every league/cup/continental competition for that country - EXCLUDING
anything with "friendl" in the name as a safety net against noise buckets
like 667.

SEASONS PULLED PER COMPETITION: the most recent season already in
leagues_config.json's "seasons" list, PLUS that season + 1 - this covers
both "catch up any new matches in the ongoing season" and "the new season
just started and isn't in the config's season list yet" without needing
to hardcode each competition's calendar convention. A competition whose
next season genuinely hasn't started yet just comes back empty and gets
skipped, same as always.

Competitions with an EMPTY "seasons" list in leagues_config.json (like
New Zealand's old defunct Premiership was, before the fix) are skipped
entirely here - those need the one-off pull_fixtures.py treatment first
to establish a baseline, not a "refresh."

KNOWN GAP: Papua New Guinea has tracked clubs but isn't in
leagues_config.json under any spelling - needs manual investigation
(same pattern as the New Zealand National League gap), not fixable by
this script.

SETUP:
  1. pip install requests
  2. export API_FOOTBALL_KEY="ff088abc91c859625de9b4d1aee11136"
  3. Adjust OUTPUT_DIR / CLUB_METADATA_PATH / LEAGUES_CONFIG_PATH if
     they're not sitting next to this script.
  4. Run: python refresh_all_tracked.py
     (Add --dry-run first to see exactly what WOULD be pulled and roughly
     how long it'll take, without spending any API calls.)
"""

import csv
import json
import os
import sys
import time
import requests
from pathlib import Path

API_KEY = os.environ.get("API_FOOTBALL_KEY")
USE_RAPIDAPI = False

if USE_RAPIDAPI:
    BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
    HEADERS = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": "api-football-v1.p.rapidapi.com"}
else:
    BASE_URL = "https://v3.football.api-sports.io"
    HEADERS = {"x-apisports-key": API_KEY}

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "data" / "fixtures"  # <-- adjust if needed
CLUB_METADATA_PATH = SCRIPT_DIR / "club_metadata.json"
LEAGUES_CONFIG_PATH = SCRIPT_DIR / "leagues_config.json"
SLEEP_SECONDS = 6.5

# Country CODE (as used in club_metadata.json) -> exact leagues_config.json
# key, for the handful that don't auto-match by simple space-to-hyphen
# conversion of the readable name. If you hit a KeyError for some other
# country, add it here.
COUNTRY_CODE_OVERRIDES = {
    "ATG": "Antigua-And-Barbuda",
    "BIH": "Bosnia",
    "CZE": "Czech-Republic",
    "MAC": "Macao",
    "MKD": "Macedonia",
    "TRI": "Trinidad-And-Tobago",
    "USA": "USA",
    # PNG intentionally omitted - not in leagues_config.json at all yet.
}


def slugify(name: str) -> str:
    return name.replace(" ", "-")


def fetch_fixtures_by_date(date_str: str) -> list[dict]:
    """One call returns EVERY fixture across EVERY competition worldwide
    for a single date - used to cheaply discover which tracked
    competitions actually had activity recently, before spending a full
    call per competition/season on ones that had nothing happen."""
    resp = requests.get(
        f"{BASE_URL}/fixtures",
        headers=HEADERS,
        params={"date": date_str},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        print(f"    API error: {data['errors']}")
    return data.get("response", [])


def find_recently_active_league_ids(days_back: int) -> set:
    """Checks the last `days_back` days (one API call per day, covering
    ALL competitions at once) and returns the set of league_ids that had
    at least one fixture in that window."""
    from datetime import date, timedelta
    active = set()
    today = date.today()
    for i in range(days_back):
        d = (today - timedelta(days=i)).isoformat()
        print(f"Checking activity on {d}...")
        fixtures = fetch_fixtures_by_date(d)
        for fx in fixtures:
            active.add(fx["league"]["id"])
        print(f"    {len(fixtures)} fixtures worldwide, "
              f"{len(set(fx['league']['id'] for fx in fixtures))} distinct competitions")
        time.sleep(SLEEP_SECONDS)
    return active


def fetch_fixtures(league_id: int, season: int) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/fixtures",
        headers=HEADERS,
        params={"league": league_id, "season": season},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
        resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        print(f"    API error: {data['errors']}")
    return data.get("response", [])


def fixture_to_row(fx: dict) -> dict:
    fixture, teams, goals, league = fx["fixture"], fx["teams"], fx["goals"], fx["league"]
    status_short = fixture["status"]["short"]
    return {
        "fixture_id": fixture["id"], "date": fixture["date"], "status": status_short,
        "round": league["round"],
        "home_team": teams["home"]["name"], "home_team_id": teams["home"]["id"],
        "away_team": teams["away"]["name"], "away_team_id": teams["away"]["id"],
        "home_score": goals["home"] if goals["home"] is not None else "",
        "away_score": goals["away"] if goals["away"] is not None else "",
        "played": status_short in ("FT", "AET", "PEN"),
        "venue_id": fixture.get("venue", {}).get("id") or "",
    }


def write_csv(rows, path):
    fieldnames = ["fixture_id", "date", "status", "round", "home_team", "home_team_id",
                  "away_team", "away_team_id", "home_score", "away_score", "played", "venue_id"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def build_country_code_to_key(leagues_config: dict) -> dict:
    """country CODE (club_metadata.json style, e.g. 'GER') -> leagues_config.json key"""
    # Minimal readable-name lookup just for this matching step - the full
    # version lives in country_codes.py; duplicated narrowly here so this
    # script has no import dependency on other project files.
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from country_codes import COUNTRY_INFO
    except ImportError:
        raise SystemExit("country_codes.py not found next to this script - needed for "
                          "country code -> leagues_config.json key matching.")

    lc_keys = set(leagues_config.keys())
    mapping = {}
    for code, (flag, name) in COUNTRY_INFO.items():
        if code in COUNTRY_CODE_OVERRIDES:
            mapping[code] = COUNTRY_CODE_OVERRIDES[code]
            continue
        candidate = name.replace(" ", "-")
        if candidate in lc_keys:
            mapping[code] = candidate
    return mapping


def build_pull_list():
    with open(CLUB_METADATA_PATH) as f:
        club_metadata = json.load(f)
    with open(LEAGUES_CONFIG_PATH) as f:
        leagues_config = json.load(f)

    tracked_codes = set(m["country"] for m in club_metadata.values() if m["country"])
    code_to_key = build_country_code_to_key(leagues_config)

    unmapped = tracked_codes - set(code_to_key.keys())
    if unmapped:
        print(f"WARNING: {len(unmapped)} tracked country code(s) have no leagues_config.json "
              f"match and will be skipped: {sorted(unmapped)}")

    tracked_keys = set(code_to_key.values()) | {"World"}

    pull_list = []  # (leagues_config_key, competition_name, league_id, [seasons])
    for key in tracked_keys:
        comps = leagues_config.get(key, [])
        for comp in comps:
            if comp["type"] not in ("league", "cup", "continental"):
                continue
            if "friendl" in comp["name"].lower():
                continue
            seasons = comp.get("seasons") or []
            if not seasons:
                continue  # never-pulled competition - use pull_fixtures.py for that first
            latest = max(seasons)
            pull_list.append((key, comp["name"], comp["league_id"], sorted({latest, latest + 1})))

    return pull_list


def main():
    dry_run = "--dry-run" in sys.argv
    skip_check = "--no-check" in sys.argv
    days_back = 4
    for arg in sys.argv:
        if arg.startswith("--days="):
            days_back = int(arg.split("=")[1])

    pull_list = build_pull_list()
    print(f"{len(pull_list)} competitions in the tracked universe.\n")

    if not skip_check:
        if not API_KEY and not dry_run:
            raise SystemExit("Set API_FOOTBALL_KEY environment variable first.")
        if dry_run:
            print(f"[dry-run] Would check the last {days_back} day(s) for activity "
                  f"({days_back} API calls), then only pull competitions that had a match.\n")
        else:
            active_ids = find_recently_active_league_ids(days_back)
            print(f"\n{len(active_ids)} distinct competitions had activity in the last "
                  f"{days_back} day(s).")
            before = len(pull_list)
            pull_list = [p for p in pull_list if p[2] in active_ids]
            print(f"Narrowed from {before} to {len(pull_list)} competitions worth pulling.\n")

    total_calls = sum(len(seasons) for _, _, _, seasons in pull_list)
    est_minutes = round(total_calls * SLEEP_SECONDS / 60, 1)
    print(f"{len(pull_list)} competitions to pull, {total_calls} API calls, "
          f"~{est_minutes} minutes at current rate limit.\n")

    if dry_run:
        for key, name, league_id, seasons in pull_list:
            print(f"  {key} / {name} (id={league_id}) -> seasons {seasons}")
        print("\nDry run only - no fixture-pulling API calls made. "
              "Remove --dry-run to actually pull.")
        return

    if not API_KEY:
        raise SystemExit("Set API_FOOTBALL_KEY environment variable first.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, (key, name, league_id, seasons) in enumerate(pull_list, 1):
        for season in seasons:
            print(f"[{i}/{len(pull_list)}] Pulling {key} / {name} {season} (id={league_id})...")
            fixtures = fetch_fixtures(league_id, season)
            if not fixtures:
                print("    No fixtures returned - skipping.")
                time.sleep(SLEEP_SECONDS)
                continue
            rows = [fixture_to_row(fx) for fx in fixtures]
            filename = f"{key}_{slugify(name)}_{league_id}_{season}.csv"
            write_csv(rows, OUTPUT_DIR / filename)
            print(f"    Wrote {len(rows)} fixtures to {filename}")
            time.sleep(SLEEP_SECONDS)

    print("\nDone. Re-run run_ratings.py -> generate_rankings.py -> "
          "generate_slug_registry.py -> generate_homepage.py to pick it all up.")


if __name__ == "__main__":
    main()
