"""
generate_rankings.py

Produces rankings.json - the new site's homepage table data, replacing
the old baked-in CLUBS array in index.html. Combines inputs that
run_ratings.py writes:
  - history/{team_id}.json    (rank/elo time series) - "Tier A" fields
  - club_metadata.json        (name, country, league_code, current season)
  - confederation_mapping.json (for the "league" season-label format)
  - match_log/{team_id}.json  (rolling per-match result log) - "Tier B" fields

Tier A: rank/prev_rank/rank_change/elo/elo_change, all-time high/low
(rank + elo, with dates), times_no1/top5/top10/top50/tier_counts -
everything computable purely from the elo/rank snapshot history.

Tier B: last_result/opponent/score, calendar-year record (cy_w/cy_d/
cy_l/cy_pts/cy_pct/cy_gp), form5/form10 - needs the per-match result
log, since none of this is derivable from aggregate rating alone.
"CURRENT calendar year" is taken from the year of the true latest
snapshot date (the same value already used for the stale-club filter),
not the machine's real-world clock, so a club's calendar-year record
is always internally consistent with whatever "now" this run of
rankings.json represents.

STALE-CLUB EXCLUSION: only clubs whose history's LAST recorded date
matches the true latest snapshot date across the whole dataset are
included. A club whose history stops earlier has genuinely fallen out
of the tracked universe (relegated below trackable tiers, 365-day
inactivity reset determining its tier can no longer be resolved, etc.)
and its stale rank/elo is not comparable to currently-tracked clubs -
see the same fix already applied to preview_rankings.py.

Usage:
    python generate_rankings.py
"""

import glob
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
MATCH_LOG_DIR = os.path.join(SCRIPT_DIR, "match_log")
CLUB_METADATA_PATH = os.path.join(SCRIPT_DIR, "club_metadata.json")
CONFEDERATION_MAPPING_PATH = os.path.join(SCRIPT_DIR, "confederation_mapping.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "rankings.json")

# Confederations whose leagues span a calendar-year boundary (e.g.
# Aug-May) display as "2026-27". CONMEBOL/OFC run calendar-year seasons
# and display as a bare year, "2026".
HYPHENATED_CONFEDERATIONS = {"UEFA", "CONCACAF", "CAF", "AFC"}

# Career-milestone rank thresholds for tier_counts. Only the first three
# (no1, top5, top10) and top50 are confirmed from the old site's real
# output - the rest is a reasonable milestone ladder, easy to adjust
# later since it's a pure formula over existing data, not new
# collection. Flag to Greg for review.
TIER_COUNT_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]


def format_season_label(season: str, country: str, confederation_mapping: dict) -> str:
    confed = confederation_mapping.get(country)
    if confed is None:
        # Unknown confederation - default to bare year rather than guess
        # wrong in the more "eye-catching" hyphenated direction.
        return season
    if confed in HYPHENATED_CONFEDERATIONS:
        try:
            year = int(season)
            return f"{year}-{str(year + 1)[-2:]}"
        except ValueError:
            return season
    return season


def compute_tier_b_fields(match_log: list[dict], current_year: int) -> dict:
    """match_log entries are in chronological order (oldest first, exactly
    as written by match_log.py's deque). form5/form10 read most-recent-
    first, matching how football "form" is conventionally displayed."""
    if not match_log:
        return {
            "last_result": None, "last_opponent": None, "last_score": None,
            "cy_w": 0, "cy_d": 0, "cy_l": 0, "cy_pts": 0, "cy_pct": None, "cy_gp": 0,
            "form5": [], "form10": [],
        }

    last = match_log[-1]
    most_recent_first = list(reversed(match_log))

    def format_form(entries: list[dict]) -> list[dict]:
        return [
            {"result": m["result"], "opponent": m["opponent"], "elo_change": m["elo_change"]}
            for m in entries
        ]

    cy_matches = [m for m in match_log if m["date"].startswith(f"{current_year}-")]
    cy_w = sum(1 for m in cy_matches if m["result"] == "W")
    cy_d = sum(1 for m in cy_matches if m["result"] == "D")
    cy_l = sum(1 for m in cy_matches if m["result"] == "L")
    cy_gp = len(cy_matches)
    cy_pts = cy_w * 3 + cy_d
    cy_pct = round(100 * cy_pts / (cy_gp * 3), 1) if cy_gp else None

    return {
        "last_result": last["result"],
        "last_opponent": last["opponent"],
        "last_score": f"{last['gf']}-{last['ga']}",
        "cy_w": cy_w, "cy_d": cy_d, "cy_l": cy_l,
        "cy_pts": cy_pts, "cy_pct": cy_pct, "cy_gp": cy_gp,
        "form5": format_form(most_recent_first[:5]),
        "form10": format_form(most_recent_first[:10]),
    }


