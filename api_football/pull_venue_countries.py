"""
pull_venue_countries.py

Scans every fixtures CSV in data/fixtures/ for distinct venue_ids, looks
up each one's real country via API-Football's /venues endpoint, and
writes venue_id -> country into venue_country_overrides.json - the file
match_context_builder.py already reads to resolve MatchContext.venue_country,
which elo_engine.py's is_neutral() compares against home_team_country to
detect forced-relocation neutral venues (the "Ukraine playing abroad"
case, and any other club whose actual match venue doesn't match their
home country).

Incremental by design: venue_ids already in venue_country_overrides.json
are skipped, so re-running this after a fresh data pull only fetches
whatever's genuinely new - safe to run repeatedly as part of your normal
refresh cadence.

SETUP:
  1. pip install requests
  2. export API_FOOTBALL_KEY="ff088abc91c859625de9b4d1aee11136"
  3. Run from the same folder as data/fixtures/ and country_code_mapping.json
     (creates venue_country_overrides.json if it doesn't exist).
  4. Run: python pull_venue_countries.py
     Add --dry-run first to see how many venues would be looked up
     without spending any API calls.
"""

import csv
import glob
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
FIXTURES_DIR = SCRIPT_DIR / "data" / "fixtures"
COUNTRY_CODE_MAPPING_PATH = SCRIPT_DIR / "country_code_mapping.json"
VENUE_OVERRIDES_PATH = SCRIPT_DIR / "venue_country_overrides.json"
SLEEP_SECONDS = 0.25  # API-Football Pro plan: 300 req/min (5/sec)


def find_all_venue_ids() -> set:
    venue_ids = set()
    for path in FIXTURES_DIR.glob("*.csv"):
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                vid = row.get("venue_id")
                if vid:
                    venue_ids.add(vid)
    return venue_ids


def normalize_country_name(raw_name: str, canonical_names: set) -> str:
    """
    Matches API-Football's venue country name (e.g. "Trinidad and Tobago")
    against country_code_mapping.json's keys (e.g. "Trinidad-And-Tobago")
    to find this system's canonical spelling - case/hyphen/space
    insensitive. Falls back to a simple space->hyphen conversion of the
    raw name if no match is found, so it's still usable, but callers
    should treat that fallback case as worth a manual check (printed
    clearly, not silently accepted).

    A handful of countries use a genuinely different (usually shorter)
    name in this system than a venue API is likely to return (e.g. this
    system's "Bosnia" vs. the full "Bosnia and Herzegovina") - the
    fold-and-compare above can't catch those since they're not just a
    spacing/hyphenation difference, so they're listed explicitly here.
    Add to this table as new mismatches turn up.
    """
    def fold(s):
        return s.lower().replace("-", " ").replace("_", " ").strip()

    known_aliases = {
        "bosnia and herzegovina": "Bosnia",
        "republic of the congo": "Congo",
        "dr congo": "Congo-DR",
        "democratic republic of the congo": "Congo-DR",
        "north macedonia": "Macedonia",
        "united states": "USA",
        "korea republic": "South-Korea",
        "south korea": "South-Korea",
        "cote d'ivoire": "Ivory-Coast",
        "ivory coast": "Ivory-Coast",
        "czechia": "Czech-Republic",
    }
    folded_target = fold(raw_name)
    if folded_target in known_aliases:
        return known_aliases[folded_target]

    for canonical in canonical_names:
        if fold(canonical) == folded_target:
            return canonical
    return raw_name.replace(" ", "-")  # best-effort fallback


def fetch_venue_country(venue_id: str) -> str | None:
    resp = requests.get(f"{BASE_URL}/venues", headers=HEADERS, params={"id": venue_id}, timeout=30)
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} for venue_id={venue_id}: {resp.text[:200]}")
        return None
    data = json.loads(resp.content.decode("utf-8"))
    if data.get("errors"):
        print(f"  API error for venue_id={venue_id}: {data['errors']}")
    response = data.get("response", [])
    if not response:
        return None
    return response[0].get("country")


def main():
    dry_run = "--dry-run" in sys.argv

    all_venue_ids = find_all_venue_ids()
    print(f"{len(all_venue_ids)} distinct venue_id(s) found across your fixtures data.")

    overrides = {}
    if VENUE_OVERRIDES_PATH.exists():
        with open(VENUE_OVERRIDES_PATH) as f:
            overrides = json.load(f)

    to_fetch = sorted(all_venue_ids - set(overrides.keys()))
    print(f"{len(to_fetch)} venue_id(s) not yet resolved "
          f"({len(all_venue_ids) - len(to_fetch)} already in venue_country_overrides.json).")

    if dry_run:
        est_minutes = round(len(to_fetch) * SLEEP_SECONDS / 60, 1)
        print(f"\n[dry-run] Would make {len(to_fetch)} API calls, ~{est_minutes} minutes. "
              f"Remove --dry-run to actually pull.")
        return

    if not to_fetch:
        print("Nothing new to fetch.")
        return

    if not API_KEY:
        raise SystemExit("Set API_FOOTBALL_KEY environment variable first.")

    with open(COUNTRY_CODE_MAPPING_PATH) as f:
        canonical_names = set(json.load(f).keys())

    resolved, unmatched, empty = 0, [], []
    for i, venue_id in enumerate(to_fetch, 1):
        if i % 100 == 0 or i == len(to_fetch):
            print(f"  {i}/{len(to_fetch)}...")
        raw_country = fetch_venue_country(venue_id)
        if raw_country is None:
            empty.append(venue_id)
            time.sleep(SLEEP_SECONDS)
            continue
        canonical = normalize_country_name(raw_country, canonical_names)
        if canonical not in canonical_names:
            unmatched.append((venue_id, raw_country, canonical))
        overrides[venue_id] = canonical
        resolved += 1
        time.sleep(SLEEP_SECONDS)

    with open(VENUE_OVERRIDES_PATH, "w") as f:
        json.dump(overrides, f, indent=2, sort_keys=True)

    print(f"\n{resolved} venue(s) resolved and written to {VENUE_OVERRIDES_PATH}.")
    if empty:
        print(f"{len(empty)} venue_id(s) returned no data from the API (invalid/removed venue?): "
              f"{empty[:20]}{'...' if len(empty) > 20 else ''}")
    if unmatched:
        print(f"\n{len(unmatched)} venue(s) got a country name that didn't match anything in "
              f"country_code_mapping.json - used a best-effort fallback spelling, worth a check:")
        for venue_id, raw, fallback in unmatched:
            print(f"  venue_id={venue_id}: API said {raw!r} -> stored as {fallback!r}")

    print("\nRe-run run_ratings.py to pick up the new venue data.")


if __name__ == "__main__":
    main()
