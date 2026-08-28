"""
MATCHDAY INSIGHTS — Site Update Script
========================================
Run this script to update index.html and all_history.json.

USAGE:
    python update_site.py

REQUIRED FILES IN THE SAME FOLDER:
    New_UEFA_Club_Ranking_Revamp_.xlsx
    New_Historical_Rankings_Revamp.xlsx
    index_base.html
    league_config.py

OUTPUT FILES (push these to GitHub):
    index.html
    all_history.json
"""

import pandas as pd
# SEO page generator (optional — only runs if generate_club_pages.py is present)
_seo_gen = None  # loaded after SCRIPT_DIR is defined
import numpy as np
import json
import re
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

# ── Import config ──────────────────────────────────────────────────────────────
try:
    import league_config as cfg
except ImportError:
    print("ERROR: league_config.py not found. Make sure it's in the same folder.")
    sys.exit(1)

# ── File paths ─────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
try:
    import sys as _sys; _sys.path.insert(0, SCRIPT_DIR)
    from generate_club_pages import generate_all as _seo_gen
except ImportError:
    _seo_gen = None
RANK_FILE     = os.path.join(SCRIPT_DIR, 'New_UEFA_Club_Ranking_Revamp_.xlsx')
HISTORY_FILE  = os.path.join(SCRIPT_DIR, 'New_Historical_Rankings_Revamp.xlsx')
BASE_HTML     = os.path.join(SCRIPT_DIR, 'index_base.html')
OUT_HTML      = os.path.join(SCRIPT_DIR, 'index.html')
OUT_HISTORY   = os.path.join(SCRIPT_DIR, 'all_history.json')

for f in [RANK_FILE, HISTORY_FILE, BASE_HTML]:
    if not os.path.exists(f):
        print(f"ERROR: Required file not found: {os.path.basename(f)}")
        sys.exit(1)

print("=" * 60)
print("MATCHDAY INSIGHTS — Site Update")
print("=" * 60)

# ═══════════════════════════════════════════════════════════════
# STEP 1: LOAD ALL DATA
# ═══════════════════════════════════════════════════════════════
print("\n[1/5] Loading spreadsheet data...")

df_rank    = pd.read_excel(RANK_FILE, sheet_name='Rank', header=0)
df_matches = pd.read_excel(RANK_FILE, sheet_name='Matches', header=0,
                usecols=['Season','Type','Team 1 Level','Team 1','Team 2 Level','Team 2'])
df_scores  = pd.read_excel(HISTORY_FILE, sheet_name='Historical Scores', header=0)
df_hrank   = pd.read_excel(HISTORY_FILE, sheet_name='Historical Rank', header=0)
df_records = pd.read_excel(HISTORY_FILE, sheet_name='Club Records ', header=0, usecols=range(8))

# Date columns: newest first in spreadsheet → reverse to oldest first
date_cols     = [c for c in df_scores.columns if re.match(r'\d+/\d+/\d+', str(c))]
dates_ordered = list(reversed(date_cols))  # oldest → newest

print(f"    Clubs in ranking sheet: {len(df_rank)}")
print(f"    Date range: {dates_ordered[0]} → {dates_ordered[-1]} ({len(dates_ordered)} dates)")

# ═══════════════════════════════════════════════════════════════
# STEP 2: BUILD ALL_HISTORY.JSON
# ═══════════════════════════════════════════════════════════════
print("\n[2/5] Building all_history.json...")

scores_idx = df_scores.set_index('Club')
ranks_idx  = df_hrank.set_index('Club')
all_clubs  = sorted(set(df_scores['Club'].dropna()) | set(df_hrank['Club'].dropna()))

