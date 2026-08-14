"""
run_ratings.py

Orchestration script: reads pull_data.py's fixture CSVs, processes every
played match in strict chronological order (globally, not per-league,
since a club's rating must reflect matches in the order they actually
happened across ALL competitions it played in), and produces updated
club ratings via elo_engine.py + match_context_builder.py.

KNOWN GAPS - see the three raise NotImplementedError points below.
pull_data.py's current output doesn't yet carry everything MatchContext
needs:
    1. venue_id - not extracted by pull_fixtures() at all yet
    2. competition_type / competition_name - only league_id is present;
       needs a leagues_config.json lookup
    3. home_team_country / away_team_country - not present; needs a
       team_id -> country mapping (likely already exists in your
       crosswalk tooling)

This script is structured so those three lookups are isolated in their
own functions (get_venue_id, get_competition_info, get_team_country) -
once you tell me how each is sourced, only those three functions need
real implementations; everything else here is ready to run as-is.

Usage:
    python run_ratings.py
"""

import csv
import glob
import json
import os
import sys
from datetime import datetime
from typing import Optional

import openpyxl

from elo_engine import (
    ClubState,
    MatchContext,
    needs_starting_position_reset,
    process_match,
    starting_position_standard,
    untracked_placeholder_rating,
)
from match_context_builder import build_match_context, _load_json, FINALS_CONFIG_PATH, VENUE_OVERRIDES_PATH

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(SCRIPT_DIR, "data", "fixtures")
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
COUNTRY_CODE_MAPPING_PATH = os.path.join(SCRIPT_DIR, "country_code_mapping.json")
LEAGUE_STARTS_PATH = os.path.join(SCRIPT_DIR, "League_Starts_updated.xlsx")
TEAM_ID_SPLITS_PATH = os.path.join(SCRIPT_DIR, "team_id_splits.json")
TEAM_ID_SPLIT_RESOLUTIONS_PATH = os.path.join(SCRIPT_DIR, "team_id_split_resolutions.json")

# Countries deliberately excluded from the rating engine entirely (raises
# rather than assigning any rating) - NOT the same as a country that simply
# has no domestic league data tracked (see UNRANKED_COUNTRY_DEFAULT below,
# which handles that case as a permanently-unranked club instead). Crimea's
# competition was already removed from leagues_config.json, so its clubs
# shouldn't reach this function at all in practice - kept here as a safety
# net and for any future deliberate exclusions.
EXCLUDED_COUNTRIES = {"Crimea"}

# Flat default Starting Position for a club whose country has NO domestic
# league tracked in leagues_config.json at all (e.g. Djibouti, South-Sudan -
# clubs only ever seen via CECAFA/CAF continental competitions). Matches
# the same "zero confederation coefficient -> 500.00" floor used everywhere
# else in this system (Bermuda, Cuba, Mongolia, Pakistan, Yemen all got this
# same default in League_Starts_updated.xlsx), for consistency.
UNRANKED_COUNTRY_DEFAULT = 500.0


# ---------------------------------------------------------------------------
# STARTING POSITION SEEDING
# ---------------------------------------------------------------------------

def load_league_starts() -> dict:
    """
    Reads League_Starts_updated.xlsx into {code_or_code_tier: start_rating},
    e.g. {"ENG": 1844.67, "ENG_2": 1156.55, "BER": 500.0, ...}. A bare code
    (no _N suffix) means tier 1.
    """
    wb = openpyxl.load_workbook(LEAGUE_STARTS_PATH, data_only=True)
    ws = wb["Sheet1"]
    starts = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        code = row[0]
        if not code:
            continue
        value = row[1] if row[1] is not None else row[2]
        if value is not None:
            starts[code] = value
    return starts


def build_team_tier_by_season(fixtures: list[dict], league_lookup: dict) -> dict:
    """
    (team_id, season) -> tier, built from every fixture belonging to a
    type=="league" competition. Keyed by season (not just team_id) since
    a club's TIER changes across seasons (promotion/relegation) even
    though its COUNTRY never does - unlike build_team_country_lookup,
    this can't safely be a single global team_id -> value lookup.
    """
    lookup = {}
    for row in fixtures:
        entry = league_lookup.get(int(row["league_id"]))
        if entry is None or entry["type"] != "league":
            continue
        for team_id in (row["home_team_id"], row["away_team_id"]):
            lookup[(team_id, row["season"])] = entry["tier"]
    return lookup


# ---------------------------------------------------------------------------
# SEASON-BOUNDARY SNAPSHOTS
# (the automated equivalent of your "Included League Starts" spreadsheet's
# per-club end-of-season Max Game / Rating columns)
# ---------------------------------------------------------------------------

def build_season_end_trigger_points(fixtures: list[dict], league_lookup: dict) -> dict:
    """
    For every (league_id, season) group of type=="league" fixtures, finds
    the index (in the globally chronologically-sorted fixtures list) of
    that group's LAST match - the exact moment at which it's safe to
    snapshot every club in that tier's rating as "end of season" data,
    since no later match in that group can still change it.

    Returns {fixture_list_index: [(league_id, season), ...]} - a list
    per index since, in principle, more than one group's final match
    could land on the same index position (extremely unlikely with
    real timestamps, but handled rather than silently dropped).

    IMPORTANT: call this AFTER fixtures has been sorted chronologically,
    using enumerate() over that exact same sorted list - the indices
    are only meaningful relative to that specific order.
    """
    last_index = {}  # (league_id, season) -> highest index seen so far
    for i, row in enumerate(fixtures):
        entry = league_lookup.get(int(row["league_id"]))
        if entry is None or entry["type"] != "league":
            continue
        key = (row["league_id"], row["season"])
        last_index[key] = i

    triggers = {}
    for key, idx in last_index.items():
        triggers.setdefault(idx, []).append(key)
    return triggers


