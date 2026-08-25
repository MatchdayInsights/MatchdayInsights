"""
club_history.py

Standalone tool - traces how a single club's rank and elo evolved
across its full recorded history, using history/{team_id}.json output
from run_ratings.py. Look the club up by team_id or by name (partial,
case-insensitive match against names scraped from fixture data, same
approach as preview_rankings.py).

Usage:
    python club_history.py --name Zenit
    python club_history.py --team_id 47
    python club_history.py --name Bayern --monthly       # one row per month (default)
    python club_history.py --name Bayern --full           # every snapshot, not condensed
    python club_history.py --name Bayern --chart           # also save a PNG chart, if matplotlib is installed
"""

import argparse
import csv
import glob
import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
FIXTURES_GLOB = os.path.join(SCRIPT_DIR, "data", "fixtures", "*.csv")


def build_team_name_and_country_lookup() -> dict:
    """Same domestic-first, World-fallback approach as preview_rankings.py.
    team_country_overrides.json is applied LAST and always wins, exactly
    matching the real pipeline's behavior (run_ratings.py's
    build_team_country_lookup) - without this, a fix Greg makes via
    overrides would correctly take effect in the real rankings.json/
    history/ output but silently NOT show up in these preview tools,
    which is exactly the kind of "did my fix actually work?" confusion
    this is meant to prevent."""
    lookup = {}
    csv_paths = glob.glob(FIXTURES_GLOB)

    def scan(paths, skip_world):
        for path in paths:
            base = os.path.basename(path)
            country_guess = base.split("_")[0]
            if skip_world and country_guess == "World":
                continue
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    for side in ("home", "away"):
                        tid = row.get(f"{side}_team_id")
                        name = row.get(f"{side}_team")
                        if tid and name and str(tid) not in lookup:
                            lookup[str(tid)] = (name, country_guess)

    scan(csv_paths, skip_world=True)
    scan(csv_paths, skip_world=False)

    overrides_path = os.path.join(SCRIPT_DIR, "team_country_overrides.json")
    if os.path.exists(overrides_path):
        with open(overrides_path, encoding="utf-8") as f:
            overrides = json.load(f)
        for tid, country in overrides.items():
            name = lookup.get(tid, (f"(unknown, team_id={tid})", None))[0]
            lookup[tid] = (name, country)

    return lookup


def find_team_id_by_name(name_query: str, name_lookup: dict) -> list[tuple[str, str, str]]:
    """Returns [(team_id, name, country), ...] for every case-insensitive substring match."""
    q = name_query.lower()
    matches = []
    for tid, (name, country) in name_lookup.items():
        if q in name.lower():
            matches.append((tid, name, country))
    return matches


