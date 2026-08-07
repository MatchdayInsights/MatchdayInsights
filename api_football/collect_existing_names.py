"""
collect_existing_names.py

Pulls every club name Matchday Insights has ever tracked out of
all_history.json (its "history" object is keyed by club name — this
captures your FULL historical roster, not just clubs currently ranked,
which is exactly what you want for merging historical pre-2025 data).

USAGE:
    Copy your current all_history.json into this folder (or edit
    ALL_HISTORY_PATH below to point at it directly), then:
    python collect_existing_names.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALL_HISTORY_PATH = os.path.join(SCRIPT_DIR, "all_history.json")  # <-- adjust path if needed
OUT_PATH = os.path.join(SCRIPT_DIR, "existing_club_names.json")


def main():
    if not os.path.exists(ALL_HISTORY_PATH):
        print(f"{ALL_HISTORY_PATH} not found.")
        print("Copy your all_history.json into this folder, or edit ALL_HISTORY_PATH in this script.")
        return

    with open(ALL_HISTORY_PATH, encoding="utf-8") as f:
        data = json.load(f)

    names = sorted(data.get("history", {}).keys())

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(names, f, indent=2, ensure_ascii=False)

    print(f"Found {len(names)} club names in your existing tracking history.")
    print(f"Saved to {OUT_PATH}")


if __name__ == "__main__":
    main()
