"""
fetch_leagues.py

Pulls the FULL /leagues list from API-Football ONE TIME and saves it to
leagues_master.json. This costs exactly 1 request out of your daily quota,
regardless of how many leagues come back (all 8,549+ entries).

Do NOT call the /leagues endpoint repeatedly with different filters to
"search" — that burns quota for no reason. Call this once, then use
search_leagues.py to filter the saved file locally as many times as you want
for free.

USAGE:
    Set your API key below, then:
    python fetch_leagues.py
"""

import requests
import json
import os

API_KEY = "b3d61bb980d740790b311fc3de4da661"  # <-- paste your real key here
BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")


def main():
    print("Fetching full /leagues list (this uses 1 request)...")
    resp = requests.get(f"{BASE}/leagues", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("errors"):
        print("API returned errors:", data["errors"])
        return

    leagues = data["response"]
    print(f"Got {len(leagues)} league entries.")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(leagues, f, indent=2)

    print(f"Saved to {OUT_PATH}")

    # Show remaining quota from response headers, if present
    remaining = resp.headers.get("x-ratelimit-requests-remaining")
    if remaining:
        print(f"Requests remaining today: {remaining}")


if __name__ == "__main__":
    main()
