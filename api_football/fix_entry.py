"""
fix_entry.py

Quickly look up and correct ONE entry in crosswalk.json — for when you
picked wrong, hit 'k' by mistake, or just want to double-check a specific
club — without hunting through a huge JSON file by hand or re-running the
whole review session.

USAGE:
    python fix_entry.py "1. FC Duren"

    Searches crosswalk.json for entries whose key contains that text
    (case-insensitive), shows the current value, and lets you:
      - type a new value to set it
      - type 'k' to mark it unmatched
      - type 'd' to delete the entry entirely (goes back to "needs review"
        next time you run build_crosswalk.py)
      - Enter to leave it unchanged
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")


def main():
    if len(sys.argv) < 2:
        print('Usage: python fix_entry.py "search text"')
        return

    query = " ".join(sys.argv[1:]).lower()

    if not os.path.exists(CROSSWALK_PATH):
        print(f"{CROSSWALK_PATH} not found.")
        return

    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)

    matches = [k for k in crosswalk if query in k.lower()]

    if not matches:
        print(f"No entries found containing '{query}'.")
        return

    for key in matches:
        current = crosswalk[key]
        current_display = current if current is not None else "(marked unmatched)"
        print(f"\n'{key}'  ->  {current_display}")

        choice = input(
            "  New value, 'k' to mark unmatched, 'd' to delete (re-review later), "
            "or Enter to leave unchanged: "
        ).strip()

        if not choice:
            continue
        elif choice.lower() == "d":
            del crosswalk[key]
            print("  Deleted — will show up again next time you run build_crosswalk.py.")
        elif choice.lower() == "k":
            crosswalk[key] = None
            print("  Marked unmatched.")
        else:
            crosswalk[key] = choice
            print(f"  Updated to '{choice}'.")

        with open(CROSSWALK_PATH, "w", encoding="utf-8") as f:
            json.dump(crosswalk, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\nSaved to {CROSSWALK_PATH}")


if __name__ == "__main__":
    main()