def main():
    if not os.path.isdir(HISTORY_DIR):
        print(f"No history/ directory found at {HISTORY_DIR} - run run_ratings.py first.")
        return
    if not os.path.exists(CLUB_METADATA_PATH):
        print(f"No club_metadata.json found - run the latest run_ratings.py first "
              f"(this file is a new output, added alongside history/).")
        return

    with open(CLUB_METADATA_PATH, encoding="utf-8") as f:
        club_metadata = json.load(f)

    confederation_mapping = {}
    if os.path.exists(CONFEDERATION_MAPPING_PATH):
        with open(CONFEDERATION_MAPPING_PATH, encoding="utf-8") as f:
            confederation_mapping = json.load(f)
    else:
        print("WARNING: confederation_mapping.json not found - every 'league' season "
              "label will default to a bare year regardless of confederation. Run "
              "extract_confederation_mapping.py to fix this.")

    has_match_logs = os.path.isdir(MATCH_LOG_DIR)
    if not has_match_logs:
        print("WARNING: match_log/ not found - Tier B fields (last_result/opponent/"
              "score, calendar-year record, form5/form10) will all be blank/None. "
              "Run the latest run_ratings.py first (match_log/ is a new output).")

    history_files = glob.glob(os.path.join(HISTORY_DIR, "*.json"))
    print(f"Reading {len(history_files)} club history files...")

    parsed = []
    for path in history_files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data["dates"]:
            parsed.append(data)

    # NOTE: dates are compared as parsed datetime objects, NOT as raw
    # strings - "9/8/2025" sorts AFTER "8/6/2026" lexicographically
    # (since "9" > "8" character-by-character) despite being chronologically
    # ~11 months EARLIER. A naive max() on the raw strings picks the wrong
    # "latest" date and silently excludes almost every genuinely current
    # club as if it were stale.
    latest_date = max(
        (rec["dates"][-1] for rec in parsed),
        key=lambda d: datetime.strptime(d, "%m/%d/%Y"),
    )
    current_year = datetime.strptime(latest_date, "%m/%d/%Y").year
    print(f"Latest snapshot date across the dataset: {latest_date} "
          f"(calendar-year fields use {current_year} as 'current')")

    rankings = {}
    stale_count = 0
    missing_metadata_count = 0

    for data in parsed:
        if data["dates"][-1] != latest_date:
            stale_count += 1
            continue

        team_id = data["team_id"]
        dates, e, r = data["dates"], data["e"], data["r"]

        meta = club_metadata.get(team_id)
        if meta is None:
            missing_metadata_count += 1
            meta = {"name": f"(unknown, team_id={team_id})", "country": None,
                     "league_code": None, "season": None}

        rank = r[-1]
        elo = e[-1]
        if len(r) >= 2:
            prev_rank = r[-2]
            rank_change = prev_rank - rank  # positive = improved (moved toward rank 1)
            elo_change = round(e[-1] - e[-2], 2)
        else:
            prev_rank = None
            rank_change = None
            elo_change = None

        high_rank_i = min(range(len(r)), key=lambda i: r[i])
        low_rank_i = max(range(len(r)), key=lambda i: r[i])
        high_elo_i = max(range(len(e)), key=lambda i: e[i])
        low_elo_i = min(range(len(e)), key=lambda i: e[i])

        tier_counts = [sum(1 for x in r if x <= t) for t in TIER_COUNT_THRESHOLDS]

        league_label = None
        if meta["season"] is not None and meta["country"] is not None:
            league_label = format_season_label(meta["season"], meta["country"], confederation_mapping)

        match_log = []
        if has_match_logs:
            match_log_path = os.path.join(MATCH_LOG_DIR, f"{team_id.replace(':', '-')}.json")
            if os.path.exists(match_log_path):
                with open(match_log_path, encoding="utf-8") as f:
                    match_log = json.load(f)["matches"]
        tier_b = compute_tier_b_fields(match_log, current_year)

        rankings[team_id] = {
            "team_id": team_id,
            "rank": rank,
            "prev_rank": prev_rank,
            "rank_change": rank_change,
            "club": meta["name"],
            "league_code": meta["league_code"],
            "country": meta["country"],
            "league": league_label,
            "elo": round(elo, 1),
            "elo_change": elo_change,
            "all_time_high_elo": round(e[high_elo_i], 1),
            "all_time_high_elo_date": dates[high_elo_i],
            "all_time_low_elo": round(e[low_elo_i], 1),
            "all_time_low_elo_date": dates[low_elo_i],
            "all_time_high_rank": r[high_rank_i],
            "all_time_high_rank_date": dates[high_rank_i],
            "all_time_low_rank": r[low_rank_i],
            "all_time_low_rank_date": dates[low_rank_i],
            "times_no1": tier_counts[0],
            "top5": tier_counts[1],
            "top10": tier_counts[2],
            "top50": tier_counts[4],
            "tier_counts": tier_counts,
            **tier_b,
        }

    print(f"\n{stale_count} club(s) excluded - no longer part of the tracked universe as of "
          f"{latest_date} (their history stopped earlier).")
    if missing_metadata_count:
        print(f"WARNING: {missing_metadata_count} club(s) had a history file but no "
              f"club_metadata.json entry - shouldn't normally happen, worth checking.")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rankings, f, separators=(",", ":"))
    print(f"\nWrote rankings.json - {len(rankings)} currently-tracked clubs")


if __name__ == "__main__":
    main()

