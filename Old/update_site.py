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
df_lt      = pd.read_excel(RANK_FILE, sheet_name='League Tables', header=None)
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

    prev_rank = int(row['PR']) if pd.notna(row.get('PR')) else int(row['#'])

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
    })

# Ensure clubs are sorted by rank regardless of spreadsheet order
CLUBS.sort(key=lambda x: x['rank'])
print(f"    Built {len(CLUBS)} clubs")

# ═══════════════════════════════════════════════════════════════
# STEP 4: BUILD LEAGUE TABLES
# ═══════════════════════════════════════════════════════════════
print("\n[4/5] Building LEAGUE_TABLES...")

def ss(v): return str(v).strip() if pd.notna(v) else ''
def si(v):
    try:    return int(v) if pd.notna(v) else 0
    except: return 0

def color_zone(t):
    t = t.lower()
    if 'champions league' in t: return '#1F4E79' if 'qualif' not in t else '#2E5FA3'
    if 'europa league'    in t: return '#833C00' if 'qualif' not in t else '#A04000'
    if 'conference'       in t:
        if 'playoff' in t or 'play-off' in t: return '#4A235A'
        return '#375623' if 'qualif' not in t else '#4A235A'
    if 'relega' in t: return '#A0522D' if ('playoff' in t or 'play-off' in t) else '#7B2C2C'
    if 'promot' in t: return '#2E5FA3' if ('playoff' in t or 'play-off' in t) else '#1F4E79'
    return '#444444'

def parse_zones(cells, nt):
    z, sp = {}, {}
    for cell in cells:
        for part in str(cell).split(','):
            p = part.strip()
            if not p: continue
            m = re.match(r'Top\s+(\d+):\s*(.+)', p, re.I)
            if m:
                n, lbl = int(m.group(1)), m.group(2).strip()
                for i in range(1, n+1): z[str(i)] = {'label': lbl, 'color': color_zone(lbl)}
                continue
            m = re.match(r'(\d+)[-–](\d+)(?:\w*):\s*(.+)', p, re.I)
            if m:
                lo, hi, lbl = int(m.group(1)), int(m.group(2)), m.group(3).strip()
                for i in range(lo, hi+1): z[str(i)] = {'label': lbl, 'color': color_zone(lbl)}
                continue
            m = re.match(r'(\d+)(?:\w*):\s*(.+)', p, re.I)
            if m:
                z[str(int(m.group(1)))] = {'label': m.group(2).strip(), 'color': color_zone(m.group(2))}
                continue
            m = re.match(r'(?:Bottom|Last)\s+(\d+)\s*[:\s]+(.+)', p, re.I)
            if m:
                n, lbl = int(m.group(1)), m.group(2).strip().lstrip(':').strip()
                for i in range(nt-n+1, nt+1): z[str(i)] = {'label': lbl, 'color': color_zone(lbl)}
                continue
            if ':' in p and not re.match(r'^\d', p) and not re.match(r'^(Top|Bottom|Last)', p, re.I):
                cn, lbl = p.split(':', 1)
                sp[cn.strip()] = {'label': lbl.strip(), 'color': color_zone(lbl)}
    return z, sp

def read_teams(nc, cc, rc, start_row):
    teams = []
    r = start_row + 4
    while r < len(df_lt):
        cv, rv = df_lt.iloc[r, cc], df_lt.iloc[r, rc]
        if pd.isna(cv) or not ss(cv): break
        try:   ri = int(rv)
        except: break
        if ri <= 0: break
        teams.append({
            'note': ss(df_lt.iloc[r, nc]), 'club': ss(cv), 'rank': ri,
            'gp': si(df_lt.iloc[r,rc+1]), 'w': si(df_lt.iloc[r,rc+2]),
            'd':  si(df_lt.iloc[r,rc+3]), 'l': si(df_lt.iloc[r,rc+4]),
            'gf': si(df_lt.iloc[r,rc+5]), 'ga': si(df_lt.iloc[r,rc+6]),
            'gd': si(df_lt.iloc[r,rc+7]), 'pts': si(df_lt.iloc[r,rc+8]),
        })
        r += 1
    return teams, r

def read_block(nc, cc, rc):
    results = {}
    r = 0
    while r < len(df_lt):
        code_v = ss(df_lt.iloc[r, nc])
        if not re.match(r'^[A-Z]{2,7}(_\d)?$', code_v):
            r += 1; continue
        code    = code_v
        season  = ss(df_lt.iloc[r, cc])
        tieb    = ss(df_lt.iloc[r+1, nc]) if r+1 < len(df_lt) else ''
        zcells  = [ss(df_lt.iloc[r+2, c]) for c in range(nc, nc+14)
                   if c < df_lt.shape[1] and ss(df_lt.iloc[r+2, c])]
        teams, next_r = read_teams(nc, cc, rc, r)
        if teams:
            teams.sort(key=lambda x: x['rank'])
            zones, specials = parse_zones(zcells, len(teams))
            for t in teams:
                if t['club'] in specials: t['special_zone'] = specials[t['club']]
            results[code] = {'name': code, 'season': season, 'tiebreaker': tieb,
                             'zones': zones, 'teams': teams}
        r = next_r
    return results