history = {}
for club in all_clubs:
    has_s = club in scores_idx.index
    has_r = club in ranks_idx.index
    e_raw, r_raw = [], []
    for d in date_cols:  # newest first
        v = scores_idx.at[club, d] if has_s and d in scores_idx.columns else np.nan
        e_raw.append(round(float(v), 6) if pd.notna(v) else None)
        v = ranks_idx.at[club, d] if has_r and d in ranks_idx.columns else np.nan
        r_raw.append(None if (pd.isna(v) or str(v) == 'NR') else int(v))
    history[club] = {'e': list(reversed(e_raw)), 'r': list(reversed(r_raw))}

all_history = {'dates': dates_ordered, 'history': history}
print(f"    {len(dates_ordered)} dates, {len(history)} clubs")

# Fix any dates where ALL clubs have None rank (missing rank sheet column)
# Fill from the nearest non-None value to prevent chart gaps
for date_idx in range(len(dates_ordered)):
    none_ranks = sum(1 for d in history.values()
                    if len(d['r']) > date_idx and d['r'][date_idx] is None)
    total = sum(1 for d in history.values() if len(d['r']) > date_idx)
    if total > 0 and none_ranks / total > 0.9:  # >90% None = missing column
        filled = 0
        for club, data in history.items():
            r = data['r']
            if len(r) > date_idx and r[date_idx] is None:
                # Try next dates first, then previous
                replacement = None
                for j in range(date_idx + 1, min(date_idx + 4, len(r))):
                    if r[j] is not None:
                        replacement = r[j]; break
                if replacement is None:
                    for j in range(date_idx - 1, max(date_idx - 4, -1), -1):
                        if r[j] is not None:
                            replacement = r[j]; break
                if replacement is not None:
                    r[date_idx] = replacement
                    filled += 1
        if filled > 0:
            print(f"    ⚠ Fixed missing rank column at {dates_ordered[date_idx]} ({filled} clubs filled)")

# ═══════════════════════════════════════════════════════════════
# STEP 3: BUILD CLUBS ARRAY
# ═══════════════════════════════════════════════════════════════
print("\n[3/5] Building CLUBS array...")

# season_pct from Club Records
records_by_club = {}
for _, row in df_records.iterrows():
    records_by_club[str(row['Club'])] = [
        None if pd.isna(row.get(s)) else round(float(row[s]) * 100, 1)
        for s in cfg.SEASON_LIST
    ]

# season_league from Matches
league_matches = df_matches[df_matches['Type'] == 'League']
club_season_levels = defaultdict(lambda: defaultdict(list))
for _, row in league_matches.iterrows():
    season = str(row['Season']) if pd.notna(row['Season']) else None
    if season and season in cfg.SEASON_LIST:
        for team, level in [(row['Team 1'], row['Team 1 Level']),
                            (row['Team 2'], row['Team 2 Level'])]:
            if pd.notna(team) and pd.notna(level):
                club_season_levels[str(team)][season].append(str(level))

# Total match count per club (all competitions, all tracked seasons) —
# used to hold off milestone alerts for clubs new to the dataset until
# they've built up a real sample size.
match_counts = Counter()
for _, row in df_matches.iterrows():
    if pd.notna(row.get('Team 1')):
        match_counts[str(row['Team 1'])] += 1
    if pd.notna(row.get('Team 2')):
        match_counts[str(row['Team 2'])] += 1

# Form column names
result_cols = ['< Result'] + [f'<{i} Result' for i in range(2, 11)]
opp_cols    = ['<Opp']     + [f'<{i} Opp'    for i in range(2, 11)]
elo_cols    = ['< Match', '<2 Matches', '<3 Matches', '<4 Matches', '<5 Matches',
               '<6 Matches', '<7 Matches', '< 8 Matches', '<9 Matches', '<10 Matches']

def parse_form(row, n):
    results = []
    for i in range(n):
        r_col = result_cols[i] if i < len(result_cols) else None
        o_col = opp_cols[i]    if i < len(opp_cols)    else None
        e_col = elo_cols[i]    if i < len(elo_cols)     else None
        if r_col not in row.index or pd.isna(row.get(r_col)):
            break
        r_val = str(row[r_col]).strip().upper()
        if r_val not in ('W', 'D', 'L'):
            break
        entry = {
            'result': r_val,
            'opponent': str(row[o_col]).strip() if o_col and pd.notna(row.get(o_col)) else ''
        }
        if e_col and pd.notna(row.get(e_col)):
            try:
                entry['elo_change'] = round(float(row[e_col]), 1)
            except:
                entry['elo_change'] = 0.0
        results.append(entry)
    return results

