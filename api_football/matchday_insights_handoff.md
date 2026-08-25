# Matchday Insights — Project Handoff

Context for a new conversation. This covers where the project stands, why key
decisions were made, and what's still open. All files referenced below have
already been delivered and should be present in your `api_football` folder.

## What this project is

Rebuilding Matchday Insights (a global club football Elo rating site) on a
fresh API-Football data pipeline, replacing the old manual worldfootball.net
process. Core engine (`run_ratings.py` + `elo_engine.py`) computes Elo ratings
across ~13,000+ clubs from ~260,000 matches (2020–present). Currently building
the site-facing output layer on top of that engine.

## Core architectural decisions (already built, don't relitigate)

- **`team_id` is the universal key** for everything going forward — history
  files, rankings, metadata, slugs. This replaces the old site's name-string
  joins, which caused constant coordination problems (disambiguation suffixes,
  slug-registry drift).
- **Per-club history files** (`history/{team_id}.json`) replaced the old
  monolithic `all_history.json`. Self-contained, one file per genuinely-tracked
  club, no null-padding — a club's file simply starts wherever its real
  history begins.
- **Snapshot cadence**: every Monday and Thursday (alternating 4-day/3-day
  gaps), starting `2021-08-09` (matches the old site's public chart start,
  even though real match processing/burn-in begins 2020-01-01).
- **Point-in-time correctness**: a snapshot only includes clubs that are
  `club_is_tracked=True` *at that exact moment* — this falls out naturally
  from processing fixtures chronologically, no special go-live cross-checking
  needed.
- **`rankings.json`** replaces the old baked-in `CLUBS` array in `index.html`.
  Built in two tiers:
  - **Tier A** (done): rank/prev_rank/rank_change/elo/elo_change, all-time
    high/low (rank + elo, with dates), times_no1/top5/top10/top50/tier_counts.
    Pure aggregation over `history/`.
  - **Tier B** (done): last_result/opponent/score, calendar-year record
    (cy_w/cy_d/cy_l/cy_pts/cy_pct/cy_gp), form5/form10. Required building new
    match-by-match result logging (`match_log.py`) since the engine
    previously only tracked aggregate rating, not individual results.

## Key files and what they do

**Core engine:**
- `run_ratings.py` — main pipeline, processes all fixtures chronologically
- `elo_engine.py` — the Elo math itself (`process_match`, `ClubState`, Starting
  Position formulas)
- `match_context_builder.py` — home advantage, neutral-venue, K-factor context
  per match
- `history_snapshots.py` — companion module, writes `history/{team_id}.json`
- `match_log.py` — companion module, writes `match_log/{team_id}.json`
  (bounded rolling log, last 150 matches per club)

**Rankings generation:**
- `generate_rankings.py` — combines `history/` + `club_metadata.json` +
  `confederation_mapping.json` + `match_log/` → `rankings.json`
- `confederation_mapping.json` / `extract_confederation_mapping.py` — country
  → confederation, derived directly from `Leagues_Included_in_Ranking.xlsx`'s
  own column structure (not hand-typed — avoids edge-case errors like
  Israel/UEFA, Australia/AFC, Kazakhstan/UEFA, Guyana-Suriname/CONCACAF)

**Diagnostic/spot-check tools** (all reuse the real pipeline's logic, not
simplified reimplementations — except where noted):
- `preview_rankings.py` — quick top-N ranking preview + full CSV
- `club_history.py` — one club's full rank/elo trajectory, monthly or full
- `diagnose_club.py` — traces exactly why a specific club is/isn't tracked,
  step by step through `get_starting_position()`
- `diagnose_history_dates.py` — distribution of "last recorded date" across
  all clubs, for diagnosing stale-exclusion issues
- `check_match_count_anomalies.py` — flags clubs with anomalous match counts
  vs. peers in the same league_id/season (catches merged/shared team_ids)

**Data-quality inputs (all resolved/current as of last session):**
- `relegation_percentages.json` (263 codes, all gaps closed — Gibraltar,
  Congo/COD, Tajikistan/TJK, Serbia SRB_2 all fixed)
