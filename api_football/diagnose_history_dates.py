"""
diagnose_history_dates.py

Quick diagnostic - shows the distribution of "last recorded date"
across every history/{team_id}.json file, to figure out WHY
generate_rankings.py's stale-exclusion filter is excluding far more
clubs than expected. Different patterns point at different root causes:

  - One (or a handful) of dates far LATER than everything else: some
    fixture in the raw data has an anomalous/wrong date pulling the
    global "latest date" ceiling up artificially, making every normal
    club look stale by comparison even though nothing is actually wrong
    with them.

  - Most clubs clustering around one date that's earlier than expected:
    something caused a mass simultaneous drop in tracking around that
    point - e.g. a season_inclusion.json or League_Starts_updated.xlsx
    change that affected many countries/tiers at once, or the fixture
    pull itself didn't actually extend as far as expected this run.

  - A smooth/gradual spread of dates: probably normal and expected -
    clubs genuinely do drop out of tracking at different points for
    different real reasons (relegation, inactivity). Only worth
    worrying about if the COUNT at the true latest date is much smaller
    than expected.

Usage:
    python diagnose_history_dates.py
"""

import glob
import json
import os
from collections import Counter
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")


def main():
    files = glob.glob(os.path.join(HISTORY_DIR, "*.json"))
    print(f"Reading {len(files)} club history files...\n")

    last_dates = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data["dates"]:
            last_dates.append((data["team_id"], data["dates"][-1]))

    counter = Counter(d for _, d in last_dates)
    by_date = sorted(counter.items(), key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"))

    print(f"{'DATE':<12} {'# CLUBS':>8}")
    print("-" * 22)
    for date, count in by_date:
        marker = "  <-- MAX" if count == max(counter.values()) else ""
        print(f"{date:<12} {count:>8}{marker}")

    print()
    latest = by_date[-1]
    biggest = max(by_date, key=lambda x: x[1])
    print(f"Latest date in the dataset: {latest[0]} ({latest[1]} club(s))")
    print(f"Date with the MOST clubs:   {biggest[0]} ({biggest[1]} club(s))")

    if latest[0] != biggest[0]:
        print()
        print("These are DIFFERENT dates - the true 'latest' date has very few clubs")
        print("while a much earlier date has most of them. This points at an anomalous")
        print("outlier: something with a genuinely later (possibly wrong) date exists")
        print("in the data, separate from where the bulk of clubs actually stand.")
        print()
        outlier_teams = [tid for tid, d in last_dates if d == latest[0]]
        print(f"team_id(s) with the anomalous latest date ({latest[0]}): {outlier_teams}")


if __name__ == "__main__":
    main()
