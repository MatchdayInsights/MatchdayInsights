"""
reopen_unmatched.py

Removes every entry currently marked unmatched (null / 'k') from
crosswalk.json, sending them back into the "needs review" pool WITHOUT
touching anything you've already resolved.

After running this, just run build_crosswalk.py normally — since
everything else is already decided, it'll only prompt you for these.

USAGE:
    python reopen_unmatched.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")


def main():
    if not os.path.exists(CROSSWALK_PATH):
        print(f"{CROSSWALK_PATH} not found.")
        return

    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)

    unmatched = [name for name, value in crosswalk.items() if value is None]

    if not unmatched:
        print("Nothing marked unmatched — nothing to reopen.")
        return

    print(f"{len(unmatched)} club(s) currently marked unmatched:")
    for name in unmatched:
        print(f"  {name}")

    confirm = input(f"\nReopen these {len(unmatched)} for review? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled — nothing changed.")
        return

    for name in unmatched:
        del crosswalk[name]

    with open(CROSSWALK_PATH, "w", encoding="utf-8") as f:
        json.dump(crosswalk, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"\nRemoved {len(unmatched)} entries. Run build_crosswalk.py now — "
          f"it'll only prompt for these, since everything else is already resolved.")


if __name__ == "__main__":
    main()
