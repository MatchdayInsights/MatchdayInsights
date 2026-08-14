"""
audit_coverage.py

Two checks against your finished crosswalk.json:

1. DUPLICATES — flags any real team (team_id) selected as the target of
   MORE THAN ONE different old_name. Distinct from a legitimate
   multi-identity LINK (like Reggina), where ONE old_name correctly
   points at TWO team_ids — that's intentional and isn't flagged here.

2. COVERAGE — for every competition in leagues_config.json, lists any
   real team appearing in that competition's pulled data that ISN'T the
   target of any mapping from your existing roster.

   CAVEAT: Cup competitions will show a lot of "missing" teams that are
   NOT real gaps — early rounds are full of lower-tier/amateur opponents
   you never intended to track. Treat League-type results as the ones
   worth real scrutiny.

USAGE:
    python audit_coverage.py
    python audit_coverage.py --leagues-only
"""

import json
import os
import argparse
import glob
import csv
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")
API_NAMES_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")
MASTER_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")

# Coverage only means something for confederations where your EXISTING
# roster has historical data to match against. Any other country will
# trivially show ~100% of its clubs as "missing" -- not a real gap, just
# because there was never anything to match them against in the first
# place. Scoped to UEFA + CONMEBOL by default; pass --all-countries to
# see everything (mostly noise) anyway.
UEFA_COUNTRIES = {
    "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
    "Belgium", "Bosnia", "Bulgaria", "Croatia", "Cyprus", "Czech-Republic",
    "Denmark", "England", "Estonia", "Faroe-Islands", "Finland", "France",
    "Georgia", "Germany", "Gibraltar", "Greece", "Hungary", "Iceland",
    "Ireland", "Israel", "Italy", "Kazakhstan", "Kosovo", "Latvia",
    "Liechtenstein", "Lithuania", "Luxembourg", "Macedonia", "Malta",
    "Moldova", "Montenegro", "Netherlands", "Northern-Ireland", "Norway",
    "Poland", "Portugal", "Romania", "Russia", "San-Marino", "Scotland",
    "Serbia", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland",
    "Turkey", "Ukraine", "Wales",
}
CONMEBOL_COUNTRIES = {
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia",
    "Ecuador", "Paraguay", "Peru", "Uruguay", "Venezuela",
}
TRACKED_CONFEDERATIONS = UEFA_COUNTRIES | CONMEBOL_COUNTRIES


FILENAME_RE = re.compile(r"(\d+)_(\d{4})\.csv$")


def build_league_lookup(config):
    """league_id (int) -> 'Country - Competition Name'"""
    lookup = {}
    for country, comps in config.items():
        for comp in comps:
            lookup[comp["league_id"]] = f"{country} - {comp.get('name', comp['league_id'])}"
    return lookup


def league_label_for_file(filename, lookup):
    m = FILENAME_RE.search(os.path.basename(filename))
    if not m:
        return "Unknown competition"
    league_id = int(m.group(1))
    return lookup.get(league_id, f"Unknown competition (league_id {league_id})")


