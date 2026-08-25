"""
check_match_count_anomalies.py

Flags clubs playing an anomalous number of DOMESTIC LEAGUE matches
compared to their real peers - same league_id, same season. This is a
much cleaner signal than "total matches across everything" would be,
since:

  - Clubs in the same league_id/season play a fixed, predictable number
    of league matches (a round-robin schedule) - almost always
    identical across every club in that group, or very close to it.
  - Continental competitions and domestic cups are entirely SEPARATE
    league_ids - a club that legitimately played extra continental
    matches is compared only within its own domestic league's group,
    never against those extra matches.
  - Cup/knockout-format competitions are excluded from this check
    entirely (via leagues_config.json's type=="league" classification),
    not just deprioritized - a knockout cup has completely legitimate
    match-count variance (a finalist obviously played more rounds than
    a first-round loser) that would otherwise flood this check with
    false positives having nothing to do with a real data bug.

A club whose LEAGUE match count for a given league_id/season is way
out of line with its own group's peers is the clearest signal of
exactly the bug worth checking for: a team_id shared between two real
clubs (see team_id_splits.json for the existing remediation mechanism),
a double-counted fixture pull, or similar.

NOTE: league_id/season are not columns in the raw fixture CSVs - like
run_ratings.py's load_all_fixtures(), they're derived from the filename
({Country}_{Competition}_{league_id}_{season}.csv).

Usage:
    python check_match_count_anomalies.py
    python check_match_count_anomalies.py --ratio 1.3   # more/less sensitive
"""

import argparse
import csv
import glob
import json
import os
from collections import defaultdict, Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_GLOB = os.path.join(SCRIPT_DIR, "data", "fixtures", "*.csv")
LEAGUES_CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")


