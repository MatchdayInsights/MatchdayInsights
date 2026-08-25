"""
streaks.py

Computes "current active streak" for a club's rank thresholds - how many
CONSECUTIVE most-recent snapshots (in the Mon/Thu update cadence, not
matches) a club has held rank <= threshold, counting backward from the
latest snapshot until the streak breaks. Zero if they're not currently
within that threshold at all.

Deliberately labeled "updates" not "matchdays" - this measures snapshot
history (history/{team_id}.json's chronological rank array), which is a
biweekly cadence, not literal match-by-match data.
"""

TIER_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]


def compute_active_streaks(ranks: list[int], thresholds: list[int] = TIER_THRESHOLDS) -> dict:
    """
    ranks: chronological (oldest -> newest) list of rank-per-snapshot,
           e.g. history["r"] from history/{team_id}.json.
    Returns {threshold: streak_count} - streak_count is 0 if the club's
    MOST RECENT snapshot isn't within that threshold at all.
    """
    if not ranks:
        return {t: 0 for t in thresholds}

    result = {}
    for t in thresholds:
        streak = 0
        for r in reversed(ranks):
            if r <= t:
                streak += 1
            else:
                break
        result[t] = streak
    return result


if __name__ == "__main__":
    import json, sys
    for path in sys.argv[1:]:
        with open(path) as f:
            hist = json.load(f)
        streaks = compute_active_streaks(hist["r"])
        print(f"{path} (team_id={hist['team_id']}):")
        for t, s in streaks.items():
            if s > 0:
                print(f"  Top {t}: {s} consecutive updates (current rank: {hist['r'][-1]})")
