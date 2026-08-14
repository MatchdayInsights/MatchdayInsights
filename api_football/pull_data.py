"""
pull_data.py

Pulls standings + fixtures for every league in leagues_config.json.
Supports multi-season entries ("seasons": [2024, 2025]) — each season costs
2 requests (1 standings + 1 fixtures), cached locally so re-runs don't
waste quota unless you delete cache/.

Fixtures are filtered to HISTORY_START and later before being written to
CSV — a season file may technically start earlier (e.g. Aug 2024), but
only matches on/after the cutoff are kept, per your actual requirement.
Standings are NOT filtered by date (a final/current table isn't a
date-range concept), so every requested season's standings are kept whole.

USAGE:
    Fill in leagues_config.json (see leagues_config.example.json), then:
    python pull_data.py
"""

import requests
import json
import os
import time
from datetime import date, datetime

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
if not API_KEY:
    raise SystemExit("Set the API_FOOTBALL_KEY environment variable before running this script (do not hardcode it here - your previous key was exposed in this file and should be rotated on API-Football's dashboard).")
BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

HISTORY_START = date(2020, 1, 1)  # widened from 2025-01-01 to catch clubs that dropped off before then.
# Safe to lower globally even though CONMEBOL doesn't need this: this only trims fixtures WITHIN
# whatever seasons are actually listed per competition in leagues_config.json — CONMEBOL's season
# list stays narrow (2024/2025) regardless, so there's nothing extra for this to filter out there.

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
OUT_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "standings"), exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "fixtures"), exist_ok=True)


def api_get(endpoint, params, use_cache=True):
    cache_key = endpoint.strip("/") + "_" + "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    cache_path = os.path.join(CACHE_DIR, cache_key + ".json")

    if use_cache and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params, timeout=30)

    if not resp.ok:
        # Pull the real reason out of the response body, not just the HTTP
        # status — API-Football puts the actual explanation (suspended
        # account, quota exceeded, invalid plan for this league, etc.) in
        # the JSON body, which raise_for_status() alone won't show you.
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        raise requests.exceptions.HTTPError(
            f"{resp.status_code} {resp.reason} — API response: {body}",
            response=resp,
        )

    data = resp.json()

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    remaining = resp.headers.get("x-ratelimit-requests-remaining")
    if remaining:
        print(f"    (requests remaining today: {remaining})")

    time.sleep(0.3)  # stay well under the per-minute rate limit
    return data


def pull_standings(league_id, season):
    data = api_get("standings", {"league": league_id, "season": season})
    if data.get("errors"):
        print(f"    ERROR: {data['errors']}")
        return None
    try:
        # standings is a list of GROUPS, each group a list of team rows —
        # e.g. Argentina's Primera División splits into multiple zones.
        # Grabbing only [0] (the old behavior) silently drops every group
        # after the first — this iterates ALL of them instead.
        groups = data["response"][0]["league"]["standings"]
    except (IndexError, KeyError):
        print("    No standings data returned (season may not have started, or wrong season year)")
        return None

    flat = []
    for group in groups:
        for r in group:
            flat.append({
                "group": r.get("group", ""),
                "rank": r["rank"],
                "team": r["team"]["name"],
                "team_id": r["team"]["id"],
                "played": r["all"]["played"],
                "won": r["all"]["win"],
                "drawn": r["all"]["draw"],
                "lost": r["all"]["lose"],
                "goals_for": r["all"]["goals"]["for"],
                "goals_against": r["all"]["goals"]["against"],
                "goal_diff": r["goalsDiff"],
                "points": r["points"],
                "form": r.get("form"),
            })

    if len(groups) > 1:
        print(f"    (competition has {len(groups)} groups/zones — all included)")

    return flat


