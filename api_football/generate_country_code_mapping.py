"""
generate_country_code_mapping.py

leagues_config.json uses full country names ("Albania", "South-Korea").
League_Starts.xlsx (and everything else in the rating system) uses
3-letter codes ("ALB", "KOR"). This script proposes a mapping between
the two and writes it to country_code_mapping.csv for you to review and
correct - deliberately NOT auto-applying anything without your
confirmation, since a wrong guess here (e.g. "Macedonia" naively
matching "MAC", which is actually Macao's code) would silently seed
clubs with the wrong country's Starting Position.

Matching strategy, in order:
    1. Curated exception dictionary for well-known football-association
       codes that don't follow the "first 3 letters" pattern.
    2. First-3-letters-uppercase match, but ONLY if that guess doesn't
       collide with a DIFFERENT country's already-confirmed code
       (collisions get flagged, not silently picked).
    3. Anything left over is flagged as unmatched - needs your input
       entirely.

Every row gets a "confidence" column (exception / auto / COLLISION /
unmatched) so you know exactly which rows actually need your attention
vs. which are just there for your final sign-off.

Usage:
    python generate_country_code_mapping.py

Produces: country_code_mapping.csv

Review it, fix/fill any row that isn't confidence=exception or
confidence=auto, then run apply_country_code_mapping.py.
"""

import csv
import json
import os
import re
import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
LEAGUE_STARTS_PATH = os.path.join(SCRIPT_DIR, "League_Starts.xlsx")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "country_code_mapping.csv")

# Official FIFA country codes (source: RSSSF, rsssf.org/miscellaneous/fifa-codes.html,
# cross-checked against Wikipedia's List of FIFA country codes). Covers every
# standard FIFA-member exception to the "first 3 letters" pattern, plus the
# handful of non-FIFA-member entities that are still tracked by their
# confederation (e.g. Guadeloupe -> GLP under CONCACAF, per FIFA's own
# "non-member codes used by confederations" list).
KNOWN_EXCEPTIONS = {
    # Europe
    "England": "ENG", "Scotland": "SCO", "Wales": "WAL", "Northern-Ireland": "NIR",
    "Ireland": "IRL", "Germany": "GER", "Netherlands": "NED", "Spain": "ESP",
    "Switzerland": "SUI", "Czech-Republic": "CZE", "Bosnia": "BIH", "Macedonia": "MKD",
    "Faroe-Islands": "FRO", "Gibraltar": "GIB", "Belarus": "BLR", "Moldova": "MDA",
    "Kosovo": "KOS", "Liechtenstein": "LIE", "San-Marino": "SMR", "Malta": "MLT",
    "Moldova": "MDA", "Gibraltar": "GIB",
    "Latvia": "LVA", "Lithuania": "LTU", "Iceland": "ISL", "Slovenia": "SVN",
    "Slovakia": "SVK", "Serbia": "SRB", "Romania": "ROU", "Montenegro": "MNE",
    "Sweden": "SWE",
    # Asia
    "South-Korea": "KOR", "Saudi-Arabia": "KSA", "United-Arab-Emirates": "UAE",
    "Chinese-Taipei": "TPE", "Hong-Kong": "HKG", "China": "CHN", "Japan": "JPN",
    "Iran": "IRN", "Iraq": "IRQ", "Indonesia": "IDN", "Malaysia": "MAS",
    "Maldives": "MDV", "Mongolia": "MGL", "Myanmar": "MYA", "Pakistan": "PAK",
    "Palestine": "PLE", "Singapore": "SGP", "Sri-Lanka": "SRI", "Syria": "SYR",
    "Tajikistan": "TAJ", "Turkmenistan": "TKM", "Kyrgyzstan": "KGZ", "Bahrain": "BHR",
    "Cambodia": "CAM", "Macao": "MAC",
    # Africa
    "Ivory-Coast": "CIV", "Congo-DR": "COD", "Congo": "CGO", "South-Africa": "RSA",
    "Burkina-Faso": "BFA", "Burundi": "BDI", "Cameroon": "CMR", "Cape-Verde": "CPV",
    "Central-African-Republic": "CTA", "Guinea-Bissau": "GNB", "Malawi": "MWI",
    "Mauritania": "MTN", "Mauritius": "MRI", "Sao-Tome-e-Principe": "STP",
    "Sudan": "SDN", "Eswatini": "SWZ", "Zanzibar": "ZAN", "Mali": "MLI",
    "Liberia": "LBR", "Libya": "LBY", "Morocco": "MAR", "South-Sudan": "SSD",
    "Djibouti": "DJI", "Comoros": "COM", "Seychelles": "SEY", "Mozambique": "MOZ",
    "Chad": "CHA", "Madagascar": "MAD", "Central-African-Republic": "CTA",
    "Equatorial-Guinea": "EQG", "Sierra-Leone": "SLE",
    # North/Central America & Caribbean
    "Costa-Rica": "CRC", "Dominican-Republic": "DOM", "El-Salvador": "SLV",
    "Trinidad-And-Tobago": "TRI", "Antigua-And-Barbuda": "ATG", "Barbados": "BRB",
    "Belize": "BLZ", "Bermuda": "BER", "Cayman-Islands": "CAY", "Cuba": "CUB",
    "Curacao": "CUW", "Guadeloupe": "GLP", "Guatemala": "GUA", "Puerto-Rico": "PUR",
    "Saint-Kitts-and-Nevis": "SKN", "Saint-Lucia": "LCA",
    "Saint-Vincent-and-the-Grenadin": "VIN",  # exact (truncated) spelling as it
                                                # actually appears in the data
    "Turks-and-Caicos-Islands": "TCA", "British-Virgin-Islands": "VGB",
    "US-Virgin-Islands": "VIR", "Grenada": "GRN", "Nicaragua": "NCA",
    "Nigeria": "NGA", "Guyana": "GUY", "Dominica": "DMA", "Anguilla": "AIA",
    "Martinique": "MTQ", "Guinea-Bissau": "GNB", "Netherlands-Antilles": "CUW",
    # Middle East / Asia
    "Lebanon": "LBN", "Afghanistan": "AFG", "Brunei": "BRU",
    # Oceania
    "New-Zealand": "NZL", "American-Samoa": "ASA", "Cook-Islands": "COK",
    "New-Caledonia": "NCL", "Papua-New-Guinea": "PNG", "Solomon-Islands": "SOL",
    "Tahiti": "TAH", "Tonga": "TGA", "Vanuatu": "VAN", "Samoa": "SAM",
    # Europe/misc odds
    "Turkey": "TUR", "Austria": "AUT",
}


