"""
match_context_builder.py

Builds a MatchContext (from elo_engine.py) for each raw match record
pulled from your pipeline. The one piece that can't be read directly
off a fixture - whether a competition's FINAL is single-leg (and
therefore neutral) or two-legged - is re-confirmed EVERY SEASON, since
formats can change year to year.

Two run modes, auto-detected:

  INTERACTIVE (you're running this yourself, e.g. at your desk during
  the annual review): the first time a competition's final is seen in a
  given season, it prompts you directly. Answered once per
  competition-per-season, then cached.

  NON-INTERACTIVE (a scheduled/automated run with nobody watching): it
  CANNOT prompt you - input() would just hang or error. Instead it:
    1. Falls back to last season's answer for that competition as a
       provisional value (competition formats rarely change), so the
       pipeline doesn't halt.
    2. Logs the gap to pending_confirmations.json.
    3. If GITHUB_TOKEN and GITHUB_REPOSITORY are set (both present
       automatically inside a GitHub Actions run), opens a GitHub Issue
       so you get a real notification (GitHub emails you on new issues)
       rather than having to remember to check logs. Answer the issue's
       checklist however you like, then rerun
       resolve_pending_confirmations.py to write your answers back into
       finals_config.json.
    If a competition has NEVER been confirmed before (no prior season to
    fall back on), it defaults to NOT single-leg (not neutral) - same
    "unknown defaults to false" pattern used for venue-country overrides
    - and is flagged just as loudly for review.

Usage:
    from match_context_builder import build_match_context, MatchContext

    ctx = build_match_context(raw_match_record)
    # ctx is now ready to pass into elo_engine.process_match()

Run this file directly to process a batch of matches (interactive
pre-population before a real pipeline run):
    python match_context_builder.py path/to/matches.json
"""

import json
import os
import sys
import urllib.request
from typing import Optional

from elo_engine import MatchContext

FINALS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "finals_config.json")
VENUE_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "venue_country_overrides.json")
PENDING_CONFIRMATIONS_PATH = os.path.join(os.path.dirname(__file__), "pending_confirmations.json")


