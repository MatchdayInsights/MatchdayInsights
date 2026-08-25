"""
league_lookup.py

Loads leagues_config.json into league_id -> {country, name, tier, type}
(same shape as run_ratings.py's build_league_lookup), plus a season-display
formatter that decides whether a raw API-Football season integer (e.g.
2022) should render as "2022" (season contained within one calendar year)
or "2022-23" (season crosses a year boundary, e.g. most of Europe's Jul-Jun
cadence).

IMPORTANT: the country lists below are best-effort, built from general
football-calendar knowledge, not from an authoritative source in the
pipeline (no such file exists yet - run_ratings.py takes season directly
from each fixture file's own label and never needs to know the calendar
convention itself). Confidently-known entries are commented; anything not
listed defaults to "crosses year boundary" (YYYY-YY+1), which is a
reasonable default for most of Europe/CAF/West Asia but is a real guess
for some countries. Greg should review and correct this list.
"""

import json
from pathlib import Path

LEAGUES_CONFIG_PATH = Path("/home/claude/leagues_config.json")
if not LEAGUES_CONFIG_PATH.exists():
    LEAGUES_CONFIG_PATH = Path("/mnt/user-data/uploads/leagues_config.json")

# Countries whose top-level season is genuinely contained within one
# calendar year (Jan-Dec) - display as a single year, e.g. "2025".
# Everything NOT in this set defaults to "crosses a year boundary" format,
# e.g. "2025-26".
SINGLE_CALENDAR_YEAR_COUNTRIES = {
    # CONMEBOL - all calendar-year (confident)
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
    "Paraguay", "Peru", "Uruguay", "Venezuela",
    # UEFA calendar-year exceptions - Nordic/Baltic + Belarus (confident)
    "Sweden", "Norway", "Finland", "Iceland", "Faroe-Islands",
    "Estonia", "Latvia", "Lithuania", "Belarus",
    # CONCACAF - Apertura/Clausura calendar-year style + MLS/CPL (confident)
    "Mexico", "Honduras", "Guatemala", "El-Salvador", "Costa-Rica",
    "Panama", "Nicaragua", "USA", "Canada",
    # AFC - well-known calendar-year leagues (confident)
    "China", "South-Korea", "Indonesia", "Malaysia", "Singapore",
    # Reviewed and confirmed by Greg, 2026-08-24:
    "Georgia", "Japan", "Kazakhstan", "New-Zealand",
    # NOTE: reviewed and confirmed CROSSES YEAR (Jul-Jun default, correct
    # as-is, NOT single-year) by Greg, 2026-08-24: Armenia, Azerbaijan,
    # Vietnam, Thailand.
    # Still unreviewed / genuinely uncertain, left at Jul-Jun default:
    # rest of CAF (genuinely mixed, many already follow Aug-May Euro-style
    # so the default is probably close for most).
}

# Continental ("World"-country) competitions that actually run the long
# Aug/Sep-May Euro-style calendar and so cross a year boundary. Everything
# else under "World" (single-event tournaments like the FIFA Club World
# Cup or UEFA Super Cup, or calendar-year continental leagues like
# CONMEBOL Libertadores) defaults to a bare year - the OPPOSITE default
# from domestic leagues, since single-event/short tournaments are the
# norm for continental competitions, not the exception. Confirmed with
# Greg 2026-08-24 that FIFA Club World Cup is correctly single-year.
HYPHENATED_CONTINENTAL_COMPETITIONS = {
    "UEFA Champions League", "UEFA Europa League",
    "UEFA Europa Conference League",
    "AFC Champions League Elite", "AFC Champions League Two",
    "CAF Champions League", "CAF Confederation Cup",
}


def load_league_lookup() -> dict:
    with open(LEAGUES_CONFIG_PATH) as f:
        leagues_config = json.load(f)
    lookup = {}
    for country, comps in leagues_config.items():
        for comp in comps:
            lookup[str(comp["league_id"])] = {
                "country": country,
                "type": comp["type"],
                "name": comp["name"],
                "tier": comp.get("tier"),
            }
    return lookup


def format_season_display(season: str, country: str, competition_name: str = None) -> str:
    if season is None:
        return "—"
    try:
        year = int(season)
    except (TypeError, ValueError):
        return season

    if country == "World":
        crosses_year_boundary = competition_name in HYPHENATED_CONTINENTAL_COMPETITIONS
    else:
        crosses_year_boundary = country not in SINGLE_CALENDAR_YEAR_COUNTRIES

    if crosses_year_boundary:
        return f"{year}-{str(year + 1)[-2:]}"
    return str(year)
