"""
check_duplicates.py

For every team_id that got claimed by more than one old_name in
crosswalk.json, checks YOUR OWN all_history.json to see whether the two
old_names' rating data overlaps in time or is sequential.

  - SEQUENTIAL (one name's data ends right around when the other begins):
    almost certainly fine — just a naming convention change in your own
    source spreadsheet over time, nothing to fix.

  - OVERLAPPING (both names have real rating data in the same date range):
    a real issue worth investigating — your own historical data may have
    genuinely tracked the same club twice under two different names
    simultaneously, which would need manual reconciliation.

USAGE:
    python check_duplicates.py
    (needs crosswalk.json AND all_history.json in this folder)
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")
ALL_HISTORY_PATH = os.path.join(SCRIPT_DIR, "all_history.json")
API_NAMES_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")


def get_identity_entries(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [(value, None)]
    if isinstance(value, dict):
        return [(value.get("name"), value.get("team_id"))]
    if isinstance(value, list):
        return [(v.get("name"), v.get("team_id")) for v in value if isinstance(v, dict)]
    return []


def date_range_with_data(name, history, dates):
    entry = history.get(name)
    if not entry:
        return None
    e_list = entry.get("e", [])
    active_dates = [dates[i] for i, v in enumerate(e_list) if v is not None and i < len(dates)]
    if not active_dates:
        return None
    return active_dates[0], active_dates[-1], len(active_dates)


def ranges_overlap(range_a, range_b, dates):
    idx = {d: i for i, d in enumerate(dates)}
    a_start, a_end = idx.get(range_a[0]), idx.get(range_a[1])
    b_start, b_end = idx.get(range_b[0]), idx.get(range_b[1])
    if None in (a_start, a_end, b_start, b_end):
        return None
    return a_start <= b_end and b_start <= a_end


def main():
    if not os.path.exists(CROSSWALK_PATH):
        print(f"{CROSSWALK_PATH} not found.")
        return
    if not os.path.exists(ALL_HISTORY_PATH):
        print(f"{ALL_HISTORY_PATH} not found. Copy your all_history.json into this folder.")
        return
    if not os.path.exists(API_NAMES_PATH):
        print(f"{API_NAMES_PATH} not found. Run collect_api_names.py first.")
        return

    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)
    with open(ALL_HISTORY_PATH, encoding="utf-8") as f:
        all_history_data = json.load(f)
    with open(API_NAMES_PATH, encoding="utf-8") as f:
        api_data = json.load(f)

    # Plain-string crosswalk values (the common case -- unambiguous matches)
    # don't carry an explicit team_id, so look it up here. Missing this step
    # is what caused 16 of 17 real duplicates to go undetected before.
    name_to_id = {}
    for name, entries in api_data.items():
        if len(entries) == 1:
            name_to_id[name] = entries[0]["team_id"]

    dates = all_history_data.get("dates", [])
    history = all_history_data.get("history", {})

    team_id_to_old_names = {}
    for old_name, value in crosswalk.items():
        for name, team_id in get_identity_entries(value):
            if not team_id:
                team_id = name_to_id.get(name)
            if team_id:
                team_id_to_old_names.setdefault(team_id, set()).add(old_name)

    duplicates = {tid: names for tid, names in team_id_to_old_names.items() if len(names) > 1}

    if not duplicates:
        print("No duplicates found.")
        return

    print(f"Checking {len(duplicates)} duplicate(s) against your own rating history...\n")

    for tid, names in duplicates.items():
        names = sorted(names)
        print(f"team_id {tid}: {' vs '.join(names)}")

        ranges = {}
        for name in names:
            r = date_range_with_data(name, history, dates)
            if r:
                ranges[name] = r
                print(f"  '{name}': {r[2]} datapoints, {r[0]} -> {r[1]}")
            else:
                print(f"  '{name}': no rating history data found under this exact name")

        if len(ranges) == 2:
            (name_a, range_a), (name_b, range_b) = list(ranges.items())
            overlap = ranges_overlap(range_a, range_b, dates)
            if overlap is None:
                print("  -> Could not determine overlap (date format mismatch)")
            elif overlap:
                print("  -> WARNING: OVERLAPPING -- both names have data in the same period. Worth investigating.")
            else:
                print("  -> OK -- sequential, not overlapping. Likely just a naming change over time.")
        print()


if __name__ == "__main__":
    main()