def take_season_snapshot(
    league_id: str, season: str, league_lookup: dict,
    fixtures: list[dict], club_states: dict,
) -> dict:
    """
    Captures every club's rating as it stood at the end of this
    (league_id, season)'s final match - min, max, per-club ratings, and
    total club count. This is exactly what the Standard-case Starting
    Position formula (and the tier-bootstrap placeholder-to-real
    transition) needs as input for whoever gets promoted INTO this tier
    the following season.
    """
    team_ids_in_group = set()
    for row in fixtures:
        if row["league_id"] == league_id and row["season"] == season:
            team_ids_in_group.add(row["home_team_id"])
            team_ids_in_group.add(row["away_team_id"])

    ratings = {tid: club_states[tid].rating for tid in team_ids_in_group if tid in club_states}

    entry = league_lookup[int(league_id)]
    return {
        "country": entry["country"],
        "tier": entry["tier"],
        "season": season,
        "ratings": ratings,
        "min": min(ratings.values()) if ratings else None,
        "max": max(ratings.values()) if ratings else None,
        "total_clubs": len(ratings),
    }


# ---------------------------------------------------------------------------
# LEAGUE-LEVEL STARTING POSITION OVERRIDES
# For competitions that don't belong to any single country (e.g. OFC Pro
# League, a genuine multi-national Oceania league debuting 2026) - every
# club is treated as if it were an untracked/unranked club from
# source_country with an unknown tier, i.e. exactly what a hypothetical
# unranked lower-tier club from that country would compute to if it played
# a cup tie against that country's ranked top-tier side. This reuses the
# EXACT SAME generic placeholder-chain logic as any other untracked club
# (deepest-tracked-tier scan, snapshot-preferred value, placeholder ratio) -
# it does NOT require source_country to actually have a tracked 2nd tier of
# its own; the placeholder chain derives that value the normal way, off
# whatever source_country's deepest ACTUALLY tracked tier is.
#
# Fill in the real league_id once known - this is keyed by league_id, not
# any country, since these clubs' individual home nations are irrelevant
# to how they should be seeded.
# ---------------------------------------------------------------------------
LEAGUE_STARTING_POSITION_OVERRIDES = {
    1214: {"source_country": "Australia"},  # OFC Pro League
}


