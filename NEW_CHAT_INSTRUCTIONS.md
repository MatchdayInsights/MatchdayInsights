# MATCHDAY INSIGHTS — NEW CHAT MASTER INSTRUCTIONS
## Read this fully before doing anything

---

## 0. RECORD BADGES + #1 STREAK LINE — LIVE

**Status: merged into `update_site.py` and `index_base.html`, confirmed working on the live site.**

What shipped:

1. **Bug fix (`index_base.html`):** `loadAllHistory()` now fetches `./all_history.json` (relative)
   instead of a hardcoded absolute GitHub Pages URL, so the all-time charts aren't dependent on
   one exact domain/repo path matching. See section 11 for the original symptom.

2. **Record badges on the main rankings table:**
   - A small statement under the club name (fills the dead space next to the flag/code) when a
     club is at an all-time-record rank or rating, e.g. "new all-time-high rank", "all-time-high
     rank — 28 matchdays", "tied all-time-high rank — first since 5/21/2026". Rank and rating
     statements each render on their **own line** (not joined with a separator) — joining them
     caused long combinations to get clipped, so each stat now gets full width and wraps.
   - A green/red bordered box around the rank number and/or rating number when that specific
     stat is at its all-time record, following a matchday the club actually played.
   - A dedicated line for the #1 club only: "N matchdays at #1".
   - Full logic and field definitions are in section 6 (new fields) and section 8a.
   - The four new fields (`rank_streak`, `rank_streak_since`, `rank_prev_since`, `top1_streak`)
     are computed directly inside `update_site.py`'s per-club loop (right where `min_r` is
     already calculated) — no separate script or merge step needed at runtime.
     `compute_records.py` still lives in the local folder as the original standalone reference
     implementation the logic was validated against, but isn't part of the live pipeline.

3. **Known upstream data issue (not a code bug):** the `Historical Rank` sheet's newest date
   column can occasionally be non-sequential — missing rank slots partway through — which throws
   off `all_time_high_rank`/`all_time_low_rank` (and therefore the badges) for clubs in the
   affected range. Confirmed by comparing the `Rank` sheet (source of truth for current rank)
   against `Historical Rank`'s newest column across the whole table: a clean 1..N sequence should
   match exactly, gaps mean this has recurred. Worth a quick spot-check after each update if a
   badge looks wrong — compare a club's current rank (`Rank` sheet, column `#`) against its
   value in `Historical Rank`'s newest date column; they should be identical.

---

## 1. PROJECT OVERVIEW

**Site:** matchdayinsights.com  
**X/Twitter:** @MDInsights_FC  
**Stack:** Single `index.html` + `all_history.json` on GitHub Pages. Vanilla JS, no build step.  
**Local folder:** `C:\Users\Greg\Matchday Insights\`

**Brand rules — never violate:**
- Never say "ELO" in any user-facing text — say "our model", "our rating", or "rating points"
- URL always: `matchdayinsights.com` (full path, mixed case)
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
- `generate_club_pages.py` — SEO static page generator (auto-called by update_site.py)
- `h2h_generator.html` — H2H matchup tool (auto-updated by script)
- `weekly_tools.html` — Risers/Fallers + Country vs Country tool
- `.gitignore` — tells Git to ignore xlsx files and other large/unnecessary files
- `New_UEFA_Club_Ranking_Revamp_.xlsx` — rankings data (replaced each update, NOT pushed to GitHub)
- `New_Historical_Rankings_Revamp.xlsx` — history data (replaced each update, NOT pushed to GitHub)
- `compute_records.py` — precompute script for record badges / #1 streak (see section 0). Reads
  `New_Historical_Rankings_Revamp.xlsx` directly; not yet folded into `update_site.py`.

**To run (Command Prompt — `%date%` auto-fills today's date, safe to paste as-is every time):**
```
cd "C:\Users\Greg\Matchday Insights"
python update_site.py
git add -A
git commit -m "Update %date%"
git push origin master
```
Note: `[date]` in older versions of this doc was a placeholder to type manually, not a variable —
pasting it literally committed as "Update [date]" every time. `%date%` fixes that for cmd.exe.
If using PowerShell instead, use `git commit -m "Update $(Get-Date -Format 'MM/dd/yyyy')"`.

**Output:** `index.html`, `all_history.json`, and `clubs/` folder all pushed to GitHub in one step.

**GitHub repo:** https://github.com/MatchdayInsights/MatchdayInsights.git  
**Live site:** https://matchdayinsights.com

**What the script does (6 steps):**
1. Load both xlsx files (Rank + Matches + Historical Scores/Rank + Club Records sheets)
2. Build `all_history.json` from Historical Scores + Rank sheets (includes gap filler)
3. Build CLUBS array
4. Inject into `index_base.html` → output `index.html`
5. Auto-regenerate `h2h_generator.html` if present in folder
6. Generate SEO club pages (`clubs/` folder, `sitemap.xml`) if `generate_club_pages.py` is present

---

## 3b. GIT / GITHUB WORKFLOW

Greg uses Git from Command Prompt — no GitHub Desktop.

**One-time setup (already done):**
```
git config --global user.name "Matchday Insights"
git config --global user.email "gregory.m.toledo@gmail.com"
cd "C:\Users\Greg\Matchday Insights"
git init
git remote add origin https://github.com/MatchdayInsights/MatchdayInsights.git
git pull origin main
```

**Every Monday/Thursday update (4 commands, Command Prompt — safe to paste verbatim):**
```
cd "C:\Users\Greg\Matchday Insights"
python update_site.py
git add -A
git commit -m "Update %date%"
git push origin master
```

**Key facts:**
- Branch is `master` (not `main`)
- Repo URL: `https://github.com/MatchdayInsights/MatchdayInsights.git`
- xlsx files are in `.gitignore` — never pushed to GitHub (too large)
- The `clubs/` folder (~1,751 HTML files) pushes automatically with `git add -A`
- First push after adding clubs was ~120MB — subsequent pushes are small (only changed files)

