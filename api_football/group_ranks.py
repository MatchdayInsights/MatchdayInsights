"""
group_ranks.py

Computes each tracked club's rank WITHIN its confederation and WITHIN its
own country, alongside the existing overall global rank. Both are derived
from the same elo ordering already used for the overall rank - a club's
confederation/country rank is just its position within the subset of
tracked clubs sharing that confederation/country, sorted by elo descending.
"""

import json
from pathlib import Path

CONFEDERATION_MAPPING_PATH = Path("/mnt/user-data/uploads/confederation_mapping.json")


def compute_group_ranks(rankings: dict) -> dict:
    """
    rankings: the full rankings.json dict (team_id -> club record, each
    with at least "elo" and "country").

    Returns {team_id: {"confederation": str, "confederation_rank": int,
    "confederation_size": int, "country_rank": int, "country_size": int}}
    """
    with open(CONFEDERATION_MAPPING_PATH) as f:
        confederation_mapping = json.load(f)

    by_confederation = {}
    by_country = {}
    for tid, c in rankings.items():
        country = c.get("country")
        if not country:
            continue
        confed = confederation_mapping.get(country, "Unknown")
        by_confederation.setdefault(confed, []).append(tid)
        by_country.setdefault(country, []).append(tid)

    result = {}
    for confed, tids in by_confederation.items():
        tids.sort(key=lambda t: rankings[t]["elo"], reverse=True)
        for i, tid in enumerate(tids):
            result.setdefault(tid, {})["confederation"] = confed
            result[tid]["confederation_rank"] = i + 1
            result[tid]["confederation_size"] = len(tids)

    for country, tids in by_country.items():
        tids.sort(key=lambda t: rankings[t]["elo"], reverse=True)
        for i, tid in enumerate(tids):
            result.setdefault(tid, {})["country_rank"] = i + 1
            result[tid]["country_size"] = len(tids)

    return result


if __name__ == "__main__":
    with open("/home/claude/rankings_run/rankings.json") as f:
        rankings = json.load(f)
    group_ranks = compute_group_ranks(rankings)
    print("Bayern (157):", group_ranks.get("157"))