CLUBS = []
for _, row in df_rank.iterrows():
    club        = str(row['Club']).strip()
    league_code = str(row['League']).strip()
    country     = re.sub(r'_\d+$', '', league_code)  # ENG_2 → ENG

    e_list = history.get(club, {'e': []})['e']
    r_list = history.get(club, {'r': []})['r']

    valid_e = [(i, v) for i, v in enumerate(e_list) if v is not None]
    valid_r = [(i, v) for i, v in enumerate(r_list) if v is not None]

    if valid_e:
        max_e = max(v for _, v in valid_e)
        min_e = min(v for _, v in valid_e)
        ath_elo_date = next(dates_ordered[i] for i, v in reversed(valid_e) if v == max_e)
        atl_elo_date = next(dates_ordered[i] for i, v in reversed(valid_e) if v == min_e)
    else:
        max_e = min_e = float(row['ELO'])
        ath_elo_date = atl_elo_date = dates_ordered[-1]

    if valid_r:
        min_r = min(v for _, v in valid_r)
        max_r = max(v for _, v in valid_r)
        ath_rank_date = next(dates_ordered[i] for i, v in reversed(valid_r) if v == min_r)
        atl_rank_date = next(dates_ordered[i] for i, v in reversed(valid_r) if v == max_r)
    else:
        min_r = max_r = int(row['#'])
        ath_rank_date = atl_rank_date = dates_ordered[-1]

    # Career-high rank streak — how many consecutive most-recent matchdays the
    # club has held its own all-time-best rank (min_r), the date that current
    # run began, and (if they've been at min_r before) the date they last held
    # it prior to this run. Only computed when currently AT the best rank.
    rank_streak = 0
    rank_streak_since = None
    rank_prev_since = None
    if r_list and r_list[-1] is not None and r_list[-1] == min_r:
        idx = len(r_list) - 1
        while idx >= 0 and r_list[idx] == min_r:
            idx -= 1
        rank_streak = (len(r_list) - 1) - idx
        rank_streak_since = dates_ordered[idx + 1]
        j = idx
        while j >= 0 and r_list[j] != min_r:
            j -= 1
        if j >= 0:
            rank_prev_since = dates_ordered[j]
    # Being #1 is just the min_r==1 case of the same streak, so it falls out for free.
    top1_streak = rank_streak if (r_list and r_list[-1] == 1) else 0

    tier_counts  = [sum(1 for v in r_list if v is not None and v <= t) for t in cfg.TIER_THRESHOLDS]
    elo_history  = e_list[-200:]
    rank_history = r_list[-200:]

    sp = records_by_club.get(club, [None] * 6)
    sl = []
    for s in cfg.SEASON_LIST:
        levels = club_season_levels.get(club, {}).get(s, [])
        sl.append(Counter(levels).most_common(1)[0][0] if levels else None)
    for i in range(len(cfg.SEASON_LIST)):
        if sp[i] is not None and sl[i] is None:
            sl[i] = league_code

    cy_w  = int(row['W CY'])  if pd.notna(row.get('W CY'))  else 0
    cy_d  = int(row['D CY'])  if pd.notna(row.get('D CY'))  else 0
    cy_l  = int(row['L CY'])  if pd.notna(row.get('L CY'))  else 0
    cy_gp = int(row['GP CY']) if pd.notna(row.get('GP CY')) else 0
    cy_pts = cy_w * 3 + cy_d
    cy_pct = round(cy_pts / (cy_gp * 3) * 100, 1) if cy_gp > 0 else 0.0

    all_elos = [v for v in e_list if v is not None]
    if len(all_elos) > 1 and max(all_elos) > min(all_elos):
        elo_pct = round((float(row['ELO']) - min(all_elos)) / (max(all_elos) - min(all_elos)) * 100, 1)
    else:
        elo_pct = 50.0

    prev_rank = int(row['PR']) if pd.notna(row.get('PR')) and str(row.get('PR')).strip() != 'NR' else int(row['#'])

    CLUBS.append({
        'rank':       int(row['#']),
        'prev_rank':  prev_rank,
        'rank_change': prev_rank - int(row['#']),
        'club':       club,
        'league_code': league_code,
        'country':    country,
        'league':     str(row.get('Current Season', '')).strip(),
        'elo':        round(float(row['ELO']), 1),
        'elo_pct':    elo_pct,
        'elo_change': round(float(row['Score ▲/▼']), 1) if pd.notna(row.get('Score ▲/▼')) else 0.0,
        'last_result': str(row['Last Result']).strip() if pd.notna(row.get('Last Result')) else '',
        'opponent':   str(row['Opponent']).strip() if pd.notna(row.get('Opponent')) else '',
        'score':      str(row.get('Score', '')).strip() if pd.notna(row.get('Score')) else '',
        'cy_w':  cy_w,  'cy_d':  cy_d,  'cy_l':  cy_l,
        'cy_pts': cy_pts, 'cy_pct': cy_pct, 'cy_gp': cy_gp,
        'form5':  parse_form(row, 5),
        'form10': parse_form(row, 10),
        'elo_history':  elo_history,
        'rank_history': rank_history,
        'all_time_high_elo':       round(max_e, 1),
        'all_time_high_elo_date':  ath_elo_date,
        'all_time_low_elo':        round(min_e, 1),
        'all_time_low_elo_date':   atl_elo_date,
        'all_time_high_rank':      min_r,
        'all_time_high_rank_date': ath_rank_date,
        'all_time_low_rank':       max_r,
        'all_time_low_rank_date':  atl_rank_date,
        'times_no1': tier_counts[0],
        'top5':      tier_counts[1],
        'top10':     tier_counts[2],
        'top50':     tier_counts[4],
        'tier_counts':    tier_counts,
        'season_pct':     sp,
        'season_league':  sl,
        'rank_streak':        rank_streak,
        'rank_streak_since':  rank_streak_since,
        'rank_prev_since':    rank_prev_since,
        'top1_streak':        top1_streak,
    })