# Build regular leagues
LEAGUE_TABLES = {}
for block in cfg.LEAGUE_BLOCKS:
    nc, cc, rc = block
    result = read_block(nc, cc, rc)
    LEAGUE_TABLES.update(result)

# Build playoff leagues
for code, pcfg in cfg.PLAYOFF_LEAGUES.items():
    all_teams = []
    groups_out = {}
    for i, grp in enumerate(pcfg['groups']):
        teams, _ = read_teams(grp['note_col'], grp['club_col'], grp['rank_col'], grp['start_row'])
        zr = grp['zone_row']
        zcells = [ss(df_lt.iloc[zr, c]) for c in range(grp['note_col']-1, grp['note_col']+14)
                  if c < df_lt.shape[1] and ss(df_lt.iloc[zr, c])]
        zones, _ = parse_zones(zcells, len(teams))
        # Fix note leak
        for t in teams:
            if t.get('note') == t['club']: t['note'] = ''
        groups_out[pcfg['group_keys'][i]] = {
            'name': grp['name'], 'zones': zones,
            'teams': sorted(teams, key=lambda x: x['rank'])
        }
        all_teams.extend(teams)

    all_teams.sort(key=lambda x: x['rank'])
    tieb_row = pcfg['tiebreaker_row']
    tieb_col = pcfg['tiebreaker_col']
    tieb = ss(df_lt.iloc[tieb_row, tieb_col]) if tieb_row < len(df_lt) else ''

    club_group = {}
    for gkey, grp_data in groups_out.items():
        for t in grp_data['teams']:
            club_group[t['club']] = gkey

    LEAGUE_TABLES[code] = {
        'name': pcfg['full_name'], 'season': '2025-26',
        'tiebreaker': tieb, 'playoff_format': True,
        'club_group': club_group,
        'teams': all_teams,
        'zones': groups_out[pcfg['group_keys'][0]]['zones'],
        'groups': groups_out,
    }

# Apply zone overrides from config
for code, overrides in cfg.ZONE_OVERRIDES.items():
    if code in LEAGUE_TABLES:
        for rank_str, (label, color) in overrides.items():
            LEAGUE_TABLES[code]['zones'][rank_str] = {'label': label, 'color': color}

# Apply manual notes from config
for code, notes in cfg.MANUAL_NOTES.items():
    league = LEAGUE_TABLES.get(code)
    if not league: continue
    for t in league.get('teams', []):
        if t['club'] in notes: t['note'] = notes[t['club']]
    for grp in league.get('groups', {}).values():
        for t in grp.get('teams', []):
            if t['club'] in notes: t['note'] = notes[t['club']]

# Add eur_rank + elo to all teams
club_lookup = {c['club']: {'rank': c['rank'], 'elo': c['elo']} for c in CLUBS}
for league in LEAGUE_TABLES.values():
    for t in league.get('teams', []):
        info = club_lookup.get(t['club'])
        if info: t['eur_rank'] = info['rank']; t['elo'] = round(info['elo'], 1)
    for grp in league.get('groups', {}).values():
        for t in grp.get('teams', []):
            info = club_lookup.get(t['club'])
            if info: t['eur_rank'] = info['rank']; t['elo'] = round(info['elo'], 1)

print(f"    Built {len(LEAGUE_TABLES)} league tables: {sorted(LEAGUE_TABLES.keys())}")

# ═══════════════════════════════════════════════════════════════
# STEP 5: INJECT INTO index_base.html AND SAVE
# ═══════════════════════════════════════════════════════════════
print("\n[5/5] Injecting data and saving...")

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
html = replace_const(html, 'LEAGUE_TABLES',  LEAGUE_TABLES)
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

# Add Luxembourg flag if missing
if 'LUX:`' not in html:
    lux_entry = f"  LUX:`{cfg.LUX_FLAG_SVG}`,"
    lva_pos = html.find("  LVA:`", html.find('SVG_FLAGS={'))
    if lva_pos > 0:
        html = html[:lva_pos] + lux_entry + '\n' + html[lva_pos:]

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
print("\n" + "=" * 60)
print("✓ UPDATE COMPLETE")
print(f"  Clubs:   {len(CLUBS)}")
print(f"  Leagues: {len(LEAGUE_TABLES)}")
print(f"  Dates:   {len(dates_ordered)} ({dates_ordered[0]} → {dates_ordered[-1]})")
print("=" * 60)
print("\nNext step: push index.html and all_history.json to GitHub.")


# ═══════════════════════════════════════════════════════════════
# STEP 6: REGENERATE H2H GENERATOR (runs automatically if file exists)
# ═══════════════════════════════════════════════════════════════
H2H_FILE = os.path.join(SCRIPT_DIR, 'h2h_generator.html')

if os.path.exists(H2H_FILE):
    print("\n[6/6] Regenerating h2h_generator.html...")
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
    print("\n[6/6] h2h_generator.html not in folder — skipping (place it here to auto-update)")
