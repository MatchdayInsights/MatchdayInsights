"""
clean_leagues_config_seasons.py

Removes any season from leagues_config.json's "seasons" lists that falls
before the confederation-appropriate official start (season 2020 for
UEFA, season 2025 for everyone else) - the exact same threshold logic as
pull_data.py's season_meets_threshold(), kept as an identical standalone
copy here rather than imported, so this can run without needing
API_FOOTBALL_KEY set just to clean a config file.

This doesn't change what pull_data.py actually pulls (it already skips
these seasons itself) - it just keeps leagues_config.json itself tidy and
consistent with what's really being tracked, rather than carrying stray
season entries that were pulled broadly before the true start dates were
pinned down.

Usage:
    python clean_leagues_config_seasons.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")

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
    if country in SEASON_THRESHOLD_OVERRIDES:
        return season >= SEASON_THRESHOLD_OVERRIDES[country]

    if country == "World":
        is_uefa = "UEFA" in competition_name
    else:
        is_uefa = country in UEFA_COUNTRIES

    threshold = UEFA_SEASON_THRESHOLD if is_uefa else OTHER_SEASON_THRESHOLD
    return season >= threshold


def main():
    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues = json.load(f)

    total_removed = 0
    removed_detail = []
    empty_comps = []

    for country, comps in leagues.items():
        for comp in comps:
            name = comp.get("name", comp["league_id"])
            seasons = comp.get("seasons") or []
            kept = [s for s in seasons if season_meets_threshold(country, name, s)]
            removed = [s for s in seasons if s not in kept]

            if removed:
                total_removed += len(removed)
                removed_detail.append(f"{country} / {name}: removed {removed}, kept {kept}")
                comp["seasons"] = kept

            if not kept:
                empty_comps.append(f"{country} / {name} (league_id={comp['league_id']})")

    with open(LEAGUES_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(leagues, f, indent=2, ensure_ascii=False)

    print(f"Removed {total_removed} pre-threshold season entries across {len(removed_detail)} competitions.")
    if removed_detail:
        print("\nDetail:")
        for line in removed_detail:
            print(f"  {line}")

    if empty_comps:
        print(f"\nWARNING: {len(empty_comps)} competition(s) now have ZERO seasons left at all "
              f"(every season they had was before the threshold) - these are still present in "
              f"leagues_config.json but effectively dead weight until real seasons exist for them:")
        for c in empty_comps:
            print(f"  {c}")


if __name__ == "__main__":
    main()
