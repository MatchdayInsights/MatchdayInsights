"""
generate_competition_classification_sheet.py

Reads leagues_config.json and flattens every competition entry (across
all 171 countries plus the "World" continental/global list) into a CSV
with empty type/tier columns for you to fill in - one-time classification
work, done in a spreadsheet rather than 585 individual terminal prompts.

Usage:
    python generate_competition_classification_sheet.py

Produces: competition_classification.csv

HOW TO FILL IT IN:
    type column - one of:
        league      - a domestic league division (tracked or untracked)
        cup         - a domestic knockout cup
        supercup    - a domestic super cup / single-match curtain-raiser
        continental - a confederation club competition (UCL, Libertadores, etc.)
        global      - a FIFA club competition (Club World Cup, Intercontinental Cup)

    tier column - ONLY fill in for type == "league":
        1, 2, 3, 4, etc. - which division this is within its country's
        pyramid. Leave blank for cup/supercup/continental/global rows.

    Once filled in, run apply_competition_classification.py to merge
    your answers back into leagues_config.json (adds "type" and "tier"
    keys to each competition entry).
"""

import csv
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "competition_classification.csv")


def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        leagues = json.load(f)

    rows = []
    for country, comps in leagues.items():
        for comp in comps:
            seasons = comp.get("seasons", [])
            if not seasons:
                seasons_display = ""
            elif len(seasons) == 1:
                seasons_display = str(seasons[0])
            else:
                seasons_display = f"{min(seasons)}-{max(seasons)}"
            rows.append({
                "country": country,
                "name": comp["name"],
                "league_id": comp["league_id"],
                "seasons": seasons_display,
                "type": "",   # <- fill in: league / cup / supercup / continental / global
                "tier": "",   # <- fill in ONLY for type == "league"
            })

    # Sort by country, then league_id, so it's stable and easy to scan -
    # "World" naturally sorts last alphabetically, keeping continental/
    # global entries grouped together at the end.
    rows.sort(key=lambda r: (r["country"], r["league_id"]))

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "name", "league_id", "seasons", "type", "tier"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} competition entries to {OUTPUT_PATH}")
    print("Fill in the 'type' column for every row, and 'tier' for league rows only.")
    print("Then run apply_competition_classification.py to merge your answers back in.")


if __name__ == "__main__":
    main()
