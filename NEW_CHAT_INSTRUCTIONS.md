# MATCHDAY INSIGHTS — NEW CHAT MASTER INSTRUCTIONS
## Read this fully before doing anything

---

## 1. PROJECT OVERVIEW

**Site:** matchdayinsights.github.io/MatchdayInsights  
**X/Twitter:** @MDInsights_FC  
**Stack:** Single `index.html` + `all_history.json` on GitHub Pages. Vanilla JS, no build step.  
**Local folder:** `C:\Users\Greg\Matchday Insights\`

**Brand rules — never violate:**
- Never say "ELO" in any user-facing text — say "our model", "our rating", or "rating points"
- URL always: `matchdayinsights.github.io/MatchdayInsights` (full path, mixed case)
- Body background always `#f5f6f2` (off-white) — never dark for graphic body
- Header/footer always `#1a1a2e` dark
- Minimum font size 14px in any graphic

---

## 2. DATA STATE (as of July 6, 2026)

- **1,751 ranked clubs** across UEFA + CONMEBOL
- **519 dates** in all_history.json (Aug 9, 2021 → Jul 26, 2026)
- **2,442 clubs** total in all_history.json (UEFA + CONMEBOL + lower divisions + inactive)
- **Update schedule:** Monday & Thursday
- **League tables:** removed from site as of July 2026
- **CONMEBOL added:** July 2026 — ARG, ARG_2, BOL, BRA, BRA_2, BRA_3, CHI, COL, ECU, PAR, PER, URU, VEN

---

## 3. LOCAL UPDATE SCRIPT (PRIMARY WORKFLOW)

Greg runs updates himself locally. No Claude session needed for routine updates.

**Files in `C:\Users\Greg\Matchday Insights\`:**
- `update_site.py` — the engine, never edit
- `league_config.py` — only contains SEASON_LIST and TIER_THRESHOLDS, rarely needs editing
- `index_base.html` — master template
- `h2h_generator.html` — H2H matchup tool (auto-updated by script)
- `weekly_tools.html` — Risers/Fallers + Country vs Country tool
- `New_UEFA_Club_Ranking_Revamp_.xlsx` — rankings data (replaced each update)
- `New_Historical_Rankings_Revamp.xlsx` — history data (replaced each update)

**To run:**
```
cd "C:\Users\Greg\Matchday Insights"
python update_site.py
```

**Output:** `index.html` + `all_history.json` → push both to GitHub.

**What the script does (5 steps):**
1. Load both xlsx files (Rank + Matches + Historical Scores/Rank + Club Records sheets)
2. Build `all_history.json` from Historical Scores + Rank sheets (includes gap filler)
3. Build CLUBS array
4. Inject into `index_base.html` → output `index.html`
5. Auto-regenerate `h2h_generator.html` if present in folder

---

## 4. LEAGUE_CONFIG.PY — MINIMAL, RARELY NEEDS EDITING

League tables have been removed from the site. `league_config.py` now only contains:

```python
SEASON_LIST = ['2026-27', '2025-26', '2024-25', '2023-24', '2022-23', '2021-22']
TIER_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]  # never change
LUX_FLAG_SVG = '...'  # Luxembourg flag SVG — do not edit
```

`SEASON_LIST` needs updating once per year when a new season starts (add the new season at the front, drop the oldest from the end).

**CONMEBOL country codes** (used in `country` field after `_N` stripping):
`ARG, BOL, BRA, CHI, COL, ECU, PAR, PER, URU, VEN`
These are automatically handled — `ARG_2` → `ARG` etc. No config change needed. when a new season starts (add the new season at the front, drop the oldest from the end).

---

## 5. PIPELINE CRITICAL RULES

```python
# Country field strips league suffix - ENG_2 → ENG
country = re.sub(r'_\d+$', '', league_code)

# After building CLUBS, always sort by rank
CLUBS.sort(key=lambda x: x['rank'])

# Club count auto-updates in index_base.html header on every run

# Gap filler — detects dates where >90% of clubs have None rank
# (missing rank column in spreadsheet) and fills from adjacent dates
# Fires automatically with ⚠ warning printed to console
# Example: "⚠ Fixed missing rank column at 6/1/2026 (1510 clubs filled)"

# all_history.json correct structure:
# { "dates": [...oldest→newest], "history": { "Club Name": { "e": [...], "r": [...] } } }
# Keys: "history" (not "clubs"), "e"/"r" (not "scores"/"ranks")

