"""
build_config.py

Turns leagues_master.json into leagues_config.json without making you
scan 1,239 entries by hand.

Logic:
  - Leagues and Cups are grouped SEPARATELY within each country. If a
    country has exactly one League-type entry, it's auto-added — no
    prompt, nothing to decide. Same independently for Cups. So a typical
    country with 1 league + 1 cup gets BOTH auto-added with zero prompts.
  - If a country has MULTIPLE entries of the same type (this is where
    "lower tiers of major countries" or "multiple domestic cups" choices
    live), you get prompted once per type, with all options listed
    alphabetically, and can pick one, several (comma-separated), 'a' for
    all, or skip entirely.
  - World/continental competitions (Champions League, Copa Libertadores,
    World Cup, Euros, etc.) are handled once at the end in their own
    section, since they aren't tied to any single real country.
  - Re-running this script SKIPS countries already in leagues_config.json,
    so you can stop partway through and resume later without redoing work.
  - SEASONS: each selected competition gets EVERY season that overlaps
    HISTORY_START (currently 2025-01-01) through today — not just the
    "current" one. For European-style (Aug-May) leagues this usually means
    two season entries (e.g. 2024 AND 2025), since between them they cover
    Jan 2025 onward. Seasons that haven't started yet are excluded
    automatically (this is what caused the Albania 403 earlier — a season
    marked "current" before it had any actual data).

USAGE:
    python build_config.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_PATH = os.path.join(SCRIPT_DIR, "leagues_master.json")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "leagues_config.json")

# CONMEBOL was only added to Matchday Insights in July 2026 — there is no
# "clubs that dropped off before 1/1/2025" problem for it at all, since none
# of its history predates that. Widening it too would just burn extra API
# quota for zero benefit, so --rewiden excludes these by default.
CONMEBOL_COUNTRIES = {
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia",
    "Ecuador", "Paraguay", "Peru", "Uruguay", "Venezuela",
}

# All 55 UEFA member associations — used as a POSITIVE inclusion list for
# --rewiden's default scope. "Not CONMEBOL" alone is NOT the same as
# "European": it silently includes anything else sitting in your config too
# (AFC countries like Uzbekistan/Vietnam auto-added during an early,
# unscoped build_config.py run, for example). Names should match
# API-Football's country.name field — check leagues_master.json if one of
# your countries doesn't get picked up (e.g. "Czech Republic" vs "Czechia").
UEFA_COUNTRIES = {
    "Albania", "Andorra", "Armenia", "Austria", "Azerbaijan", "Belarus",
    "Belgium", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus",
    "Czech Republic", "Denmark", "England", "Estonia", "Faroe Islands",
    "Finland", "France", "Georgia", "Germany", "Gibraltar", "Greece",
    "Hungary", "Iceland", "Israel", "Italy", "Kazakhstan", "Kosovo",
    "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta",
    "Moldova", "Monaco", "Montenegro", "Netherlands", "North Macedonia",
    "Northern Ireland", "Norway", "Poland", "Portugal", "Republic of Ireland",
    "Ireland", "Romania", "Russia", "San Marino", "Scotland", "Serbia",
    "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "Turkey",
    "Ukraine", "Wales",
}


def load_master():
    if not os.path.exists(MASTER_PATH):
        print("leagues_master.json not found. Run fetch_leagues.py first.")
        raise SystemExit(1)
    with open(MASTER_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_existing_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


from datetime import date

HISTORY_START = date(2025, 1, 1)  # pull all seasons overlapping this date through today


def seasons_covering_range(seasons, start_cutoff=None):
    """
    Return the sorted list of season years whose date range overlaps
    [start_cutoff, today]. Handles both season conventions correctly:
      - European-style (Aug-May): "2024" season (Aug 2024-May 2025) AND
        "2025" season (Aug 2025-May 2026) both get included, since between
        them they cover Jan 2025 onward.
      - Calendar-year (Jan-Dec): just "2025" is needed.
    Excludes seasons that haven't started yet (start date in the future) —
    this is what caused the Albania 403 earlier: a season marked "current"
    before it actually kicked off has no data to pull yet.
    """
    if start_cutoff is None:
        start_cutoff = HISTORY_START  # read the CURRENT global, not one baked in at import time
    today = date.today()
    matching = []
    for s in seasons:
        start_str, end_str = s.get("start"), s.get("end")
        try:
            start = date.fromisoformat(start_str) if start_str else None
        except ValueError:
            start = None
        try:
            end = date.fromisoformat(end_str) if end_str else None
        except ValueError:
            end = None

        if start and start > today:
            continue  # hasn't started yet — no data, would 403 like Albania did
        if end and end < start_cutoff:
            continue  # season ended before our history window starts
        matching.append(s["year"])

    return sorted(set(matching))


def make_entry(league_obj):
    league = league_obj["league"]
    seasons = seasons_covering_range(league_obj.get("seasons", []))
    return {"name": league["name"], "league_id": league["id"], "seasons": seasons}


def prompt_for_group(label, options):
    """Show a numbered list and let the user pick one, several, all, or none."""
    options = sorted(options, key=lambda o: o["league"]["name"])
    print(f"\n{label} — {len(options)} option(s) found:")
    for i, opt in enumerate(options, 1):
        seasons = seasons_covering_range(opt.get("seasons", []))
        season_label = ",".join(str(s) for s in seasons) if seasons else "NONE (no data in range)"
        print(f"  [{i}] {opt['league']['name']} (id {opt['league']['id']}, seasons: {season_label})")

    choice = input(
        f"  Pick number(s) comma-separated (e.g. 1 or 1,2), 'a' for all, "
        f"or Enter to skip: "
    ).strip()

    if not choice:
        return []
    if choice.lower() == "a":
        return options
    try:
        idxs = [int(x.strip()) - 1 for x in choice.split(",")]
        return [options[i] for i in idxs if 0 <= i < len(options)]
    except ValueError:
        print("  Couldn't parse that, skipping.")
        return []


def process_group(country_key, options, config, auto_count, prompt_count, type_label):
    """Auto-add if exactly one option, otherwise prompt. Merges into config[country_key]."""
    if len(options) == 1:
        config.setdefault(country_key, [])
        config[country_key].append(make_entry(options[0]))
        return auto_count + 1, prompt_count

    selected = prompt_for_group(f"{country_key} — {type_label}", options)
    if selected:
        config.setdefault(country_key, [])
        config[country_key].extend(make_entry(o) for o in selected)
    return auto_count, prompt_count + 1


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--world", action="store_true",
                         help="Reopen just the World/continental section to add more competitions, without touching anything else.")
    parser.add_argument("--history-start", type=str, default=None,
                         help="Override the history cutoff (YYYY-MM-DD). Affects both new selections "
                              "and --rewiden. Default is the built-in HISTORY_START (2025-01-01).")
    parser.add_argument("--rewiden", action="store_true",
                         help="Re-examine every ALREADY-SELECTED competition using the current "
                              "--history-start and WIDEN its seasons list if more seasons now qualify. "
                              "Never removes seasons, only adds. No prompts — always safe.")
    parser.add_argument("--include-conmebol", action="store_true",
                         help="Widen ALL countries in your config, not just UEFA ones (despite the "
                              "flag name — kept for backward compatibility). Off by default since "
                              "non-UEFA countries (CONMEBOL, or anything else that snuck into your "
                              "config) have no pre-2025 legacy data to backfill in the first place.")
    parser.add_argument("--country", type=str, default=None,
                         help="Reopen ONE country's full League+Cup menu (e.g. --country Germany) to "
                              "add competitions you previously declined — useful after widening the "
                              "history window reveals a previously-'NONE' league now has real data. "
                              "Already-selected competitions are marked and left untouched.")
    args = parser.parse_args()

    global HISTORY_START
    if args.history_start:
        HISTORY_START = date.fromisoformat(args.history_start)
    print(f"Using history cutoff: {HISTORY_START}\n")

    master = load_master()
    config = load_existing_config()

    if args.country:
        country_entries = [
            e for e in master
            if (e["country"].get("name") or "") == args.country
            and e["league"].get("type") in ("League", "Cup")
        ]
        if not country_entries:
            print(f"No League/Cup entries found for '{args.country}' in leagues_master.json "
                  f"(check spelling/capitalization).")
            return

        country_sorted = sorted(country_entries, key=lambda e: e["league"]["name"])
        already_selected_ids = {c["league_id"] for c in config.get(args.country, [])}

        print(f"\n{'='*70}\n{args.country.upper()} — {len(country_sorted)} League/Cup competitions found")
        print("(already-selected ones are marked with *)")
        print(f"{'='*70}")
        for i, opt in enumerate(country_sorted, 1):
            mark = "*" if opt["league"]["id"] in already_selected_ids else " "
            seasons = seasons_covering_range(opt.get("seasons", []))
            season_label = ",".join(str(s) for s in seasons) if seasons else "NONE"
            print(f"{mark} [{i}] {opt['league']['name']} ({opt['league']['type']}, id {opt['league']['id']}, seasons: {season_label})")

        choice = input("\nPick number(s) to ADD (comma-separated), or Enter to cancel: ").strip()
        if not choice:
            print("Nothing added.")
            return
        try:
            idxs = [int(x.strip()) - 1 for x in choice.split(",")]
            new_picks = [country_sorted[i] for i in idxs if 0 <= i < len(country_sorted)]
        except ValueError:
            print("Couldn't parse that — nothing added.")
            return

        existing = config.get(args.country, [])
        added_names = []
        for o in new_picks:
            if o["league"]["id"] in already_selected_ids:
                continue
            existing.append(make_entry(o))
            added_names.append(o["league"]["name"])

        config[args.country] = existing
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        if added_names:
            print(f"\nAdded: {', '.join(added_names)}")
        else:
            print("\nEverything you picked was already selected — nothing added.")
        print(f"Saved to {CONFIG_PATH}")
        return

    if args.rewiden:
        master_by_id = {e["league"]["id"]: e for e in master}
        widened, unchanged, not_found = 0, 0, 0
        skipped_non_uefa = set()

        for country, comps in config.items():
            if not args.include_conmebol and country not in UEFA_COUNTRIES:
                if country != "World":
                    skipped_non_uefa.add(country)
                continue
            for comp in comps:
                master_entry = master_by_id.get(comp["league_id"])
                if not master_entry:
                    not_found += 1
                    continue
                old_seasons = set(comp.get("seasons", []))
                new_seasons = set(seasons_covering_range(master_entry.get("seasons", [])))
                combined = sorted(old_seasons | new_seasons)  # only ever grows, never shrinks
                if set(combined) != old_seasons:
                    print(f"  {country} — {comp.get('name')}: {sorted(old_seasons)} -> {combined}")
                    comp["seasons"] = combined
                    widened += 1
                else:
                    unchanged += 1

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"\nWidened: {widened}")
        print(f"Already covered the full range, no change: {unchanged}")
        if not_found:
            print(f"WARNING: {not_found} entries had a league_id not found in leagues_master.json — left unchanged")
        if skipped_non_uefa:
            print(f"(Skipped {len(skipped_non_uefa)} non-UEFA countries in your config — "
                  f"{', '.join(sorted(skipped_non_uefa))} — pass --include-conmebol to widen "
                  f"everything anyway, though non-UEFA countries shouldn't need this)")
        print(f"Saved to {CONFIG_PATH}")
        return

    world_entries = [e for e in master if (e["country"].get("name") or "") == "World"]

    if args.world:
        if not world_entries:
            print("No World entries found in leagues_master.json.")
            return

        world_sorted = sorted(world_entries, key=lambda e: e["league"]["name"])
        already_selected_ids = {c["league_id"] for c in config.get("World", [])}

        print(f"\n{'='*70}\nWORLD / CONTINENTAL COMPETITIONS — {len(world_sorted)} found")
        print("(already-selected ones are marked with *)")
        print(f"{'='*70}")
        for i, opt in enumerate(world_sorted, 1):
            mark = "*" if opt["league"]["id"] in already_selected_ids else " "
            seasons = seasons_covering_range(opt.get("seasons", []))
            season_label = ",".join(str(s) for s in seasons) if seasons else "NONE"
            print(f"{mark} [{i}] {opt['league']['name']} (id {opt['league']['id']}, seasons: {season_label})")

        choice = input(
            "\nPick number(s) to ADD (comma-separated), or Enter to cancel: "
        ).strip()
        if not choice:
            print("Nothing added.")
            return
        try:
            idxs = [int(x.strip()) - 1 for x in choice.split(",")]
            new_picks = [world_sorted[i] for i in idxs if 0 <= i < len(world_sorted)]
        except ValueError:
            print("Couldn't parse that — nothing added.")
            return

        existing = config.get("World", [])
        added_names = []
        for o in new_picks:
            if o["league"]["id"] in already_selected_ids:
                continue  # already there, don't duplicate
            existing.append(make_entry(o))
            added_names.append(o["league"]["name"])

        config["World"] = existing
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        if added_names:
            print(f"\nAdded: {', '.join(added_names)}")
        else:
            print("\nEverything you picked was already in the config — nothing added.")
        print(f"World now has {len(config['World'])} competition(s) total. Saved to {CONFIG_PATH}")
        return

    # Real countries: split League vs Cup so each type auto-adds/prompts independently
    # (a country with exactly 1 league AND exactly 1 cup should auto-add BOTH, not
    # get lumped into a false "2 options" prompt).
    leagues_by_country = {}
    cups_by_country = {}

    for entry in master:
        country = entry["country"].get("name") or "Unknown"
        etype = entry["league"].get("type")

        if country == "World":
            continue
        elif etype == "League":
            leagues_by_country.setdefault(country, []).append(entry)
        elif etype == "Cup":
            cups_by_country.setdefault(country, []).append(entry)

    countries = sorted(set(leagues_by_country) | set(cups_by_country))
    auto_added = 0
    prompted = 0
    skipped_existing = 0

    print(f"{len(countries)} countries found (domestic leagues + cups).\n")

    for country in countries:
        if country in config:
            skipped_existing += 1
            continue

        if country in leagues_by_country:
            auto_added, prompted = process_group(
                country, leagues_by_country[country], config, auto_added, prompted, "League"
            )
        if country in cups_by_country:
            auto_added, prompted = process_group(
                country, cups_by_country[country], config, auto_added, prompted, "Cup"
            )

        # Save after every country so a mid-session Ctrl+C doesn't lose progress
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    # World / continental competitions — handled once, separately, since they don't
    # belong to any single real country. This list is typically 50-150 entries
    # (Champions League, Europa League, Copa Libertadores, World Cup, Euros, plus
    # qualifiers/youth/women's competitions that also get tagged here) — small
    # enough to scan directly rather than needing per-country iteration.
    if "World" not in config and world_entries:
        world_sorted = sorted(world_entries, key=lambda e: e["league"]["name"])
        print(
            f"\n{'='*70}\n"
            f"WORLD / CONTINENTAL COMPETITIONS — {len(world_sorted)} found\n"
            f"(Champions League, Copa Libertadores, World Cup, Euros, and also\n"
            f"qualifiers/youth/women's competitions that share this bucket)\n"
            f"{'='*70}"
        )
        selected = prompt_for_group("World", world_sorted)
        if selected:
            config["World"] = [make_entry(o) for o in selected]
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\nDone.")
    print(f"  Auto-added (single option): {auto_added}")
    print(f"  Prompted groups:            {prompted}")
    print(f"  Countries already in config, skipped: {skipped_existing}")
    print(f"  Total keys in config now:   {len(config)}")
    print(f"  Saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
