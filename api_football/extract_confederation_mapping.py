"""
extract_confederation_mapping.py

Reads Leagues_Included_in_Ranking.xlsx and produces
confederation_mapping.json: {base_country_code: confederation_name}.

WHY THIS EXISTS: rankings.json's "league" field (the season label shown
on a club's page, e.g. "2026-27" vs "2026") needs to know which
confederation a country belongs to - UEFA/CONCACAF/CAF/AFC display as
hyphenated two-year spans, CONMEBOL/OFC display as a bare year, since
CONMEBOL/OFC run calendar-year seasons while the others don't. Rather
than hand-type a ~200-country static list (real risk of edge-case
errors - Israel is UEFA not AFC, Australia is AFC not OFC, Kazakhstan
is UEFA not AFC, Guyana/Suriname are CONCACAF not CONMEBOL despite
being geographically South American, etc.), this derives the mapping
directly from the SAME spreadsheet block structure
extract_season_inclusion.py already reads - each confederation's column
block contains exactly the country/tier codes that confederation
governs, per Greg's own already-curated data.

Scans every season-column within each confederation's block (not just
one), and collects every unique BASE country code found (a tier suffix
like "_2" is stripped - confederation membership doesn't vary by tier).

Usage:
    python extract_confederation_mapping.py
"""

import json
import os

import openpyxl
from openpyxl.utils import column_index_from_string

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "Leagues_Included_in_Ranking.xlsx")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "confederation_mapping.json")

# Same column layout as extract_season_inclusion.py's CONFEDERATION_BLOCKS -
# only the column range matters here, not the season labels, since we're
# scanning every column in the block regardless of which season it is.
CONFEDERATION_BLOCKS = {
    "UEFA":     {"cols": ("B", "H"), "rows": (4, 83)},
    "AFC":      {"cols": ("K", "L"), "rows": (4, 83)},
    "CAF":      {"cols": ("O", "P"), "rows": (4, 83)},
    "CONCACAF": {"cols": ("S", "T"), "rows": (4, 83)},
    "CONMEBOL": {"cols": ("W", "X"), "rows": (4, 83)},
    "OFC":      {"cols": ("AA", "AB"), "rows": (4, 83)},
}


def base_code(code: str) -> str:
    """Strips a tier suffix, e.g. "ENG_2" -> "ENG". Confederation
    membership is the same across every tier of a given country."""
    return code.split("_")[0]


def main():
    wb = openpyxl.load_workbook(INPUT_PATH, data_only=True)
    ws = wb["Sheet1"]

    mapping = {}
    conflicts = []
    for confed, block in CONFEDERATION_BLOCKS.items():
        col_start = column_index_from_string(block["cols"][0])
        col_end = column_index_from_string(block["cols"][1])
        row_start, row_end = block["rows"]
        codes_this_confed = set()
        for row in range(row_start, row_end + 1):
            for col in range(col_start, col_end + 1):
                val = ws.cell(row=row, column=col).value
                if val:
                    codes_this_confed.add(base_code(str(val).strip()))

        for code in codes_this_confed:
            if code in mapping and mapping[code] != confed:
                conflicts.append((code, mapping[code], confed))
            mapping[code] = confed

    if conflicts:
        print(f"WARNING: {len(conflicts)} country code(s) appeared in more than one "
              f"confederation's block - this shouldn't happen (a country doesn't "
              f"change confederation season to season), check for a typo/misplaced "
              f"code in the spreadsheet:")
        for code, confed1, confed2 in conflicts:
            print(f"  {code}: seen under both {confed1!r} and {confed2!r}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)

    by_confed = {}
    for code, confed in mapping.items():
        by_confed.setdefault(confed, []).append(code)
    print(f"\nWrote {len(mapping)} country codes to {OUTPUT_PATH}")
    for confed in CONFEDERATION_BLOCKS:
        codes = sorted(by_confed.get(confed, []))
        print(f"  {confed}: {len(codes)} countries")


if __name__ == "__main__":
    main()
