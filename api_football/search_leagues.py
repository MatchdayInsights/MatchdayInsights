"""
search_leagues.py

Searches leagues_master.json (created by fetch_leagues.py) locally —
no API calls, no quota used. Use this as many times as you want while
building your league config.

USAGE:
    python search_leagues.py --country Andorra
    python search_leagues.py --country "San Marino" --type League
    python search_leagues.py --name "Serie D"
    python search_leagues.py --country England          # see everything for England
"""

import json
import os
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")


def load_leagues():
    if not os.path.exists(MASTER_PATH):
        print(f"leagues_master.json not found. Run fetch_leagues.py first.")
        raise SystemExit(1)
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", help="Filter by country name (partial match, case-insensitive)")
    parser.add_argument("--name", help="Filter by league/cup name (partial match, case-insensitive)")
    parser.add_argument("--type", choices=["League", "Cup"], help="Filter by competition type")
    parser.add_argument("--current-only", action="store_true",
                         help="Only show leagues with a 'current' active season")
    parser.add_argument("--min-year", type=int,
                         help="Only show leagues with at least one season >= this year (e.g. 2020)")
    args = parser.parse_args()

    leagues = load_leagues()
    results = []

    for entry in leagues:
        league = entry["league"]
        country = entry["country"]
        seasons = entry.get("seasons", [])

        if args.country and args.country.lower() not in (country.get("name") or "").lower():
            continue
        if args.name and args.name.lower() not in (league.get("name") or "").lower():
            continue
        if args.type and league.get("type") != args.type:
            continue
        if args.current_only and not any(s.get("current") for s in seasons):
            continue
        if args.min_year and not any(s["year"] >= args.min_year for s in seasons):
            continue

        current_season = next((s["year"] for s in seasons if s.get("current")), None)
        all_years = sorted(s["year"] for s in seasons) if seasons else []
        if args.min_year:
            all_years = [y for y in all_years if y >= args.min_year]

        results.append({
            "id": league["id"],
            "name": league["name"],
            "type": league.get("type"),
            "country": country.get("name"),
            "current_season": current_season,
            "years_available": f"{all_years[0]}-{all_years[-1]}" if all_years else "none",
        })

    if not results:
        print("No matches.")
        return

    print(f"{len(results)} match(es):\n")
    print(f"{'ID':<8}{'Name':<35}{'Type':<8}{'Country':<20}{'Current':<10}{'Years'}")
    print("-" * 100)
    for r in sorted(results, key=lambda x: (x["country"] or "", x["name"] or "")):
        print(f"{r['id']:<8}{r['name']:<35}{r['type']:<8}{r['country']:<20}{str(r['current_season']):<10}{r['years_available']}")


if __name__ == "__main__":
    main()