**If push fails with auth error:** GitHub uses Personal Access Tokens not passwords.
Go to github.com → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token → tick `repo` → copy and use as password.

---

## 3c. DOMAIN & SEO

**Live URL:** https://matchdayinsights.com (custom domain via GoDaddy → GitHub Pages)  
**GitHub Pages:** Settings → Pages → Custom domain: matchdayinsights.com + Enforce HTTPS  
**Sitemap:** https://matchdayinsights.com/sitemap.xml — submit to Google Search Console  

**SEO club pages:**
- 1,751 static HTML pages in `clubs/` folder
- Each has unique title, meta description, canonical URL, all-time stats, last 5 results, related clubs
- CTA button links back to main SPA via hash routing (`index.html#club=palmeiras`)
- Auto-regenerated every update cycle by `generate_club_pages.py`
- `SITE_BASE` at top of `generate_club_pages.py` = `https://matchdayinsights.com`

**To change domain in future:** update `SITE_BASE` in `generate_club_pages.py` and re-run update

**Club name changes:**
- Spreadsheet update → script picks up new name automatically
- Old slug becomes dead link — acceptable, Google will recrawl
- `all_history.json` needs manual fix: find old name key, rename to new name (find & replace in text editor)
- **Whitespace quirks are now handled automatically** (fixed after a real incident — Olympique
  Lyonnais got a worldfootball.net trailing space `'Olympique Lyonnais '` in the Rank sheet, but
  the historical sheets' lookup wasn't matching it consistently, silently resetting their
  all-time-high rank/rating to that day's value and firing false "new record" badges despite
  the club having dropped 5 spots). `update_site.py` now strips every name-bearing column
  (`Club` in Rank/Historical Scores/Historical Rank/Club Records, `Team 1`/`Team 2` in Matches)
  right after loading, so a stray space in one sheet but not another can't break the
  cross-sheet lookups anymore. No manual step needed for whitespace-only differences — only a
  genuine name change (different words) still needs the `all_history.json` manual rename above.

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

  // PENDING — not yet added to update_site.py, see section 0 / 8c:
  rank_ath, rank_atl,              // bool — current rank == all_time_high_rank / all_time_low_rank
  rank_streak,                     // int — consecutive matchdays currently at rank_ath (0 if not rank_ath)
  rank_streak_since,               // date string — when the current streak began
  rank_prev_since,                 // date string or null — last time at that rank before this
                                    // streak began (null if this is the club's first time ever there)
  elo_ath, elo_atl,                // bool — current elo == all_time_high_elo / all_time_low_elo
                                    // (float tolerance ~1e-6, since exact ties are rare)
  top1_streak,                     // int — consecutive matchdays at rank #1 (0 if not currently #1)
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

## 8a. RECORD BADGES + #1 STREAK LINE (pending — see section 0)

Renders on the main rankings table, driven by the fields added in section 6. **Only render any
of this if the club actually played this matchday** — gate on `last_result` being non-empty
(never show a badge on a bye week, even if the underlying flags are true).

**Statement line** (goes under the club name, in the dead space next to flag/league code):
- `rank_ath` true, `rank_streak === 1`, `rank_prev_since === null` → "new all-time-high rank"
- `rank_ath` true, `rank_streak === 1`, `rank_prev_since` set → "tied all-time-high rank — first since `{rank_prev_since}`"
- `rank_ath` true, `rank_streak > 1` → "all-time-high rank — `{rank_streak}` matchdays"
- `rank_atl` true → "new all-time-low rank" (no streak/tied variants for lows — kept simple)
- `elo_ath` true → "new all-time-high rating" (ratings are floats — no streak/tied language, just new-high/new-low)
- `elo_atl` true → "new all-time-low rating"
- If a club hits both a rank record and a rating record the same matchday, show both indicators
  (box both the rank number and the rating number; statement line can show either or both,
  whichever reads cleaner — decide at build time).

**Colored box**: green (rank_ath/elo_ath) or red (rank_atl/elo_atl) border + faint background
drawn directly around the specific number that hit the record — the rank number cell for a rank
record, the rating number cell for a rating record.

**#1 streak line**: for the club currently ranked #1 only, a separate line (don't conflate with
the general statement above) reading "`{top1_streak}` matchdays at #1".

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
| All-time chart showed "All-time data unavailable" | `loadAllHistory()` in index_base.html fetched a hardcoded absolute URL (`https://matchdayinsights.github.io/MatchdayInsights/all_history.json`) instead of a relative path — fragile if that exact domain/repo path doesn't match. Fix: `fetch('./all_history.json')`. Applied, live. |
| Club falsely showed "new all-time-high rank/rating" right after dropping in rank | A trailing/leading space on the club's name in one sheet but not another (e.g. worldfootball.net's `'Olympique Lyonnais '`) meant the stripped name used in `CLUBS` didn't match the unstripped key in the `history` dict — history lookup silently came back empty, so today's value became both the fake all-time high and low. Fix: strip every name-bearing column (`Club`, `Team 1`, `Team 2`) right after loading each sheet, before any lookups. See section 3c. |

---

## 12. SESSION STARTERS

**Resume record badge / #1 streak enhancement (see section 0):**
```
Read NEW_CHAT_INSTRUCTIONS.md first.
Upload: index_base.html, update_site.py, New_Historical_Rankings_Revamp.xlsx
Say: "Finish the record badge enhancement — see section 0."
```

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