def pull_fixtures(league_id, season):
    data = api_get("fixtures", {"league": league_id, "season": season})
    if data.get("errors"):
        print(f"    ERROR: {data['errors']}")
        return None

    flat = []
    skipped_before_cutoff = 0
    for m in data["response"]:
        fixture_date_str = m["fixture"]["date"]  # ISO 8601, e.g. "2025-08-16T15:00:00+00:00"
        try:
            fixture_date = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            fixture_date = None  # keep it rather than silently drop on a parse failure

        if fixture_date is not None and fixture_date < HISTORY_START:
            skipped_before_cutoff += 1
            continue

        flat.append({
            "fixture_id": m["fixture"]["id"],
            "date": fixture_date_str,
            "status": m["fixture"]["status"]["short"],  # e.g. FT, NS (not started), PST
            "round": m.get("league", {}).get("round", ""),  # e.g. "1st Round", "Preliminary Round"
            "home_team": m["teams"]["home"]["name"],
            "home_team_id": m["teams"]["home"]["id"],
            "away_team": m["teams"]["away"]["name"],
            "away_team_id": m["teams"]["away"]["id"],
            "home_score": m["goals"]["home"],
            "away_score": m["goals"]["away"],
            "played": m["fixture"]["status"]["short"] == "FT",
            "venue_id": (m["fixture"].get("venue") or {}).get("id"),
        })

    if skipped_before_cutoff and skipped_before_cutoff == len(data["response"]):
        # Every match in this season was before the cutoff — season file will be
        # empty, which is expected for e.g. the earlier of two seasons pulled to
        # cover a mid-season cutoff date, not a bug.
        pass

    return flat


def main():
    config_path = os.path.join(SCRIPT_DIR, "leagues_config.json")
    if not os.path.exists(config_path):
        print("leagues_config.json not found. Copy leagues_config.example.json and fill it in.")
        return

    with open(config_path, encoding="utf-8") as f:
        leagues = json.load(f)

    import csv

    failures = []

    for country, comps in leagues.items():
        for comp in comps:
            league_id = comp["league_id"]
            name = comp.get("name", league_id)

            # Support both the old single-"season" format and the new
            # multi-"seasons" format (from add_historical_seasons.py), so an
            # un-migrated config still works.
            seasons_list = comp.get("seasons") or [comp["season"]]

            for season in seasons_list:
                print(f"{country} — {name} (league {league_id}, season {season})")

                try:
                    standings = pull_standings(league_id, season)
                    if standings:
                        path = os.path.join(OUT_DIR, "standings", f"{league_id}_{season}.csv")
                        with open(path, "w", newline="", encoding="utf-8-sig") as f:
                            writer = csv.DictWriter(f, fieldnames=standings[0].keys())
                            writer.writeheader()
                            writer.writerows(standings)
                        print(f"    standings: {len(standings)} teams -> {path}")
                except requests.exceptions.HTTPError as e:
                    print(f"    STANDINGS FAILED: {e}")
                    failures.append(f"{country} / {name} (league {league_id}, season {season}) — standings — {e}")

                try:
                    fixtures = pull_fixtures(league_id, season)
                    if fixtures:
                        path = os.path.join(OUT_DIR, "fixtures", f"{league_id}_{season}.csv")
                        with open(path, "w", newline="", encoding="utf-8-sig") as f:
                            writer = csv.DictWriter(f, fieldnames=fixtures[0].keys())
                            writer.writeheader()
                            writer.writerows(fixtures)
                        played = sum(1 for x in fixtures if x["played"])
                        print(f"    fixtures: {len(fixtures)} matches ({played} played, {len(fixtures)-played} upcoming) -> {path}")
                    else:
                        print(f"    fixtures: none on/after {HISTORY_START} for this season")
                except requests.exceptions.HTTPError as e:
                    print(f"    FIXTURES FAILED: {e}")
                    failures.append(f"{country} / {name} (league {league_id}, season {season}) — fixtures — {e}")

    print("\nDone. See data/standings/ and data/fixtures/")

    if failures:
        print(f"\n{len(failures)} failure(s) — see pull_errors.log:")
        for f_msg in failures:
            print(f"  {f_msg}")
        log_path = os.path.join(SCRIPT_DIR, "pull_errors.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(failures))
    else:
        print("No failures.")


if __name__ == "__main__":
    main()
