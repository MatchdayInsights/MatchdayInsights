"""
preview_rankings.py

Standalone sanity-check tool - NOT part of the real rankings.json
pipeline (that comes next). Reads every club's LATEST snapshot from
history/{team_id}.json, joins it against team names scraped from raw
fixture data (data/fixtures/*.csv), sorts by current rank, and prints
the top N to the console plus a CSV for easier scanning.

Purpose: let you eyeball whether the new engine's output looks
directionally right against your currently-running manual process,
before we invest in the full rankings.json schema/design.

Usage:
    python preview_rankings.py            # top 50 to console + CSV
    python preview_rankings.py --top 200   # top 200
    python preview_rankings.py --country Spain   # filter to one country
"""

import argparse
import csv
import glob
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
FIXTURES_GLOB = os.path.join(SCRIPT_DIR, "data", "fixtures", "*.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "rankings_preview.csv")


def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%m/%d/%Y")


def build_team_name_and_country_lookup() -> dict:
    """
    Scans every fixture CSV once, building team_id -> (name, country).
    Domestic-league files always take priority over continental/
    international competition files (saved under the pseudo-country
    "World", e.g. Champions League) - a top club appears in both, and
    we want its real home country, not "World". Two passes: first only
    non-World files, then fill in anything still missing (genuinely
    international-only entries, if any) from World files as a fallback.

    team_country_overrides.json is applied LAST and always wins, exactly
    matching the real pipeline's behavior (run_ratings.py's
    build_team_country_lookup) - without this, a fix Greg makes via
    overrides would correctly take effect in the real rankings.json/
    history/ output but silently NOT show up in this preview tool,
    which is exactly the kind of "did my fix actually work?" confusion
    this is meant to prevent.
    """
    lookup = {}
    csv_paths = glob.glob(FIXTURES_GLOB)

    def scan(paths, skip_world):
        for path in paths:
            base = os.path.basename(path)
            country_guess = base.split("_")[0]
            if skip_world and country_guess == "World":
                continue
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    for side in ("home", "away"):
                        tid = row.get(f"{side}_team_id")
                        name = row.get(f"{side}_team")
                        if tid and name and str(tid) not in lookup:
                            lookup[str(tid)] = (name, country_guess)

    scan(csv_paths, skip_world=True)   # pass 1: domestic files only
    scan(csv_paths, skip_world=False)  # pass 2: fill any remaining gaps from World files

    overrides_path = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
    if os.path.exists(overrides_path):
        with open(overrides_path, encoding="utf-8") as f:
            overrides = json.load(f)
        for tid, country in overrides.items():
            name = lookup.get(tid, (f"(unknown, team_id={tid})", None))[0]
            lookup[tid] = (name, country)

    return lookup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=50, help="How many rows to show (default 50)")
    parser.add_argument("--country", type=str, default=None,
                         help="Optional: only show clubs whose team_id was first seen "
                              "under this country string (rough filter, for spot-checking)")
    args = parser.parse_args()

    if not os.path.isdir(HISTORY_DIR):
        print(f"No history/ directory found at {HISTORY_DIR} - run run_ratings.py first.")
        return

    print("Building team_id -> name lookup from fixture data...")
    name_lookup = build_team_name_and_country_lookup()
    print(f"  {len(name_lookup)} team_ids resolved to a name.")

    rows = []
    history_files = glob.glob(os.path.join(HISTORY_DIR, "*.json"))
    print(f"Reading {len(history_files)} club history files...")

    # First pass: find the true "latest" snapshot date across the whole
    # dataset (the date of the most recent run_ratings.py catch-up
    # snapshot). A club whose history stops before this date has
    # correctly dropped out of the tracked universe at some point
    # (relegated to an unranked tier, or its whole tier fell out of
    # season_inclusion for that season) - showing its last (stale) rank
    # as if it were current is meaningless, since that rank was only
    # ever valid against a completely different, smaller, older universe
    # of clubs. Only clubs still active as of the true latest date belong
    # in a "current" rankings view.
    all_data = []
    latest_date = None
    latest_date_parsed = None
    for path in history_files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not data["dates"]:
            continue
        all_data.append(data)
        this_last = parse_date(data["dates"][-1])
        if latest_date_parsed is None or this_last > latest_date_parsed:
            latest_date_parsed = this_last
            latest_date = data["dates"][-1]

    dropped_count = 0
    for data in all_data:
        if data["dates"][-1] != latest_date:
            dropped_count += 1
            continue
        team_id = data["team_id"]
        name, country = name_lookup.get(team_id, (f"(unknown name, team_id={team_id})", "?"))
        rows.append({
            "rank": data["r"][-1],
            "club": name,
            "country": country,
            "elo": round(data["e"][-1], 1),
            "as_of": data["dates"][-1],
            "team_id": team_id,
        })
    print(f"  {dropped_count} clubs excluded - no longer part of the tracked universe as of "
          f"the latest snapshot ({latest_date}), so their last known rank/elo is stale and "
          f"not comparable to currently-tracked clubs.")

    rows.sort(key=lambda x: x["rank"])

    if args.country:
        rows = [r for r in rows if r["country"].lower() == args.country.lower()]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "club", "country", "elo", "as_of", "team_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote full sorted list ({len(rows)} clubs) to {OUTPUT_CSV}\n")

    print(f"{'RANK':>5}  {'CLUB':<32} {'COUNTRY':<16} {'ELO':>8}  AS OF")
    print("-" * 80)
    for r in rows[:args.top]:
        print(f"{r['rank']:>5}  {r['club']:<32.32} {r['country']:<16.16} {r['elo']:>8}  {r['as_of']}")


if __name__ == "__main__":
    main()