# Ensure clubs are sorted by rank regardless of spreadsheet order
CLUBS.sort(key=lambda x: x['rank'])
print(f"    Built {len(CLUBS)} clubs")

# ═══════════════════════════════════════════════════════════════
# STEP 3b: MILESTONE DETECTION
# ═══════════════════════════════════════════════════════════════
print("\n[3b] Checking for milestones...")

TODAY = dates_ordered[-1]
RANK_THRESHOLDS = [1, 10, 25, 50, 100]
MIN_MATCHES_FOR_MILESTONES = 20
milestones = []

for c in CLUBS:
    club = c['club']
    played = match_counts.get(club, 0)

    # A club's rank can shift purely because OTHER clubs moved — that's not
    # a milestone for this club. Only flag when their own rating actually
    # changed this update, which only happens if they played a match.
    e_list = history.get(club, {'e': []})['e']
    played_this_update = (
        len(e_list) >= 2
        and e_list[-1] is not None
        and e_list[-2] is not None
        and e_list[-1] != e_list[-2]
    )

    # Only flag genuine milestones — wait until a club has a real sample size,
    # so newly-added clubs (e.g. a new confederation rollout) don't immediately
    # trigger "all-time high" off a handful of matches.
    if played >= MIN_MATCHES_FOR_MILESTONES and played_this_update:
        if c['all_time_high_elo_date'] == TODAY:
            milestones.append(f"  \u25B2 ALL-TIME HIGH RATING  — {club}: {c['all_time_high_elo']} (rank #{c['rank']})")
        if c['all_time_low_elo_date'] == TODAY:
            milestones.append(f"  \u25BC ALL-TIME LOW RATING   — {club}: {c['all_time_low_elo']} (rank #{c['rank']})")
        if c['all_time_high_rank_date'] == TODAY:
            milestones.append(f"  \u25B2 ALL-TIME HIGH RANK    — {club}: #{c['all_time_high_rank']}")
        if c['all_time_low_rank_date'] == TODAY:
            milestones.append(f"  \u25BC ALL-TIME LOW RANK     — {club}: #{c['all_time_low_rank']}")

    # Round-number rank threshold crossings (entering/leaving top N)
    prev_rank, rank = c['prev_rank'], c['rank']
    if played >= MIN_MATCHES_FOR_MILESTONES and played_this_update and prev_rank != rank:
        for t in RANK_THRESHOLDS:
            if prev_rank > t and rank <= t:
                milestones.append(f"  \u2605 ENTERED TOP {t:<4}     — {club}: #{prev_rank} \u2192 #{rank}")
            elif prev_rank <= t and rank > t:
                milestones.append(f"  \u2606 DROPPED OUT OF TOP {t:<4} — {club}: #{prev_rank} \u2192 #{rank}")