def get_starting_position(
    team_id: str,
    season: str,
    team_country_lookup: dict,
    team_tier_by_season: dict,
    country_code_mapping: dict,
    league_starts: dict,
    untracked_club_tiers: Optional[dict] = None,
    season_snapshots: Optional[dict] = None,
    current_league_id: Optional[str] = None,
) -> tuple[float, str]:
    """
    Determines a club's Starting Position the moment it's first seen in
    the processed match history. Returns (rating, source) where source
    is a short string describing which path was used, for logging/
    auditing - seeding 20,000+ clubs silently with no way to spot-check
    which ones fell back to a placeholder would be a real problem later.

    current_league_id: the league_id of the match currently triggering
        this seed - checked against LEAGUE_STARTING_POSITION_OVERRIDES.
        If matched, the club is treated as an untracked club from
        source_country with an unknown tier (see module docstring above
        LEAGUE_STARTING_POSITION_OVERRIDES) rather than resolving its own
        actual country - the source string gets a "league_override:"
        prefix so this is visible in the seeding audit either way.

    season_snapshots: optional {"country|tier|season": {...}} from
        season_snapshots.json (see take_season_snapshot). When computing
        an untracked club's placeholder rating, the tier-above's value is
        taken from the END OF THE IMMEDIATELY PRECEDING SEASON's actual
        snapshot if one exists (average of that tier's real, evolved
        club ratings), rather than always chaining from the static
        League_Starts bootstrap value - so a placeholder computed in
        year 5 reflects how strong the tracked tier genuinely is by
        then, not how strong it was at the very first season. Falls back
        to the static League_Starts value when no prior-season snapshot
        exists yet (the true first season, or when season_snapshots
        isn't provided at all).

    untracked_club_tiers: optional {team_id: {"tier_depth_below_deepest_tracked": N, ...}}
        from untracked_club_tiers.json (see pull_untracked_standings.py /
        apply_untracked_leagues.py). When a club is found here, its
        precise tier depth is used instead of the generic "always one
        level below deepest tracked" assumption - the difference between
        correctly distinguishing a Czech 3rd-tier club from a 4th-tier
        one, versus treating every untracked club identically.

    Resolution order:
      0. current_league_id matches a LEAGUE_STARTING_POSITION_OVERRIDES
         entry -> country is forced to source_country, tier forced to
         unknown, falls through into the normal untracked-club logic below.
      1. Country unknown entirely (never seen in a domestic fixture) ->
         raises, since we can't do anything sensible without it.
      2. Country deliberately excluded (EXCLUDED_COUNTRIES) -> raises.
      3. Country has no domestic league data at all -> UNRANKED_COUNTRY_DEFAULT,
         season-locked like any other untracked club.
      4. Tier known for this specific season AND a direct League_Starts
         entry exists for country_code[_tier] -> use it directly (the
         normal, expected case for every genuinely tracked division).
      5. Tier known but deeper than what's directly in League_Starts
         (shouldn't normally happen post-cleanup, but handled rather than
         crashing) -> chain the untracked-placeholder ratios from the
         deepest available tier for that country.
      6. Tier NOT known, but club found in untracked_club_tiers -> chain
         the placeholder ratios using its PRECISE known depth.
      7. Tier NOT known at all and not in untracked_club_tiers either
         (genuinely unidentified club, OR a league-override club) ->
         untracked-placeholder chain assuming just one level below
         deepest tracked tier - the generic fallback.
    """
    override = None
    if current_league_id is not None:
        override = LEAGUE_STARTING_POSITION_OVERRIDES.get(int(current_league_id))

    if override is not None:
        country = override["source_country"]
        tier = None  # force placeholder treatment, never a direct/known-tier lookup
    else:
        country = team_country_lookup.get(team_id)
        if country is None:
            raise ValueError(f"team_id={team_id}: country unknown, cannot seed Starting Position")
        tier = team_tier_by_season.get((team_id, season))

    if country in EXCLUDED_COUNTRIES:
        raise ValueError(f"team_id={team_id} ({country}): deliberately excluded "
                          f"(see EXCLUDED_COUNTRIES) - this club should not be reaching "
                          f"the rating engine at all.")

    code = country_code_mapping.get(country)
    if code is None or league_starts.get(code) is None:
        # No domestic league data available for this country at all (e.g.
        # Djibouti, South-Sudan clubs that only show up via CECAFA/CAF
        # continental competitions but have no tracked domestic pyramid) -
        # NOT the same as a deliberate exclusion. Treated as a permanently
        # unranked club: flat default rating, season-locked exactly like
        # any other untracked club (recalculated - to the same value,
        # currently - at each season boundary). If domestic data for this
        # country is ever added to League_Starts, this path stops firing
        # automatically and the club starts getting a real tiered rating
        # instead, no code change needed.
        rating, source = UNRANKED_COUNTRY_DEFAULT, f"placeholder:unranked_country:{country}"
        if override is not None:
            source = f"league_override:{current_league_id}:{source}"
        return rating, source

    if tier is not None:
        key = code if tier == 1 else f"{code}_{tier}"
        if key in league_starts:
            return league_starts[key], f"direct:{key}"

    # Find the deepest tier for this country that DOES have a direct
    # League_Starts entry, to chain the placeholder ratios from.
    deepest_tier = 1
    deepest_value = league_starts.get(code)
    t = 2
    while f"{code}_{t}" in league_starts:
        deepest_tier = t
        deepest_value = league_starts[f"{code}_{t}"]
        t += 1

    # Prefer the deepest tracked tier's ACTUAL end-of-preceding-season
    # rating over the static bootstrap value, if a snapshot exists for it.
    # This is what makes an untracked club's placeholder reflect how
    # strong the tracked tier genuinely is by the current season, rather
    # than always chaining off the original 2020/2025 baseline forever.
    value_source = "static"
    if season_snapshots is not None:
        try:
            preceding_season = str(int(season) - 1)
        except ValueError:
            preceding_season = None
        if preceding_season is not None:
            snap_key = f"{country}|{deepest_tier}|{preceding_season}"
            snap = season_snapshots.get(snap_key)
            if snap is not None and snap.get("ratings"):
                deepest_value = sum(snap["ratings"].values()) / len(snap["ratings"])
                value_source = f"snapshot:{preceding_season}"

    if tier is None and untracked_club_tiers is not None and override is None:
        known = untracked_club_tiers.get(team_id)
        if known is not None:
            precise_depth = known["tier_depth_below_deepest_tracked"]
            target_tier = deepest_tier + precise_depth
            placeholder = untracked_placeholder_rating(deepest_value, deepest_tier, target_tier)
            return placeholder, f"placeholder:{code}_t{target_tier}:known_depth:{value_source}"

    target_tier = tier if (tier is not None and tier > deepest_tier) else deepest_tier + 1
    placeholder = untracked_placeholder_rating(deepest_value, deepest_tier, target_tier)
    reason = "tier_unknown" if tier is None else "tier_deeper_than_tracked"
    source = f"placeholder:{code}_t{target_tier}:{reason}:{value_source}"
    if override is not None:
        source = f"league_override:{current_league_id}:{source}"
    return placeholder, source


# ---------------------------------------------------------------------------
# GAP #2 (leagues_config.json lookup) and #3 (team country) - RESOLVED
# ---------------------------------------------------------------------------

def build_league_lookup(leagues_config: dict) -> dict:
    """
    league_id -> {country, type, name, tier}. Requires leagues_config.json
    to already have "type" (and "tier" for type=="league") merged in via
    apply_competition_classification.py - raises a clear error per-league
    if that hasn't been done yet, rather than silently treating an
    unclassified competition as some default type.
    """
    lookup = {}
    for country, comps in leagues_config.items():
        for comp in comps:
            if "type" not in comp:
                raise ValueError(
                    f"{country} / {comp['name']} (league_id={comp['league_id']}) has no "
                    f"'type' field - run apply_competition_classification.py first."
                )
            lookup[comp["league_id"]] = {
                "country": country,
                "type": comp["type"],
                "name": comp["name"],
                "tier": comp.get("tier"),
            }
    return lookup


