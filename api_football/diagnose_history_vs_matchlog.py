"""
diagnose_history_vs_matchlog.py

history/{team_id}.json and match_log/{team_id}.json are written by two
different mechanisms (snapshot-moment-based vs per-match-based) and can
legitimately end up covering slightly different populations of clubs.
This shows exactly which team_ids differ, so a count mismatch between
the two directories can be diagnosed with real examples instead of
guessed at.

Usage:
    python diagnose_history_vs_matchlog.py
"""

import glob
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
MATCH_LOG_DIR = os.path.join(SCRIPT_DIR, "match_log")


def ids_in(directory):
    return {
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(directory, "*.json"))
    }


def main():
    history_ids = ids_in(HISTORY_DIR)
    match_log_ids = ids_in(MATCH_LOG_DIR)

    only_history = history_ids - match_log_ids
    only_match_log = match_log_ids - history_ids

    print(f"history/: {len(history_ids)} files")
    print(f"match_log/: {len(match_log_ids)} files")
    print(f"In both: {len(history_ids & match_log_ids)}")
    print(f"Only in history/ (no match_log/ entry): {len(only_history)}")
    print(f"Only in match_log/ (no history/ entry): {len(only_match_log)}")

    if only_match_log:
        print(f"\n=== team_id(s) with a match_log/ entry but NO history/ entry ===")
        for tid in sorted(only_match_log)[:20]:
            path = os.path.join(MATCH_LOG_DIR, f"{tid}.json")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            matches = data["matches"]
            if matches:
                print(f"  team_id={tid}: {len(matches)} match(es) in log, "
                      f"dates {matches[0]['date']} to {matches[-1]['date']}")
            else:
                print(f"  team_id={tid}: empty log")
        if len(only_match_log) > 20:
            print(f"  ...({len(only_match_log) - 20} more)")

    if only_history:
        print(f"\n=== team_id(s) with a history/ entry but NO match_log/ entry ===")
        for tid in sorted(only_history)[:20]:
            path = os.path.join(HISTORY_DIR, f"{tid}.json")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"  team_id={tid}: {len(data['dates'])} snapshot(s), "
                  f"{data['dates'][0]} to {data['dates'][-1]}")
        if len(only_history) > 20:
            print(f"  ...({len(only_history) - 20} more)")


if __name__ == "__main__":
    main()
