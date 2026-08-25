"""
match_log.py

Companion module for run_ratings.py, alongside history_snapshots.py.
Maintains a bounded per-club rolling log of individual match results,
written to match_log/{team_id}.json - the input generate_rankings.py
needs for Tier B fields (last_result/opponent/score, calendar-year
record, form5/form10) that can't be derived from the elo/rank snapshot
history alone, since those only ever needed aggregate rating, not a
log of individual results.

Design:
  - Bounded per club (deque, maxlen=MAX_LOG_LENGTH) rather than the full
    multi-year history - form5/form10 only ever need the last 10, and
    calendar-year stats only need matches since Jan 1 of the current
    year (comfortably under 150 for even a very active club across
    league + cup + continental competitions in one year). Keeps memory
    bounded across ~4,000 tracked clubs without needing the full match
    history in memory for the whole run.
  - Logged independently PER SIDE, gated on exactly the same
    club_is_tracked condition already used for whether that side's
    rating gets updated (update_a/update_b in process_match) - a
    tracked club's cup match against an untracked lower-tier opponent
    is a real result that belongs in ITS OWN log, even though the
    untracked opponent doesn't get a log of its own.
  - "score" is always GF-GA from that specific club's own perspective,
    not literal home-away - matches how a club's own results are
    normally displayed (e.g. a 2-1 away win still reads "2-1" for the
    winning side, not "1-2").
"""

import glob
import json
import os
from collections import deque

MAX_LOG_LENGTH = 150  # comfortably covers both form10 and a full calendar
                       # year's matches for even a very active club


class MatchLogRecorder:
    def __init__(self):
        self.logs: dict[str, deque] = {}

    def record_match(self, team_id: str, opponent_name: str, opponent_team_id: str,
                      match_date, gf: int, ga: int, elo_change: float,
                      season: str = None, league_id: str = None,
                      competition_type: str = None) -> None:
        if gf > ga:
            result = "W"
        elif gf < ga:
            result = "L"
        else:
            result = "D"

        entry = {
            "date": match_date.isoformat(),
            "opponent": opponent_name,
            "opponent_team_id": opponent_team_id,
            "result": result,
            "gf": gf,
            "ga": ga,
            "elo_change": round(elo_change, 2),
            # Added for season-by-season aggregation (e.g. club page charts).
            # Sourced from the fixture's own season/league_id at the call
            # site in run_ratings.py - NOT derived from match_date, since
            # season boundaries vary by competition (Jul-Jun for most UEFA
            # leagues, calendar-year for CONMEBOL and some UEFA countries
            # e.g. Scandinavia) and API-Football's own season label already
            # encodes this correctly per competition.
            "season": season,
            "league_id": league_id,
            "competition_type": competition_type,
        }

        log = self.logs.setdefault(team_id, deque(maxlen=MAX_LOG_LENGTH))
        log.append(entry)

    def write_all(self, output_dir: str) -> int:
        """Clears every pre-existing *.json file in output_dir FIRST -
        see history_snapshots.py's SnapshotRecorder.write_all() for why
        this matters (a logic fix that changes which clubs qualify must
        not leave stale pre-fix files sitting around, silently
        corrupting any downstream consumer that reads everything in the
        directory)."""
        os.makedirs(output_dir, exist_ok=True)
        for existing in glob.glob(os.path.join(output_dir, "*.json")):
            os.remove(existing)
        for team_id, log in self.logs.items():
            safe_id = team_id.replace(":", "-")
            with open(os.path.join(output_dir, f"{safe_id}.json"), "w", encoding="utf-8") as f:
                json.dump({"team_id": team_id, "matches": list(log)}, f, separators=(",", ":"))
        return len(self.logs)
