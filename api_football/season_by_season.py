"""
season_by_season.py

Computes league points won per season from a club's match_log entries,
for the "Points Won - Season by Season" club-page chart.

Deliberately LEAGUE matches only (competition_type == "league") - this
chart is specifically about league campaigns, matching the reference
design (each row shows a league-tier badge). Cup results are excluded
here (they still feed Last 12 Months / Recent Form elsewhere, which are
correctly all-competitions).

Points shown as a PERCENTAGE of possible points (pts / (gp*3)), not a raw
total - a 34-game season and a 38-game season aren't otherwise comparable
on the same bar chart. League name/tier badge and season display format
("2022-23" vs "2026") come from leagues_config.json via league_lookup.py.
"""

from league_lookup import load_league_lookup, format_season_display

_LEAGUE_LOOKUP = None


def get_league_lookup():
    global _LEAGUE_LOOKUP
    if _LEAGUE_LOOKUP is None:
        _LEAGUE_LOOKUP = load_league_lookup()
    return _LEAGUE_LOOKUP


def compute_season_by_season(matches: list[dict], max_seasons: int = 5) -> list[dict]:
    """
    Returns up to `max_seasons` most-recent seasons, most recent first:
    [{"season": "2025", "season_display": "2025-26", "league_id": "428",
      "league_name": "Serie D - Girone C", "tier": 4,
      "pts": 55, "pts_pct": 50.9, "w": 14, "d": 13, "l": 9, "gp": 36}, ...]
    Only competition_type == "league" matches are counted.
    A club that changed league_id mid-season (promotion/relegation playoffs,
    restructuring) will have its season's matches split across two rows,
    not silently merged - merging two different tiers' points into one row
    would misrepresent the badge.
    """
    league_matches = [m for m in matches if m.get("competition_type") == "league"]
    if not league_matches:
        return []

    lookup = get_league_lookup()

    groups: dict[tuple, list] = {}
    for m in league_matches:
        key = (m.get("season"), m.get("league_id"))
        groups.setdefault(key, []).append(m)

    rows = []
    for (season, league_id), ms in groups.items():
        w = sum(1 for m in ms if m["result"] == "W")
        d = sum(1 for m in ms if m["result"] == "D")
        l = sum(1 for m in ms if m["result"] == "L")
        gp = w + d + l
        pts = w * 3 + d
        pts_pct = round(100 * pts / (gp * 3), 1) if gp else 0.0

        league_info = lookup.get(league_id, {})
        country = league_info.get("country")

        rows.append({
            "season": season,
            "season_display": format_season_display(season, country),
            "league_id": league_id,
            "league_name": league_info.get("name", f"League {league_id}"),
            "tier": league_info.get("tier"),
            "pts": pts, "pts_pct": pts_pct,
            "w": w, "d": d, "l": l, "gp": gp,
        })

    rows.sort(key=lambda r: (r["season"] or ""), reverse=True)
    return rows[:max_seasons]


if __name__ == "__main__":
    import json, sys
    for path in sys.argv[1:]:
        with open(path) as f:
            data = json.load(f)
        result = compute_season_by_season(data["matches"])
        print(f"{path} (team_id={data['team_id']}):")
        print(json.dumps(result, indent=2))
