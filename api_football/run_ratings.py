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
from history_snapshots import generate_snapshot_dates, SnapshotRecorder, SNAPSHOT_START_DATE
from match_log import MatchLogRecorder, MAX_LOG_LENGTH

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(SCRIPT_DIR, "data", "fixtures")
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
COUNTRY_CODE_MAPPING_PATH = os.path.join(SCRIPT_DIR, "country_code_mapping.json")
LEAGUE_STARTS_PATH = os.path.join(SCRIPT_DIR, "League_Starts_updated.xlsx")
TEAM_ID_SPLITS_PATH = os.path.join(SCRIPT_DIR, "team_id_splits.json")
TEAM_ID_SPLIT_RESOLUTIONS_PATH = os.path.join(SCRIPT_DIR, "team_id_split_resolutions.json")
SEASON_INCLUSION_PATH = os.path.join(SCRIPT_DIR, "season_inclusion.json")
RELEGATION_PERCENTAGES_PATH = os.path.join(SCRIPT_DIR, "relegation_percentages.json")

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

    Checks season_type_overrides (season-aware), not just the entry's
    flat default type - a fixture belonging to a league_id whose type is
    overridden to "cup" for this specific season (e.g. Japan's J1 League,
    league_id 98, in 2026 - the one-off bridging tournament, filed under
    the same ID as the normal league) must NOT count as tier-confirming
    league data here, or a club could get its tier "confirmed" via a
    competition that isn't really that season's tracked league at all.
    """
    lookup = {}
    for row in fixtures:
        entry = league_lookup.get(int(row["league_id"]))
        if entry is None:
            continue
        overrides = entry.get("season_type_overrides") or {}
        effective_type = overrides.get(str(row["season"]), entry["type"])
        if effective_type != "league":
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
        # MUST stay played-only here, unlike most other consumers of the
        # now-unfiltered fixtures list - fixtures now includes scheduled/
        # not-yet-played rows, and using one of those would trigger "end
        # of season" off the SCHEDULED final matchday (which could be
        # months away, or postponed) instead of the actual last completed
        # match, corrupting every Standard-case Starting Position
        # calculation that depends on this season's real min/max.
        if row["played"] != "True":
            continue
        entry = league_lookup.get(int(row["league_id"]))
        if entry is None:
            continue
        overrides = entry.get("season_type_overrides") or {}
        effective_type = overrides.get(str(row["season"]), entry["type"])
        if effective_type != "league":
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
    season_inclusion: Optional[dict] = None,
    relegation_percentages: Optional[dict] = None,
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

    untracked_club_tiers: optional {team_id: {"tier": N, ...}}
        from untracked_club_tiers.json (see pull_untracked_standings.py /
        apply_untracked_leagues.py). N is the club's ACTUAL tier number
        in its country's pyramid (e.g. 4 for a country's 4th division) -
        not a depth relative to whatever's currently directly tracked,
        which would go stale if that changes. When a club is found here,
        its precise tier is used instead of the generic "always one
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
         entry exists for country_code[_tier]:
           4a. If a real season_snapshots.json entry exists for this
               tier's PRECEDING season -> this is a genuine mid-history
               promotion into an already-tracked tier. Uses the dynamic
               Standard-case formula (preceding season's real min/max
               from the snapshot, blended with relegation_percentages.json's
               real percentage for that season) - NOT the static bootstrap
               value, which would otherwise give every promoted club the
               same original-bootstrap rating forever regardless of how
               the tier has actually evolved. Raises if the percentage
               data is missing for that season, rather than silently
               falling back to the stale bootstrap value.
           4b. If no preceding-season snapshot exists -> this genuinely
               is the tier's first-ever tracked season, so the static
               League_Starts bootstrap value is correct as-is.
      5. Tier known but deeper than what's directly in League_Starts
         (shouldn't normally happen post-cleanup, but handled rather than
         crashing) -> chain the untracked-placeholder ratios from the
         deepest available tier for that country.
      6. Tier NOT known, but club found in untracked_club_tiers -> chain
         the untracked-placeholder ratios using its PRECISE actual tier.
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

    # Even if the raw fixture data says this club plays in a real
    # type=="league" competition (tier is not None), that only tells us
    # match data EXISTS for this season - not that this tier was actually
    # a genuinely tracked division that specific season. Historical data
    # was pulled broadly (2020+ for Europe, 2025+ elsewhere) regardless of
    # whether a given tier's inclusion status held for the whole window -
    # a country's division count shifts year to year. season_inclusion.json
    # (from Leagues_Included_in_Ranking.xlsx) is the real source of truth;
    # if this specific (code, tier, season) isn't in it, treat the tier as
    # unknown for Starting Position purposes, same as any other untracked
    # club, even though we technically know it from the fixture data.
    if tier is not None and season_inclusion is not None:
        key_to_check = code if tier == 1 else f"{code}_{tier}"
        included_this_season = season_inclusion.get(season, [])
        if key_to_check not in included_this_season:
            tier = None

    if tier is not None:
        key = code if tier == 1 else f"{code}_{tier}"
        if key in league_starts:
            # A tier existing in the static League_Starts file is only
            # correct as-is for that tier's TRUE FIRST tracked season -
            # using it for every subsequent season's promotions would give
            # every newly-promoted club the exact same original bootstrap
            # rating forever, ignoring how the tier has actually evolved.
            # Check whether a real preceding-season snapshot exists AND
            # that preceding season was actually season_inclusion-confirmed
            # as a genuinely tracked division - a snapshot can exist purely
            # from burn-in match processing even for a season that wasn't
            # officially tracked (e.g. a country's true 2020-21 season
            # start date meant a tier's matches got processed starting
            # mid-way through what would otherwise look like "season 2020",
            # but that tier wasn't actually counted as tracked until the
            # season after) - snapshot existence alone isn't proof of a
            # genuine prior tracked season.
            preceding_season = None
            try:
                preceding_season = str(int(season) - 1)
            except ValueError:
                pass

            snap = None
            preceding_season_was_tracked = True  # assume tracked if no season_inclusion data available
            if preceding_season is not None and season_snapshots is not None:
                snap = season_snapshots.get(f"{country}|{tier}|{preceding_season}")
            if preceding_season is not None and season_inclusion is not None:
                preceding_season_was_tracked = key in season_inclusion.get(preceding_season, [])

            if snap is not None and snap.get("min") is not None and snap.get("max") is not None \
                    and preceding_season_was_tracked:
                # Confirmed genuine mid-history promotion - this tier was
                # already tracked last season, so we have real min/max to
                # work from. Now we specifically need this season's
                # relegation percentage - if that's missing, this is a
                # real data gap (not something to guess at silently with
                # the stale bootstrap value), so it raises rather than
                # falling back.
                pct = None
                if relegation_percentages is not None:
                    pct = relegation_percentages.get(key, {}).get(preceding_season)

                if pct is None:
                    raise ValueError(
                        f"team_id={team_id} ({country}, {key}): promoted into an already-"
                        f"tracked tier for season {season}, but no relegation_percentages.json "
                        f"entry exists for {key} season {preceding_season} - cannot compute "
                        f"a correct Standard-case Starting Position without it. Add this "
                        f"season's relegation data rather than let this silently use the "
                        f"stale original bootstrap value."
                    )

                rating = snap["min"] + (snap["max"] - snap["min"]) * pct
                return rating, f"standard_promotion:{key}:season{preceding_season}:pct{pct:.4f}"

            # No genuine preceding tracked season - either no snapshot
            # exists at all, or one exists purely from burn-in processing
            # of a season that wasn't actually counted as tracked. Either
            # way this is effectively the tier's first REAL tracked
            # season, so the static bootstrap value from League_Starts is
            # correct as-is.
            return league_starts[key], f"direct:{key}"

    # Find the deepest tier for this country that DOES have a direct
    # League_Starts entry AND was actually included that season (if
    # season_inclusion data is available) - a tier existing in the static
    # League_Starts file doesn't mean it was genuinely tracked every
    # season; scanning past a season-excluded tier here would anchor an
    # untracked club's placeholder off a value that wasn't real for that
    # season, undermining the whole point of the season-gating check above.
    included_this_season = season_inclusion.get(season, []) if season_inclusion is not None else None
    deepest_tier = 1
    deepest_value = league_starts.get(code)
    t = 2
    while f"{code}_{t}" in league_starts:
        if included_this_season is not None and f"{code}_{t}" not in included_this_season:
            break
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
            target_tier = known["tier"]
            placeholder = untracked_placeholder_rating(deepest_value, deepest_tier, target_tier)
            return placeholder, f"placeholder:{code}_t{target_tier}:known_tier:{value_source}"

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
    league_id -> {country, type, name, tier, season_type_overrides, season_aliases}.
    Requires leagues_config.json to already have "type" (and "tier" for
    type=="league") merged in via apply_competition_classification.py -
    raises a clear error per-league if that hasn't been done yet, rather
    than silently treating an unclassified competition as some default
    type.

    season_type_overrides (optional per entry): {"<season>": "<type>"} -
    for the rare case where a single league_id represents a genuinely
    different kind of competition in one specific season (see
    get_competition_info's docstring for the concrete Japan example).
    Absent for the vast majority of competitions, which use the same
    type every season.
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
                "season_type_overrides": comp.get("season_type_overrides") or {},
                "season_aliases": comp.get("season_aliases") or {},
            }
    return lookup


def get_competition_info(league_id: str, season: str, league_lookup: dict) -> tuple[str, str]:
    """
    Returns (competition_type, competition_name) for a league_id, via the
    classified leagues_config.json data - season-aware, because a single
    league_id can represent genuinely different things in different
    seasons. Example: Japan's J1 League (league_id 98) is a normal
    type=="league" competition in 2025 and 2027, but API-Football filed
    the one-off 2026 bridging tournament (the "100 Year Vision League" -
    East/West groups, no promotion or relegation) under that SAME
    league_id rather than giving it its own. A competition entry's
    optional "season_type_overrides": {"2026": "cup"} in
    leagues_config.json handles exactly this - checked here before
    falling back to the entry's normal type.
    """
    entry = league_lookup.get(int(league_id))
    if entry is None:
        raise KeyError(f"league_id {league_id} not found in leagues_config.json")
    overrides = entry.get("season_type_overrides") or {}
    comp_type = overrides.get(str(season), entry["type"])
    return comp_type, entry["name"]


def build_team_country_lookup(fixtures: list[dict], league_lookup: dict, overrides: Optional[dict] = None) -> dict:
    """
    A club's country is resolved with TYPE=='league' appearances taking
    priority over TYPE=='cup' appearances, not treated as equally
    authoritative. Within each type, the MOST RECENT chronological
    occurrence wins (fixtures are pre-sorted before this runs) - so a
    club that changed countries at some point (rare, but real: ID reuse,
    or a genuine cross-border move) resolves to wherever it's playing
    now, not wherever it started. This matters because a meaningful
    number of real clubs genuinely play across two countries' domestic
    competitions at once - several Welsh clubs (Cardiff, Swansea,
    Wrexham) compete in the ENGLISH league pyramid while also entering
    the Welsh Cup; Toronto FC/
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

        # NOTE: named comp_season_overrides, NOT "overrides" - this
        # function's own "overrides" parameter (team_country_overrides.json)
        # must never be shadowed by this per-entry lookup. An earlier
        # version of this loop reused the name "overrides" here and
        # silently clobbered the real manual-overrides parameter by the
        # time it was applied below, breaking every club that used to
        # resolve correctly via team_country_overrides.json.
        comp_season_overrides = entry.get("season_type_overrides") or {}
        effective_type = comp_season_overrides.get(str(row["season"]), entry["type"])

        target = league_country if effective_type == "league" else cup_country
        conflicts = league_conflicts if effective_type == "league" else cup_conflicts

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
              f"whichever was seen most recently, worth a spot-check if any of these look important:")
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
    Reads every fixture CSV in data/fixtures/ and returns ALL rows -
    played AND scheduled/not-yet-played - as a flat list of dicts ready
    for chronological sorting. league_id AND season are recovered from
    the filename, NOT from the match date - a season spanning two
    calendar years (e.g. Aug 2025-May 2026) would otherwise get
    misclassified for its January-onward matches if we derived season
    from date[:4] instead of the actual season file it came from.

    Includes not-yet-played rows DELIBERATELY (changed 2026-08-25,
    Greg's fix) - build_team_tier_by_season() needs to know which
    league a club is rostered in for the new season the moment that
    league's fixture list is pulled, not only once its first match has
    actually been played. Before this change, a club whose season
    happened to open with a CUP tie (very common - domestic Super Cups
    and first cup rounds are routinely played before the league season
    starts) would show tier=None until their first LEAGUE match, and in
    the meantime get misclassified as having fallen out of tracked
    status entirely (see the season_changed gating fix a few lines below
    in main() - this fixes the same underlying problem from the other
    end: even with that gate, a club whose league hasn't started yet
    still couldn't be CONFIRMED tracked without this).

    Callers that need actual match RESULTS (not just roster/tier
    membership) must explicitly filter on row["played"] == "True"
    themselves - this function no longer does that filtering centrally.

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
                # Keep EVERY row here, played or not - see the docstring
                # above for why. row["played"] stays as the raw "True"/
                # "False" string from the CSV; callers that need actual
                # match RESULTS (not just roster/tier membership) must
                # explicitly filter on it themselves - load_all_fixtures()
                # no longer does that filtering centrally.
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

def apply_season_aliases(fixtures: list[dict], league_lookup: dict) -> int:
    """
    Rewrites row["season"] in place for any fixture whose league_id has a
    "season_aliases" entry matching that row's season - e.g. Japan's J1
    League (league_id 98): API-Football tagged the one-off 2026 bridging
    tournament "2026" and the new autumn-spring season that actually
    followed it "2027", but Greg's call is that these are genuinely ONE
    continuous season split across two API-Football season labels, not
    two separate season transitions - so "2027" gets aliased to "2026"
    here, uniformly, before anything downstream (tier lookup, country
    lookup, season_changed, match_log tagging, rankings.json's "league"
    field) ever sees the raw label.

    Applied once, as early as possible (right after league_lookup is
    built, before fixtures.sort()) specifically so every consumer needs
    zero additional season-aware logic of its own - unlike
    season_type_overrides, which had to be threaded through every single
    place that checks competition type individually.
    """
    remapped = 0
    for row in fixtures:
        entry = league_lookup.get(int(row["league_id"]))
        if entry is None:
            continue
        aliases = entry.get("season_aliases") or {}
        alias = aliases.get(str(row["season"]))
        if alias is not None and alias != row["season"]:
            row["season"] = alias
            remapped += 1
    return remapped


def main():
    print("Loading fixtures...")
    fixtures = load_all_fixtures()
    played_count = sum(1 for row in fixtures if row["played"] == "True")
    print(f"  {len(fixtures)} total fixtures found ({played_count} played, "
          f"{len(fixtures) - played_count} scheduled/not yet played) across "
          f"all pulled leagues/seasons")

    fixtures.sort(key=fixture_sort_key)

    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        leagues_config = json.load(f)
    league_lookup = build_league_lookup(leagues_config)

    remapped_seasons = apply_season_aliases(fixtures, league_lookup)
    if remapped_seasons:
        print(f"Applied season_aliases to {remapped_seasons} fixture-side occurrences.")

    # Cross-check: every competition/season leagues_config.json says should
    # be tracked, against what fixture data was ACTUALLY loaded above. A
    # competition can be perfectly configured (correct league_id, type,
    # tier, season_inclusion.json entry) and still produce zero clubs with
    # no error anywhere, simply because its fixtures CSV was never pulled
    # or wasn't in data/fixtures/ yet when this ran - that gap is otherwise
    # invisible until someone notices a whole country missing from the
    # rankings output. Flagging it here, at the top of the run, makes it
    # immediately visible instead.
    seasons_with_data = set()
    for row in fixtures:
        seasons_with_data.add((row["league_id"], row["season"]))
    missing_data = []
    for country, comps in leagues_config.items():
        for comp in comps:
            for season in comp.get("seasons", []):
                key = (str(comp["league_id"]), str(season))
                if key not in seasons_with_data:
                    missing_data.append((country, comp["name"], comp["league_id"], season))
    if missing_data:
        print(f"\nWARNING: {len(missing_data)} configured competition/season(s) have NO "
              f"fixture data loaded - the CSV either doesn't exist in data/fixtures/ yet "
              f"or wasn't found. These will silently produce zero clubs with no other "
              f"warning unless you check for this:")
        for country, name, league_id, season in missing_data:
            print(f"  {country} / {name} (id={league_id}) - season {season}")
        print()

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

    if os.path.exists(SEASON_INCLUSION_PATH):
        with open(SEASON_INCLUSION_PATH, encoding="utf-8") as f:
            season_inclusion = json.load(f)
        print(f"  Loaded season_inclusion.json - {len(season_inclusion)} seasons of real tracked-division data "
              f"(from Leagues_Included_in_Ranking.xlsx)")
    else:
        season_inclusion = None
        print("  season_inclusion.json not found - falling back to treating ANY season with pulled "
              "fixture data for a tier as genuinely tracked, which may not reflect actual "
              "year-to-year division-count changes. Run extract_season_inclusion.py to build this.")

    if os.path.exists(RELEGATION_PERCENTAGES_PATH):
        with open(RELEGATION_PERCENTAGES_PATH, encoding="utf-8") as f:
            relegation_percentages = json.load(f)
        print(f"  Loaded relegation_percentages.json - {len(relegation_percentages)} tiers with real "
              f"relegation data, needed for any mid-history promotion into an already-tracked tier")
    else:
        relegation_percentages = None
        print("  relegation_percentages.json not found - any mid-history promotion into an already-"
              "tracked tier will FAIL rather than silently use a stale bootstrap value. Run "
              "convert_relegation_percentages.py to build this.")

    finals_config = _load_json(FINALS_CONFIG_PATH)
    venue_overrides = _load_json(VENUE_OVERRIDES_PATH)

    print("Computing season-boundary snapshot trigger points...")
    season_end_triggers = build_season_end_trigger_points(fixtures, league_lookup)
    season_snapshots = {}  # (country, tier, season) -> snapshot dict, keyed
                            # as a string "country|tier|season" for JSON output

    print("Computing public chart-history snapshot dates (Mon/Thu cadence)...")
    history_dates = generate_snapshot_dates(SNAPSHOT_START_DATE, datetime.now().date())
    history_recorder = SnapshotRecorder(history_dates)
    match_log_recorder = MatchLogRecorder()
    last_processed_match_date = None  # tracked for the final catch-up snapshot

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
    tracked_status_lost_events = []  # collected during the run, filtered
                                      # and printed only at the very end -
                                      # see the filtering logic after the
                                      # main loop for why (most of these
                                      # turn out to be real, correct
                                      # relegations that get promoted back
                                      # later in the same run - e.g. Brann
                                      # in 2022 - printing every one of
                                      # those immediately is noise, not
                                      # signal; only a club that's STILL
                                      # untracked once the whole run
                                      # finishes is worth surfacing).
    club_current_name: dict[str, str] = {}  # most recently seen display
                                             # name per team_id - updated on
                                             # EVERY match appearance, not
                                             # just at seed time, so it
                                             # reflects renames/rebrands.
    club_current_meta: dict[str, dict] = {}  # team_id -> {"country":...,
                                              # "league_code":..., "season":...}
                                              # - the club's CURRENT tier
                                              # identity, refreshed alongside
                                              # club_is_tracked whenever a
                                              # club is (re)seeded. Powers
                                              # rankings.json's country/
                                              # league_code fields - a club's
                                              # tier can change via
                                              # promotion/relegation, so this
                                              # always reflects the latest
                                              # resolved value, not a static
                                              # one-time lookup.

    processed = 0
    skipped_missing_data = 0
    skipped_no_venue = 0
    seeding_failures = 0
    seeding_failure_details = []  # written to seeding_failures_report.json
    skipped_match_details = []  # every skipped match, with enough detail to
                                 # actually go find and fix it - written to
                                 # skipped_matches_report.json at the end,
                                 # not just counted

    def _current_club_meta(team_id: str, season: str) -> dict:
        """Country + league_code (e.g. "ENG_2") + season, exactly matching
        the code/key resolution logic used throughout get_starting_position -
        computed independently here since get_starting_position only
        returns (rating, source), not the resolved identity itself."""
        country = get_team_country(team_id, team_country_lookup)
        base_code = country_code_mapping.get(country)
        tier = team_tier_by_season.get((team_id, season))
        league_code = base_code if (tier is None or tier == 1) else f"{base_code}_{tier}"
        return {"country": base_code, "league_code": league_code, "season": season}

    for i, row in enumerate(fixtures):
        # fixtures now includes scheduled/not-yet-played rows too (see
        # load_all_fixtures() docstring) - the tier/country lookups built
        # above deliberately use those, but actual rating processing
        # obviously can't do anything with a match that has no result yet.
        # Skipped here, not at load time, precisely so this loop is the
        # ONLY place that requires a real played match.
        if row["played"] != "True":
            continue

        home_id = row["home_team_id"]
        away_id = row["away_team_id"]
        season = row["season"]
        match_date = fixture_sort_key(row).date()

        # Capture any public chart-history snapshot dates that have now
        # fully passed, using club state exactly as it stands before this
        # fixture is applied - BEFORE either side gets seeded/reseeded
        # below. Getting this ordering right matters: if a brand-new
        # club's seeding happened first, the very first snapshot this
        # match's date newly makes eligible would already see that club
        # in club_states and incorrectly backfill it into every
        # historical catch-up snapshot back to SNAPSHOT_START_DATE with
        # its flat initial rating, even though its real first match is
        # potentially years later.
        history_recorder.maybe_snapshot(match_date, club_states, club_is_tracked)
        last_processed_match_date = match_date

        # Track the most recently seen name and current tier identity for
        # both sides, on EVERY match appearance - not just at seed time.
        # A directly-tracked club never goes through the reseed branch
        # below (its rating evolves via real match results instead), so
        # capturing this only at initial seed would go stale the moment
        # that club is later promoted or relegated. Name and tier identity
        # should always reflect the club's most recent real appearance.
        if row.get("home_team"):
            club_current_name[home_id] = row["home_team"]
        if row.get("away_team"):
            club_current_name[away_id] = row["away_team"]
        club_current_meta[home_id] = _current_club_meta(home_id, season)
        club_current_meta[away_id] = _current_club_meta(away_id, season)

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
            was_tracked = club_is_tracked.get(team_id, True)

            # Season-transition re-check (tracked-status reconfirmation /
            # reseed) is deliberately gated to LEAGUE-type matches only.
            # A club's tier - and therefore whether it's still genuinely
            # tracked - can only be confirmed from domestic league fixture
            # data (team_tier_by_season is built purely from league
            # appearances). Cup or continental competitions (a domestic
            # Super Cup, the first round of a domestic cup) routinely get
            # played - and pulled - before that season's LEAGUE fixtures
            # exist yet. Letting one of those matches trigger the
            # season-transition check would resolve tier=None (not because
            # the club actually dropped tiers, but because league data for
            # the new season simply hasn't arrived), which falls straight
            # through to the untracked-placeholder path and misclassifies
            # a still-elite, still-tracked club as having fallen out of
            # tracked status - exactly what happened to Bayern Munich and
            # Borussia Dortmund after the 2026 German Super Cup was
            # processed weeks before Bundesliga's 2026-27 fixtures existed.
            # Deferring this check to the club's first LEAGUE match of the
            # new season is a strictly safer failure mode: at worst it
            # delays detecting a genuine relegation by a few weeks until
            # the new league season actually starts, rather than falsely
            # un-tracking a club that never changed tier at all.
            #
            # Uses the SEASON-AWARE type (season_type_overrides), not the
            # entry's flat default - a league_id whose type varies by
            # season (e.g. Japan's J1 League, league_id 98: type="league"
            # in 2025/2027, but API-Football filed the one-off 2026
            # bridging tournament under this same ID as a "cup" override)
            # must resolve consistently here and in get_competition_info,
            # or a club could get its tier reconfirmed via a competition
            # this file elsewhere treats as not-a-real-league-season.
            match_overrides = league_entry.get("season_type_overrides") or {}
            effective_type = match_overrides.get(str(season), league_entry["type"])
            season_changed = (
                not needs_seed
                and club_seeded_season.get(team_id) != season
                and effective_type == "league"
            )

            # An UNTRACKED club whose season has changed gets its
            # placeholder recalculated fresh (using whatever the
            # tier-above's CURRENT snapshot is now) rather than carrying
            # over a stale value - untracked ratings are season
            # constants, not running totals. If it turns out to now be
            # PROMOTED into a genuinely tracked tier, this same
            # recalculation correctly starts it fresh as a brand-new
            # tracked club (get_starting_position's normal Starting
            # Position, not whatever placeholder value it carried while
            # untracked) - Greg's stated design: a promoted club is
            # "treated as if brand new for the ranking."
            needs_reseed = season_changed and not was_tracked

            # A club that IS currently tracked, but whose season has
            # changed, needs a check too - a normal relegation (finish
            # one season, start the next a few weeks later) never
            # triggers the 365-day inactivity-gap reset below, so
            # without this check a relegated club would silently keep
            # evolving via real match results in a tier that's no
            # longer supposed to be tracked at all. This only actually
            # RESETS the rating if the check confirms tracked status
            # genuinely dropped this season - if it's still tracked
            # (e.g. just a normal continuing top-tier club), the
            # existing evolved rating is left untouched below.
            needs_tracked_status_check = season_changed and was_tracked

            if not (needs_seed or needs_reseed or needs_tracked_status_check):
                continue
            try:
                rating, source = get_starting_position(
                    team_id, season, team_country_lookup, team_tier_by_season,
                    country_code_mapping, league_starts, untracked_club_tiers,
                    season_snapshots, row["league_id"], season_inclusion, relegation_percentages,
                )
                still_tracked = source.startswith("direct") or source.startswith("league_override") or source.startswith("standard_promotion")

                if needs_tracked_status_check and still_tracked:
                    # Still genuinely tracked this season (the normal,
                    # common case - most tracked clubs stay tracked
                    # season to season) - just refresh the season
                    # marker so this check doesn't keep re-firing every
                    # match this season. Rating keeps evolving from its
                    # current real value, untouched.
                    club_seeded_season[team_id] = season
                    continue

                # Every remaining case gets a freshly-computed rating:
                # a brand-new club, an untracked club's season refresh
                # (possibly now promoted into a tracked tier), or a
                # previously-tracked club that just fell OUT of tracked
                # status this season (relegated below what's directly
                # tracked, or its league dropped from season_inclusion) -
                # treated exactly like any other untracked-placeholder
                # club from this point on, per Greg's stated design,
                # not left silently evolving from its old tracked value.
                if needs_tracked_status_check and not still_tracked:
                    # Collected, not printed here - see the filtering pass
                    # after the main loop for why.
                    tracked_status_lost_events.append({
                        "team_id": team_id,
                        "name": row.get("home_team") if team_id == home_id else row.get("away_team"),
                        "season": season,
                        "source": source,
                        "league_id": row["league_id"],
                        "league_name": league_entry.get("name") if league_entry else "?",
                        "date": row["date"],
                    })
                club_states[team_id] = ClubState(rating=rating, last_match_date=None)
                seed_sources[team_id] = source
                # league_override clubs (e.g. OFC Pro League) are genuinely
                # tracked - a real league, ratings should evolve via match
                # results normally, not stay season-locked like an
                # untracked-placeholder club.
                club_is_tracked[team_id] = still_tracked
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

        competition_type, competition_name = get_competition_info(row["league_id"], row["season"], league_lookup)

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

        # A match can be marked played (status FT/AET/PEN) but still have
        # an empty score field - a genuine API-Football data-quality gap
        # (or, historically, a pull-script bug that wrote played=True
        # without confirming goals were actually non-null - fixed at the
        # pull-script source, but already-pulled CSVs from before that fix
        # may still have rows like this). Skip just this one match with a
        # clear report entry rather than crash the entire multi-hour run
        # over a single bad row.
        try:
            home_score = int(row["home_score"])
            away_score = int(row["away_score"])
        except ValueError:
            skipped_match_details.append({
                "reason": "invalid_score",
                "fixture_id": row.get("fixture_id"),
                "league_id": row["league_id"],
                "competition_name": competition_name,
                "country_context": league_entry.get("country") if league_entry else None,
                "date": row["date"],
                "home_team": row.get("home_team"), "away_team": row.get("away_team"),
                "home_score_raw": row.get("home_score"), "away_score_raw": row.get("away_score"),
            })
            continue
        goal_margin = abs(home_score - away_score)

        if home_score > away_score:
            result_a = 1.0
        elif home_score < away_score:
            result_a = 0.0
        else:
            result_a = 0.5

        # 365-day inactivity reset: if either club's last recorded match
        # was more than a year before this one, process_match needs a
        # freshly-computed Starting Position ready to hand it - it won't
        # compute this itself. Only builds entries for the side(s) that
        # actually need it.
        reset_lookup = {}
        reset_failed = False
        for label, team_id in (("a", home_id), ("b", away_id)):
            if needs_starting_position_reset(club_states[team_id].last_match_date, match_date):
                try:
                    fresh_rating, fresh_source = get_starting_position(
                        team_id, season, team_country_lookup, team_tier_by_season,
                        country_code_mapping, league_starts, untracked_club_tiers,
                        season_snapshots, row["league_id"], season_inclusion, relegation_percentages,
                    )
                    reset_lookup[label] = fresh_rating
                    seed_sources[team_id] = fresh_source + ":inactivity_reset"
                    club_is_tracked[team_id] = fresh_source.startswith("direct") or fresh_source.startswith("league_override") or fresh_source.startswith("standard_promotion")
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
                        "context": "inactivity_reset",
                    })
                    print(f"  SEEDING FAILED (inactivity reset): {team_name!r} (team_id={team_id}, "
                          f"playing in {league_entry.get('name') if league_entry else row['league_id']}): {e}")
                    reset_failed = True

        if reset_failed:
            skipped_missing_data += 1
            skipped_match_details.append({
                "reason": "inactivity_reset_failed",
                "fixture_id": row.get("fixture_id"),
                "league_id": row["league_id"],
                "competition_name": league_entry.get("name") if league_entry else None,
                "country_context": league_entry.get("country") if league_entry else None,
                "date": row["date"],
                "home_team": row.get("home_team"), "away_team": row.get("away_team"),
            })
            continue

        rating_a_before = club_states[home_id].rating
        rating_b_before = club_states[away_id].rating

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

        # Log this match into each side's own rolling result history -
        # independently gated per side on exactly the same
        # club_is_tracked condition already used above for update_a/
        # update_b, so a tracked club's match against an untracked
        # opponent still correctly logs from the TRACKED side's own
        # perspective (its own rating did move), while the untracked
        # side (whose rating never moves mid-season) doesn't get a
        # meaningless log entry of its own.
        if club_is_tracked.get(home_id, True):
            match_log_recorder.record_match(
                home_id, row.get("away_team"), away_id, match_date,
                gf=home_score, ga=away_score,
                elo_change=club_states[home_id].rating - rating_a_before,
                season=season,
                league_id=row["league_id"],
                competition_type=competition_type,
            )
        if club_is_tracked.get(away_id, True):
            match_log_recorder.record_match(
                away_id, row.get("home_team"), home_id, match_date,
                gf=away_score, ga=home_score,
                elo_change=club_states[away_id].rating - rating_b_before,
                season=season,
                league_id=row["league_id"],
                competition_type=competition_type,
            )

        # Season-boundary snapshot check: has this exact match's index just
        # completed one or more (league_id, season) groups?
        for league_id_key, season_key in season_end_triggers.get(i, []):
            snap = take_season_snapshot(league_id_key, season_key, league_lookup, fixtures, club_states)
            snap_key = f"{snap['country']}|{snap['tier']}|{snap['season']}"
            season_snapshots[snap_key] = snap

    with open(os.path.join(SCRIPT_DIR, "season_snapshots.json"), "w") as f:
        json.dump(season_snapshots, f, indent=2)
    print(f"\nWrote season_snapshots.json - {len(season_snapshots)} tier-seasons captured")

    # Filter tracked_status_lost_events down to only clubs that are STILL
    # untracked as of the end of the run - see Brann, 2022: they lost
    # tracked status mid-run when relegated, then correctly regained it
    # the following season once the same run processed their promotion
    # back. Printing every such event as it happened would mean drowning
    # a handful of genuinely-still-stuck clubs in years of accurate,
    # already-resolved history. club_is_tracked now holds each club's
    # FINAL status for this run, which is exactly the check needed.
    still_lost = [e for e in tracked_status_lost_events if not club_is_tracked.get(e["team_id"], False)]
    if still_lost:
        print(f"\n{len(still_lost)} club(s) lost tracked status at some point and are STILL "
              f"untracked as of this run's latest date - each of these is either a genuine "
              f"current relegation (expected) or worth a spot-check like the Brann case:")
        for e in still_lost:
            print(f"  {e['name']!r} (team_id={e['team_id']}) - lost entering season "
                  f"{e['season']}, resolved via {e['source']!r} instead of direct/"
                  f"league_override/standard_promotion. Triggered by league_id="
                  f"{e['league_id']} ({e['league_name']}), date={e['date']}.")
    if len(tracked_status_lost_events) > len(still_lost):
        print(f"\n({len(tracked_status_lost_events) - len(still_lost)} other tracked-status-loss "
              f"event(s) this run self-resolved later - e.g. a real relegation followed by "
              f"a real promotion back, like Brann in 2022-23 - and are not shown.)")

    if last_processed_match_date is not None:
        history_recorder.finalize(club_states, club_is_tracked, last_processed_match_date)
        history_output_dir = os.path.join(SCRIPT_DIR, "history")
        num_history_files = history_recorder.write_all(history_output_dir)
        print(f"Wrote {num_history_files} per-club chart-history files to "
              f"{history_output_dir}/ (public rankings/chart data, "
              f"Mon/Thu cadence from {SNAPSHOT_START_DATE.isoformat()})")

        club_metadata = {}
        for team_id in history_recorder.histories:
            club_metadata[team_id] = {
                "name": club_current_name.get(team_id, f"(unknown, team_id={team_id})"),
                "country": club_current_meta.get(team_id, {}).get("country"),
                "league_code": club_current_meta.get(team_id, {}).get("league_code"),
                "season": club_current_meta.get(team_id, {}).get("season"),
            }
        with open(os.path.join(SCRIPT_DIR, "club_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(club_metadata, f, indent=2, sort_keys=True)
        print(f"Wrote club_metadata.json - name/country/league_code/season for "
              f"{len(club_metadata)} clubs (the rankings.json generator's other input, "
              f"alongside history/)")

        match_log_output_dir = os.path.join(SCRIPT_DIR, "match_log")
        num_match_log_files = match_log_recorder.write_all(match_log_output_dir)
        print(f"Wrote {num_match_log_files} per-club match-log files to "
              f"{match_log_output_dir}/ (last up to {MAX_LOG_LENGTH} matches per club - "
              f"powers Tier B rankings.json fields: last_result/opponent/score, "
              f"calendar-year record, form5/form10)")

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