def load_valid_codes() -> set:
    wb = openpyxl.load_workbook(LEAGUE_STARTS_PATH, data_only=True)
    ws = wb["Sheet1"]
    codes = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]:
            base = re.sub(r"_\d$", "", row[0])
            codes.add(base)
    return codes


def main():
    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues = json.load(f)
    countries = set(c for c in leagues.keys() if c != "World")

    # Also pick up countries that only ever appear via team_country_overrides.json
    # (API-sourced names from resolve_unknown_countries.py, for clubs whose
    # domestic league isn't tracked in leagues_config.json at all - e.g. South
    # Sudan, Djibouti, playing only in a continental competition). Without this,
    # every such country silently falls through as "unmatched" or never gets
    # considered at all, since leagues_config.json's own keys don't cover them.
    overrides_path = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
    if os.path.exists(overrides_path):
        with open(overrides_path, encoding="utf-8") as f:
            overrides = json.load(f)
        before = len(countries)
        countries.update(overrides.values())
        added = len(countries) - before
        if added:
            print(f"Added {added} additional countries found only in team_country_overrides.json")

    valid_codes = load_valid_codes()

    used_codes = {}  # code -> country already assigned it (collision detection)
    rows = []

    for country in sorted(countries):
        if country in KNOWN_EXCEPTIONS:
            code = KNOWN_EXCEPTIONS[country]
            confidence = "exception"
        else:
            guess = country[:3].upper().replace("-", "")
            if guess in valid_codes:
                code = guess
                confidence = "auto"
            else:
                code = ""
                confidence = "unmatched"

        if code and code in used_codes and used_codes[code] != country:
            confidence = "COLLISION"
            rows.append({
                "country": country, "suggested_code": code, "confidence": confidence,
                "note": f"code {code} already claimed by {used_codes[code]!r} - needs manual resolution"
            })
            continue

        if code:
            used_codes[code] = country

        if code and code not in valid_codes:
            confidence = "unmatched"
            note = f"guessed {code!r} but it's not in League_Starts.xlsx at all"
        elif not code:
            note = "no confident guess - fill in manually"
        else:
            note = ""

        rows.append({
            "country": country, "suggested_code": code, "confidence": confidence, "note": note
        })

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "suggested_code", "confidence", "note"])
        writer.writeheader()
        writer.writerows(rows)

    n_exception = sum(1 for r in rows if r["confidence"] == "exception")
    n_auto = sum(1 for r in rows if r["confidence"] == "auto")
    n_needs_review = sum(1 for r in rows if r["confidence"] in ("unmatched", "COLLISION"))

    print(f"Wrote {len(rows)} countries to {OUTPUT_PATH}")
    print(f"  {n_exception} matched via known exceptions")
    print(f"  {n_auto} auto-matched via first-3-letters")
    print(f"  {n_needs_review} need your manual review (confidence = unmatched or COLLISION)")
    print("\nReview every row, especially anything not 'exception' or 'auto', "
          "then run apply_country_code_mapping.py.")


if __name__ == "__main__":
    main()