if milestones:
    print(f"    {len(milestones)} milestone(s) this update:")
    for m in milestones:
        print(m)
else:
    print("    No milestones this update.")

# Append to a running log so milestones aren't lost once the console scrolls
try:
    log_path = os.path.join(SCRIPT_DIR, 'milestones_log.txt')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n=== {TODAY} ===\n")
        if milestones:
            for m in milestones:
                f.write(m.strip() + '\n')
        else:
            f.write("  (no milestones)\n")
except Exception as e:
    print(f"    WARNING: Could not write milestones_log.txt — {e}")

# ═══════════════════════════════════════════════════════════════
# STEP 4: INJECT INTO index_base.html AND SAVE
# ═══════════════════════════════════════════════════════════════
print("\n[4/5] Injecting data and saving...")

with open(BASE_HTML, encoding='utf-8') as f:
    html = f.read()

def replace_const(html, name, value):
    marker = f'const {name}='
    idx = html.find(marker)
    if idx < 0:
        print(f"    WARNING: {name} not found in HTML — skipping")
        return html
    val_start = idx + len(marker)
    while html[val_start] in ' \t\n': val_start += 1
    open_c  = html[val_start]
    close_c = ']' if open_c == '[' else '}'
    depth = 0; in_str = False; esc = False; i = val_start
    while i < len(html):
        c = html[i]
        if esc:            esc = False
        elif c == '\\' and in_str: esc = True
        elif c == '"' and not esc: in_str = not in_str
        elif not in_str:
            if c == open_c:  depth += 1
            elif c == close_c:
                depth -= 1
                if depth == 0: val_end = i + 1; break
        i += 1
    return html[:val_start] + json.dumps(value, separators=(',', ':')) + html[val_end:]

CHART_DATES_60  = dates_ordered[-60:]
CHART_DATES_200 = dates_ordered[-200:]

html = replace_const(html, 'CLUBS',          CLUBS)
html = replace_const(html, 'CHART_DATES_60', CHART_DATES_60)
html = replace_const(html, 'CHART_DATES_200',CHART_DATES_200)

# Update club count and date string
club_count = f'{len(CLUBS):,}'
html = re.sub(r'\d[\d,]+ [Cc]lubs', lambda m: f'{club_count} ' + ('Clubs' if m.group().split()[1][0].isupper() else 'clubs'), html)
html = re.sub(r'(<span class="stat-val">)\d[\d,]+(</span><span class="stat-label">Clubs Ra)', lambda m: m.group(1) + club_count + m.group(2), html)
html = re.sub(r'(of <strong>)\d[\d,]+(</strong>)', lambda m: m.group(1) + club_count + m.group(2), html)
today = datetime.now().strftime('%B %-d, %Y') if sys.platform != 'win32' else datetime.now().strftime('%B %d, %Y').replace(' 0', ' ')
for pattern in [r'Updated \w+ \d+, \d{4}']:
    html = re.sub(pattern, f'Updated {today}', html)


