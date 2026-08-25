"""
bracket.py

Parses a continental knockout bracket from a raw fixtures CSV (the same
files run_ratings.py reads from data/fixtures/), using the "round" field.

Two-legged rounds (most knockout rounds except the Final) are represented
as two separate rows - same two teams, home/away swapped. This module
pairs them up and computes an aggregate score per tie.

KNOWN DATA GAP: when a tie is level on aggregate and decided by penalties,
the raw data has no penalty-shootout score anywhere (status shows "PEN" or
"AET", "played" is False, and home_score/away_score reflect normal+extra
time only). For any non-Final round, the winner can still be inferred by
checking which of the two teams appears in the NEXT round's fixtures. For
the Final itself, there's no next round to check - a penalty-decided
Final's winner is genuinely unresolvable from this data alone and is
reported as "TBD (penalties - not in data)".
"""

import csv
import json
from pathlib import Path

FIXTURES_DIR = Path("/home/claude/fixtures_full")
OVERRIDES_PATH = Path("/home/claude/bracket_overrides.json")


def _load_overrides() -> dict:
    if not OVERRIDES_PATH.exists():
        return {}
    with open(OVERRIDES_PATH) as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _override_key(league_id: str, season: str, round_name: str, team_a_id: str, team_b_id: str) -> str:
    a, b = sorted([team_a_id, team_b_id], key=int)
    return f"{league_id}_{season}_{round_name}_{a}_{b}"

# Canonical bracket order, with accepted raw "round" label aliases per
# stage - different competitions/data sources label the same stage
# differently (UEFA says "Round of 16", the Club World Cup data says
# "8th Finals" for the identical stage).
BRACKET_ROUNDS = [
    ("Round of 32", ["Round of 32", "16th Finals"]),
    ("Round of 16", ["Round of 16", "8th Finals"]),
    ("Quarter-finals", ["Quarter-finals", "Quarterfinals"]),
    ("Semi-finals", ["Semi-finals", "Semifinals"]),
    ("Final", ["Final"]),
]


def _find_fixtures_file(country: str, competition_slug_hint: str, league_id: str, season: str) -> Path | None:
    matches = list(FIXTURES_DIR.glob(f"{country}_*_{league_id}_{season}.csv"))
    return matches[0] if matches else None


def load_fixtures_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _reorder_for_tree_layout(bracket: list[dict]) -> list[dict]:
    """
    Reorders each round's ties so the bracket reads as a real tree, not
    just whatever order the source data happened to list matches in.
    Works backward from the Final: for each tie in round N+1, its two
    participants each came from exactly one tie in round N (found by
    team_id membership, not winner_id - this still works correctly even
    when a tie's winner is unresolved, e.g. a penalty shootout with no
    override entry yet, since we only need to know WHICH tie a team
    belongs to, not who won it).

    Not every round-N slot has a round-N-1 parent - e.g. UEFA's "Round of
    32" is actually an 8-tie knockout PLAY-OFF among the lower seeds, not
    a doubling of Round of 16; half of Round of 16 is direct-entry seeds
    with no Round of 32 match at all. Ties with no matched parent are
    left where they are (via the "remaining" append) rather than forcing
    artificial symmetry.
    """
    for i in range(len(bracket) - 1, 0, -1):
        child_round = bracket[i]
        parent_round = bracket[i - 1]

        team_to_parent_tie = {}
        for tie in parent_round["ties"]:
            team_to_parent_tie[tie["team_a_id"]] = tie
            team_to_parent_tie[tie["team_b_id"]] = tie

        new_order = []
        seen = set()
        for child_tie in child_round["ties"]:
            for team_id in (child_tie["team_a_id"], child_tie["team_b_id"]):
                parent_tie = team_to_parent_tie.get(team_id)
                if parent_tie is not None and id(parent_tie) not in seen:
                    new_order.append(parent_tie)
                    seen.add(id(parent_tie))

        remaining = [t for t in parent_round["ties"] if id(t) not in seen]
        parent_round["ties"] = new_order + remaining

    return bracket


def find_continental_competitions_in_fixtures(team_id: str) -> list[dict]:
    """
    Like find_continental_competitions() in league_table.py, but scans
    FIXTURES data instead of standings - these can have different season
    coverage (e.g. fixtures may go back to 2020 for a competition while
    standings were only ever pulled for 2024+), so bracket availability
    shouldn't be limited by whatever standings happen to exist.
    """
    results = []
    for path in FIXTURES_DIR.glob("World_*.csv"):
        rows = load_fixtures_rows(path)
        if any(r["home_team_id"] == team_id or r["away_team_id"] == team_id for r in rows):
            parts = path.stem.split("_")
            season = parts[-1]
            league_id = parts[-2]
            competition_name = " ".join(parts[1:-2]).replace("-", " ")
            results.append({
                "league_id": league_id, "season": season,
                "competition_name": competition_name, "path": path,
            })
    results.sort(key=lambda r: r["season"], reverse=True)
    return results