def get_competition_info(league_id: str, league_lookup: dict) -> tuple[str, str]:
    """Returns (competition_type, competition_name) for a league_id, via
    the classified leagues_config.json data."""
    entry = league_lookup.get(int(league_id))
    if entry is None:
        raise KeyError(f"league_id {league_id} not found in leagues_config.json")
    return entry["type"], entry["name"]


def build_team_country_lookup(fixtures: list[dict], league_lookup: dict, overrides: Optional[dict] = None) -> dict:
    """
    A club's country is resolved with TYPE=='league' appearances taking
    priority over TYPE=='cup' appearances, not treated as equally
    authoritative. This matters because a meaningful number of real
    clubs genuinely play across two countries' domestic competitions at
    once - several Welsh clubs (Cardiff, Swansea, Wrexham) compete in the
    ENGLISH league pyramid while also entering the Welsh Cup; Toronto FC/
    CF Montreal/Vancouver Whitecaps play MLS (USA) while also entering
    the Canadian Championship; French overseas-department clubs
    (Guadeloupe, Martinique) enter the mainland Coupe de France on top of
    their own confederation-recognized competitions. In every one of
    these cases, the club's TRUE tier/Starting-Position country is
    wherever it plays its actual LEAGUE football - the cup appearance is
    a guest/overseas participation, not its competitive home.

    overrides: optional {team_id: country} from team_country_overrides.json -
        checked FIRST, before any automatic resolution, for the rare
        genuinely-ambiguous cases (e.g. two DIFFERENT league-type
        appearances for the same team_id in unrelated countries - which
        looks like API-Football data noise/ID reuse rather than a real
        dual-competition club, and can't be resolved by the
        league-over-cup priority rule since both sides are league-type).
        Build this file manually for whichever team_ids get flagged
        below after you've checked what they actually are.

    Only when a club has NO league-type appearance at all (only ever
    seen in cup fixtures) do we fall back to whichever country its cup
    appearances belong to - and only THAT tier of ambiguity (multiple
    cup-only countries, or multiple conflicting LEAGUE countries, which
    would be genuinely unusual) gets flagged as a real conflict worth
    reviewing.
    """
    league_country = {}    # team_id -> country, from type=="league" fixtures only
    league_conflicts = set()
    cup_country = {}        # team_id -> country, from type=="cup" fixtures only
    cup_conflicts = set()
    team_names = {}          # team_id -> a club name, for readable warning output

    for row in fixtures:
        league_id = int(row["league_id"])
        entry = league_lookup.get(league_id)
        if entry is None or entry["country"] == "World":
            continue  # continental/global or unclassified - skip

        target = league_country if entry["type"] == "league" else cup_country
        conflicts = league_conflicts if entry["type"] == "league" else cup_conflicts

        for team_id, name in ((row["home_team_id"], row.get("home_team")),
                               (row["away_team_id"], row.get("away_team"))):
            team_names.setdefault(team_id, name)
            if team_id in target and target[team_id] != entry["country"]:
                conflicts.add((team_id, target[team_id], entry["country"]))
            target[team_id] = entry["country"]

    lookup = dict(cup_country)  # cup appearances are the fallback layer...
    lookup.update(league_country)  # ...league appearances always win when both exist

    overrides = overrides or {}
    lookup.update(overrides)  # manual overrides always win, over everything

    unresolved_league_conflicts = {
        (tid, c1, c2) for (tid, c1, c2) in league_conflicts if tid not in overrides
    }
    if unresolved_league_conflicts:
        print(f"  WARNING: {len(unresolved_league_conflicts)} team_id(s) appeared under more than one "
              f"country via LEAGUE-type competitions specifically - this is genuinely unusual "
              f"(a club normally has exactly one home league), likely API-Football data noise "
              f"rather than a real dual-competition club. Add these to "
              f"team_country_overrides.json once you've checked what they actually are:")
        for team_id, c1, c2 in unresolved_league_conflicts:
            print(f"    {team_names.get(team_id)!r} (team_id={team_id}): seen under both {c1!r} and {c2!r}")

    cup_only_conflicts = {
        (tid, c1, c2) for (tid, c1, c2) in cup_conflicts
        if tid not in league_country and tid not in overrides
    }
    if cup_only_conflicts:
        print(f"  NOTE: {len(cup_only_conflicts)} team_id(s) with no league appearance at all "
              f"showed up under more than one country via cup competitions - resolved to "
              f"whichever was seen first, worth a spot-check if any of these look important:")
        for team_id, c1, c2 in cup_only_conflicts:
            print(f"    {team_names.get(team_id)!r} (team_id={team_id}): seen under both {c1!r} and {c2!r}")

    return lookup


def get_team_country(team_id: str, team_country_lookup: dict) -> str | None:
    """
    Returns the club's country, or None if it's never been seen in any
    domestic fixture in the currently loaded dataset (e.g. a club that
    only appears in a continental competition because its own domestic
    league/cup fixtures haven't been pulled). None flows through to
    MatchContext.home_team_country=None, which elo_engine's is_neutral()
    correctly treats as "can't confirm a country mismatch -> not neutral"
    per the same lazy-override default used for venue_country.
    """
    return team_country_lookup.get(team_id)


# ---------------------------------------------------------------------------
# GAP #1 - still open (pull_data.py doesn't extract venue_id yet)
# ---------------------------------------------------------------------------

