"""
rename_files.py

Renames everything in data/standings/ and data/fixtures/ from the
league_id-based naming (e.g. 39_2025.csv) to a readable convention using
the country and competition name from leagues_config.json:

    England_Premier-League_39_2025.csv

The league_id and season stay in the filename (for traceability and
guaranteed uniqueness) — only the cryptic leading number gets a readable
prefix.

Safe to re-run: already-renamed files are detected and skipped, so this
won't double-rename anything if you run it again after a fresh pull_data.py
adds new files alongside already-renamed ones.

USAGE:
    python rename_files.py
"""

import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
DATA_DIRS = [
    os.path.join(SCRIPT_DIR, "data", "standings"),
    os.path.join(SCRIPT_DIR, "data", "fixtures"),
]

OLD_NAME_RE = re.compile(r"^(\d+)_(\d{4})\.csv$")  # matches e.g. "39_2025.csv"


def sanitize(text):
    """Make a string safe for a Windows filename: strip accents/punctuation,
    collapse whitespace to single hyphens, drop anything filesystem-unsafe."""
    # Replace common problematic characters outright
    text = text.replace("&", "and")
    # Keep letters (incl. accented), digits, spaces, hyphens — drop everything else
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def build_lookup(config):
    """Map league_id -> (country, competition_name)."""
    lookup = {}
    for country, comps in config.items():
        for comp in comps:
            lookup[comp["league_id"]] = (country, comp.get("name", str(comp["league_id"])))
    return lookup


def rename_in_dir(directory, lookup):
    if not os.path.isdir(directory):
        print(f"  (skipping, folder not found: {directory})")
        return 0, 0, 0

    renamed, already_done, unmatched = 0, 0, 0

    for filename in os.listdir(directory):
        if not filename.endswith(".csv"):
            continue

        m = OLD_NAME_RE.match(filename)
        if not m:
            already_done += 1  # assume it's already in the new format (or unrelated file) — leave alone
            continue

        league_id, season = int(m.group(1)), m.group(2)

        if league_id not in lookup:
            print(f"    WARNING: {filename} — league_id {league_id} not found in leagues_config.json, leaving as-is")
            unmatched += 1
            continue

        country, name = lookup[league_id]
        new_filename = f"{sanitize(country)}_{sanitize(name)}_{league_id}_{season}.csv"

        old_path = os.path.join(directory, filename)
        new_path = os.path.join(directory, new_filename)

        if os.path.exists(new_path):
            print(f"    SKIP (target already exists): {filename} -> {new_filename}")
            continue

        os.rename(old_path, new_path)
        print(f"    {filename}  ->  {new_filename}")
        renamed += 1

    return renamed, already_done, unmatched


def main():
    if not os.path.exists(CONFIG_PATH):
        print("leagues_config.json not found.")
        return

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    lookup = build_lookup(config)
    print(f"Loaded {len(lookup)} competitions from leagues_config.json\n")

    total_renamed = 0
    for directory in DATA_DIRS:
        print(f"{directory}:")
        renamed, already_done, unmatched = rename_in_dir(directory, lookup)
        total_renamed += renamed
        print(f"  Renamed: {renamed}   Already in new format / other files: {already_done}   Unmatched: {unmatched}\n")

    print(f"Done. {total_renamed} file(s) renamed total.")


if __name__ == "__main__":
    main()
