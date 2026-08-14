"""
list_all_countries.py

Prints every unique country name actually present in leagues_master.json —
run this to get the REAL strings API-Football uses, so any hardcoded
country lists (like UEFA_COUNTRIES in build_config.py / scan_missed_leagues.py)
can be corrected against ground truth instead of guessed at one mismatch
at a time.

USAGE:
    python list_all_countries.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")


def main():
    if not os.path.exists(MASTER_PATH):
        print(f"{MASTER_PATH} not found.")
        return

    with open(MASTER_PATH, encoding="utf-8") as f:
        master = json.load(f)

    countries = sorted(set(e["country"].get("name") or "(none)" for e in master))

    print(f"{len(countries)} unique country names found in leagues_master.json:\n")
    for c in countries:
        print(f"  {c}")


if __name__ == "__main__":
    main()
