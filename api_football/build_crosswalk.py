"""
build_crosswalk.py

Matches your existing club names (existing_club_names.json) against
API-Football's actual teams (api_football_names.json — now tracked by
team_id, not just name, so two different real clubs sharing an identical
name — e.g. San Marino's "AC Libertas" vs an unrelated Croatian club also
called "Libertas" — are never silently merged into one entry).

Logic:
  - Exact match (case-insensitive) auto-resolves with NO prompt — UNLESS
    that name is shared by more than one real team, in which case it's
    routed to manual review instead of guessing which one you mean.
  - Everything else gets ranked fuzzy-match suggestions. If a matched name
    is shared by multiple real teams, each one shows as its own separate,
    correctly-labeled line — never merged into one confusing entry.
  - "/keyword" searches names by substring. "@country" filters candidates
    (and search) to a specific country's league label — also doubles as
    the fix for same-name-different-country clubs: filter to the country
    you know it's actually in, and the wrong one disappears.
  - Names with only ONE real team behind them are stored as a plain
    string in crosswalk.json (unchanged from before — fully backward
    compatible with anything you've already decided). Names shared by
    MULTIPLE teams are stored as {"name":..., "team_id":...} once you
    pick a specific one, so it's unambiguous downstream.
  - Saves after every decision. Resumable. Prints a full report at the
    end listing every unresolved club by name, plus a cumulative view
    across all sessions.

REQUIRES: pip install rapidfuzz
REQUIRES: api_football_names.json built by the team-ID-aware version of
          collect_api_names.py (re-run it if yours predates this).

USAGE:
    python build_crosswalk.py
"""

import json
import os
from rapidfuzz import process, fuzz

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXISTING_PATH = os.path.join(SCRIPT_DIR, "existing_club_names.json")
API_NAMES_PATH = os.path.join(SCRIPT_DIR, "api_football_names.json")
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "crosswalk.json")

NUM_SUGGESTIONS = 6