def build_bracket(rows: list[dict], league_id: str = None, season: str = None) -> list[dict]:
    """
    Returns [{"round": str, "ties": [tie, ...]}, ...] in bracket order,
    only for rounds present in BRACKET_ROUNDS that actually have data.
    "round" in the returned dict is the CANONICAL name (e.g. "Round of
    16"), even if the source data used an alias (e.g. "8th Finals") -
    keeps downstream display consistent across competitions/data sources.

    league_id/season (needed to key manual overrides) aren't in the row
    data itself - the fixtures CSV has no such column - so pass them in
    from the filename (see build_bracket_section in generate_club_page.py
    for how that's parsed).

    Winner resolution order: aggregate score -> next round's participant
    list -> bracket_overrides.json (for penalty shootouts, where neither
    of the above can resolve it - see bracket_overrides.json).

    Each tie: {"team_a": name, "team_a_id": id, "team_b": name,
    "team_b_id": id, "agg_a": int, "agg_b": int, "winner_id": id|None,
    "winner_resolved_via": "aggregate"|"next_round"|"manual_override"|None,
    "legs": [row, row]}
    """
    overrides = _load_overrides()
    # canonical_name -> matching raw rows, only where data actually exists
    present_rounds = []
    rows_by_canonical = {}
    for canonical, aliases in BRACKET_ROUNDS:
        matching = [r for r in rows if r["round"] in aliases]
        if matching:
            present_rounds.append(canonical)
            rows_by_canonical[canonical] = matching

    # participants of each round, used to resolve penalty-decided ties in
    # an EARLIER round by checking who shows up in the round after it
    participants_by_round = {}
    for rnd in present_rounds:
        ids = set()
        for row in rows_by_canonical[rnd]:
            ids.add(row["home_team_id"])
            ids.add(row["away_team_id"])
        participants_by_round[rnd] = ids

    bracket = []
    for idx, rnd in enumerate(present_rounds):
        rnd_rows = rows_by_canonical[rnd]

        # group into ties by unordered team pair
        pairs: dict[frozenset, list] = {}
        for r in rnd_rows:
            key = frozenset({r["home_team_id"], r["away_team_id"]})
            pairs.setdefault(key, []).append(r)

        next_round_participants = (
            participants_by_round[present_rounds[idx + 1]]
            if idx + 1 < len(present_rounds) else None
        )

        ties = []
        for team_pair, legs in pairs.items():
            legs = sorted(legs, key=lambda r: r["date"])
            agg = {}
            names = {}
            for leg in legs:
                h, a = leg["home_team_id"], leg["away_team_id"]
                names[h] = leg["home_team"]
                names[a] = leg["away_team"]
                agg[h] = agg.get(h, 0) + int(leg["home_score"] or 0)
                agg[a] = agg.get(a, 0) + int(leg["away_score"] or 0)

            team_ids = list(team_pair)
            # stable order: whichever was home in the first leg listed first
            if legs[0]["home_team_id"] in team_ids:
                team_ids = [legs[0]["home_team_id"], legs[0]["away_team_id"]]
            a_id, b_id = team_ids
            agg_a, agg_b = agg.get(a_id, 0), agg.get(b_id, 0)

            winner_id, resolved_via = None, None
            if agg_a != agg_b:
                winner_id = a_id if agg_a > agg_b else b_id
                resolved_via = "aggregate"
            elif next_round_participants is not None:
                if a_id in next_round_participants and b_id not in next_round_participants:
                    winner_id, resolved_via = a_id, "next_round"
                elif b_id in next_round_participants and a_id not in next_round_participants:
                    winner_id, resolved_via = b_id, "next_round"

            if winner_id is None and league_id and season:
                key = _override_key(league_id, season, rnd, a_id, b_id)
                if key in overrides:
                    winner_id = overrides[key]["winner_id"]
                    resolved_via = "manual_override"
            # else: unresolvable (e.g. penalty-decided Final with no
            # override entry yet) - stays None

            ties.append({
                "team_a": names[a_id], "team_a_id": a_id,
                "team_b": names[b_id], "team_b_id": b_id,
                "agg_a": agg_a, "agg_b": agg_b,
                "winner_id": winner_id, "winner_resolved_via": resolved_via,
                "legs": legs,
            })

        bracket.append({"round": rnd, "ties": ties})

    return _reorder_for_tree_layout(bracket)


if __name__ == "__main__":
    rows = load_fixtures_rows(FIXTURES_DIR / "World_UEFA-Champions-League_2_2025.csv")
    bracket = build_bracket(rows)
    for rnd in bracket:
        print(f"=== {rnd['round']} ===")
        for t in rnd["ties"]:
            w = t["winner_id"]
            w_name = t["team_a"] if w == t["team_a_id"] else (t["team_b"] if w == t["team_b_id"] else "TBD (penalties - not in data)")
            print(f"  {t['team_a']} {t['agg_a']}-{t['agg_b']} {t['team_b']}  -> winner: {w_name} ({t['winner_resolved_via']})")