def build_league_type_lookup() -> dict:
    """league_id (str) -> "league"/"cup"/etc, from leagues_config.json.
    Needed so this check can restrict itself to genuine domestic
    round-robin LEAGUE competitions only - a knockout-format cup
    competition has completely legitimate match-count variance (a
    finalist obviously played more rounds than a first-round loser),
    which would otherwise flood this check with false positives that
    have nothing to do with a real data bug."""
    if not os.path.exists(LEAGUES_CONFIG_PATH):
        return {}
    with open(LEAGUES_CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    lookup = {}
    for country, competitions in config.items():
        for comp in competitions:
            lookup[str(comp["league_id"])] = comp.get("type")
    return lookup


def group_mode(values: list[int]) -> int:
    """Most common count value in the group - in a real, bug-free single
    round-robin, nearly every club shares almost exactly this count, so
    it's a far more robust baseline than the median, which one-off
    cup-style appearances (a club that shows up only once or twice) can
    drag down badly. Ties broken toward the smaller value, which is the
    more conservative (less likely to under-flag) choice."""
    counts = Counter(values)
    max_freq = max(counts.values())
    candidates = [v for v, freq in counts.items() if freq == max_freq]
    return min(candidates)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratio", type=float, default=1.4,
                         help="Flag a club if its match count exceeds this multiple "
                              "of its group's mode (default 1.4x)")
    parser.add_argument("--min_extra", type=int, default=3,
                         help="AND its match count must also exceed the mode by at "
                              "least this many absolute matches (default 3) - "
                              "avoids flagging small leagues on 1-2 match noise")
    parser.add_argument("--min_group_size", type=int, default=4,
                         help="Skip groups (league_id+season) with fewer than this "
                              "many clubs - too small to have a meaningful mode (default 4)")
    parser.add_argument("--min_matches_for_baseline", type=int, default=3,
                         help="Clubs with fewer matches than this are excluded from "
                              "the group's baseline calculation entirely (default 3) - "
                              "genuine one-off cup-tie opponents shouldn't count toward "
                              "'what's normal for this group', and they're not what "
                              "this check is looking for anyway")
    args = parser.parse_args()

    # (league_id, season) -> team_id -> match count
    group_counts = defaultdict(lambda: defaultdict(int))
    # (league_id, season) -> team_id -> name (for display)
    team_names = {}
    # (league_id, season) -> (country, league_name)
    group_info = {}

    csv_paths = glob.glob(FIXTURES_GLOB)
    print(f"Scanning {len(csv_paths)} fixture files...")

    league_type_lookup = build_league_type_lookup()
    if not league_type_lookup:
        print("WARNING: leagues_config.json not found or empty - cannot tell league "
              "competitions apart from cup/knockout ones, so EVERY competition file "
              "will be checked. Knockout-format cups will likely produce false "
              "positives (a finalist legitimately plays more rounds than a first-round "
              "loser) - results should be treated with real skepticism until this file "
              "is available.")

    skipped_files = 0
    skipped_non_league = 0
    for path in csv_paths:
        # league_id/season/country/league_name are NOT columns in the raw
        # CSV - they're only encoded in the filename, exactly like
        # run_ratings.py's load_all_fixtures() derives them. Filenames are
        # {Country}_{CompetitionName}_{league_id}_{season}.csv - league_id
        # and season are always the LAST TWO underscore-separated tokens.
        filename = os.path.basename(path)
        parts = filename.replace(".csv", "").split("_")
        if len(parts) < 4:
            skipped_files += 1
            continue
        country_guess, league_name = parts[0], parts[1].replace("-", " ")
        league_id, season = parts[-2], parts[-1]
        if not league_id.isdigit():
            skipped_files += 1
            continue

        if league_type_lookup and league_type_lookup.get(league_id) != "league":
            skipped_non_league += 1
            continue

        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Deliberately domestic-league-only: skip anything that isn't
                # a genuine league-type fixture, so cup runs and continental
                # competitions never factor into this specific comparison.
                if row.get("played") != "True":
                    continue

                key = (league_id, season)
                group_info.setdefault(key, (country_guess, league_name))

                home_id = row.get("home_team_id")
                away_id = row.get("away_team_id")
                if home_id:
                    group_counts[key][home_id] += 1
                    team_names[(key, home_id)] = row.get("home_team", f"team_id={home_id}")
                if away_id:
                    group_counts[key][away_id] += 1
                    team_names[(key, away_id)] = row.get("away_team", f"team_id={away_id}")

    if skipped_files:
        print(f"  ({skipped_files} file(s) skipped - filename didn't match the expected "
              f"{{Country}}_{{Competition}}_{{league_id}}_{{season}}.csv pattern)")
    if skipped_non_league:
        print(f"  ({skipped_non_league} cup/knockout/other-type file(s) excluded - "
              f"this check only applies to genuine round-robin LEAGUE competitions)")

    print(f"Checking {len(group_counts)} (league, season) groups for outliers "
          f"(flagging anything over {args.ratio}x the group's mode, AND at least "
          f"{args.min_extra} matches more than the mode)...\n")

    flagged_total = 0
    for key, counts in sorted(group_counts.items()):
        if len(counts) < args.min_group_size:
            continue

        # Baseline is computed ONLY from clubs with a meaningful number of
        # matches - one-off cup-tie opponents (a handful of matches at
        # most) shouldn't drag down what counts as "normal" for this
        # group, and outlier-checking only makes sense among clubs that
        # were genuine, substantial participants in this competition.
        substantial = {tid: c for tid, c in counts.items() if c >= args.min_matches_for_baseline}
        if len(substantial) < args.min_group_size:
            continue
        mode = group_mode(list(substantial.values()))
        if mode == 0:
            continue

        outliers = [
            (tid, c) for tid, c in substantial.items()
            if c > mode * args.ratio and c - mode >= args.min_extra
        ]
        if not outliers:
            continue

        country, league_name = group_info[key]
        league_id, season = key
        print(f"=== {country} / {league_name} (league_id={league_id}, season={season}) "
              f"- group mode: {mode} matches (typical/expected count) ===")
        for tid, count in sorted(outliers, key=lambda x: -x[1]):
            name = team_names.get((key, tid), f"team_id={tid}")
            print(f"  '{name}' (team_id={tid}): {count} matches "
                  f"({count / mode:.1f}x the group mode, +{count - mode} extra)")
            flagged_total += 1
        print()

    if flagged_total == 0:
        print("No anomalies found - every club's domestic league match count is "
              "in line with its peers.")
    else:
        print(f"{flagged_total} outlier(s) flagged total. Each is worth a look with "
              f"investigate_team.py <team_id> - if it turns out to be two real clubs "
              f"sharing an ID, add a rule to team_id_splits.json.")


if __name__ == "__main__":
    main()