def load_json(path, label):
    if not os.path.exists(path):
        print(f"{path} not found. Run {label} first.")
        raise SystemExit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_crosswalk():
    if os.path.exists(CROSSWALK_PATH):
        with open(CROSSWALK_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_crosswalk(crosswalk):
    with open(CROSSWALK_PATH, "w", encoding="utf-8") as f:
        json.dump(crosswalk, f, indent=2, ensure_ascii=False, sort_keys=True)


def expand_to_options(name_items, api_data, country_filter=None):
    """
    name_items: list of (name, score) tuples (from fuzzy match) or plain
    name strings (from search — no score).
    Returns a flat list of option dicts: {name, team_id, leagues, score}
    — one per DISTINCT real team, even if several share a name.
    """
    options = []
    for item in name_items:
        if isinstance(item, tuple):
            name, score = item[0], item[1]
        else:
            name, score = item, None
        for entry in api_data.get(name, []):
            if country_filter:
                if not any(country_filter.lower() in lg.lower() for lg in entry["leagues"]):
                    continue
            options.append({
                "name": name,
                "team_id": entry["team_id"],
                "leagues": entry["leagues"],
                "score": score,
            })
    return options


def print_options(options):
    for j, opt in enumerate(options, 1):
        score_str = f"({opt['score']:.0f}% match)  " if opt["score"] is not None else ""
        leagues = opt["leagues"]
        league_str = ", ".join(leagues[:2])
        if len(leagues) > 2:
            league_str += f" (+{len(leagues)-2} more)"
        print(f"  [{j}] {opt['name']}  {score_str}— {league_str}")


def search_names(keyword, names):
    keyword = keyword.lower()
    return [n for n in names if keyword in n.lower()]


def resolve_value(name, team_id, api_data):
    """Plain string if this name is globally unambiguous; disambiguated
    object if it's shared by more than one real team — regardless of
    whether a filter narrowed today's VISIBLE list to just one, since the
    name itself is still ambiguous to anyone reading crosswalk.json later
    without that context."""
    entries = api_data.get(name, [])
    if len(entries) <= 1:
        return name
    return {"name": name, "team_id": team_id}


def main():
    existing = load_json(EXISTING_PATH, "collect_existing_names.py")
    api_data = load_json(API_NAMES_PATH, "collect_api_names.py")  # {name: [{team_id, leagues}]}
    api_names = list(api_data.keys())
    api_names_lower = {n.lower(): n for n in api_names}
    crosswalk = load_crosswalk()

    auto_matched = 0
    already_done = 0
    resolved_this_session = 0
    ambiguous_exact_deferred = 0

    kept_unmatched_this_session = []
    skipped_this_session = []

    to_review = []

    for old_name in existing:
        if old_name in crosswalk:
            already_done += 1
            continue

        exact_name = api_names_lower.get(old_name.strip().lower())
        if exact_name:
            entries = api_data.get(exact_name, [])
            if len(entries) == 1:
                crosswalk[old_name] = exact_name
                auto_matched += 1
                continue
            else:
                # Exact name match, but shared by multiple real teams —
                # do NOT silently guess. Goes to manual review, where the
                # fuzzy match will naturally rank it ~100% and show all
                # the real candidates separately.
                ambiguous_exact_deferred += 1

        to_review.append(old_name)

    save_crosswalk(crosswalk)

    print(f"Total existing clubs: {len(existing)}")
    print(f"  Already decided (previous session): {already_done}")
    print(f"  Auto-matched (exact match, unambiguous, no prompt needed): {auto_matched}")
    if ambiguous_exact_deferred:
        print(f"  Exact name match but shared by multiple teams (deferred to review): {ambiguous_exact_deferred}")
    print(f"  Need review: {len(to_review)}")
    print()

    if not to_review:
        print("Nothing left to review.")
    else:
        input(f"Press Enter to start reviewing {len(to_review)} unmatched club(s) one at a time "
              f"(Ctrl+C any time to stop — progress is saved after every decision)...")

        for i, old_name in enumerate(to_review, 1):
            name_score_pairs = process.extract(
                old_name, api_names, scorer=fuzz.WRatio, limit=NUM_SUGGESTIONS
            )
            name_score_pairs = [(n, s) for n, s, _ in name_score_pairs]
            current_options = expand_to_options(name_score_pairs, api_data)

            print(f"\n[{i}/{len(to_review)}] '{old_name}'")
            print_options(current_options)

            resolved = False
            active_filter = None

            while not resolved:
                filter_note = f"  [filtered to: {active_filter}]" if active_filter else ""
                choice = input(
                    f"  Pick a number, type a name manually, '/keyword' to search, "
                    f"'@country' to filter by country, 'k' to keep as unmatched, "
                    f"or Enter to skip for now{filter_note}: "
                ).strip()

                if not choice:
                    skipped_this_session.append(old_name)
                    resolved = True

                elif choice.lower() == "k":
                    crosswalk[old_name] = None
                    kept_unmatched_this_session.append(old_name)
                    resolved_this_session += 1
                    resolved = True

                elif choice.startswith("@"):
                    country_kw = choice[1:].strip()
                    if not country_kw:
                        active_filter = None
                        current_options = expand_to_options(name_score_pairs, api_data)
                        print("    Filter cleared — showing original candidates again.")
                        print_options(current_options)
                    else:
                        active_filter = country_kw
                        # Search the FULL database for this country, not just
                        # whatever survived the original narrow fuzzy match —
                        # the real answer might not have been in that top-6 at all.
                        country_pool = [
                            name for name, entries in api_data.items()
                            if any(country_kw.lower() in lg.lower() for e in entries for lg in e["leagues"])
                        ]
                        if not country_pool:
                            print(f"    No teams found with a league label containing '{country_kw}'.")
                        elif len(country_pool) <= 20:
                            # Small enough to just show everything, alphabetically —
                            # this is exactly the case for smaller nations (San Marino,
                            # Andorra, etc.) where you want to see the whole roster.
                            current_options = expand_to_options(
                                sorted(country_pool), api_data, country_filter=country_kw
                            )
                            print(f"    {len(country_pool)} team(s) found in '{country_kw}' — showing all:")
                            print_options(current_options)
                        else:
                            # Too many to dump in full — fuzzy-rank within the
                            # complete country pool (not the original candidates)
                            # so the best matches surface even if they weren't in
                            # the original top-6 at all.
                            country_matches = process.extract(
                                old_name, country_pool, scorer=fuzz.WRatio, limit=NUM_SUGGESTIONS
                            )
                            country_matches = [(n, s) for n, s, _ in country_matches]
                            current_options = expand_to_options(country_matches, api_data, country_filter=country_kw)
                            print(f"    {len(country_pool)} team(s) found in '{country_kw}' — "
                                  f"showing best {len(current_options)} matches (use '/keyword' to search all of them by name):")
                            print_options(current_options)

                elif choice.startswith("/"):
                    keyword = choice[1:].strip()
                    results = search_names(keyword, api_names)
                    if not results:
                        scope = f" within the '{active_filter}' filter" if active_filter else ""
                        print(f"    No names contain '{keyword}'{scope}. Try another search, or '@' to clear the filter.")
                    else:
                        current_options = expand_to_options(results[:20], api_data, country_filter=active_filter)
                        if not current_options:
                            print(f"    {len(results)} name(s) matched '{keyword}', but none within the '{active_filter}' filter. Try '@' to clear it.")
                        else:
                            print(f"    {len(current_options)} option(s) for '{keyword}':")
                            print_options(current_options)
                        if len(results) > 20:
                            print(f"    (capped at 20 name matches — refine your search to narrow further)")

                elif choice.isdigit() and 1 <= int(choice) <= len(current_options):
                    picked = current_options[int(choice) - 1]
                    crosswalk[old_name] = resolve_value(picked["name"], picked["team_id"], api_data)
                    resolved_this_session += 1
                    resolved = True

                else:
                    exact = api_names_lower.get(choice.lower())
                    if exact:
                        entries = api_data.get(exact, [])
                        if len(entries) == 1:
                            crosswalk[old_name] = exact
                            resolved_this_session += 1
                            resolved = True
                        else:
                            # Typed a name that's ambiguous -- ask which specific team
                            print(f"    '{exact}' matches {len(entries)} different real teams — which one?")
                            sub_options = expand_to_options([exact], api_data)
                            print_options(sub_options)
                            sub_choice = input("    Pick a number, or Enter to cancel: ").strip()
                            if sub_choice.isdigit() and 1 <= int(sub_choice) <= len(sub_options):
                                picked = sub_options[int(sub_choice) - 1]
                                crosswalk[old_name] = resolve_value(picked["name"], picked["team_id"], api_data)
                                resolved_this_session += 1
                                resolved = True
                            # else loop back, re-prompt for this same club
                    else:
                        confirm = input(
                            f"    '{choice}' doesn't exactly match any name in api_football_names.json. "
                            f"Use it anyway? (y/n): "
                        ).strip().lower()
                        if confirm == "y":
                            crosswalk[old_name] = choice
                            resolved_this_session += 1
                            resolved = True

                if resolved:
                    save_crosswalk(crosswalk)

    # ── Full end-of-session report ──────────────────────────────────────
    print(f"\n{'='*70}")
    print("SESSION REPORT")
    print(f"{'='*70}")
    print(f"Resolved this session: {resolved_this_session}")

    if kept_unmatched_this_session:
        print(f"\nMarked unmatched ('k') this session — {len(kept_unmatched_this_session)}:")
        for name in kept_unmatched_this_session:
            print(f"  {name}")

    if skipped_this_session:
        print(f"\nSkipped this session (still pending, will show up again next run) — {len(skipped_this_session)}:")
        for name in skipped_this_session:
            print(f"  {name}")

    all_pending = [n for n in existing if n not in crosswalk]
    all_kept_unmatched = [n for n, v in crosswalk.items() if v is None]

    if all_pending:
        print(f"\nTOTAL still pending across all sessions — {len(all_pending)}:")
        for name in all_pending:
            print(f"  {name}")

    if all_kept_unmatched:
        print(f"\nTOTAL marked unmatched across all sessions — {len(all_kept_unmatched)}:")
        for name in all_kept_unmatched:
            print(f"  {name}")

    print(f"\nSaved to {CROSSWALK_PATH}")
    if all_pending:
        print("Re-run this script any time to continue with what's left.")


if __name__ == "__main__":
    main()