def get_venue_id(fixture_row: dict) -> str | None:
    """
    Reads venue_id directly from the fixture row. Returns None (not an
    error) if the column is missing entirely - this happens for any
    fixture CSV pulled before the venue_id patch to pull_data.py, so
    older already-pulled data still works, it just can't detect the
    forced-relocation neutral-venue case (Ukraine-abroad-style ties)
    for those specific matches. Re-pulling with the current pull_data.py
    closes that gap going forward.
    """
    return fixture_row.get("venue_id") or None


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

def load_all_fixtures() -> list[dict]:
    """
    Reads every fixture CSV in data/fixtures/, keeps only played matches
    (status == 'FT'), and returns them as a flat list of dicts ready for
    chronological sorting. league_id AND season are recovered from the
    filename, NOT from the match date - a season spanning two calendar
    years (e.g. Aug 2025-May 2026) would otherwise get misclassified for
    its January-onward matches if we derived season from date[:4] instead
    of the actual season file it came from.

    Filenames are of the form {Country}_{CompetitionName}_{league_id}_{season}.csv
    (e.g. "Albania_Cup_707_2020.csv") - league_id and season are always
    the LAST TWO underscore-separated tokens, regardless of how many
    tokens precede them (country/competition names can have multiple
    words, but always hyphenated rather than underscore-separated, so
    this split is reliable).
    """
    all_fixtures = []
    skipped_files = []
    for path in glob.glob(os.path.join(FIXTURES_DIR, "*.csv")):
        filename = os.path.basename(path)
        parts = filename.replace(".csv", "").split("_")

        if len(parts) < 2:
            skipped_files.append(filename)
            continue
        league_id, season = parts[-2], parts[-1]

        if not league_id.isdigit():
            skipped_files.append(filename)
            continue

        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["played"] != "True":
                    continue
                row["league_id"] = league_id
                row["season"] = season
                all_fixtures.append(row)

    if skipped_files:
        print(f"  WARNING: skipped {len(skipped_files)} file(s) in data/fixtures/ that don't match "
              f"the expected 'league_id_season.csv' format (numeric league_id) - these were NOT "
              f"processed, so any matches in them are missing from this run:")
        for fn in skipped_files:
            print(f"    - {fn}")

    return all_fixtures


# ---------------------------------------------------------------------------
# TEAM-ID SPLITTING
# For cases where API-Football has reused the same numeric team_id for two
# genuinely different real clubs (e.g. "Al Shorta" - a common name across
# Arab countries - assigned the same ID for both an Iraqi club and a
# Sudanese one). Rewrites home_team_id/away_team_id in-place on every
# fixture BEFORE any country/tier resolution happens, so everything
# downstream (club_states, team_country_lookup, seed_sources, etc.) just
# naturally treats the two virtual IDs as entirely separate clubs without
# needing any special-casing anywhere else in the pipeline.
# ---------------------------------------------------------------------------

