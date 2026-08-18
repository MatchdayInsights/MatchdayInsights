"""
extract_go_live_dates.py

Now that pull_data.py only pulls seasons at/after each confederation's
real official start (2020 for UEFA, 2025 for everyone else), the
EARLIEST fixture date in each tracked league's own fixture files IS the
real season-start date - no manual date compilation needed.

The go-live date is NOT start_date + a fixed 365-day offset - real
season kickoffs shift by days or weeks year to year, so this finds the
ACTUAL earliest fixture date of the competition's second tracked season
and uses that directly. If only one season has been pulled so far, the
real go-live date isn't knowable yet and is left as null (pending)
rather than guessed at with an approximation - re-run this script once
next season's data is pulled and it fills in automatically.

Writes go_live_dates.json:
    {code: {start_season, start_date, go_live_season, go_live_date}}

Usage:
    python extract_go_live_dates.py
"""

import csv
import glob
import json
import os
from datetime import date, datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(SCRIPT_DIR, "data", "fixtures")
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
COUNTRY_CODE_MAPPING_PATH = os.path.join(SCRIPT_DIR, "country_code_mapping.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "go_live_dates.json")

UEFA_SEASON_THRESHOLD = 2020
OTHER_SEASON_THRESHOLD = 2025

UEFA_COUNTRIES = {
    "England", "Scotland", "Wales", "Northern-Ireland", "Ireland", "Spain",
    "Germany", "Italy", "France", "Portugal", "Netherlands", "Belgium",
    "Greece", "Norway", "Turkey", "Denmark", "Czech-Republic", "Poland",
    "Croatia", "Switzerland", "Cyprus", "Serbia", "Sweden", "Kazakhstan",
    "Austria", "Russia", "Ukraine", "Andorra", "Albania", "Armenia",
    "Azerbaijan", "Belarus", "Bosnia", "Bulgaria", "Estonia",
    "Faroe-Islands", "Finland", "Georgia", "Gibraltar", "Hungary",
    "Iceland", "Israel", "Kosovo", "Latvia", "Liechtenstein", "Lithuania",
    "Luxembourg", "Macedonia", "Malta", "Moldova", "Montenegro",
    "Romania", "San-Marino", "Slovakia", "Slovenia",
}


def load_season_threshold_overrides():
    path = os.path.join(SCRIPT_DIR, "season_threshold_overrides.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


SEASON_THRESHOLD_OVERRIDES = load_season_threshold_overrides()


def season_meets_threshold(country, competition_name, season):
    """Identical logic to pull_data.py's version - kept in sync as a
    standalone copy (same reasoning as clean_leagues_config_seasons.py)
    rather than imported, to avoid coupling this to pull_data.py's
    module-level API key check."""
    season = int(season)
    if country in SEASON_THRESHOLD_OVERRIDES:
        return season >= SEASON_THRESHOLD_OVERRIDES[country]

    if country == "World":
        is_uefa = "UEFA" in competition_name
    else:
        is_uefa = country in UEFA_COUNTRIES

    threshold = UEFA_SEASON_THRESHOLD if is_uefa else OTHER_SEASON_THRESHOLD
    return season >= threshold


def build_tracked_league_codes():
    """league_id (str) -> (code, country, competition_name), for every
    type=='league' competition - country and competition_name kept
    alongside the code so season_meets_threshold() can be applied per
    fixture file, catching stale already-pulled seasons that a
    season_threshold_overrides.json entry has since excluded, not just
    seasons pull_data.py would skip on a fresh pull."""
    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)
    with open(COUNTRY_CODE_MAPPING_PATH, encoding="utf-8") as f:
        country_code_mapping = json.load(f)

    league_id_to_info = {}
    for country, comps in leagues_config.items():
        code_base = country_code_mapping.get(country)
        if code_base is None:
            continue
        for comp in comps:
            if comp.get("type") != "league":
                continue
            tier = comp.get("tier", 1)
            code = code_base if tier == 1 else f"{code_base}_{tier}"
            league_id_to_info[str(comp["league_id"])] = (code, country, comp.get("name", ""))

    return league_id_to_info


def main():
    league_id_to_info = build_tracked_league_codes()
    print(f"{len(league_id_to_info)} tracked league-type competitions to scan.")

    # code -> {season: earliest_match_date_that_season}, not just one
    # overall earliest date - the go-live date is the REAL start of the
    # next season, not start_date + a fixed 365-day guess, since actual
    # season kickoffs shift by days/weeks year to year.
    earliest_date_by_code_season = {}
    skipped_pre_threshold = 0

    for path in glob.glob(os.path.join(FIXTURES_DIR, "*.csv")):
        filename = os.path.basename(path)
        parts = filename.replace(".csv", "").split("_")
        if len(parts) < 2 or not parts[-2].isdigit():
            continue
        league_id, season = parts[-2], parts[-1]

        info = league_id_to_info.get(league_id)
        if info is None:
            continue  # not a tracked league-type competition - skip
        code, country, competition_name = info

        if not season_meets_threshold(country, competition_name, season):
            skipped_pre_threshold += 1
            continue  # excludes stale already-pulled seasons too, not just future pulls

        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["played"] != "True":
                    continue
                try:
                    match_date = datetime.fromisoformat(
                        row["date"].replace("Z", "+00:00")
                    ).date()
                except (ValueError, TypeError):
                    continue

                key = (code, season)
                if key not in earliest_date_by_code_season or match_date < earliest_date_by_code_season[key]:
                    earliest_date_by_code_season[key] = match_date

    if skipped_pre_threshold:
        print(f"Skipped {skipped_pre_threshold} fixture file(s) whose season doesn't meet the "
              f"threshold (including season_threshold_overrides.json exclusions).")

    # Reorganize into code -> [(season, earliest_date), ...] sorted chronologically
    by_code = {}
    for (code, season), earliest_date in earliest_date_by_code_season.items():
        by_code.setdefault(code, []).append((season, earliest_date))

    result = {}
    pending = []
    for code, season_dates in sorted(by_code.items()):
        season_dates.sort(key=lambda x: x[1])  # sort by actual date, not season label
        start_season, start_date = season_dates[0]

        if len(season_dates) >= 2:
            next_season, go_live_date = season_dates[1]
            result[code] = {
                "start_season": start_season,
                "start_date": start_date.isoformat(),
                "go_live_season": next_season,
                "go_live_date": go_live_date.isoformat(),
            }
        else:
            # Only one season's data pulled so far - the real next-season
            # kickoff date isn't known yet, so don't guess at it with a
            # fixed offset. Flag as pending instead.
            result[code] = {
                "start_season": start_season,
                "start_date": start_date.isoformat(),
                "go_live_season": None,
                "go_live_date": None,
            }
            pending.append(code)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)

    print(f"Wrote {OUTPUT_PATH} - {len(result)} codes.")
    if pending:
        print(f"\n{len(pending)} code(s) only have ONE season of data pulled so far, so their real "
              f"go_live_date isn't known yet (not guessed via a fixed offset - will fill in "
              f"automatically once next season's fixtures are pulled and this script re-run):")
        for code in pending:
            print(f"  {code}")

    missing = set(info[0] for info in league_id_to_info.values()) - set(result.keys())
    if missing:
        print(f"\n{len(missing)} tracked code(s) had NO played fixture data found at all "
              f"(no fixture file pulled yet, or genuinely no matches played) - not in the output:")
        for code in sorted(missing):
            print(f"  {code}")


if __name__ == "__main__":
    main()
