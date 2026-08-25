"""
diagnose_club.py

Standalone diagnostic tool - traces exactly WHY a specific club did or
did not become a genuinely tracked (club_is_tracked=True) club, by
running the same setup run_ratings.py's main() does, then walking
get_starting_position() for every season that club actually appeared in.

Use this whenever a club you expect to be tracked/ranked is missing
from history/ output, instead of guessing - it'll show precisely which
check failed: no country resolved, no tier resolved, tier resolved but
not in season_inclusion.json for that season, no League_Starts value,
no untracked_club_tiers.json entry, etc.

Usage:
    python diagnose_club.py --team_id 9030
    python diagnose_club.py --name "Miami FC"
"""

import argparse
import json
import os

from run_ratings import (
    load_all_fixtures, fixture_sort_key, build_league_lookup,
    build_team_country_lookup, build_team_tier_by_season, load_league_starts,
    get_starting_position, get_team_country, apply_team_id_splits,
    SCRIPT_DIR, LEAGUES_CONFIG_PATH, COUNTRY_CODE_MAPPING_PATH,
    SEASON_INCLUSION_PATH, TEAM_ID_SPLITS_PATH,
)
from match_context_builder import _load_json


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--team_id", type=str)
    group.add_argument("--name", type=str, help="Partial, case-insensitive match against team names in fixture data")
    args = parser.parse_args()

    print("Loading fixtures (same setup as run_ratings.py)...")
    fixtures = load_all_fixtures()
    fixtures.sort(key=fixture_sort_key)

    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)
    league_lookup = build_league_lookup(leagues_config)

    splits_config = _load_json(TEAM_ID_SPLITS_PATH)
    if splits_config:
        apply_team_id_splits(fixtures, league_lookup, splits_config)

    if args.name:
        q = args.name.lower()
        matches = {}
        for row in fixtures:
            for side in ("home", "away"):
                tid = str(row[f"{side}_team_id"])
                name = row[f"{side}_team"]
                if q in name.lower():
                    matches[tid] = name
        if not matches:
            print(f"No club name containing '{args.name}' found in fixture data.")
            return
        if len(matches) > 1:
            print(f"{len(matches)} clubs match '{args.name}' - be more specific, or use --team_id:")
            for tid, name in sorted(matches.items(), key=lambda x: x[1]):
                print(f"  team_id={tid:<8} {name}")
            return
        team_id, team_name = next(iter(matches.items()))
    else:
        team_id = args.team_id
        team_name = None
        for row in fixtures:
            if str(row["home_team_id"]) == team_id:
                team_name = row["home_team"]
                break
            if str(row["away_team_id"]) == team_id:
                team_name = row["away_team"]
                break
        if team_name is None:
            print(f"team_id={team_id} does not appear as a home or away side in any pulled fixture at all.")
            return

    print(f"\n=== Diagnosing '{team_name}' (team_id={team_id}) ===\n")

    team_country_overrides_path = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
    team_country_overrides = _load_json(team_country_overrides_path)
    team_country_lookup = build_team_country_lookup(fixtures, league_lookup, team_country_overrides)

    country = get_team_country(team_id, team_country_lookup)
    print(f"1. Country resolution: {country!r}")
    if country is None:
        print("   -> FAILED HERE. This team_id never resolved to a country at all - it")
        print("      would need a team_country_overrides.json entry. Nothing downstream")
        print("      of this can work without a country.")
        return

    team_tier_by_season = build_team_tier_by_season(fixtures, league_lookup)

    with open(COUNTRY_CODE_MAPPING_PATH, encoding="utf-8") as f:
        country_code_mapping = json.load(f)
    league_starts = load_league_starts()

    untracked_club_tiers_path = os.path.join(SCRIPT_DIR, "untracked_club_tiers.json")
    untracked_club_tiers = _load_json(untracked_club_tiers_path) if os.path.exists(untracked_club_tiers_path) else None

    season_inclusion = None
    if os.path.exists(SEASON_INCLUSION_PATH):
        with open(SEASON_INCLUSION_PATH, encoding="utf-8") as f:
            season_inclusion = json.load(f)

    relegation_percentages_path = os.path.join(SCRIPT_DIR, "relegation_percentages.json")
    relegation_percentages = _load_json(relegation_percentages_path) if os.path.exists(relegation_percentages_path) else None

    base_code = country_code_mapping.get(country)
    print(f"2. Base country code (country_code_mapping.json): {base_code!r}")
    if base_code is None:
        print(f"   -> FAILED HERE. '{country}' has no entry in country_code_mapping.json.")
        return

    # Every (team_id, season) this club actually appeared in
    seasons_seen = sorted({s for (tid, s) in team_tier_by_season if tid == team_id})
    if not seasons_seen:
        print(f"3. Tier lookup: team_id={team_id} never appears as a key in team_tier_by_season at all "
              f"(no fixture row had this exact team_id on either side with a resolvable league/tier).")
    else:
        print(f"3. Seasons this club appears in (team_tier_by_season): {seasons_seen}")

    print()
    for season in seasons_seen:
        tier = team_tier_by_season.get((team_id, season))
        key = base_code if (tier is None or tier == 1) else f"{base_code}_{tier}"
        print(f"--- Season {season} ---")
        print(f"  Detected tier: {tier!r}  ->  key would be: {key!r}")

        included = None
        if season_inclusion is not None:
            included = key in season_inclusion.get(season, [])
            print(f"  In season_inclusion.json['{season}']: {included}")
        else:
            print("  season_inclusion.json not loaded (file missing) - cannot check this.")

        has_league_starts = key in league_starts
        print(f"  '{key}' in League_Starts_updated.xlsx (league_starts): {has_league_starts}")

        has_untracked_entry = untracked_club_tiers is not None and team_id in untracked_club_tiers
        print(f"  team_id in untracked_club_tiers.json: {has_untracked_entry}")

        try:
            rating, source = get_starting_position(
                team_id, season, team_country_lookup, team_tier_by_season,
                country_code_mapping, league_starts, untracked_club_tiers,
                None, None, season_inclusion, relegation_percentages,
            )
            is_tracked = source.startswith("direct") or source.startswith("league_override") or source.startswith("standard_promotion")
            print(f"  get_starting_position() result: rating={rating:.1f}, source={source!r}")
            print(f"  -> Would set club_is_tracked = {is_tracked}")
            if not is_tracked:
                if not included and season_inclusion is not None:
                    print(f"     REASON: '{key}' is not listed as an included/tracked division "
                          f"for season {season} in season_inclusion.json (from "
                          f"Leagues_Included_in_Ranking.xlsx) - even though it has real fixture "
                          f"data pulled, it's being gated to the untracked-placeholder chain "
                          f"because the season-inclusion spreadsheet doesn't mark it as tracked "
                          f"for this season.")
                elif not has_league_starts:
                    print(f"     REASON: '{key}' has no bootstrap value in League_Starts_updated.xlsx, "
                          f"so even though it may be season_inclusion-included, there's no Starting "
                          f"Position to seed it from directly.")
        except ValueError as e:
            print(f"  get_starting_position() RAISED: {e}")
        print()


if __name__ == "__main__":
    main()