# ---------------------------------------------------------------------------
# Persisted config loading/saving
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _save_json(path: str, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Single-leg-final determination (interactive when possible, cached PER
# SEASON, with a non-interactive fallback + notification path)
# ---------------------------------------------------------------------------

def is_final_round(round_name: str) -> bool:
    """
    Loose match on API-Football's round-naming conventions for a final.
    Deliberately broad - false positives just mean an extra prompt once,
    which is cheap; false negatives mean a real final gets treated as a
    normal two-legged match and silently gets home advantage it shouldn't.
    """
    if not round_name:
        return False
    r = round_name.lower()
    return "final" in r and "semi" not in r and "quarter" not in r


def _is_interactive() -> bool:
    """True only if there's an actual human at a terminal who could
    answer a prompt right now."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _most_recent_prior_answer(competition_name: str, season: str, finals_config: dict) -> Optional[bool]:
    """Looks for the closest prior season's cached answer for this
    competition, to use as a provisional fallback when running
    unattended. finals_config is structured {competition: {season: bool}}."""
    seasons_seen = finals_config.get(competition_name, {})
    if not seasons_seen:
        return None
    # prior seasons only, most recent first (string sort works for
    # "YYYY-YY"-style season labels; adjust if your season format differs)
    prior = sorted([s for s in seasons_seen if s < season], reverse=True)
    if not prior:
        return None
    return seasons_seen[prior[0]]


def _log_pending_confirmation(competition_name: str, season: str, provisional_value: bool, reason: str) -> None:
    pending = _load_json(PENDING_CONFIRMATIONS_PATH)
    key = f"{competition_name}__{season}"
    if key in pending:
        return  # already logged this run/season, don't spam
    pending[key] = {
        "competition": competition_name,
        "season": season,
        "provisional_value": provisional_value,
        "reason": reason,
    }
    _save_json(PENDING_CONFIRMATIONS_PATH, pending)
    _notify_github_issue(competition_name, season, provisional_value, reason)


def _notify_github_issue(competition_name: str, season: str, provisional_value: bool, reason: str) -> None:
    """
    Opens a GitHub Issue so you get a real notification (GitHub emails
    you automatically on new issues in repos you watch) rather than
    needing to remember to check pending_confirmations.json yourself.
    No-ops silently if GITHUB_TOKEN / GITHUB_REPOSITORY aren't set (e.g.
    you're not running this inside GitHub Actions) - falls back to the
    pending_confirmations.json file only in that case.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # e.g. "MatchdayInsights/MatchdayInsights"
    if not token or not repo:
        return

    title = f"Confirm final format: {competition_name} ({season})"
    body = (
        f"Automated run couldn't confirm whether the **{competition_name}** "
        f"final is single-leg (neutral) for season **{season}**.\n\n"
        f"- Provisional value used this run: `{provisional_value}` "
        f"(carried over from most recent prior season)\n"
        f"- Reason: {reason}\n\n"
        f"To resolve: reply to this issue with the correct answer, then "
        f"run `resolve_pending_confirmations.py` to write it into "
        f"`finals_config.json` and close this out."
    )
    payload = json.dumps({"title": title, "body": body}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        # Don't let a notification failure break the actual pipeline run.
        print(f"  (warning: failed to open GitHub Issue notification: {e})")


def get_is_single_leg_final(competition_name: str, season: str, finals_config: dict) -> bool:
    """
    Returns whether this competition's final is single-leg (and therefore
    neutral, per the neutral-venue rules in elo_engine.py), for the given
    season specifically - re-confirmed every year, not cached forever.

    INTERACTIVE: prompts you directly, first time this competition+season
    combo is seen.

    NON-INTERACTIVE: falls back to the most recent prior season's answer
    (if one exists) so the pipeline doesn't halt, logs the gap to
    pending_confirmations.json, and opens a GitHub Issue if configured.
    If there's no prior season at all (brand-new competition), defaults
    to False (not single-leg / not neutral) and flags it the same way.
    """
    seasons_seen = finals_config.setdefault(competition_name, {})
    if season in seasons_seen:
        return seasons_seen[season]

    if _is_interactive():
        print(f"\nNew season for competition final: {competition_name!r} ({season})")
        while True:
            answer = input(
                f"  Is the {competition_name} {season} final SINGLE-LEG (neutral venue)? [y/n]: "
            ).strip().lower()
            if answer in ("y", "yes"):
                is_single_leg = True
                break
            elif answer in ("n", "no"):
                is_single_leg = False
                break
            print("  Please answer y or n.")

        seasons_seen[season] = is_single_leg
        _save_json(FINALS_CONFIG_PATH, finals_config)
        print(f"  Saved for {season} - will ask again next season.\n")
        return is_single_leg

    # --- non-interactive fallback ---
    prior_answer = _most_recent_prior_answer(competition_name, season, finals_config)
    if prior_answer is not None:
        provisional = prior_answer
        reason = "no TTY available (scheduled run); carried over most recent prior season's answer"
    else:
        provisional = False
        reason = "no TTY available (scheduled run) AND no prior season on record; defaulted to not-neutral"

    _log_pending_confirmation(competition_name, season, provisional, reason)
    # Note: deliberately NOT cached into finals_config here - a
    # provisional/unconfirmed value should never silently become the
    # permanent cached answer. It's used for this run only, every run
    # until confirmed, and stays flagged in pending_confirmations.json.
    return provisional


# ---------------------------------------------------------------------------
# MatchContext builder
# ---------------------------------------------------------------------------

def build_match_context(
    raw_match: dict,
    finals_config: Optional[dict] = None,
    venue_overrides: Optional[dict] = None,
) -> MatchContext:
    """
    raw_match is expected to have (adjust key names to match your actual
    pull_data.py output structure):
        competition_type: "domestic_league" | "domestic_cup" |
                           "continental" | "global"
        competition_name: str  (e.g. "UEFA Champions League") - used as
                           the cache key for single-leg-final answers
        season: str  (e.g. "2025-26") - finals are re-confirmed every season
        round: str  (API-Football's round field, e.g. "Final", "Semi-finals")
        home_team_country: str
        venue_id: str or None

    finals_config / venue_overrides: pass in already-loaded dicts if
    you're processing a batch (avoids re-reading the JSON file per match);
    if omitted, this function loads them itself.
    """
    if finals_config is None:
        finals_config = _load_json(FINALS_CONFIG_PATH)
    if venue_overrides is None:
        venue_overrides = _load_json(VENUE_OVERRIDES_PATH)

    round_name = raw_match.get("round", "")
    is_final = is_final_round(round_name)

    is_single_leg = False
    if is_final and raw_match["competition_type"] in ("continental", "global", "domestic_cup"):
        is_single_leg = get_is_single_leg_final(
            raw_match["competition_name"], raw_match["season"], finals_config
        )

    venue_id = raw_match.get("venue_id")
    venue_country = venue_overrides.get(venue_id) if venue_id else None
    # venue_country stays None if not in the override table - elo_engine's
    # is_neutral() correctly treats an unresolved venue_country as "not
    # neutral" by default, per the lazy-override design.

    return MatchContext(
        competition_type=raw_match["competition_type"],
        is_final=is_final,
        is_single_leg=is_single_leg,
        home_team_country=raw_match.get("home_team_country"),
        venue_id=venue_id,
        venue_country=venue_country,
    )


# ---------------------------------------------------------------------------
# Batch pre-population helper
# ---------------------------------------------------------------------------

def prepopulate_from_matches(matches_path: str) -> None:
    """
    Runs through a batch of raw match records (JSON list) purely to
    surface every new competition-final prompt up front, rather than
    getting interrupted mid-pipeline-run. Doesn't do anything with the
    resulting MatchContexts - just walks the list to trigger caching.
    """
    with open(matches_path, "r") as f:
        matches = json.load(f)

    finals_config = _load_json(FINALS_CONFIG_PATH)
    venue_overrides = _load_json(VENUE_OVERRIDES_PATH)

    seen = 0
    for raw_match in matches:
        build_match_context(raw_match, finals_config, venue_overrides)
        seen += 1

    print(f"\nProcessed {seen} matches. finals_config.json now has "
          f"{len(_load_json(FINALS_CONFIG_PATH))} competitions cached.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python match_context_builder.py path/to/matches.json")
        sys.exit(1)
    prepopulate_from_matches(sys.argv[1])