# ALWAYS use index_base.html as injection base, never the uploaded index.html
# index_base.html has all features; uploaded index.html may be stale
```

---

## 6. FIELD NAMES (JS expects these exactly)

```javascript
// Each club in CLUBS array must have ALL of these:
{
  rank, prev_rank, rank_change,
  club, league_code, country,        // country strips _N suffix
  league, elo, elo_pct, elo_change,
  last_result, opponent, score,
  cy_w, cy_d, cy_l, cy_pts, cy_pct, cy_gp,
  form5,   // [{result, opponent, elo_change}, ...] — MUST include elo_change
  form10,  // same structure
  elo_history,   // last 200 values
  rank_history,  // last 200 values
  all_time_high_elo, all_time_high_elo_date,
  all_time_low_elo,  all_time_low_elo_date,
  all_time_high_rank, all_time_high_rank_date,
  all_time_low_rank,  all_time_low_rank_date,
  times_no1, top5, top10, top50,
  tier_counts,    // 9 ints matching TIER_THRESHOLDS
  season_pct,     // from Club Records sheet × 100
  season_league,  // from Matches sheet
}
```

---

## 7. SPREADSHEET SHEETS USED

**New_UEFA_Club_Ranking_Revamp_.xlsx:**
- `Rank` — current rankings, ELO, form columns
- `Matches` — match history for season_league calculation
- `League Tables` — no longer read by the script (league tables removed)

**New_Historical_Rankings_Revamp.xlsx:**
- `Historical Scores` — ELO history by date (columns = dates, rows = clubs)
- `Historical Rank` — rank history by date (same structure)
- `Club Records ` — season win% (note trailing space in sheet name)
  - Read with `usecols=range(8)` — first 8 columns only

**Form column names (exact):**
```python
result_cols = ['< Result'] + [f'<{i} Result' for i in range(2,11)]
opp_cols    = ['<Opp']     + [f'<{i} Opp'    for i in range(2,11)]
elo_cols    = ['< Match','<2 Matches','<3 Matches','<4 Matches','<5 Matches',
               '<6 Matches','<7 Matches','< 8 Matches','<9 Matches','<10 Matches']
# Note: col 8 is '< 8 Matches' (space before 8)
```

---

## 8. JS FEATURES IN INDEX_BASE.HTML

These are already built — never remove or rebuild:
- **Season bars panel** — Points Won % per season. Reads `season_pct` + `season_league`
- **Dynamic tier boxes** — Shows 3 relevant tiers per club from `tier_counts`
- **Chart timeframe selector** — 60/200/all-time. Uses `CHART_DATES_60` + `CHART_DATES_200`
- **Country filter** — works because `country` has `_N` stripped
- **Club profile page** — `showClub(rank-1)` function
- **Club count header** — auto-updated by script on every run

**Removed features (do not try to re-add without careful planning):**
- League tables — removed July 2026 (too much maintenance overhead)

---

## 8b. CONFEDERATION FILTER

Added July 2026. A "All Confederations" dropdown sits next to the country filter.

**Options:** All Confederations / UEFA (Europe) / CONMEBOL (South America)

**How it works in JS:**
```javascript
const CONMEBOL_COUNTRIES = ['ARG','BOL','BRA','CHI','COL','ECU','PAR','PER','URU','VEN'];
const UEFA_COUNTRIES = ['ALB','AND', ... 'WAL'];  // all UEFA member associations
// In applyFilters():
if(confederation==='CONMEBOL' && !CONMEBOL_COUNTRIES.includes(c.country)) return false;
if(confederation==='UEFA'     && !UEFA_COUNTRIES.includes(c.country))     return false;
```

**update_site.py handles automatically:**
- Injects SA flags (ARG, BOL, BRA, CHI, COL, ECU, PAR, PER, URU, VEN) into SVG_FLAGS
- Adds CONMEBOL countries to the country dropdown
- Adds the confederation dropdown if missing
- All idempotent — safe to run repeatedly

**To add a new confederation (e.g. CONCACAF):**
1. Add country codes to `CONMEBOL_COUNTRIES`-style const in `update_site.py`
2. Add a new `<option>` in the confederation dropdown HTML
3. Add a new `if(confederation==='CONCACAF'...)` check in `applyFilters`

---

## 9. TOOLS

### H2H Generator (h2h_generator.html)
Standalone tool — open in browser, type two club names, generates graphic, download as PNG.
- Has `CLUB_COLORS` lookup (~170 clubs) — `['#primary', '#secondary']`
- Has `SHORT_NAMES` lookup for long/awkward names
- Has `readableOnDark()` / `readableOnLight()` luminance functions
- Editable headline lines (default "ONE NIGHT." / "ONE CUP.")
- Download as PNG button
- **Clubs with accented names must be added by Claude** — Unicode encoding mismatch means manual typing doesn't work. Upload the file and say "Add [Club] with primary #X and secondary #Y"
- Auto-updated by `update_site.py` Step 5

### Weekly Tools (weekly_tools.html)
Two-tab tool:
- Tab 1: Risers & Fallers — choose period (1 week/2 weeks/1 month/season), top 5 or 10
- Tab 2: Country vs Country — autocomplete all UEFA nations, top 5 clubs comparison
- Download as PNG on both tabs
- Data frozen at last update — re-run script to refresh
- Not auto-updated by script (can be added if needed)

---

## 10. GRAPHIC DESIGN SYSTEM (Summer Series + Club Highlights)

```python
DARK      = '#1a1a2e'   # header/footer
BODY      = '#f5f6f2'   # graphic body (never dark)
GREEN_ACC = '#3dba5e'   # brand green
RED_ACC   = '#e84466'   # losses/drops
GOLD_ACC  = '#c8a400'   # trophies