def build_everything_from_csvs(script_dir, league_lookup, type_lookup):
    """
    ONE combined pass over data/standings/*.csv and data/fixtures/*.csv,
    building everything the coverage check needs at once:
      - api_data: {name: [{"team_id", "leagues", "standings_leagues"}]},
        same shape as api_football_names.json, but always fresh -- no
        separate collect_api_names.py run required first.
      - last_seen: {team_id: most recent PLAYED match date}, for the
        defunct-club filter.
    This replaces what used to be TWO separate full scans of the fixtures
    folder (one in collect_api_names.py, one for the defunct filter) with
    a single pass over each folder.
    """
    teams_by_id = {}  # team_id -> {"names": set, "leagues": set, "standings_leagues": set}
    last_seen = {}

    standings_files = glob.glob(os.path.join(script_dir, "data", "standings", "*.csv"))
    fixtures_files = glob.glob(os.path.join(script_dir, "data", "fixtures", "*.csv"))

    for path in standings_files:
        label = league_label_for_file(path, league_lookup)
        try:
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or "team_id" not in reader.fieldnames:
                    continue
                for row in reader:
                    name = row.get("team", "").strip()
                    tid = row.get("team_id", "").strip()
                    if not (name and tid):
                        continue
                    entry = teams_by_id.setdefault(tid, {"names": set(), "leagues": set(), "standings_leagues": set()})
                    entry["names"].add(name)
                    entry["leagues"].add(label)
                    entry["standings_leagues"].add(label)
        except (IOError, csv.Error):
            continue

    for path in fixtures_files:
        label = league_label_for_file(path, league_lookup)
        m = FILENAME_RE.search(os.path.basename(path))
        comp_league_id = int(m.group(1)) if m else None
        comp_type = type_lookup.get(comp_league_id, "?")
        try:
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or "home_team_id" not in reader.fieldnames:
                    continue
                for row in reader:
                    played = row.get("played", "").strip().lower() in ("true", "1")
                    date_str = row.get("date", "").strip()
                    for side in ("home", "away"):
                        name = row.get(f"{side}_team", "").strip()
                        tid = row.get(f"{side}_team_id", "").strip()
                        if not (name and tid):
                            continue
                        entry = teams_by_id.setdefault(tid, {"names": set(), "leagues": set(), "standings_leagues": set()})
                        entry["names"].add(name)
                        entry["leagues"].add(label)
                        # NOTE: fixtures do NOT add to standings_leagues -- a
                        # club appearing only in a fixture (e.g. a cross-tier
                        # promotion playoff) isn't a genuine standings member.
                        # last_seen is LEAGUE matches only, not Cup -- a club
                        # eliminated from a cup early but still playing in its
                        # league shouldn't look "recently active" from a cup
                        # run, and a club whose league career ended but who
                        # played a late cup tie shouldn't look falsely active.
                        if played and date_str and comp_type == "League":
                            if tid not in last_seen or date_str > last_seen[tid]:
                                last_seen[tid] = date_str
        except (IOError, csv.Error):
            continue

    api_data = {}
    for tid, info in teams_by_id.items():
        for name in info["names"]:
            api_data.setdefault(name, []).append({
                "team_id": tid,
                "leagues": sorted(info["leagues"]),
                "standings_leagues": sorted(info["standings_leagues"]),
            })

    return api_data, last_seen


def build_last_seen_dates_only(script_dir, type_lookup):
    """Lighter-weight version used only in --from-json mode, where api_data
    already came from a pre-built file and we just need last-seen dates.
    Only counts League-type matches, same as the main builder."""
    last_seen = {}
    fixtures_files = glob.glob(os.path.join(script_dir, "data", "fixtures", "*.csv"))
    for path in fixtures_files:
        m = FILENAME_RE.search(os.path.basename(path))
        comp_league_id = int(m.group(1)) if m else None
        comp_type = type_lookup.get(comp_league_id, "?")
        if comp_type != "League":
            continue
        try:
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or "home_team_id" not in reader.fieldnames:
                    continue
                for row in reader:
                    if row.get("played", "").strip().lower() not in ("true", "1"):
                        continue
                    date_str = row.get("date", "").strip()
                    if not date_str:
                        continue
                    for side in ("home", "away"):
                        tid = row.get(f"{side}_team_id", "").strip()
                        if tid and (tid not in last_seen or date_str > last_seen[tid]):
                            last_seen[tid] = date_str
        except (IOError, csv.Error):
            continue
    return last_seen