def apply_team_id_splits(fixtures: list[dict], league_lookup: dict, splits_config: dict) -> int:
    """
    splits_config format (team_id_splits.json):
    {
      "5242": [
        {"match_if_country": "Sudan", "virtual_suffix": "sudan"},
        {"match_if_competition_contains": "CAF", "virtual_suffix": "sudan"},
        {"match_if_country": "Iraq", "virtual_suffix": "iraq"},
        {"match_if_competition_contains": "AFC", "virtual_suffix": "iraq"}
      ],
      "8086": [
        {"match_if_country": "Burkina-Faso", "virtual_suffix": "burkina"},
        {"match_if_country": "Benin", "virtual_suffix": "benin"},
        {"match_if_country": "Togo", "virtual_suffix": "togo"},
        {"ambiguous": true, "options": ["burkina", "benin", "togo"]}
      ]
    }

    Rules are checked in order for each match this raw team_id appears in;
    the first matching rule wins. An "ambiguous" rule (must be last) fires
    when NO country/competition-name rule could tell the split apart on
    its own - e.g. three same-confederation clubs sharing one ID, where
    "CAF" appears in the competition name regardless of which of the
    three actually played. In that case:

      - Checks TEAM_ID_SPLIT_RESOLUTIONS_PATH first, keyed by this exact
        fixture_id - if this specific match has already been resolved
        (by you, in a prior run), reuses that answer with no prompt.
      - If running interactively, prompts you with the match details
        (opponent, date, competition) and the list of valid options,
        saves your answer permanently keyed by fixture_id (so it's
        asked once per real match, ever - not once per run).
      - If running unattended (no TTY), leaves this specific fixture
        un-split and logs it to team_id_split_resolutions.json under a
        "_pending" section instead of guessing, printing a summary count
        at the end so you know how many are waiting on you.

    A raw ID configured for splitting whose match doesn't satisfy ANY
    rule at all (no country/competition match AND no ambiguous fallback
    defined) is left un-split for that fixture and warned about once -
    better to surface an unhandled context than silently misassign it.

    Virtual IDs are named "{raw_id}::{suffix}" - the "::" is deliberately
    unlike anything a real API-Football ID could contain, so it's always
    visually obvious in seed_sources/reports/etc. which club records are
    split-virtual rather than a real raw ID.

    Returns the number of team_id occurrences actually remapped, for a
    quick sanity-check in the console output.
    """
    if not splits_config:
        return 0

    resolutions = _load_json(TEAM_ID_SPLIT_RESOLUTIONS_PATH)
    pending = resolutions.get("_pending", {})
    resolved = {k: v for k, v in resolutions.items() if k != "_pending"}

    remapped_count = 0
    unhandled_warned = set()
    newly_resolved = 0

    for row in fixtures:
        league_id = int(row["league_id"])
        entry = league_lookup.get(league_id)
        match_country = entry["country"] if entry else None
        comp_name = entry["name"] if entry else ""
        fixture_id = row.get("fixture_id")

        for side in ("home_team_id", "away_team_id"):
            raw_id = row[side]
            rules = splits_config.get(raw_id)
            if rules is None:
                continue

            matched_suffix = None
            ambiguous_options = None
            for rule in rules:
                if "match_if_country" in rule and rule["match_if_country"] == match_country:
                    matched_suffix = rule["virtual_suffix"]
                    break
                if "match_if_competition_contains" in rule and rule["match_if_competition_contains"] in comp_name:
                    matched_suffix = rule["virtual_suffix"]
                    break
                if rule.get("ambiguous"):
                    ambiguous_options = rule["options"]
                    break

            if matched_suffix is None and ambiguous_options is not None:
                res_key = f"{raw_id}:{fixture_id}"
                if res_key in resolved:
                    matched_suffix = resolved[res_key]["suffix"]
                elif _is_interactive():
                    opponent = row.get("away_team") if side == "home_team_id" else row.get("home_team")
                    print(f"\nAmbiguous split for team_id={raw_id} ({row.get(side.replace('_id',''), '?')!r}):")
                    print(f"  {row.get('date','?')[:10]}  {comp_name}  vs {opponent!r}")
                    print(f"  Options: {', '.join(ambiguous_options)}")
                    while True:
                        answer = input(f"  Which club was this? [{'/'.join(ambiguous_options)}]: ").strip().lower()
                        if answer in ambiguous_options:
                            break
                        print(f"  Please enter one of: {', '.join(ambiguous_options)}")
                    matched_suffix = answer
                    resolved[res_key] = {
                        "suffix": matched_suffix, "team_id": raw_id,
                        "date": row.get("date"), "competition": comp_name,
                        "opponent": opponent,
                    }
                    newly_resolved += 1
                    print(f"  Saved - will not be asked about this match again.\n")
                else:
                    if res_key not in pending:
                        pending[res_key] = {
                            "team_id": raw_id, "fixture_id": fixture_id,
                            "date": row.get("date"), "competition": comp_name,
                            "options": ambiguous_options,
                        }

            if matched_suffix is not None:
                row[side] = f"{raw_id}::{matched_suffix}"
                remapped_count += 1
            elif ambiguous_options is None:
                key = (raw_id, match_country, comp_name)
                if key not in unhandled_warned:
                    unhandled_warned.add(key)
                    print(f"  WARNING: team_id={raw_id} is configured in team_id_splits.json but "
                          f"a match in {match_country!r} / {comp_name!r} didn't match any rule - "
                          f"left un-split for this fixture. Add a rule for this context if it's "
                          f"one of the two real clubs, or ignore if it's a genuine third context.")

    if newly_resolved:
        resolved_out = dict(resolved)
        if pending:
            resolved_out["_pending"] = pending
        _save_json_local(TEAM_ID_SPLIT_RESOLUTIONS_PATH, resolved_out)
    elif pending:
        out = dict(resolved)
        out["_pending"] = pending
        _save_json_local(TEAM_ID_SPLIT_RESOLUTIONS_PATH, out)
        print(f"  {len(pending)} ambiguous split(s) couldn't be resolved (no TTY available) - "
              f"logged to team_id_split_resolutions.json under '_pending'. Run interactively "
              f"to resolve them, or they'll stay un-split (using the raw shared ID) until then.")

    return remapped_count