- `country_code_mapping.json` (Tajikistan, Congo, Gibraltar+GBR fallback fixed)
- `team_country_overrides.json` (New Saints→Wales and others)
- `untracked_club_tiers.json` — built via `pull_untracked_standings.py` +
  `apply_untracked_leagues.py`; uses **absolute tier numbers** (not relative
  depth-below-deepest-tracked — changed per Greg's request, since relative
  depth goes stale if the tracked baseline ever changes). Supports `EXCLUDE`
  (deliberate, e.g. women's/youth leagues — auto-pre-filled by keyword) and
  `N/A` (no standings data available) as valid non-numeric values.
- `season_inclusion.json` / `extract_season_inclusion.py` — which
  country/tier codes are genuinely tracked per season, from
  `Leagues_Included_in_Ranking.xlsx`

**Cross-confederation calibration (separate from the main rating pipeline —
does NOT feed into Elo, purely for manual review):**
- `pull_cross_confederation_friendlies.py` — pulls club friendlies since 2020,
  filters to genuinely cross-confederation matchups
- `summarize_cross_confederation_friendlies.py` — confederation-vs-
  confederation W-D-L/points% matrix
- `list_cross_confederation_friendlies.py` — browsable match list for
  spot-checking the aggregate numbers

## Two important bugs fixed in the last session (both now verified correct)

1. **A club that got relegated *without* a long inactivity gap kept silently
   evolving as if still tracked.** `club_is_tracked` was previously only
   re-checked on (a) a club's very first seed, or (b) a 365+ day gap — a
   normal season-to-season relegation triggers neither. Fixed by adding a
   check that fires on every season transition: if still tracked, keep
   evolving normally (untouched); if it just dropped out of tracked status,
   treat it exactly like any other untracked club from that point forward. On
   promotion back into a tracked tier, a club is correctly reseeded from
   scratch (the original Starting Position calculation), not resumed from its
   old tracked rating or whatever placeholder value it accumulated while
   untracked.
2. **Newly-seeded clubs were incorrectly backfilled into history** back to
   the `2021-08-09` snapshot start with a flat rating, even if their real
   first match was years later. Was a call-ordering bug (snapshot logic ran
   *after* the current match's clubs were seeded, not before). Fixed by
   reordering.
3. **`history/` and `match_log/` were never cleared between runs.**
   `write_all()` only wrote files for clubs computed in the current run - it
   never deleted stale files left over from a previous run. Since fixes #1/#2
   changed which clubs qualify for tracking, a re-run left old pre-fix files
   sitting alongside new ones, and `generate_rankings.py` (which just reads
   everything in the directory) silently counted orphaned garbage as if it
   were current. Fixed by having both recorders' `write_all()` wipe the
   output directory before writing fresh files each run - confirmed with a
   direct test (an orphaned file was correctly removed on the next write).
   **If you have old `history/`/`match_log/` folders from before this fix,
   delete them before your next run** (or just trust the new code - it'll
   clean itself either way).

**Given these fixes, the last full real run's numbers (4,049 tracked / 80
excluded) are now stale — a fresh `run_ratings.py` run is warranted before
trusting current rankings.json output.**

## Recurring gotcha this session (watch for it)

Multiple times, a delivered bug fix appeared not to work because Greg was
running an old cached local copy of a file instead of the newly-delivered
one. Worth double-checking file timestamps/re-downloading before assuming a
fix didn't work.

## What's NOT done yet (open items)

- **Re-run the full pipeline** with the two bug fixes above, re-validate
  numbers
- **`slug_registry.json`** — new version, keyed by `team_id` (permanent
  slugs, survive renames) — not yet built
- **Static per-club page generator** — now fully unblocked (all inputs exist:
  `history/`, `club_metadata.json`, `rankings.json`, `match_log/`) but not
  started
- **`tier_counts` threshold ladder** — currently `[1,5,10,25,50,100,250,500,
  1000]`, only the first 3 + top50 confirmed against the old site's real
  data, rest is a reasonable guess pending Greg's review
- **Friendlies → ratings decision** — deliberately NOT wired into the rating
  engine yet; whether/how friendly results should ever influence competitive
  Elo (weakened lineups, no stakes) is an open methodology question
- **Venue/neutral-site gap** — ~50k+ matches processed without venue data
  (forced-relocation neutral-venue detection, e.g. Ukraine-abroad ties, not
  caught for these) — long-standing known gap, not addressed this session
- **Incremental processing** (only re-process new matches, not the whole
  dataset each run) — original roadmap item, not yet started

## How to resume in a new chat

Paste this document as your first message, then just say what you want to
work on next.