# Fonts (Google Fonts):
# Barlow Condensed 400/600/700/900 — all headlines
# JetBrains Mono 400/600/700 — all stats/labels

# Rendering:
# device_scale_factor=2 always
# Width: 1080px always
# Full_page=True for table/summary; fixed 1080×1080 for title card

# Flags: always inline SVG, never emoji
```

---

## 11. KNOWN BUGS (all fixed in current scripts)

| Bug | Fix |
|---|---|
| Country filter only showed top-flight clubs | Strip `_N` from `league_code` when setting `country` |
| Rank history showed gap/drop on missing date | Gap filler detects >90% None dates and fills from adjacent |
| f-strings in gap filler showed literally | Use string concatenation, not f-strings, in gap filler print statements |
| H2H tool crashed silently | Apostrophe in SHORT_NAMES broke JS string — avoid apostrophes in values |
| Clubs with accented names wrong color in H2H | Unicode escape mismatch — always add via Claude, never type manually |
| CLUBS out of rank order | `CLUBS.sort(key=lambda x: x['rank'])` after building array |
| SA clubs not showing flag | Flags injected by update_site.py — re-run script if missing |
| SA clubs not in country dropdown | Dropdown updated by update_site.py — re-run script if missing |

---

## 12. SESSION STARTERS

**Site update (use Claude only if local script fails):**
```
Read NEW_CHAT_INSTRUCTIONS.md first.
Upload: index_base.html, New_UEFA_Club_Ranking_Revamp_.xlsx, New_Historical_Rankings_Revamp.xlsx
Say: "Run the full pipeline."
```

**Summer Series graphics:**
```
Read NEW_CHAT_INSTRUCTIONS.md + SUMMER_SERIES_REFERENCE_GRAPHICS.md first.
Upload: all_history.json
The three REFERENCE_*.py files are the gold standard — adapt them, don't redesign.
Say: "Build Day X graphics for [Country]. [paste league table + European qualifier info]"
```

**H2H / Club highlight graphic:**
```
Read NEW_CHAT_INSTRUCTIONS.md first.
Upload: all_history.json
Say: "Build H2H graphic for [Club A] vs [Club B] — [competition] — [stage]"
Or: "Build club highlight for [Club] — [story angle] — [key stats]"
```

**Adding a club color to H2H tool:**
```
Upload: h2h_generator.html
Say: "Add [Club Name] with primary #XXXXXX and secondary #XXXXXX"
Claude handles Unicode encoding — never try to type accented names manually
```

**Script bug:**
```
Upload: update_site.py, league_config.py
Paste the full error message
Say: "Fix this error"
```

---

## 13. CONTENT STRATEGY

- **X posts:** not Greg's preference — minimal posting
- **Reddit:** r/soccer, r/footballanalysis — 1 quality post/month
- **H2H graphics:** best engagement format — finals, derbies, promotion deciders
- **Automated pre-match graphics:** h2h_generator.html handles this locally
- **Reply strategy:** reply to @OptaJoe/@BBCSport within 10 min with one sharp stat
- **Never say "ELO"** — always "our model" or "rating points"

---

## 14. ROADMAP

- **P1 (done):** Stable site, local update script
- **P2 (active):** Audience growth, content tools (H2H generator, weekly tools)
- **P3:** Fixtures integration
- **P4:** Port rating engine to Python (gating milestone)
- **P5:** Full automation pipeline (~$35/mo)
- **P6:** Pitch Fotmob/WhoScored/SofaScore/The Athletic
- **P7 (under consideration):** Global expansion beyond UEFA

**Long-term goal:** licensing/acquisition by a football data company — not Twitter audience size.