def get_identity_entries(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [(value, None)]
    if isinstance(value, dict):
        return [(value.get("name"), value.get("team_id"))]
    if isinstance(value, list):
        return [(v.get("name"), v.get("team_id")) for v in value if isinstance(v, dict)]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leagues-only", action="store_true",
                         help="Skip Cup-type competitions in the coverage section.")
    parser.add_argument("--all-countries", action="store_true",
                         help="Show every country, not just UEFA+CONMEBOL (mostly noise -- "
                              "any confederation you haven't historically tracked will show "
                              "~100% of its clubs as 'missing' by definition).")
    parser.add_argument("--min-coverage", type=float, default=0.15,
                         help="Skip competitions where less than this fraction of their current "
                              "teams are already mapped from your roster (default 0.15). This is "
                              "how 'was this competition part of my original tracking' gets "
                              "determined automatically -- a newly-added deep tier (e.g. Portugal "
                              "Campeonato Prio) will have ~0%% pre-existing coverage; a competition "
                              "you were already tracking will have a real chunk already mapped. "
                              "Set to 0 to disable this filter and see everything.")
    parser.add_argument("--uefa-cutoff", type=str, default="2021-01-01",
                         help="UEFA clubs whose LAST played match is before this date, with no "
                              "match since, are excluded from the coverage report -- they'd "
                              "already dropped out before your tracking era started, so a "
                              "'missing' flag for them isn't a real gap. Default 2021-01-01.")
    parser.add_argument("--conmebol-cutoff", type=str, default="2026-01-01",
                         help="Same idea for CONMEBOL, which you started tracking much later. "
                              "Default 2026-01-01.")
    parser.add_argument("--no-defunct-filter", action="store_true",
                         help="Disable the last-played-date filter entirely, showing everything.")
    parser.add_argument("--from-json", action="store_true",
                         help="Use a pre-built api_football_names.json instead of scanning "
                              "data/standings and data/fixtures directly. Slower to set up "
                              "(needs collect_api_names.py run first) but useful if you don't "
                              "have the raw CSV folders available. Default: scan CSVs directly.")
    args = parser.parse_args()

    required = [CROSSWALK_PATH, CONFIG_PATH]
    if args.from_json:
        required.append(API_NAMES_PATH)
    for path in required:
        if not os.path.exists(path):
            print(f"{path} not found.")
            return

    with open(CROSSWALK_PATH, encoding="utf-8") as f:
        crosswalk = json.load(f)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    type_lookup = {}
    if os.path.exists(MASTER_PATH):
        with open(MASTER_PATH, encoding="utf-8") as f:
            master = json.load(f)
        for e in master:
            type_lookup[e["league"]["id"]] = e["league"].get("type", "?")

    last_seen_dates = {}
    if args.from_json:
        with open(API_NAMES_PATH, encoding="utf-8") as f:
            api_data = json.load(f)
        if not args.no_defunct_filter:
            print("(--from-json mode: scanning data/fixtures/ separately for the defunct-club filter...)")
            last_seen_dates = build_last_seen_dates_only(SCRIPT_DIR, type_lookup)
    else:
        league_lookup = build_league_lookup(config)
        print("Scanning data/standings/ and data/fixtures/ directly (single pass)...")
        api_data, last_seen_dates_built = build_everything_from_csvs(SCRIPT_DIR, league_lookup, type_lookup)
        if not args.no_defunct_filter:
            last_seen_dates = last_seen_dates_built
        if not api_data:
            print("(WARNING: no data found under data/standings/ or data/fixtures/ in this folder -- "
                  "make sure you're running this from your api_football folder, or use --from-json "
                  "if you only have api_football_names.json available.)")
            return

    name_to_id = {}
    for name, entries in api_data.items():
        if len(entries) == 1:
            name_to_id[name] = entries[0]["team_id"]

    team_id_to_old_names = {}
    unresolvable_strings = []

    for old_name, value in crosswalk.items():
        for name, team_id in get_identity_entries(value):
            if team_id is None:
                team_id = name_to_id.get(name)
                if team_id is None:
                    unresolvable_strings.append((old_name, name))
                    continue
            team_id_to_old_names.setdefault(team_id, set()).add(old_name)

    duplicates = {tid: names for tid, names in team_id_to_old_names.items() if len(names) > 1}

    print("=" * 70)
    print("DUPLICATE CHECK")
    print("=" * 70)
    if duplicates:
        print(f"{len(duplicates)} team(s) mapped from MORE THAN ONE old_name — review these:\n")
        for tid, names in duplicates.items():
            print(f"  team_id {tid}: claimed by {', '.join(sorted(names))}")
    else:
        print("None found — every real team is claimed by at most one entry in your roster.")

    if unresolvable_strings:
        print(f"\n({len(unresolvable_strings)} entries use a name not found in api_football_names.json — "
              f"likely a manually-typed unverified name. Excluded from both checks below.)")
        for old_name, name in unresolvable_strings[:10]:
            print(f"  {old_name} -> '{name}'")
        if len(unresolvable_strings) > 10:
            print(f"  ... and {len(unresolvable_strings)-10} more")

    selected_team_ids = set(team_id_to_old_names.keys())

    if not args.no_defunct_filter and not last_seen_dates:
        print("(WARNING: no fixtures data found for the last-played-date filter -- "
              "make sure data/fixtures/ is in this folder. Continuing without it.)\n")

    print(f"\n{'='*70}")
    print("COVERAGE CHECK")
    print("=" * 70)
    print("(Cup results show expected noise -- early rounds are full of\n"
          " lower-tier opponents you never intended to track. Focus on\n"
          " League results for real gaps.)\n")

    total_missing = 0
    total_excluded_defunct = 0
    skipped_countries = 0
    skipped_new_tier = 0
    for country, comps in config.items():
        if not args.all_countries and country not in TRACKED_CONFEDERATIONS:
            skipped_countries += 1
            continue

        cutoff = args.uefa_cutoff if country in UEFA_COUNTRIES else args.conmebol_cutoff

        for comp in comps:
            league_id = comp["league_id"]
            comp_type = type_lookup.get(league_id, "?")
            if args.leagues_only and comp_type == "Cup":
                continue

            label = f"{country} - {comp.get('name')}"
            teams_in_comp = {
                (name, entry["team_id"])
                for name, entries in api_data.items()
                for entry in entries
                if label in entry.get("standings_leagues", entry["leagues"])
            }
            if not teams_in_comp:
                continue

            missing_raw = [(name, tid) for name, tid in teams_in_comp if tid not in selected_team_ids]

            missing = []
            for name, tid in missing_raw:
                last_seen = last_seen_dates.get(tid)
                if last_seen and last_seen < cutoff:
                    total_excluded_defunct += 1
                    continue
                missing.append((name, tid))

            covered_count = len(teams_in_comp) - len(missing_raw)
            coverage_ratio = covered_count / len(teams_in_comp)

            if coverage_ratio < args.min_coverage:
                skipped_new_tier += 1
                continue

            if missing:
                total_missing += len(missing)
                print(f"{label} [{comp_type}] — {covered_count}/{len(teams_in_comp)} already mapped, "
                      f"{len(missing)} unmapped team(s):")
                for name, tid in sorted(missing):
                    last_played = last_seen_dates.get(tid)
                    date_note = f" — last league match {last_played}" if last_played else " — no league match found"
                    print(f"  {name}  (team_id {tid}){date_note}")
                print()

    if skipped_countries:
        print(f"(Skipped {skipped_countries} non-UEFA/CONMEBOL countries -- "
              f"pass --all-countries to include them, though expect mostly noise)\n")

    if skipped_new_tier:
        print(f"(Skipped {skipped_new_tier} competition(s) with under {args.min_coverage:.0%} pre-existing "
              f"coverage -- these look like newly-added deep tiers rather than competitions you were "
              f"already tracking. Pass --min-coverage 0 to see everything anyway.)\n")

    if total_excluded_defunct and not args.no_defunct_filter:
        print(f"(Excluded {total_excluded_defunct} club(s) whose last LEAGUE match was before "
              f"{args.uefa_cutoff} [UEFA] / {args.conmebol_cutoff} [CONMEBOL], with nothing since -- "
              f"these had already dropped out before your tracking era, not a real gap. "
              f"Pass --no-defunct-filter to see them anyway.)\n")

    if total_missing == 0:
        print("Nothing found — every team in every already-tracked competition is mapped from your roster.")
    else:
        print(f"Total unmapped across genuinely pre-existing competitions: {total_missing}")


if __name__ == "__main__":
    main()
