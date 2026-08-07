"""
scan_missed_leagues.py

Scans EVERY country already in leagues_config.json that ISN'T CONMEBOL or
World (i.e. your European/UEFA countries), and reports any League/Cup
competition that:
  1. Exists in leagues_master.json
  2. Is NOT already in your config for that country
  3. Now has real season coverage under the current --history-start
     (meaning it likely showed "NONE" and got declined under the old,
     narrower 2025-01-01 window, but has real pre-2025 data worth
     backfilling)

This replaces manually running `build_config.py --country X` once per
country — one scan covers everything.

Report-only by default — nothing gets added without you seeing it first.
Pass --auto-add to add everything flagged without further review (use
with some caution — this adds every match, not just ones you'd judge as
worth tracking; report-only + a quick eyeball is the safer default).

USAGE:
    python scan_missed_leagues.py --history-start 2020-01-01
    python scan_missed_leagues.py --history-start 2020-01-01 --auto-add
"""

import json
import os
import sys
import argparse
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_config as bc  # reuse seasons_covering_range / make_entry — no logic duplication/drift

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")

# All 55 UEFA member associations. Used as a POSITIVE inclusion list rather
# than "everything that isn't CONMEBOL" — that exclusion-based approach was
# a real bug: it silently swept in AFC countries (Uzbekistan, Vietnam, etc.)
# that had already been auto-added to leagues_config.json during an early,
# unscoped build_config.py run, before confederation scoping was a thing.
# Names should match API-Football's country.name field — if a country of
# yours doesn't get picked up, it likely means their exact string differs
# slightly (e.g. "Czech Republic" vs "Czechia") — check leagues_master.json
# for the exact spelling and adjust this list.
UEFA_COUNTRIES = {
    "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
    "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus",
    "Czech Republic", "Denmark", "England", "Estonia", "Faroe Islands",
    "Finland", "France", "Georgia", "Germany", "Gibraltar", "Greece",
    "Hungary", "Iceland", "Israel", "Italy", "Kazakhstan", "Kosovo",
    "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta",
    "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia",
    "Northern Ireland", "Norway", "Poland", "Portugal", "Republic of Ireland",
    "Ireland", "Romania", "Russia", "San Marino", "Scotland", "Serbia",
    "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Turkey",
    "Ukraine", "Wales",
}
EXCLUDE_KEYWORDS = [
    "women", "u23", "u-23", "u21", "u-21", "u20", "u-20", "u19", "u-19",
    "u18", "u-18", "u17", "u-17", "youth", "junior", "academy",
    "reserve", "reserves", " ii ", " b ", "all-star", "all star",
    "summer cup", "winter cup", "trophy match", "friendlies",
]


def is_excluded(name):
    name_padded = f" {name.lower()} "  # padding so " ii " / " b " match at string edges too
    return any(kw in name_padded for kw in EXCLUDE_KEYWORDS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-start", type=str, default=None,
                         help="YYYY-MM-DD. Defaults to build_config.py's built-in HISTORY_START.")
    parser.add_argument("--auto-add", action="store_true",
                         help="Add every flagged competition automatically, no per-item review. "
                              "Default is report-only.")
    parser.add_argument("--include-all", action="store_true",
                         help="Don't filter out youth/women's/reserve/exhibition competitions — "
                              "show everything found, unfiltered.")
    args = parser.parse_args()

    if args.history_start:
        bc.HISTORY_START = date.fromisoformat(args.history_start)
    print(f"Using history cutoff: {bc.HISTORY_START}\n")

    master = bc.load_master()
    config = bc.load_existing_config()

    european_countries = sorted(c for c in config.keys() if c in UEFA_COUNTRIES)
    non_uefa_in_config = sorted(c for c in config.keys() if c != "World" and c not in UEFA_COUNTRIES)

    print(f"Scanning {len(european_countries)} UEFA countries already in your config...")
    if non_uefa_in_config:
        print(f"(Skipping {len(non_uefa_in_config)} non-UEFA countries also sitting in your config: "
              f"{', '.join(non_uefa_in_config)} — these got in during an earlier unscoped run and "
              f"aren't part of this European backfill)")
    print()

    # Group master entries by country for fast lookup
    by_country = {}
    for entry in master:
        country = entry["country"].get("name") or ""
        if entry["league"].get("type") in ("League", "Cup"):
            by_country.setdefault(country, []).append(entry)

    findings = {}  # country -> list of master entries worth flagging
    excluded_count = 0

    for country in european_countries:
        already_selected_ids = {c["league_id"] for c in config.get(country, [])}
        candidates = by_country.get(country, [])

        flagged = []
        for entry in candidates:
            if entry["league"]["id"] in already_selected_ids:
                continue
            if not args.include_all and is_excluded(entry["league"]["name"]):
                excluded_count += 1
                continue
            seasons = bc.seasons_covering_range(entry.get("seasons", []))
            if seasons:  # only flag ones that actually have real data now
                flagged.append((entry, seasons))

        if flagged:
            findings[country] = flagged

    if excluded_count and not args.include_all:
        print(f"(Filtered out {excluded_count} youth/women's/reserve/exhibition competition(s) — "
              f"pass --include-all to see them anyway)\n")

    if not findings:
        print("Nothing found — every country's declined competitions still have no real data "
              "in the current history window.")
        return

    total = sum(len(v) for v in findings.values())
    print(f"Found {total} competition(s) across {len(findings)} country(ies) that aren't in your "
          f"config yet but now have real season data:\n")

    for country, flagged in findings.items():
        print(f"{country}:")
        for entry, seasons in flagged:
            season_str = ",".join(str(s) for s in seasons)
            print(f"  [{entry['league']['type']}] {entry['league']['name']} "
                  f"(id {entry['league']['id']}, seasons: {season_str})")
        print()

    if not args.auto_add:
        print("This was a report only — nothing was added.")
        print("To add specific ones: python build_config.py --history-start "
              f"{bc.HISTORY_START} --country \"Country Name\"")
        print("To add EVERYTHING flagged above automatically instead: re-run with --auto-add")
        return

    confirm = input(f"\nAdd all {total} flagged competition(s) automatically? (y/n): ").strip().lower()
    if confirm != "y":
        print("Nothing added.")
        return

    for country, flagged in findings.items():
        config.setdefault(country, [])
        for entry, _ in flagged:
            config[country].append(bc.make_entry(entry))

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Added {total} competition(s) across {len(findings)} countries.")
    print(f"Saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