# ── South American flags (injected if missing) ────────────────────────────────
SA_FLAGS = {
    'ARG': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="4.67" fill="#74ACDF"/><rect y="4.67" width="20" height="4.67" fill="#fff"/><rect y="9.33" width="20" height="4.67" fill="#74ACDF"/></svg>',
    'BOL': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="4.67" fill="#D52B1E"/><rect y="4.67" width="20" height="4.67" fill="#F9E300"/><rect y="9.33" width="20" height="4.67" fill="#007A3D"/></svg>',
    'BRA': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="14" fill="#009C3B"/><polygon points="10,1.5 18.5,7 10,12.5 1.5,7" fill="#FFDF00"/><circle cx="10" cy="7" r="3" fill="#002776"/></svg>',
    'CHI': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="7" fill="#fff"/><rect y="7" width="20" height="7" fill="#D52B1E"/><rect width="7" height="7" fill="#0032A0"/></svg>',
    'COL': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="7" fill="#FCD116"/><rect y="7" width="20" height="3.5" fill="#003087"/><rect y="10.5" width="20" height="3.5" fill="#CE1126"/></svg>',
    'ECU': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="5.6" fill="#FFD100"/><rect y="5.6" width="20" height="2.8" fill="#003087"/><rect y="8.4" width="20" height="5.6" fill="#CE1126"/></svg>',
    'PAR': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="4.67" fill="#D52B1E"/><rect y="4.67" width="20" height="4.67" fill="#fff"/><rect y="9.33" width="20" height="4.67" fill="#0038A8"/></svg>',
    'PER': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="6.67" height="14" fill="#D91023"/><rect x="6.67" width="6.67" height="14" fill="#fff"/><rect x="13.33" width="6.67" height="14" fill="#D91023"/></svg>',
    'URU': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="14" fill="#fff"/><rect y="2.33" width="20" height="1.56" fill="#75AADB"/><rect y="4.67" width="20" height="1.56" fill="#75AADB"/><rect y="7.0" width="20" height="1.56" fill="#75AADB"/><rect y="9.33" width="20" height="1.56" fill="#75AADB"/><rect y="11.67" width="20" height="1.56" fill="#75AADB"/><rect width="7" height="7" fill="#fff"/><circle cx="3.5" cy="3.5" r="1.2" fill="#F6B40E"/></svg>',
    'VEN': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14"><rect width="20" height="4.67" fill="#FFD700"/><rect y="4.67" width="20" height="4.67" fill="#003087"/><rect y="9.33" width="20" height="4.67" fill="#CF142B"/></svg>',
}
CONMEBOL_CODES = ['ARG', 'BOL', 'BRA', 'CHI', 'COL', 'ECU', 'PAR', 'PER', 'URU', 'VEN']

# Add Luxembourg flag if missing
if 'LUX:`' not in html:
    lux_entry = f"  LUX:`{cfg.LUX_FLAG_SVG}`,"
    lva_pos = html.find("  LVA:`", html.find('SVG_FLAGS={'))
    if lva_pos > 0:
        html = html[:lva_pos] + lux_entry + '\n' + html[lva_pos:]

# Add South American flags if missing
flags_start = html.find('SVG_FLAGS={')
flags_end   = html.find('};', flags_start) + 1
for code, svg in SA_FLAGS.items():
    if f'{code}:`' not in html[flags_start:flags_end]:
        html = html[:flags_end-1] + f'\n  {code}:`{svg}`,' + '\n' + html[flags_end-1:]
        flags_end = html.find('};', flags_start) + 1  # recalculate after insertion

