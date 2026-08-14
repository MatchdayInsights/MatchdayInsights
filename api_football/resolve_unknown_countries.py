"""
resolve_unknown_countries.py

Reads seeding_failures_report.json (written by run_ratings.py) and, for
every team_id that failed with "country unknown" specifically (never
appeared in any domestic league/cup fixture - only in a continental/
global match, so there's nothing in the pulled data to resolve its
country from), queries API-Football's /teams endpoint directly to get
its real country, and writes the result into team_country_overrides.json
- the same override file run_ratings.py already reads.

Only handles the "country unknown" case. The other two failure reasons
("no country code mapping" and "no League_Starts entry") need a
different kind of fix (adding the country to country_code_mapping.json
or League_Starts_updated.xlsx respectively) - this script prints those
separately so you know they still need manual attention, but doesn't
try to auto-resolve them.

Usage:
    python resolve_unknown_countries.py
"""

import json
import os
import time
import requests

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
if not API_KEY:
    raise SystemExit("Set the API_FOOTBALL_KEY environment variable before running this script.")

BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FAILURES_PATH = os.path.join(SCRIPT_DIR, "seeding_failures_report.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
CACHE_DIR = os.path.join(SCRIPT_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def get_team_country(team_id):
    cache_path = os.path.join(CACHE_DIR, f"team_{team_id}.json")
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        resp = requests.get(f"{BASE}/teams", headers=HEADERS, params={"id": team_id}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        time.sleep(0.3)

    response = data.get("response", [])
    if not response:
        return None
    return response[0]["team"].get("country")


def main():
    with open(FAILURES_PATH, encoding="utf-8") as f:
        failures = json.load(f)

    country_unknown_ids = sorted(set(
        d["team_id"] for d in failures if "country unknown" in d["error"]
    ))
    other_failures = [d for d in failures if "country unknown" not in d["error"]]

    print(f"{len(country_unknown_ids)} unique team_id(s) with unresolvable country - "
          f"looking these up directly via API-Football...")

    # team_id -> {team_name, competition_name} for display purposes, pulled
    # from the FIRST failure record seen for each team_id
    context_by_id = {}
    for d in failures:
        if d["team_id"] not in context_by_id and "country unknown" in d["error"]:
            context_by_id[d["team_id"]] = {
                "team_name": d.get("team_name", "?"),
                "competition_name": d.get("competition_name", "?"),
            }

    overrides = {}
    if os.path.exists(OVERRIDES_PATH):
        with open(OVERRIDES_PATH, encoding="utf-8") as f:
            overrides = json.load(f)

    resolved, unresolved = 0, []
    for i, team_id in enumerate(country_unknown_ids, 1):
        ctx = context_by_id.get(team_id, {})
        label = f"{ctx.get('team_name', '?')!r} (team_id={team_id}, seen in {ctx.get('competition_name', '?')})"
        print(f"  [{i}/{len(country_unknown_ids)}] {label}")
        country = get_team_country(team_id)
        if country:
            overrides[str(team_id)] = country
            resolved += 1
            print(f"      -> resolved to {country!r}")
        else:
            unresolved.append((team_id, ctx.get("team_name", "?")))
            print(f"      -> no team data returned by API, could not resolve")

    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(overrides, f, indent=2, sort_keys=True)

    print(f"\nResolved {resolved} team_id(s) into {OVERRIDES_PATH}")
    if unresolved:
        print(f"{len(unresolved)} team_id(s) had no team data returned by the API at all - "
              f"genuinely unresolvable this way, needs manual investigation:")
        for team_id, name in unresolved:
            print(f"    team_id={team_id} ({name!r})")

    if other_failures:
        by_reason = {}
        for d in other_failures:
            key = "no country code mapping" if "no country code mapping" in d["error"] else \
                  "no League_Starts entry" if "no League_Starts entry" in d["error"] else "other"
            by_reason.setdefault(key, {})[d["team_id"]] = d.get("team_name", "?")
        print(f"\n{len(other_failures)} other failure(s) NOT handled by this script "
              f"(different fix needed):")
        for reason, teams in by_reason.items():
            print(f"  {reason}: {len(teams)} unique team_id(s)")
            for team_id, name in teams.items():
                print(f"    team_id={team_id} ({name!r})")


if __name__ == "__main__":
    main()
