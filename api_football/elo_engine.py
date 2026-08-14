"""
elo_engine.py

Matchday Insights - P4 Rating Engine

Implements the full rating system as specified:
  - Zero-sum Elo-style rating update with home advantage confined to the
    expected-score calculation only
  - Goal-Difference Multiplier (uncapped, validated against real blowout
    data - see conversation history)
  - Flat K=25 (no competition-type exceptions)
  - Starting Position determination across all cases: standard
    (relegation-based), newly-tracked Tier 2-4 (relegated-clubs +
    mapped-country ratio blend), Tier 5+ fallback, and untracked-division
    placeholder ratings for cup-tie opponents
  - Neutral venue determination
  - 365-day inactivity reset to Starting Position

This module is data-source agnostic: it does not know about
all_history.json, CLUBS, or your specific file layout. It operates on
plain dicts/values so you can wire it into the existing pipeline
(pull_data.py output, crosswalk-resolved club records, etc.) however
makes sense on your end.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

K_FACTOR = 25.0

HOME_ADVANTAGE = {
    "league_cup": 58.60,
    "continental_global": 81.50,
}

# Tier 5+ fallback multiplier for genuinely NEW/newly-tracked divisions
# entering the ranking (Starting Position case, not the placeholder case).
TIER_5_PLUS_MULTIPLIER = 0.78

# Untracked-division placeholder ratios (cup-tie opponents only - NOT
# used for any club that's actually in the ranking). Derived from real
# tier1->2->3->4 starts across all confederations in League_Starts.xlsx.
UNTRACKED_PLACEHOLDER_RATIOS = {
    2: 0.7626,   # tier N -> N+1 where N+1 == 2
    3: 0.7909,   # ... == 3
    4: 0.8968,   # ... == 4
}
UNTRACKED_PLACEHOLDER_FLAT = 0.8968  # tier 5+ beyond the last measured step

INACTIVITY_RESET_DAYS = 365


# ---------------------------------------------------------------------------
# CORE RATING UPDATE
# ---------------------------------------------------------------------------

def goal_difference_multiplier(goal_margin: int) -> float:
    """
    GDM per the spec:
      1 goal margin  -> 1.0
      2 goal margin  -> 1.5
      3+ goal margin -> (11 + margin) / 8   (uncapped by design - see
                                              validation against real
                                              blowout data)
    goal_margin should be a positive integer (abs(goals_for - goals_against)).
    A draw (goal_margin == 0) doesn't use GDM at all since result_x = 0.5
    on both sides and the GDM term is irrelevant to a 0.5 result in
    practice, but we still return 1.0 defensively.
    """
    if goal_margin <= 0:
        return 1.0
    if goal_margin == 1:
        return 1.0
    if goal_margin == 2:
        return 1.5
    return (11 + goal_margin) / 8


def expected_score(rating_a: float, rating_b: float, home_advantage_a: float) -> float:
    """
    Expected score for side A, with home_advantage_a applied ONLY inside
    this calculation (never added to the base rating). Pass
    home_advantage_a=0 for neutral-venue matches.
    """
    exponent = -((rating_a + home_advantage_a) - rating_b) / 400
    return 1 / (10 ** exponent + 1)


def update_ratings(
    rating_a: float,
    rating_b: float,
    result_a: float,
    goal_margin: int,
    home_advantage_a: float = 0.0,
) -> tuple[float, float]:
    """
    Core zero-sum rating update.

    result_a: 1.0 win / 0.5 draw (incl. all penalty-shootout results) / 0.0 loss
    goal_margin: absolute goal difference (0 for a draw)
    home_advantage_a: 58.60 / 81.50 / 0.0 (neutral) - applies to side A only;
                       pass 0 for side B's own expected-score calc since it's
                       computed as the complement.

    Returns (new_rating_a, new_rating_b). Verified zero-sum:
    (new_a - rating_a) == -(new_b - rating_b)
    """
    exp_a = expected_score(rating_a, rating_b, home_advantage_a)
    exp_b = 1 - exp_a
    result_b = 1 - result_a if result_a != 0.5 else 0.5

    gdm = goal_difference_multiplier(goal_margin)

    new_a = rating_a + K_FACTOR * gdm * (result_a - exp_a)
    new_b = rating_b + K_FACTOR * gdm * (result_b - exp_b)

    return new_a, new_b


# ---------------------------------------------------------------------------
# NEUTRAL VENUE DETERMINATION
# ---------------------------------------------------------------------------

@dataclass
class MatchContext:
    competition_type: str          # "domestic_league" | "domestic_cup" |
                                    # "continental" | "global" (FIFA)
    is_final: bool = False
    is_single_leg: bool = False    # relevant for finals/semifinals
    home_team_country: Optional[str] = None
    venue_id: Optional[str] = None
    venue_country: Optional[str] = None  # resolved via lazy override table;
                                          # None/unknown == assume same as
                                          # home team's country (not neutral)


def is_neutral(ctx: MatchContext) -> bool:
    """
    Neutral-venue determination per spec:
      - FIFA competitions (competition_type == "global"): always neutral
      - Continental/global finals: neutral if single-leg
      - Continental/global, other matches: neutral only if venue_country
        is known AND differs from home_team_country (lazy override table -
        default assumption when venue_country is unresolved is NOT neutral)
      - Domestic league: never neutral
      - Domestic cup: neutral only for single-leg finals/semifinals
    """
    if ctx.competition_type == "global":
        return True

    if ctx.competition_type == "continental":
        if ctx.is_final and ctx.is_single_leg:
            return True
        if ctx.venue_country and ctx.home_team_country:
            return ctx.venue_country != ctx.home_team_country
        return False  # unresolved venue -> assume not neutral

    if ctx.competition_type == "domestic_cup":
        return ctx.is_final and ctx.is_single_leg

    # domestic_league
    return False


def home_advantage_for_match(ctx: MatchContext) -> float:
    """Returns the home advantage value to use in expected_score, given
    match context. Returns 0.0 for neutral matches."""
    if is_neutral(ctx):
        return 0.0
    if ctx.competition_type in ("continental", "global"):
        return HOME_ADVANTAGE["continental_global"]
    return HOME_ADVANTAGE["league_cup"]


# ---------------------------------------------------------------------------
# STARTING POSITION - STANDARD CASE
# (league already tracked, has a prior season's final ratings)
# ---------------------------------------------------------------------------

def starting_position_standard(
    min_rating: float, max_rating: float, relegated_count: float, total_clubs: int
) -> float:
    """
    min_rating + (max_rating - min_rating) * (relegated_count / total_clubs)

    relegated_count can be fractional (e.g. 2.5 for a playoff-implicated
    slot - see weighted_relegated_average below for how that 0.5 is derived
    from raw standings data).
    """
    pct = relegated_count / total_clubs
    return min_rating + (max_rating - min_rating) * pct


def weighted_relegated_average(club_ratings_ascending: list[float], relegated_count: float) -> float:
    """
    Weighted average rating of the relegated clubs, handling fractional
    relegation counts (e.g. 2.5 = 2 confirmed + 1 playoff-implicated slot
    weighted at 0.5).

    club_ratings_ascending: ratings of the relegation-eligible clubs,
                             sorted lowest-rated first, e.g. [R1, R2, R3, ...]
    relegated_count: e.g. 2.5

    Formula: (R1 + R2 + 0.5*R3) / 2.5  for a 2.5 case, generalized to any
    fractional count.
    """
    n_full = int(relegated_count)
    frac = relegated_count - n_full

    if n_full > len(club_ratings_ascending):
        raise ValueError("relegated_count exceeds number of provided club ratings")

    weighted_sum = sum(club_ratings_ascending[:n_full])
    if frac > 0:
        if n_full >= len(club_ratings_ascending):
            raise ValueError("fractional slot requested but no additional club rating provided")
        weighted_sum += frac * club_ratings_ascending[n_full]

    return weighted_sum / relegated_count


# ---------------------------------------------------------------------------
# STARTING POSITION - NEWLY-TRACKED TIER 2/3/4
# (tier above is already tracked; this tier is being added for the first time)
# ---------------------------------------------------------------------------

def starting_position_new_tier(relegated_weighted_avg_rating: float, mapped_country_avg_ratio: float) -> float:
    """
    New Tier N Start = relegated_weighted_avg_rating * (1 + mapped_country_avg_ratio) / 2

    relegated_weighted_avg_rating: weighted_relegated_average() of the
        clubs relegated FROM the tier above INTO this newly-tracked tier
    mapped_country_avg_ratio: average(Tier_N / Tier_(N-1)) across
        countries where both tiers are already tracked, applied here as
        relegated_weighted_avg_rating * ratio (NOT tier_above_start * ratio -
        anchored to the real relegated clubs' ratings per the corrected
        design, see conversation history)
    """
    old_method_derived = relegated_weighted_avg_rating * mapped_country_avg_ratio
    return (relegated_weighted_avg_rating + old_method_derived) / 2


# ---------------------------------------------------------------------------
# STARTING POSITION - TIER 5+ FALLBACK (no direct data, league IS tracked)
# ---------------------------------------------------------------------------

def starting_position_tier_5_plus(tier_above_start: float) -> float:
    """tier_n_start = tier_(n-1)_start * 0.78, for n >= 5."""
    return tier_above_start * TIER_5_PLUS_MULTIPLIER


# ---------------------------------------------------------------------------
# UNTRACKED-DIVISION PLACEHOLDER RATINGS
# (cup-tie opponents only - clubs NOT in the ranking. Never used for a
#  club that's actually tracked.)
# ---------------------------------------------------------------------------

def untracked_placeholder_rating(deepest_tracked_tier_start: float, deepest_tracked_tier: int, target_tier: int) -> float:
    """
    Chains the flat empirical ratios down from whichever tier is the
    deepest one actually tracked for this country, to produce a
    placeholder rating for an untracked division's clubs - used only so
    a ranked club has *something* to play against in a cup tie.

    e.g. deepest_tracked_tier=1, target_tier=3:
        tier2 = tier1 * 0.7626
        tier3 = tier2 * 0.7909
    """
    if target_tier <= deepest_tracked_tier:
        raise ValueError("target_tier must be deeper than deepest_tracked_tier")

    rating = deepest_tracked_tier_start
    for tier in range(deepest_tracked_tier + 1, target_tier + 1):
        ratio = UNTRACKED_PLACEHOLDER_RATIOS.get(tier, UNTRACKED_PLACEHOLDER_FLAT)
        rating = rating * ratio
    return rating


# ---------------------------------------------------------------------------
# INACTIVITY / RE-ENTRY
# ---------------------------------------------------------------------------

def needs_starting_position_reset(last_match_date: Optional[date], current_match_date: date) -> bool:
    """
    True if the club's last recorded match was more than 365 days before
    the current match - applies whether the gap is due to relegation out
    of tracked scope, or genuine inactivity. On the next match, the club's
    rating should be reset to its (freshly recalculated) Starting Position
    rather than carried over from its stale pre-gap rating.
    """
    if last_match_date is None:
        return False  # no prior match at all - this is a first-ever entry,
                       # not a re-entry; handled by Starting Position logic
                       # directly, not this reset path.
    return (current_match_date - last_match_date).days > INACTIVITY_RESET_DAYS


# ---------------------------------------------------------------------------
# MATCH PROCESSING - orchestration example
# ---------------------------------------------------------------------------

@dataclass
class ClubState:
    rating: float
    last_match_date: Optional[date] = None


def process_match(
    club_a: ClubState,
    club_b: ClubState,
    result_a: float,
    goal_margin: int,
    match_ctx: MatchContext,
    match_date: date,
    starting_position_lookup: Optional[dict] = None,
    update_a: bool = True,
    update_b: bool = True,
) -> tuple[ClubState, ClubState]:
    """
    Processes a single match and returns updated ClubState for both sides.

    update_a / update_b: whether each side's rating actually gets written
        back after this match. An UNTRACKED club (one whose rating comes
        from the season-locked placeholder chain, not real tracked-tier
        play) must NEVER have its stored rating move based on a match
        result - its rating is fixed for the whole season and only
        changes when the season boundary triggers a fresh placeholder
        recalculation. Pass update_a/update_b=False for whichever side(s)
        are untracked. The match is still fully computed either way
        (an untracked opponent's current rating correctly still
        influences how much the TRACKED side's rating moves) - only the
        write-back is suppressed.

    starting_position_lookup: optional dict of {club_id: starting_rating}
        used to reset a club's rating if it's returning after 365+ days
        inactive. If a reset is needed and no lookup value is provided,
        this raises - callers should compute the fresh Starting Position
        before calling process_match for a club coming back from a gap.

    NOTE: this function operates on ClubState objects directly for
    illustration; wire the actual club_id resolution into your own
    pipeline's data model.
    """
    for club, label in ((club_a, "a"), (club_b, "b")):
        if needs_starting_position_reset(club.last_match_date, match_date):
            if starting_position_lookup is None:
                raise ValueError(
                    f"Club {label} requires a Starting Position reset "
                    f"(365+ days inactive) but no starting_position_lookup provided."
                )
            club.rating = starting_position_lookup[label]

    home_adv_a = home_advantage_for_match(match_ctx)

    new_rating_a, new_rating_b = update_ratings(
        rating_a=club_a.rating,
        rating_b=club_b.rating,
        result_a=result_a,
        goal_margin=goal_margin,
        home_advantage_a=home_adv_a,
    )

    if update_a:
        club_a.rating = new_rating_a
        club_a.last_match_date = match_date
    if update_b:
        club_b.rating = new_rating_b
        club_b.last_match_date = match_date

    return club_a, club_b


# ---------------------------------------------------------------------------
# Quick self-test against the worked examples from the spec conversation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Zero-sum core formula check (Team A 816.39 home vs Team B 855.48, 1-0 league win)
    a, b = update_ratings(
        rating_a=816.39, rating_b=855.48, result_a=1.0, goal_margin=1,
        home_advantage_a=HOME_ADVANTAGE["league_cup"],
    )
    print(f"Core formula test: A={a:.2f} (expect 828.19), B={b:.2f} (expect 843.68)")
    assert abs(a - 828.19) < 0.01
    assert abs(b - 843.68) < 0.01
    assert abs((a - 816.39) + (b - 855.48)) < 1e-9, "not zero-sum!"

    # Starting Position standard case (Albania 2020-21 -> 2021-22, 2.5 relegated of 10)
    sp = starting_position_standard(min_rating=646.27, max_rating=958.75, relegated_count=2.5, total_clubs=10)
    print(f"Standard Starting Position test: {sp:.2f} (expect 724.39)")
    assert abs(sp - 724.39) < 0.01

    # Weighted relegated average (2 confirmed + 1 playoff at 0.5)
    wavg = weighted_relegated_average([700, 750, 800], relegated_count=2.5)
    print(f"Weighted relegated avg test: {wavg:.2f} (expect (700+750+0.5*800)/2.5 = 740.00)")
    assert abs(wavg - 740.00) < 0.01

    # New-tier bootstrap example (relegated avg 1000, ratio 0.797 -> ~898.5)
    nt = starting_position_new_tier(relegated_weighted_avg_rating=1000, mapped_country_avg_ratio=0.797)
    print(f"New tier bootstrap test: {nt:.2f} (expect 898.50)")
    assert abs(nt - 898.5) < 0.01

    # Untracked placeholder chain (tier1 -> tier3)
    ph = untracked_placeholder_rating(deepest_tracked_tier_start=1200, deepest_tracked_tier=1, target_tier=3)
    expected_ph = 1200 * 0.7626 * 0.7909
    print(f"Untracked placeholder test: {ph:.2f} (expect {expected_ph:.2f})")
    assert abs(ph - expected_ph) < 0.01

    # Multi-goal margin zero-sum test (Team A 896.88 vs Team B 922.01, 1-5 loss for A)
    # GDM must apply to the WHOLE (Result - Expected) bracket, not just Result,
    # or this comes out asymmetric - see conversation history for the full derivation.
    a2, b2 = update_ratings(
        rating_a=896.88, rating_b=922.01, result_a=0.0, goal_margin=4,
        home_advantage_a=HOME_ADVANTAGE["league_cup"],
    )
    print(f"Multi-goal zero-sum test: A_delta={a2-896.88:.2f} (expect -25.69), "
          f"B_delta={b2-922.01:.2f} (expect +25.69)")
    assert abs((a2 - 896.88) - (-25.69)) < 0.01
    assert abs((b2 - 922.01) - 25.69) < 0.01
    assert abs((a2 - 896.88) + (b2 - 922.01)) < 1e-9, "not zero-sum!"

    print("\nAll self-tests passed.")
