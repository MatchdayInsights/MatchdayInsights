"""
summarize_cross_confederation_friendlies.py

Reads cross_confederation_friendlies.json (from
pull_cross_confederation_friendlies.py) and builds a quick-review table:
for every confederation PAIR, how did each side do against the other -
W-D-L and points percentage (3 for a win, 1 for a draw, standard
scoring) from each confederation's own perspective.

Usage:
    python summarize_cross_confederation_friendlies.py
    python summarize_cross_confederation_friendlies.py --since 2023   # only friendlies from this season onward
"""

import argparse
import json
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "cross_confederation_friendlies.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=int, default=None,
                         help="Only include friendlies from this season onward (default: all)")
    args = parser.parse_args()

    if not os.path.exists(INPUT_PATH):
        print(f"No {INPUT_PATH} found - run pull_cross_confederation_friendlies.py first.")
        return

    with open(INPUT_PATH, encoding="utf-8") as f:
        friendlies = json.load(f)

    if args.since:
        friendlies = [m for m in friendlies if m["season"] >= args.since]

    # (confed_a, confed_b) -> {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
    # always recorded from confed_a's perspective, where confed_a < confed_b
    # alphabetically, so each pairing is stored exactly once regardless of
    # which side was "home" in a given match.
    records = defaultdict(lambda: {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "matches": 0})

    for m in friendlies:
        home_confed = m["home_confederation"]
        away_confed = m["away_confederation"]
        home_score = m["home_score"]
        away_score = m["away_score"]
        if home_score is None or away_score is None:
            continue

        if home_confed < away_confed:
            key = (home_confed, away_confed)
            gf, ga = home_score, away_score
        else:
            key = (away_confed, home_confed)
            gf, ga = away_score, home_score

        rec = records[key]
        rec["matches"] += 1
        rec["gf"] += gf
        rec["ga"] += ga
        if gf > ga:
            rec["w"] += 1
        elif gf < ga:
            rec["l"] += 1
        else:
            rec["d"] += 1

    if not records:
        print("No cross-confederation friendlies found in the input file "
              f"{'for season ' + str(args.since) + ' onward' if args.since else ''}.")
        return

    print(f"{'CONFEDERATION A':<12} {'CONFEDERATION B':<12} {'MATCHES':>8} "
          f"{'A: W-D-L':>12} {'A GF-GA':>10} {'A PTS%':>8}")
    print("-" * 68)
    for (confed_a, confed_b), rec in sorted(records.items()):
        pts = rec["w"] * 3 + rec["d"]
        max_pts = rec["matches"] * 3
        pts_pct = 100 * pts / max_pts if max_pts else 0.0
        wdl = f"{rec['w']}-{rec['d']}-{rec['l']}"
        gfga = f"{rec['gf']}-{rec['ga']}"
        print(f"{confed_a:<12} {confed_b:<12} {rec['matches']:>8} "
              f"{wdl:>12} {gfga:>10} {pts_pct:>7.1f}%")

    print()
    print("Reading the table: 'A: W-D-L' and 'A PTS%' are always from CONFEDERATION A's "
          "perspective (the alphabetically-first confederation in each row) - e.g. a "
          "CAF/UEFA row shows how CAF clubs did against UEFA clubs, not the reverse.")


if __name__ == "__main__":
    main()