def load_history(team_id: str) -> dict:
    path = os.path.join(HISTORY_DIR, f"{team_id.replace(':', '-')}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def condense_monthly(dates: list, e: list, r: list) -> list[tuple]:
    """One row per calendar month - the LAST snapshot within that month."""
    rows = []
    last_month = None
    for i in range(len(dates)):
        month = dates[i].split("/")[0] + "/" + dates[i].split("/")[2]  # "M/YYYY"
        if month != last_month:
            rows.append([dates[i], e[i], r[i]])
            last_month = month
        else:
            rows[-1] = [dates[i], e[i], r[i]]  # overwrite with the latest snapshot seen this month
    return [tuple(row) for row in rows]


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", type=str, help="Club name (partial match, case-insensitive)")
    group.add_argument("--team_id", type=str, help="Exact team_id")
    parser.add_argument("--full", action="store_true", help="Show every snapshot instead of one per month")
    parser.add_argument("--chart", action="store_true", help="Also save a PNG chart (requires matplotlib)")
    args = parser.parse_args()

    if not os.path.isdir(HISTORY_DIR):
        print(f"No history/ directory found at {HISTORY_DIR} - run run_ratings.py first.")
        return

    print("Building team_id -> name lookup from fixture data...")
    name_lookup = build_team_name_and_country_lookup()

    if args.team_id:
        team_id = args.team_id
        name, country = name_lookup.get(team_id, (f"(unknown name, team_id={team_id})", "?"))
    else:
        matches = find_team_id_by_name(args.name, name_lookup)
        if not matches:
            print(f"No club name containing '{args.name}' found in fixture data.")
            return
        if len(matches) > 1:
            print(f"{len(matches)} clubs match '{args.name}' - be more specific, or use --team_id:")
            for tid, name, country in sorted(matches, key=lambda x: x[1]):
                print(f"  team_id={tid:<8} {name} ({country})")
            return
        team_id, name, country = matches[0]

    data = load_history(team_id)
    if data is None:
        print(f"'{name}' (team_id={team_id}) has no history/ file - it may not be a "
              f"genuinely tracked club (club_is_tracked=False), or hasn't been seeded yet.")
        return

    dates, e, r = data["dates"], data["e"], data["r"]
    if not dates:
        print(f"'{name}' (team_id={team_id}) has an empty history file.")
        return

    # Summary stats
    best_rank_i = min(range(len(r)), key=lambda i: r[i])
    worst_rank_i = max(range(len(r)), key=lambda i: r[i])
    high_elo_i = max(range(len(e)), key=lambda i: e[i])
    low_elo_i = min(range(len(e)), key=lambda i: e[i])

    print(f"\n=== {name} ({country}) - team_id={team_id} ===")
    print(f"Tracked from {dates[0]} to {dates[-1]}  ({len(dates)} snapshots)")
    print(f"Current:        rank {r[-1]:>5}   elo {e[-1]:>8.1f}   (as of {dates[-1]})")
    print(f"All-time high rank: {r[best_rank_i]:>5}   (on {dates[best_rank_i]})")
    print(f"All-time low rank:  {r[worst_rank_i]:>5}   (on {dates[worst_rank_i]})")
    print(f"All-time high elo:  {e[high_elo_i]:>8.1f}   (on {dates[high_elo_i]})")
    print(f"All-time low elo:   {e[low_elo_i]:>8.1f}   (on {dates[low_elo_i]})")
    print(f"Net change since {dates[0]}: elo {e[-1]-e[0]:+.1f}, rank {r[-1]-r[0]:+d} "
          f"({'improved' if r[-1] < r[0] else 'declined' if r[-1] > r[0] else 'unchanged'})")

    if args.full:
        rows = list(zip(dates, e, r))
        label = "every snapshot"
    else:
        rows = condense_monthly(dates, e, r)
        label = "one point per month (last snapshot that month)"

    print(f"\nTrend ({label}):")
    print(f"{'DATE':<12} {'ELO':>8}  {'RANK':>6}")
    print("-" * 32)
    for d, elo, rank in rows:
        print(f"{d:<12} {elo:>8.1f}  {rank:>6}")

    csv_path = os.path.join(SCRIPT_DIR, f"club_history_{team_id.replace(':', '-')}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "elo", "rank"])
        writer.writerows(zip(dates, e, r))
    print(f"\nWrote full (uncondensed) history to {csv_path}")

    if args.chart:
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from datetime import datetime as dt

            parsed_dates = [dt.strptime(d, "%m/%d/%Y") for d in dates]
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
            ax1.plot(parsed_dates, e, color="tab:green")
            ax1.set_ylabel("Elo")
            ax1.set_title(f"{name} ({country}) - team_id={team_id}")
            ax2.plot(parsed_dates, r, color="tab:blue")
            ax2.set_ylabel("Rank")
            ax2.invert_yaxis()  # lower rank number = better, so show it going "up"
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
            fig.tight_layout()
            png_path = os.path.join(SCRIPT_DIR, f"club_history_{team_id.replace(':', '-')}.png")
            fig.savefig(png_path, dpi=150)
            print(f"Wrote chart to {png_path}")
        except ImportError:
            print("\n--chart requested but matplotlib isn't installed - run "
                  "'pip install matplotlib' if you want the PNG chart, or just "
                  "open the CSV in Excel and chart it there.")


if __name__ == "__main__":
    main()
