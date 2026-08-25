"""
history_snapshots.py

Companion module for run_ratings.py. Replaces the old monolithic
all_history.json approach with self-contained per-club history files,
keyed by team_id, written to a `history/` output directory as
`history/{team_id}.json`.

Design (agreed with Greg):
  - Snapshot dates follow the old site's fixed cadence: every Monday and
    Thursday, alternating +3/+4 day gaps, starting 2021-08-09 (a Monday) -
    the same start date the old public chart history used, even though
    real match processing/burn-in begins earlier (2020-01-01).
  - A snapshot only includes clubs where club_is_tracked[team_id] is True
    AT THAT EXACT MOMENT in the chronological fixture walk. Since
    run_ratings.py only adds a club to club_states once it's genuinely
    seeded (which itself depends on season_inclusion/go-live logic), this
    naturally gives point-in-time-correct rankings with no extra
    go-live cross-checking needed here - a club that doesn't qualify
    for tracking until some future date simply isn't in club_states yet,
    so it's correctly absent from every snapshot before that date.
  - A tracked club with no match in a given window still gets an entry
    for that snapshot (rating carried forward unchanged, rank
    recomputed fresh since other clubs may have moved). A club not yet
    part of the tracked universe gets no entry at all - no null-padding
    needed, since each per-club file is self-contained and can simply
    start wherever that club's real history begins.
  - The final snapshot in a run is a "catch-up to real time" snapshot
    dated as of the last fixture actually processed (not literal
    today, since we can't know state past the last real match pulled),
    UNLESS that date already coincides with a regular scheduled
    snapshot, in which case no duplicate is added.
"""

import datetime
import glob
import json
import os


SNAPSHOT_START_DATE = datetime.date(2021, 8, 9)  # Monday - matches the old
                                                   # site's public chart
                                                   # history start date


def generate_snapshot_dates(start_date: datetime.date, end_date: datetime.date) -> list[datetime.date]:
    """
    Generates the fixed Mon(+4)/Thu(+3) alternating snapshot date sequence,
    starting at start_date (must be a Monday), through end_date inclusive.
    """
    assert start_date.strftime("%A") == "Monday", (
        f"SNAPSHOT_START_DATE must be a Monday, got {start_date} "
        f"({start_date.strftime('%A')})"
    )
    dates = []
    current = start_date
    is_monday = True  # tracks which boundary we're currently on, to know
                       # the next gap: Monday -> Thursday is +3,
                       # Thursday -> Monday is +4
    while current <= end_date:
        dates.append(current)
        current = current + datetime.timedelta(days=3 if is_monday else 4)
        is_monday = not is_monday
    return dates


def safe_history_filename(team_id: str) -> str:
    """
    team_id can include virtual-split suffixes from team_id_splits.json
    (e.g. "5242::sudan"). ':' is filesystem-safe on Linux/Mac but illegal
    in a Windows filename (reserved for drive letters), so it's replaced
    here for the filename only - the JSON payload's own "team_id" field
    still stores the real, original id unchanged.
    """
    return team_id.replace(":", "-")


class SnapshotRecorder:
    """
    Call maybe_snapshot(match_date, club_states, club_is_tracked) BEFORE
    processing each fixture, in chronological order, throughout
    run_ratings.py's main() loop. Call finalize(...) once after the loop
    ends. Call write_all(output_dir) at the very end.
    """

    def __init__(self, snapshot_dates: list[datetime.date]):
        self.snapshot_dates = snapshot_dates
        self._pointer = 0  # index into snapshot_dates of the next
                            # not-yet-captured snapshot
        # team_id -> {"dates": [...], "e": [...], "r": [...]}
        self.histories: dict[str, dict] = {}

    def _take_snapshot(self, snapshot_date: datetime.date, club_states: dict, club_is_tracked: dict) -> None:
        tracked_ids = [tid for tid in club_states if club_is_tracked.get(tid, False)]
        if not tracked_ids:
            return
        # Rank by current rating, descending - highest rating = rank 1
        ranked = sorted(tracked_ids, key=lambda tid: club_states[tid].rating, reverse=True)
        date_str = snapshot_date.strftime("%-m/%-d/%Y") if os.name != "nt" \
            else snapshot_date.strftime("%#m/%#d/%Y")
        for rank, tid in enumerate(ranked, start=1):
            entry = self.histories.setdefault(tid, {"dates": [], "e": [], "r": []})
            # Guard against ever writing two entries for the same date to
            # the same club (shouldn't happen given the pointer-advance
            # logic below, but cheap to make impossible)
            if entry["dates"] and entry["dates"][-1] == date_str:
                entry["e"][-1] = round(club_states[tid].rating, 6)
                entry["r"][-1] = rank
                continue
            entry["dates"].append(date_str)
            entry["e"].append(round(club_states[tid].rating, 6))
            entry["r"].append(rank)

    def maybe_snapshot(self, match_date: datetime.date, club_states: dict, club_is_tracked: dict) -> None:
        """
        Captures every snapshot date that is now in the past relative to
        match_date but hasn't been captured yet. Call this BEFORE
        processing the fixture at match_date, so the snapshot reflects
        state as of the end of the prior window, not mid-update from the
        fixture about to be processed.
        """
        while (
            self._pointer < len(self.snapshot_dates)
            and self.snapshot_dates[self._pointer] < match_date
        ):
            self._take_snapshot(self.snapshot_dates[self._pointer], club_states, club_is_tracked)
            self._pointer += 1

    def finalize(self, club_states: dict, club_is_tracked: dict, last_fixture_date: datetime.date) -> None:
        """
        Call once after the fixture loop ends. Captures any remaining
        regular scheduled snapshot dates up through last_fixture_date,
        then adds one final catch-up snapshot dated as of
        last_fixture_date itself, UNLESS that date already coincides
        with a regular scheduled snapshot (no duplicate).
        """
        while (
            self._pointer < len(self.snapshot_dates)
            and self.snapshot_dates[self._pointer] <= last_fixture_date
        ):
            self._take_snapshot(self.snapshot_dates[self._pointer], club_states, club_is_tracked)
            self._pointer += 1

        already_captured_today = (
            self._pointer > 0
            and self.snapshot_dates[self._pointer - 1] == last_fixture_date
        )
        if not already_captured_today:
            self._take_snapshot(last_fixture_date, club_states, club_is_tracked)

    def write_all(self, output_dir: str) -> int:
        """
        Writes one self-contained JSON file per club to
        {output_dir}/{team_id}.json. Returns the number of files written.

        Clears every pre-existing *.json file in output_dir FIRST - this
        directory must always exactly reflect the current run's true
        state. Without this, a club that no longer gets a fresh entry
        this run (e.g. correctly excluded now under a logic fix that
        wasn't in place for a previous run) leaves its stale OLD file
        sitting there untouched, silently corrupting any downstream
        consumer that just reads everything in the directory - exactly
        what happened when a logic fix changed which clubs qualify and
        the leftover pre-fix files got miscounted as current.
        """
        os.makedirs(output_dir, exist_ok=True)
        for existing in glob.glob(os.path.join(output_dir, "*.json")):
            os.remove(existing)
        for tid, hist in self.histories.items():
            payload = {
                "team_id": tid,
                "dates": hist["dates"],
                "e": hist["e"],
                "r": hist["r"],
            }
            with open(os.path.join(output_dir, f"{safe_history_filename(tid)}.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f, separators=(",", ":"))
        return len(self.histories)
