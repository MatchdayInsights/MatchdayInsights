"""
generate_homepage.py

Run this from your api_football folder (same place as run_ratings.py,
generate_rankings.py, etc). Generates index.html and rankings_table.json
from real rankings.json + slug_registry.json + confederation_mapping.json
+ history/ (for the latest update date shown in the hero/nav).

REQUIRED FILES (all relative to this script's location):
  - rankings.json          (from generate_rankings.py)
  - slug_registry.json     (from generate_slug_registry.py)
  - confederation_mapping.json
  - history/                (per-club snapshot files, for the update date)
  - country_codes.py        (flag/country-name lookup, same folder as this script)
  - index_template.html     (the page template with __LATEST_UPDATE_DATE__ token)

Run: python generate_homepage.py
Output: index.html, rankings_table.json (both written to this folder)
"""

import json
from pathlib import Path
from datetime import datetime
import sys

SCRIPT_DIR = Path(__file__).parent
RANKINGS_PATH = SCRIPT_DIR / "rankings.json"
SLUGS_PATH = SCRIPT_DIR / "slug_registry.json"
CONFEDERATION_MAPPING_PATH = SCRIPT_DIR / "confederation_mapping.json"
HISTORY_DIR = SCRIPT_DIR / "history"
TEMPLATE_PATH = SCRIPT_DIR / "index_template.html"
OUT_DIR = SCRIPT_DIR

sys.path.insert(0, str(SCRIPT_DIR))
from country_codes import country_name, COUNTRY_INFO


def get_latest_snapshot_date() -> str:
    latest = None
    for path in HISTORY_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        if not data["dates"]:
            continue
        d = datetime.strptime(data["dates"][-1], "%m/%d/%Y")
        if latest is None or d > latest:
            latest = d
    return latest.strftime("%B %-d, %Y") if latest else "Unknown"


def build_rankings_table():
    with open(RANKINGS_PATH) as f:
        rankings = json.load(f)
    with open(SLUGS_PATH) as f:
        slugs = json.load(f)
    with open(CONFEDERATION_MAPPING_PATH) as f:
        conf_map = json.load(f)

    slug_map = slugs["by_team_id"]
    table = []
    for tid, c in rankings.items():
        slug = slug_map.get(tid, {}).get("slug", tid)
        country = c["country"]
        flag_code = COUNTRY_INFO.get(country, (None, None))[0] if country else None
        table.append({
            "rank": c["rank"], "prev_rank": c["prev_rank"], "rank_change": c["rank_change"],
            "club": c["club"], "league_code": c["league_code"], "country": country,
            "country_name": country_name(country) if country else "",
            "confederation": conf_map.get(country, ""),
            "flag": flag_code,
            "league": c["league"], "elo": c["elo"], "elo_change": c["elo_change"],
            "last_result": c["last_result"], "last_opponent": c["last_opponent"],
            "last_score": c["last_score"], "slug": slug,
        })
    table.sort(key=lambda x: x["rank"])
    return table


def main():
    for required in [RANKINGS_PATH, SLUGS_PATH, CONFEDERATION_MAPPING_PATH, TEMPLATE_PATH]:
        if not required.exists():
            raise SystemExit(f"Missing required file: {required} - run the earlier "
                              f"pipeline steps first (run_ratings.py -> generate_rankings.py "
                              f"-> generate_slug_registry.py) before this script.")
    if not HISTORY_DIR.exists():
        raise SystemExit(f"Missing history/ directory at {HISTORY_DIR}")

    table = build_rankings_table()
    latest_date = get_latest_snapshot_date()

    with open(OUT_DIR / "rankings_table.json", "w") as f:
        json.dump(table, f, separators=(",", ":"))

    with open(TEMPLATE_PATH) as f:
        html = f.read()
    html = html.replace("__LATEST_UPDATE_DATE__", latest_date)

    with open(OUT_DIR / "index.html", "w") as f:
        f.write(html)

    print(f"Wrote rankings_table.json ({len(table)} clubs) and index.html")
    print(f"Latest update date shown on homepage: {latest_date}")


if __name__ == "__main__":
    main()
