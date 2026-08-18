"""
extract_season_inclusion.py

Reads Leagues_Included_in_Ranking.xlsx and produces season_inclusion.json:
{season_label(str): [list of country_tier codes actually included that season]}

WHY THIS EXISTS: leagues_config.json's "seasons" list only tells you what
raw match data was PULLED for a competition - historical data was pulled
broadly (2020+ for Europe, 2025+ for the rest of world) regardless of
whether that specific tier was actually part of the rankings in every one
of those seasons. A country's division count shifts year to year (per
your own coefficient recalculation), so a competition can have real
fixture data for a season where it wasn't actually meant to be a tracked
division that year. This file is the real source of truth for "was this
country/tier genuinely included THIS season" - separate from "does match
data exist for it."

SPREADSHEET STRUCTURE: each confederation gets its own block of columns
(one per season, with Start/End date rows), and within a season-column,
included country/tier codes are listed down the rows - but NOT at a fixed
row position, since a country occupies as many consecutive rows as its
own division count that season, so which absolute row holds which
country's data shifts depending on how many rows the preceding
(higher-ranked) countries consumed. Rank order doesn't matter for our
purposes, so this only extracts the SET of non-blank codes per column,
ignoring row position/meaning entirely - verified against the real file
that this produces the same country/tier set regardless of ragged
row-packing.

SEASON LABEL MAPPING (confirmed against your season convention, where
season N spans Aug(N) - Jun/Aug(N+1)):
  - UEFA: each confederation block's FIRST (short, Jan-Aug) column is the
    TAIL of the season labeled one year earlier than the following full
    column, not the head of that following one.
  - AFC/CAF/CONCACAF: same stub-is-prior-season-tail logic, on an Aug-Aug
    cycle instead of Aug-June.
  - CONMEBOL/OFC: calendar-year cycle (Jan-Dec), so the first column
    aligns cleanly with its own season label, no stub adjustment needed.

Usage:
    python extract_season_inclusion.py
"""

import json
import os
import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "Leagues_Included_in_Ranking.xlsx")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "season_inclusion.json")

# Each confederation block: (first_column_letter, last_column_letter, row_range,
# list of season labels in column order - already accounting for the
# stub-column-maps-to-prior-season-label logic described above)
from openpyxl.utils import column_index_from_string

CONFEDERATION_BLOCKS = {
    "UEFA":     {"cols": ("B", "I"), "rows": (4, 83),
                 "season_labels": ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"]},
    "AFC":      {"cols": ("L", "N"), "rows": (4, 83),
                 "season_labels": ["2024", "2025", "2026"]},
    "CAF":      {"cols": ("Q", "S"), "rows": (4, 83),
                 "season_labels": ["2024", "2025", "2026"]},
    "CONCACAF": {"cols": ("V", "X"), "rows": (4, 83),
                 "season_labels": ["2024", "2025", "2026"]},
    "CONMEBOL": {"cols": ("AA", "AB"), "rows": (4, 83),
                 "season_labels": ["2025", "2026"]},
    "OFC":      {"cols": ("AE", "AF"), "rows": (4, 83),
                 "season_labels": ["2025", "2026"]},
}


def main():
    wb = openpyxl.load_workbook(INPUT_PATH, data_only=True)
    ws = wb["Sheet1"]

    season_inclusion = {}  # season_label -> set of codes

    for confed, block in CONFEDERATION_BLOCKS.items():
        first_col = column_index_from_string(block["cols"][0])
        last_col = column_index_from_string(block["cols"][1])
        row_start, row_end = block["rows"]
        labels = block["season_labels"]

        n_cols = last_col - first_col + 1
        if n_cols != len(labels):
            raise ValueError(f"{confed}: column range has {n_cols} columns but "
                              f"{len(labels)} season labels given - mismatch, check CONFEDERATION_BLOCKS.")

        for i, col in enumerate(range(first_col, last_col + 1)):
            label = labels[i]
            codes_this_column = set()
            for row in range(row_start, row_end + 1):
                val = ws.cell(row=row, column=col).value
                if val:
                    codes_this_column.add(val)

            season_inclusion.setdefault(label, set()).update(codes_this_column)

    # convert sets to sorted lists for clean JSON output
    output = {season: sorted(codes) for season, codes in season_inclusion.items()}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, sort_keys=True)

    print(f"Wrote {OUTPUT_PATH}")
    for season in sorted(output.keys()):
        print(f"  season {season}: {len(output[season])} included codes")


if __name__ == "__main__":
    main()