# Add CONMEBOL countries to dropdown if missing
country_sel_start = html.find('id="filter-country"')
country_sel_end   = html.find('</select>', country_sel_start) + len('</select>')
for code in sorted(CONMEBOL_CODES):
    if f'value="{code}"' not in html[country_sel_start:country_sel_end]:
        insert_pos = html.find('</select>', country_sel_start)
        html = html[:insert_pos] + f'<option value="{code}">{code}</option>\n' + html[insert_pos:]
        country_sel_end = html.find('</select>', country_sel_start) + len('</select>')

# Add confederation dropdown if missing
if 'filter-confederation' not in html:
    conf_select = '<select class="filter-select" id="filter-confederation"><option value="">All Confederations</option><option value="UEFA">UEFA (Europe)</option><option value="CONMEBOL">CONMEBOL (South America)</option></select>'
    conf_consts = '\nconst CONMEBOL_COUNTRIES=[\'ARG\',\'BOL\',\'BRA\',\'CHI\',\'COL\',\'ECU\',\'PAR\',\'PER\',\'URU\',\'VEN\'];\nconst UEFA_COUNTRIES=[\'ALB\',\'AND\',\'ARM\',\'AUT\',\'AZE\',\'BEL\',\'BIH\',\'BLR\',\'BUL\',\'CRO\',\'CYP\',\'CZE\',\'DEN\',\'ENG\',\'ESP\',\'EST\',\'FIN\',\'FRA\',\'FRO\',\'GBR\',\'GEO\',\'GER\',\'GRE\',\'HUN\',\'IRL\',\'ISL\',\'ISR\',\'ITA\',\'KAZ\',\'KOS\',\'LTU\',\'LUX\',\'LVA\',\'MKD\',\'MLD\',\'MLT\',\'MNE\',\'NED\',\'NIR\',\'NOR\',\'POL\',\'POR\',\'ROU\',\'RUS\',\'SCO\',\'SMR\',\'SRB\',\'SUI\',\'SVK\',\'SVN\',\'SWE\',\'TUR\',\'UKR\',\'WAL\'];\n'
    # Insert dropdown after country select
    c_sel_end = html.find('</select>', html.find('id="filter-country"')) + len('</select>')
    html = html[:c_sel_end] + '\n    ' + conf_select + html[c_sel_end:]
    # Insert JS constants before applyFilters
    apply_idx = html.rfind('function applyFilters()')
    html = html[:apply_idx] + conf_consts + html[apply_idx:]
    # Update filter logic
    html = html.replace("const country=document.getElementById('filter-country').value;",
        "const country=document.getElementById('filter-country').value;\n  const confederation=document.getElementById('filter-confederation').value;", 1)
    html = html.replace("if(country&&c.country!==country)return false;",
        "if(country&&c.country!==country)return false;\n    if(confederation==='CONMEBOL'&&!CONMEBOL_COUNTRIES.includes(c.country))return false;\n    if(confederation==='UEFA'&&!UEFA_COUNTRIES.includes(c.country))return false;", 1)
    html = html.replace("['search','filter-country','filter-range','filter-result']",
        "['search','filter-country','filter-confederation','filter-range','filter-result']", 1)

# Save outputs
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

with open(OUT_HISTORY, 'w', encoding='utf-8') as f:
    json.dump(all_history, f, separators=(',', ':'))

print(f"    Saved: index.html ({os.path.getsize(OUT_HTML)/1024/1024:.1f} MB)")
print(f"    Saved: all_history.json ({os.path.getsize(OUT_HISTORY)/1024/1024:.1f} MB)")

# ═══════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# STEP 6 (OPTIONAL): GENERATE SEO CLUB PAGES
# ═══════════════════════════════════════════════════════════════
SEO_GEN = os.path.join(SCRIPT_DIR, 'generate_club_pages.py')
if os.path.exists(SEO_GEN) and _seo_gen:
    print("\n[6/6] Generating SEO club pages...")
    try:
        _seo_gen(
            CLUBS,
            output_dir=os.path.join(SCRIPT_DIR, 'clubs'),
            site_base_url='https://matchdayinsights.github.io/MatchdayInsights',
            verbose=True
        )
    except Exception as e:
        print(f"    WARNING: SEO generation failed — {e}")