def _is_interactive() -> bool:
    """True only if there's an actual human at a terminal who could answer a prompt right now."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _save_json_local(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def fixture_sort_key(row: dict):
    """Parses the ISO date string for chronological sorting."""
    return datetime.fromisoformat(row["date"].replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def main():
    print("Loading fixtures...")
    fixtures = load_all_fixtures()
    print(f"  {len(fixtures)} played matches found across all pulled leagues/seasons")

    fixtures.sort(key=fixture_sort_key)

    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)
    league_lookup = build_league_lookup(leagues_config)

    splits_config = _load_json(TEAM_ID_SPLITS_PATH)  # {} if file doesn't exist yet
    if splits_config:
        print("Applying team-ID splits (shared IDs representing two real clubs)...")
        remapped = apply_team_id_splits(fixtures, league_lookup, splits_config)
        print(f"  Remapped {remapped} fixture-side occurrences across {len(splits_config)} split team_id(s)")

    print("Building team-country lookup from domestic fixture appearances...")
    team_country_overrides_path = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
    team_country_overrides = _load_json(team_country_overrides_path)  # {} if file doesn't exist yet
    team_country_lookup = build_team_country_lookup(fixtures, league_lookup, team_country_overrides)
    print(f"  {len(team_country_lookup)} teams resolved to a country")

    print("Building team-tier-by-season lookup...")
    team_tier_by_season = build_team_tier_by_season(fixtures, league_lookup)

    with open(COUNTRY_CODE_MAPPING_PATH, encoding="utf-8") as f:
        country_code_mapping = json.load(f)
    league_starts = load_league_starts()
    print(f"  Loaded {len(league_starts)} direct Starting Position values from League_Starts_updated.xlsx")

    untracked_club_tiers_path = os.path.join(SCRIPT_DIR, "untracked_club_tiers.json")
    if os.path.exists(untracked_club_tiers_path):
        with open(untracked_club_tiers_path, encoding="utf-8") as f:
            untracked_club_tiers = json.load(f)
        print(f"  Loaded {len(untracked_club_tiers)} precise-tier untracked clubs from untracked_club_tiers.json")
    else:
        untracked_club_tiers = None
        print("  untracked_club_tiers.json not found - untracked clubs will use the generic "
              "'one level below deepest tracked tier' fallback (run pull_untracked_standings.py "
              "+ apply_untracked_leagues.py to build this database for more precise placeholders)")

    finals_config = _load_json(FINALS_CONFIG_PATH)
    venue_overrides = _load_json(VENUE_OVERRIDES_PATH)

    print("Computing season-boundary snapshot trigger points...")
    season_end_triggers = build_season_end_trigger_points(fixtures, league_lookup)
    season_snapshots = {}  # (country, tier, season) -> snapshot dict, keyed
                            # as a string "country|tier|season" for JSON output

    club_states: dict[str, ClubState] = {}
    seed_sources: dict[str, str] = {}  # for the end-of-run audit summary
    club_is_tracked: dict[str, bool] = {}  # True = real tracked-tier club,
                                            # rating evolves via matches.
                                            # False = untracked/placeholder
                                            # club, rating is season-locked.
    club_seeded_season: dict[str, str] = {}  # which season each club's
                                              # CURRENT rating was computed
                                              # for - used to detect when an
                                              # untracked club needs a fresh
                                              # placeholder recalculation.

    processed = 0
    skipped_missing_data = 0
    skipped_no_venue = 0
    seeding_failures = 0
    seeding_failure_details = []  # written to seeding_failures_report.json
    skipped_match_details = []  # every skipped match, with enough detail to
                                 # actually go find and fix it - written to
                                 # skipped_matches_report.json at the end,
                                 # not just counted

    for i, row in enumerate(fixtures):
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        season = row["season"]

        league_entry = league_lookup.get(int(row["league_id"]))
        if league_entry is None:
            # This match belongs to a league_id that's no longer in
            # leagues_config.json - most likely a competition you removed
            # (e.g. via the "remove" classification) after already having
            # pulled fixture data for it. Skip the WHOLE match (don't even
            # attempt to seed either club from it) rather than crash, but
            # record full detail so nothing just silently vanishes.
            skipped_match_details.append({
                "reason": "unclassified_league",
                "fixture_id": row.get("fixture_id"),
                "league_id": row["league_id"],
                "competition_name": None,  # unknown by definition - this
                                            # league_id isn't in leagues_config.json
                "date": row["date"],
                "home_team": row.get("home_team"), "away_team": row.get("away_team"),
            })
            continue

        for team_id in (home_id, away_id):
            needs_seed = team_id not in club_states
            needs_reseed = (
                not needs_seed
                and not club_is_tracked.get(team_id, True)
                and club_seeded_season.get(team_id) != season
            )
            # A club not yet seen gets seeded normally. An UNTRACKED club
            # already seen, but whose stored rating is from an earlier
            # season, gets its placeholder recalculated fresh for the new
            # season (using whatever the tier-above's CURRENT snapshot is
            # now) rather than carrying over a stale value or letting match
            # results have moved it - untracked ratings are season
            # constants, not running totals.
            if not (needs_seed or needs_reseed):
                continue
            try:
                rating, source = get_starting_position(
                    team_id, season, team_country_lookup, team_tier_by_season,
                    country_code_mapping, league_starts, untracked_club_tiers,
                    season_snapshots, row["league_id"],
                )
                club_states[team_id] = ClubState(rating=rating, last_match_date=None)
                seed_sources[team_id] = source
                # league_override clubs (e.g. OFC Pro League) are genuinely
                # tracked - a real league, ratings should evolve via match
                # results normally, not stay season-locked like an
                # untracked-placeholder club.
                club_is_tracked[team_id] = source.startswith("direct") or source.startswith("league_override")
                club_seeded_season[team_id] = season
            except ValueError as e:
                seeding_failures += 1
                team_name = row.get("home_team") if team_id == home_id else row.get("away_team")
                seeding_failure_details.append({
                    "team_id": team_id,
                    "team_name": team_name,
                    "league_id": row["league_id"],
                    "competition_name": league_entry.get("name") if league_entry else None,
                    "country_context": league_entry.get("country") if league_entry else None,
                    "date": row["date"],
                    "error": str(e),
                })
                print(f"  SEEDING FAILED: {team_name!r} (team_id={team_id}, "
                      f"playing in {league_entry.get('name') if league_entry else row['league_id']}): {e}")

        if home_id not in club_states or away_id not in club_states:
            skipped_missing_data += 1
            skipped_match_details.append({
                "reason": "seeding_failed",
                "fixture_id": row.get("fixture_id"),
                "league_id": row["league_id"],
                "competition_name": league_entry.get("name"),
                "country_context": league_entry.get("country"),
                "date": row["date"],
                "home_team": row.get("home_team"), "away_team": row.get("away_team"),
            })
            continue

        competition_type, competition_name = get_competition_info(row["league_id"], league_lookup)

        venue_id = get_venue_id(row)
        if venue_id is None:
            skipped_no_venue += 1
            # Still processing the match below with venue_id=None rather
            # than skipping it entirely - a continental/global final still
            # needs to be treated as neutral via the is_final/is_single_leg
            # path even without venue data; only the "forced relocation
            # abroad" neutral case is lost for this specific match.

        raw_match = {
            "competition_type": competition_type,
            "competition_name": competition_name,
            "season": season,
            "round": row["round"],
            "home_team_country": get_team_country(home_id, team_country_lookup),
            "venue_id": venue_id,
        }
        ctx = build_match_context(raw_match, finals_config, venue_overrides)

        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        goal_margin = abs(home_score - away_score)

        if home_score > away_score:
            result_a = 1.0
        elif home_score < away_score:
            result_a = 0.0
        else:
            result_a = 0.5

        match_date = fixture_sort_key(row).date()

        # 365-day inactivity reset: if either club's last recorded match
        # was more than a year before this one, process_match needs a
        # freshly-computed Starting Position ready to hand it - it won't
        # compute this itself. Only builds entries for the side(s) that
        # actually need it.
        reset_lookup = {}
        for label, team_id in (("a", home_id), ("b", away_id)):
            if needs_starting_position_reset(club_states[team_id].last_match_date, match_date):
                fresh_rating, fresh_source = get_starting_position(
                    team_id, season, team_country_lookup, team_tier_by_season,
                    country_code_mapping, league_starts, untracked_club_tiers,
                    season_snapshots, row["league_id"],
                )
                reset_lookup[label] = fresh_rating
                seed_sources[team_id] = fresh_source + ":inactivity_reset"
                club_is_tracked[team_id] = fresh_source.startswith("direct") or fresh_source.startswith("league_override")
                club_seeded_season[team_id] = season

        process_match(
            club_a=club_states[home_id],
            club_b=club_states[away_id],
            result_a=result_a,
            goal_margin=goal_margin,
            match_ctx=ctx,
            match_date=match_date,
            starting_position_lookup=reset_lookup if reset_lookup else None,
            update_a=club_is_tracked.get(home_id, True),
            update_b=club_is_tracked.get(away_id, True),
        )
        processed += 1

        # Season-boundary snapshot check: has this exact match's index just
        # completed one or more (league_id, season) groups?
        for league_id_key, season_key in season_end_triggers.get(i, []):
            snap = take_season_snapshot(league_id_key, season_key, league_lookup, fixtures, club_states)
            snap_key = f"{snap['country']}|{snap['tier']}|{snap['season']}"
            season_snapshots[snap_key] = snap

    with open(os.path.join(SCRIPT_DIR, "season_snapshots.json"), "w") as f:
        json.dump(season_snapshots, f, indent=2)
    print(f"\nWrote season_snapshots.json - {len(season_snapshots)} tier-seasons captured")

    print(f"\nProcessed {processed} matches.")
    print(f"Seeded {len(club_states)} clubs with a Starting Position.")
    if seeding_failures:
        with open(os.path.join(SCRIPT_DIR, "seeding_failures_report.json"), "w") as f:
            json.dump(seeding_failure_details, f, indent=2)
        unique_failed_teams = len(set(d["team_id"] for d in seeding_failure_details))
        print(f"{seeding_failures} seeding attempts FAILED ({unique_failed_teams} unique team_ids) - "
              f"full detail written to seeding_failures_report.json. Run resolve_unknown_countries.py "
              f"against it to auto-lookup the 'country unknown' cases via the API directly.")
    if skipped_missing_data:
        print(f"Skipped {skipped_missing_data} matches (a club involved failed seeding above).")
    if skipped_no_venue:
        print(f"{skipped_no_venue} matches processed WITHOUT venue data (gap #1 still open) - "
              f"forced-relocation neutral-venue cases (e.g. Ukraine-abroad ties) were NOT detected "
              f"for these matches. Finals/FIFA-competition neutrality still worked correctly.")

    if skipped_match_details:
        with open(os.path.join(SCRIPT_DIR, "skipped_matches_report.json"), "w") as f:
            json.dump(skipped_match_details, f, indent=2)
        unclassified_count = sum(1 for m in skipped_match_details if m["reason"] == "unclassified_league")
        seeding_count = sum(1 for m in skipped_match_details if m["reason"] == "seeding_failed")
        print(f"\n{len(skipped_match_details)} matches were skipped entirely (NOT included in any "
              f"club's rating) - full detail written to skipped_matches_report.json:")
        if unclassified_count:
            print(f"  {unclassified_count} belonged to a league_id no longer in leagues_config.json "
                  f"(likely fixture data left over from before a competition was removed)")
        if seeding_count:
            print(f"  {seeding_count} involved a club that failed to seed (see SEEDING FAILED lines above)")
        print("  Every one of these needs to be either fixed (so the match is included next run) "
              "or confirmed as correctly excluded.")
    else:
        print("\nNo matches were skipped - every match in data/fixtures/ was processed.")

    placeholder_seeds = sum(1 for s in seed_sources.values() if s.startswith("placeholder"))
    if placeholder_seeds:
        print(f"\n{placeholder_seeds} of {len(club_states)} clubs were seeded via the untracked-placeholder "
              f"chain rather than a direct League_Starts value (either their tier couldn't be determined, "
              f"or their tier goes deeper than what's directly tracked for their country). This is expected "
              f"for genuine cup-tie-only opponents; if this number looks unexpectedly high, something may be "
              f"off in the tier detection.")


if __name__ == "__main__":
    main()
