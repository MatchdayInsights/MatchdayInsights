"""
list_cross_confederation_friendlies.py

Lists the individual matches behind summarize_cross_confederation_friendlies.py's
aggregate table, so a surprising number (e.g. "724 AFC vs UEFA matches -
is that real?") can actually be eyeballed rather than just trusted.

Usage:
    python list_cross_confederation_friendlies.py --confed_a AFC --confed_b UEFA
    python list_cross_confederation_friendlies.py --confed_a AFC --confed_b UEFA --since 2023
    python list_cross_confederation_friendlies.py --confed_a AFC --confed_b UEFA --top 30
    python list_cross_confederation_friendlies.py   # no filter - lists everything
"""

import argparse
import csv
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "cross_confederation_friendlies.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confed_a", type=str, default=None,
                         help="Only show matches involving this confederation (e.g. AFC)")
    parser.add_argument("--confed_b", type=str, default=None,
                         help="Combined with --confed_a, only show matches between exactly "
                              "these two confederations (order doesn't matter)")
    parser.add_argument("--since", type=int, default=None,
                         help="Only include friendlies from this season onward")
    parser.add_argument("--top", type=int, default=None,
                         help="Only print the first N matches to console (the CSV always "
                              "has everything) - useful when a filtered result is still huge")
    args = parser.parse_args()

    if not os.path.exists(INPUT_PATH):
        print(f"No {INPUT_PATH} found - run pull_cross_confederation_friendlies.py first.")
        return

    with open(INPUT_PATH, encoding="utf-8") as f:
        friendlies = json.load(f)

    if args.since:
        friendlies = [m for m in friendlies if m["season"] >= args.since]

    if args.confed_a and args.confed_b:
        wanted = {args.confed_a.upper(), args.confed_b.upper()}
        friendlies = [
            m for m in friendlies
            if {m["home_confederation"], m["away_confederation"]} == wanted
        ]
    elif args.confed_a:
        wanted = args.confed_a.upper()
        friendlies = [
            m for m in friendlies
            if m["home_confederation"] == wanted or m["away_confederation"] == wanted
        ]

    friendlies.sort(key=lambda m: m["date"])

    if not friendlies:
        print("No matches found for that filter.")
        return

    csv_path = os.path.join(SCRIPT_DIR, "cross_confederation_friendlies_filtered.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "home_team", "home_confederation", "home_score",
                          "away_score", "away_confederation", "away_team", "season"])
        for m in friendlies:
            writer.writerow([m["date"], m["home_team"], m["home_confederation"],
                              m["home_score"], m["away_score"], m["away_confederation"],
                              m["away_team"], m["season"]])
    print(f"Wrote all {len(friendlies)} matching fixture(s) to {csv_path}\n")

    to_print = friendlies[:args.top] if args.top else friendlies
    print(f"{'DATE':<12} {'HOME':<28} {'SCORE':^9} {'AWAY':<28} {'S'}")
    print("-" * 90)
    for m in to_print:
        date_str = datetime.fromisoformat(m["date"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        home = f"{m['home_team']} ({m['home_confederation']})"
        away = f"{m['away_team']} ({m['away_confederation']})"
        score = f"{m['home_score']}-{m['away_score']}"
        print(f"{date_str:<12} {home:<28.28} {score:^9} {away:<28.28} {m['season']}")

    if args.top and len(friendlies) > args.top:
        print(f"\n...({len(friendlies) - args.top} more not shown here - see the CSV for everything)")


if __name__ == "__main__":
    main()