else:
    print("\n[6/6] generate_club_pages.py not found — skipping SEO pages")

print("\n" + "=" * 60)
print("✓ UPDATE COMPLETE")
print(f"  Clubs:   {len(CLUBS)}")
print(f"  Dates:   {len(dates_ordered)} ({dates_ordered[0]} → {dates_ordered[-1]})")
print("=" * 60)
print("\nNext step: push index.html and all_history.json to GitHub.")


# ═══════════════════════════════════════════════════════════════
# STEP 5: REGENERATE H2H GENERATOR (runs automatically if file exists)
# ═══════════════════════════════════════════════════════════════
H2H_FILE = os.path.join(SCRIPT_DIR, 'h2h_generator.html')

if os.path.exists(H2H_FILE):
    print("\n[5/5] Regenerating h2h_generator.html...")
    try:
        with open(H2H_FILE, encoding='utf-8') as f:
            h2h = f.read()

        # Build updated data strings
        slim_clubs = json.dumps(
            {c['club']: {'e': c['elo'], 'r': c['rank'], 'c': c['country'], 'lc': c['league_code']}
             for c in CLUBS},
            separators=(',', ':')
        )

        h20_dict = {}
        for club in CLUBS:
            name = club['club']
            e_vals = all_history['history'].get(name, {}).get('e', [])
            h20_dict[name] = [round(v, 1) if v is not None else None for v in e_vals[-20:]]
        slim_h20   = json.dumps(h20_dict, separators=(',', ':'))
        slim_dates = json.dumps(dates_ordered[-20:], separators=(',', ':'))

        # Extract flags from the freshly written index.html
        with open(OUT_HTML, encoding='utf-8') as f:
            idx_src = f.read()
        flags_dict = {}
        flags_start = idx_src.find('SVG_FLAGS={')
        flags_end   = idx_src.find('};', flags_start) + 1
        for m in re.finditer(r'(\w+):`([^`]+)`', idx_src[flags_start:flags_end]):
            flags_dict[m.group(1)] = m.group(2)
        slim_flags = json.dumps(flags_dict, separators=(',', ':'))

        def replace_js_obj(html, const_name, new_value):
            """Replace const NAME={...} with new_value (must start with {)"""
            marker = f'const {const_name}={{'
            idx = html.find(marker)
            if idx < 0:
                return html
            start = idx + len(f'const {const_name}=')
            depth = 0
            i = start
            while i < len(html):
                if html[i] == '{':
                    depth += 1
                elif html[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
                i += 1
            return html[:start] + new_value + html[end:]

        def replace_js_arr(html, const_name, new_value):
            """Replace const NAME=[...] with new_value (must start with [)"""
            marker = f'const {const_name}=['
            idx = html.find(marker)
            if idx < 0:
                return html
            start = idx + len(f'const {const_name}=')
            depth = 0
            i = start
            while i < len(html):
                if html[i] == '[':
                    depth += 1
                elif html[i] == ']':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
                i += 1
            return html[:start] + new_value + html[end:]

        h2h = replace_js_obj(h2h, 'CLUBS', slim_clubs)
        h2h = replace_js_obj(h2h, 'H20',   slim_h20)
        h2h = replace_js_obj(h2h, 'FLAGS',  slim_flags)
        h2h = replace_js_arr(h2h, 'DATES',  slim_dates)

        with open(H2H_FILE, 'w', encoding='utf-8') as f:
            f.write(h2h)

        size_kb = os.path.getsize(H2H_FILE) / 1024
        print(f"    Saved: h2h_generator.html ({size_kb:.0f} KB)")

    except Exception as e:
        print(f"    WARNING: Could not update h2h_generator.html — {e}")
        print("    The file may need to be regenerated manually from Claude.")
else:
    print("\n[5/5] h2h_generator.html not in folder — skipping (place it here to auto-update)")
