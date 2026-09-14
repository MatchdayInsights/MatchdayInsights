"""
MATCHDAY INSIGHTS — 55 LEAGUES · 55 DAYS
Self-service graphic generator template

USAGE:
1. Fill in the CONFIG section below
2. Run: python3 summer_series_template.py
3. Two PNGs will be saved in the same folder

REQUIREMENTS:
- pip install playwright
- playwright install chromium
- mdi_logo_b64.txt in same folder (or update LOGO_PATH)
- clubs_data.json in same folder (or update CLUBS_PATH)
- all_history.json in same folder (or update HISTORY_PATH)
"""

import asyncio, json, re
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
LOGO_PATH    = 'mdi_logo_b64.txt'
CLUBS_PATH   = 'clubs_data.json'
HISTORY_PATH = 'all_history.json'

# Auto-load league data
from league_config import get_league_config

# ─────────────────────────────────────────────
# CONFIG — EDIT THIS SECTION FOR EACH LEAGUE
# ─────────────────────────────────────────────
# ── EDIT THESE LINES EACH TIME ────────────────
COUNTRY_CODE = 'LTU'   # 3-letter code — country, league, colors, flag auto-loaded
_lc = get_league_config(COUNTRY_CODE)

CONFIG = {
    # Auto-loaded — do not edit
    'country_code':   COUNTRY_CODE,
    'country':        _lc['country'],
    'league_name':    _lc['league_name'],
    'calendar_type':  _lc['calendar_type'],
    'color_primary':  _lc['color_primary'],
    'color_secondary':_lc['color_secondary'],
    'flag_svg':       _lc['flag'],

    'day':    11,       # Day number in the series (1-55)
    'season': '2026',   # e.g. '2025-26' or '2026'

    # Season status: 'complete', 'in_progress', 'last_match'
    'season_status': 'in_progress',
    'matchday_note': 'Matchday 16 of 36 Played',

    # League table
    # Each row: (name, gp, w, d, l, gf, ga, gd, pts, zone, note)
    # zone options: 'ucl', 'uecl', 'uecl_cup', 'rel_po', 'rel_z', 'rel', 'surv', ''
    # note options: 'C' (champion), 'R' (relegated), 'P' (promoted), ''
    'teams': [
        ('FC Džiugas',       16,9,3,4,  25,16, 9,  30, 'ucl_pot',''),
        ('Kauno Žalgiris',   16,8,5,3,  34,13, 21, 29, 'ucl_pot',''),
        ('FK TransINVEST',   16,8,4,4,  29,18, 11, 28, '',       ''),
        ('FK Sūduva',        16,6,7,3,  23,13, 10, 25, '',       ''),
        ('Banga Gargždai',   16,6,5,5,  22,13, 9,  23, '',       ''),
        ('FK Žalgiris',      16,6,4,6,  21,18, 3,  22, '',       ''),
        ('FK Panevėžys',     16,6,3,7,  17,25,-8,  21, '',       ''),
        ('FC Hegelmann',     16,3,8,5,  17,24,-7,  17, '',       ''),
        ('FA Šiauliai',      16,3,8,5,  14,23,-9,  17, '',       ''),
        ('FK Riteriai',      16,0,3,13,  3,42,-39,  3, 'rel_z',  ''),
    ],

    # Zone colors (can override defaults here if needed)
    # Leave as None to use defaults
    'zone_color_overrides': None,

    # Split table into sections? (e.g. Championship split)
    # Set to None for no split, or list of (section_label, color, num_rows)
    # e.g. [('Section A — Top 6', '#1a6fc4', 6), ('Section B — Bottom 6', '#7880a0', 6)]
    'table_sections': None,

    # Legend items: list of (color, label)
    'legend': [
        ('#1a6fc4', 'Title contention zone'),
        ('#e84466', 'Relegation zone'),
    ],
    'legend_note': 'European spots based on 2025 season results.',

    # Hero section (summary graphic)
    'hero_club':   'FC Džiugas',   # Big name at top of summary
    'hero_hook':   'FC Džiugas lead after 16 matchdays. FK TransINVEST back in the top flight after a year away — sitting 3rd.',

    # Champion card
    'champion_club':  'Kauno Žalgiris',   # Last confirmed champion (or current leader)
    'champion_label': '2025 Champion · Current Runners-Up',
    'champion_note':  'First ever A Lyga title in 2025. Now in CL qualifying.',

    # European qualifiers — list of dicts
    'qualifiers': [
        {'club': 'Kauno Žalgiris',  'comp': 'Champions League',  'round': 'First Qualifying Round',  'note': '2nd straight season'},
        {'club': 'FK Panevėžys',    'comp': 'Conference League', 'round': 'Second Qualifying Round', 'note': 'Via Cup · Back after 1 year'},
        {'club': 'FC Hegelmann',    'comp': 'Conference League', 'round': 'First Qualifying Round',  'note': '2nd straight season'},
        {'club': 'FK Žalgiris',     'comp': 'Conference League', 'round': 'First Qualifying Round',  'note': '15th straight season'},
    ],
    'qualifiers_note': 'All qualifiers based on 2025 season results.',

    # Relegated clubs — list of (name, note)
    'relegated': [
        # ('Club Name', 'Relegated after X seasons'),
    ],

    # Output filenames
    'output_table':   'output_table.png',
    'output_summary': 'output_summary.png',
}

# ─────────────────────────────────────────────
# CONSTANTS (don't edit)
# ─────────────────────────────────────────────
DARK      = '#1a1a2e'
BODY      = '#f5f6f2'
GREEN_ACC = '#3dba5e'
RED_ACC   = '#e84466'
GRID      = "32px 26px 1fr 52px 52px 28px 28px 28px 28px 36px 36px 38px 46px"

START_IDX = 459 if CONFIG['calendar_type'] == 'calendar' else 408

ZONE_COLORS = {
    'ucl':     '#1a6fc4',
    'ucl_pot': '#1a6fc4',
    'uecl':    '#3dba5e',
    'uecl_cup':'#3dba5e',
    'rel_po':  '#f0a500',
    'rel_z':   '#e84466',
    'rel':     '#e84466',
    'surv':    '#f0a500',
    '':        'transparent',
}
if CONFIG['zone_color_overrides']:
    ZONE_COLORS.update(CONFIG['zone_color_overrides'])

BANNER_COLORS = {
    'complete':    ('#3dba5e', '✅'),
    'in_progress': ('#e8a020', '⏳'),
    'last_match':  ('#f0a500', '⚠️'),
}

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
with open(LOGO_PATH) as f:
    logo_b64 = f.read().strip()
with open(CLUBS_PATH) as f:
    all_clubs = json.load(f)
with open(HISTORY_PATH) as f:
    ah = json.load(f)

dates     = ah['dates']
country   = CONFIG['country_code']
lookup    = {c['club']: c for c in all_clubs if c.get('country') == country}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def season_change(club_name):
    e = ah['history'].get(club_name, {}).get('e', [])
    if not e: return 0.0, 0.0, 0.0
    start_val = e[START_IDX] if len(e) > START_IDX else None
    if start_val is None:
        for i in range(START_IDX, len(e)):
            if e[i] is not None:
                start_val = e[i]; break
    end_val = e[-1]
    if start_val is None or end_val is None: return 0.0, 0.0, 0.0
    return start_val, end_val, round(end_val - start_val, 1)

def sparkline(club_name, color, w=284, h=52):
    e = ah['history'].get(club_name, {}).get('e', [])
    start_i = START_IDX
    if len(e) > START_IDX and e[START_IDX] is None:
        for i in range(START_IDX, len(e)):
            if e[i] is not None:
                start_i = i; break
    seg = e[start_i:]
    nums = [v for v in seg if v is not None]
    if len(nums) < 2: return ''
    lo, hi = min(nums), max(nums)
    rng = hi - lo if hi != lo else 1
    valid = [(i, v) for i, v in enumerate(seg) if v is not None]
    pts_xy = [(i / (len(seg)-1) * w, h - ((v-lo)/rng)*(h-6)-3) for i,v in valid]
    path = 'M ' + ' L '.join(f'{x:.1f},{y:.1f}' for x,y in pts_xy)
    fill = path + f' L {pts_xy[-1][0]:.1f},{h} L {pts_xy[0][0]:.1f},{h} Z'
    gid  = re.sub(r'[^a-zA-Z0-9]', '', club_name)[:8]
    return f'''<svg width="{w}" height="{h}" style="display:block">
      <defs><linearGradient id="g{gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{color}" stop-opacity="0.22"/>
        <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
      </linearGradient></defs>
      <path d="{fill}" fill="url(#g{gid})"/>
      <path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="{pts_xy[-1][0]:.1f}" cy="{pts_xy[-1][1]:.1f}" r="4" fill="{color}" stroke="#fff" stroke-width="1.5"/>
    </svg>'''

def stat_row(label, value, val_color='#1a1a2e', bold=False):
    fw = '700' if bold else '500'
    return f'''<div style="display:flex;justify-content:space-between;align-items:baseline;padding:5px 0;border-bottom:1px solid #f0f0f0">
      <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:#9098b8">{label}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:{fw};color:{val_color}">{value}</div>
    </div>'''

def card(header_label, emoji, body_html, border_color):
    return f'''<div style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 8px rgba(0,0,0,0.07)">
      <div style="background:{DARK};padding:11px 18px;border-left:5px solid {border_color};display:flex;align-items:center;gap:8px">
        <span style="font-size:17px">{emoji}</span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:#dde0ec;letter-spacing:1.5px;text-transform:uppercase">{header_label}</span>
      </div>
      <div style="padding:18px">{body_html}</div>
    </div>'''

def header_bar(title_right, subtitle_right):
    c = CONFIG
    return f'''<div style="background:{DARK};padding:18px 40px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:16px">
      <div style="background:rgba(255,255,255,0.07);border-radius:10px;padding:7px 10px">
        <img src="data:image/jpeg;base64,{logo_b64}" style="height:44px;width:auto">
      </div>
      <div>
        <div style="font-family:'Barlow Condensed',sans-serif;font-size:26px;font-weight:900;color:#dde0ec;letter-spacing:1px;line-height:1">MATCHDAY INSIGHTS</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#7880a0;margin-top:3px">European Club Rankings</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:14px">
      {c['flag_svg']}
      <div style="text-align:right">
        <div style="font-family:'Barlow Condensed',sans-serif;font-size:22px;font-weight:900;color:#dde0ec;line-height:1">{title_right}</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#7880a0;margin-top:2px">{subtitle_right}</div>
      </div>
    </div>
  </div>'''

def top_bottom_bars(reverse=False):
    p, s = CONFIG['color_primary'], CONFIG['color_secondary']
    if reverse: p, s = s, p
    return f'''<div style="height:6px;display:flex">
    <div style="flex:1;background:{p}"></div>
    <div style="flex:1;background:{s}"></div>
  </div>'''

def footer_bar(left_text):
    return f'''<div style="background:{DARK};padding:14px 40px;display:flex;align-items:center;justify-content:space-between">
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;color:#dde0ec">{left_text}</div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:18px;font-weight:700;color:#3dba5e">matchdayinsights.github.io/MatchdayInsights</div>
  </div>'''

# ─────────────────────────────────────────────
# TABLE ROW
# ─────────────────────────────────────────────
def make_row(i, team):
    name, gp, w, d, l, gf, ga, gd, pts, zone, note = team
    cd = lookup.get(name, {})
    eur = cd.get('rank', '—')
    elo = cd.get('elo', 0)
    elo_str = f'{elo:.0f}' if elo else '—'
    bg = '#edeeed' if i % 2 == 0 else BODY
    dim = 'opacity:0.5;' if zone == 'rel' else ''
    zc = ZONE_COLORS.get(zone, 'transparent')
    gd_str = f'+{gd}' if gd > 0 else str(gd)
    note_html = ''
    if note == 'C':
        note_html = '<span style="display:inline-block;background:#1a6fc4;color:#fff;font-size:11px;font-weight:700;padding:1px 5px;border-radius:3px;vertical-align:middle">C</span>'
    elif note == 'R':
        note_html = '<span style="display:inline-block;background:#e84466;color:#fff;font-size:11px;font-weight:700;padding:1px 5px;border-radius:3px;vertical-align:middle">R</span>'
    elif note == 'P':
        note_html = '<span style="display:inline-block;background:#3dba5e;color:#fff;font-size:11px;font-weight:700;padding:1px 5px;border-radius:3px;vertical-align:middle">P</span>'
    return f'''<div style="display:grid;grid-template-columns:{GRID};gap:0;
        padding:7px 12px;background:{bg};border-bottom:1px solid rgba(0,0,0,0.06);
        align-items:center;position:relative;{dim}">
      <div style="position:absolute;left:0;top:0;bottom:0;width:4px;background:{zc};border-radius:2px 0 0 2px"></div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#555;text-align:center">{i+1}</div>
      <div style="text-align:center">{note_html}</div>
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:17px;font-weight:700;color:#1a1a2e;padding-left:4px">{name}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#555;text-align:right;padding-right:6px">#{eur}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#555;text-align:right;padding-right:6px">{elo_str}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#555;text-align:center">{gp}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#2ecc71;text-align:center;font-weight:700">{w}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#7880a0;text-align:center">{d}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#e84466;text-align:center">{l}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#555;text-align:center">{gf}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#555;text-align:center">{ga}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#555;text-align:center">{gd_str}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:900;color:#1a1a2e;text-align:center">{pts}</div>
    </div>'''

# ─────────────────────────────────────────────
# BUILD TABLE GRAPHIC
# ─────────────────────────────────────────────
def build_table_html():
    c = CONFIG
    banner_color, banner_icon = BANNER_COLORS[c['season_status']]
    status_text = {
        'complete':    f"✅ {c['season']} Season Complete · {c['matchday_note']}",
        'in_progress': f"⏳ {c['season']} Season In Progress · {c['matchday_note']}",
        'last_match':  f"⚠️ {c['season']} Season · Final Matchday Remaining · {c['matchday_note']}",
    }[c['season_status']]

    col_header = f'''<div style="display:grid;grid-template-columns:{GRID};gap:0;
        padding:8px 12px;background:#1a1a2e;color:rgba(255,255,255,0.6);
        font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:0.5px">
      <div style="text-align:center">#</div><div></div>
      <div style="padding-left:4px">Club</div>
      <div style="text-align:right;padding-right:6px">Eur.#</div>
      <div style="text-align:right;padding-right:6px">Rating</div>
      <div style="text-align:center">GP</div><div style="text-align:center">W</div>
      <div style="text-align:center">D</div><div style="text-align:center">L</div>
      <div style="text-align:center">GF</div><div style="text-align:center">GA</div>
      <div style="text-align:center">GD</div><div style="text-align:center">Pts</div>
    </div>'''

    if c['table_sections']:
        rows_html = ''
        team_list = list(c['teams'])
        offset = 0
        for sec_label, sec_color, sec_count in c['table_sections']:
            rows_html += f'''<div style="padding:8px 16px 4px;background:{BODY};border-top:2px solid {sec_color}">
              <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{sec_color};letter-spacing:2px;text-transform:uppercase">{sec_label}</div>
            </div>'''
            for i, team in enumerate(team_list[:sec_count]):
                rows_html += make_row(i + offset, team)
            team_list = team_list[sec_count:]
            offset += sec_count
    else:
        rows_html = ''.join(make_row(i, t) for i, t in enumerate(c['teams']))

    legend_html = ''.join(f'''<div style="display:flex;align-items:center;gap:6px;
        font-family:'JetBrains Mono',monospace;font-size:13px;color:#555">
      <div style="width:10px;height:10px;border-radius:2px;background:{lc};flex-shrink:0"></div>{ll}
    </div>''' for lc, ll in c['legend'])

    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:{BODY};width:1080px}}</style>
</head><body><div style="width:1080px;background:{BODY}">
  {top_bottom_bars()}
  {header_bar(f"{c['country'].upper()} — {c['league_name']}", f"Day {c['day']:02d} / 55 · Final Standings {c['season']}" if c['season_status'] == 'complete' else f"Day {c['day']:02d} / 55 · {c['season']} Season")}
  <div style="background:{banner_color};padding:10px 40px;text-align:center">
    <div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#1a0a00">{status_text}</div>
  </div>
  {col_header}
  {rows_html}
  <div style="padding:12px 16px;display:flex;gap:16px;flex-wrap:wrap;background:{BODY};border-top:1px solid #ddd">{legend_html}</div>
  {'<div style="padding:8px 16px 10px;background:' + BODY + ';font-family:JetBrains Mono,monospace;font-size:12px;color:#9098b8;border-top:1px solid #eee">' + c['legend_note'] + '</div>' if c.get('legend_note') else ''}
  {footer_bar(f"55 Leagues · 55 Days · Day {c['day']:02d}/55")}
  {top_bottom_bars(reverse=True)}
</div></body></html>'''

# ─────────────────────────────────────────────
# BUILD SUMMARY GRAPHIC
# ─────────────────────────────────────────────
def build_summary_html():
    c = CONFIG

    # Auto-calculate top performer and biggest drop
    results = []
    for club_name in lookup:
        start, end, chg = season_change(club_name)
        if chg != 0.0:
            results.append((club_name, start, end, chg))
    results.sort(key=lambda x: x[3], reverse=True)

    top_club,  top_start,  top_end,  top_chg  = results[0]  if results else ('—', 0, 0, 0)
    drop_club, drop_start, drop_end, drop_chg = results[-1] if results else ('—', 0, 0, 0)

    top_cd  = lookup.get(top_club, {})
    drop_cd = lookup.get(drop_club, {})
    champ_cd = lookup.get(c['champion_club'], {})

    # Top 5 with pts% bars
    top5 = sorted(lookup.values(), key=lambda x: x['rank'])[:5]
    top5_rows = ''
    for i, club_data in enumerate(top5):
        _, _, chg = season_change(club_data['club'])
        sp = club_data.get('season_pct', [None, None])
        sp_val = sp[1] if sp and len(sp) > 1 and sp[1] is not None else 0
        arrow = f'<span style="color:#2ecc71">▲{abs(chg):.0f}</span>' if chg > 0 else f'<span style="color:#e84466">▼{abs(chg):.0f}</span>'
        bg = '#f8f9ff' if i % 2 == 0 else '#fff'
        bar_color = '#3dba5e' if sp_val >= 60 else '#f0a500' if sp_val >= 40 else '#e84466'
        top5_rows += f'''<div style="padding:8px 10px;background:{bg};border-radius:6px;margin-bottom:4px">
          <div style="display:grid;grid-template-columns:24px 1fr 72px 64px 52px;align-items:center;gap:8px;margin-bottom:5px">
            <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#9098b8;font-weight:700">{i+1}</div>
            <div style="font-family:'Barlow Condensed',sans-serif;font-size:17px;font-weight:700;color:#1a1a2e">{club_data["club"]}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:#1a1a2e;text-align:right">#{club_data["rank"]}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:14px;color:#1a1a2e;text-align:right">{club_data["elo"]:.0f}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:13px;text-align:right">{arrow}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;padding-left:32px">
            <div style="flex:1;height:6px;background:#eee;border-radius:3px;overflow:hidden">
              <div style="width:{sp_val}%;height:100%;background:{bar_color};border-radius:3px"></div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#9098b8;white-space:nowrap">{sp_val}% pts won</div>
          </div>
        </div>'''

    # Champion card
    champ_sp = champ_cd.get('season_pct', [None, None])
    champ_sp_val = champ_sp[1] if champ_sp and len(champ_sp) > 1 else 'N/A'
    _, _, champ_chg = season_change(c['champion_club'])
    champ_body = f'''
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:32px;font-weight:900;color:{c['color_primary']};margin-bottom:14px;line-height:1">{c['champion_club'].upper()}</div>
      {stat_row('European Rank', f'#{champ_cd.get("rank","—")}', '#1a1a2e', True)}
      {stat_row('Rating', f'{champ_cd.get("elo",0):.1f}', '#1a1a2e', True)}
      {stat_row('Points Won %', f'{champ_sp_val}%', c['color_primary'], True)}
      {stat_row('Season Rating Change', f'{champ_chg:+.1f}', GREEN_ACC if champ_chg >= 0 else RED_ACC)}
      <div style="margin-top:12px;background:#f5f8ff;border-radius:8px;padding:10px 12px;
          font-family:'Barlow Condensed',sans-serif;font-size:16px;color:#444;line-height:1.4">
        {c['champion_note']}
      </div>'''

    # Top performer card
    perf_body = f'''
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:32px;font-weight:900;color:#1a8042;margin-bottom:4px;line-height:1">{top_club.upper()}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:44px;font-weight:700;color:{GREEN_ACC};line-height:1;margin-bottom:14px">+{top_chg:.1f}</div>
      {sparkline(top_club, GREEN_ACC, 284, 52)}
      <div style="margin-top:10px">
      {stat_row('Rating (Start → Now)', f'{top_start:.1f} → {top_end:.1f}', '#1a1a2e')}
      {stat_row('European Rank', f'#{top_cd.get("rank","—")}', '#1a1a2e')}
      </div>'''

    # Biggest drop card
    drop_body = f'''
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:32px;font-weight:900;color:#c82a48;margin-bottom:4px;line-height:1">{drop_club.upper()}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:44px;font-weight:700;color:{RED_ACC};line-height:1;margin-bottom:14px">{drop_chg:.1f}</div>
      {sparkline(drop_club, RED_ACC, 284, 52)}
      <div style="margin-top:10px">
      {stat_row('Rating (Start → Now)', f'{drop_start:.1f} → {drop_end:.1f}', '#1a1a2e')}
      {stat_row('European Rank', f'#{drop_cd.get("rank","—")}', RED_ACC)}
      </div>'''

    # European picture card
    euro_body = f'''
      <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#9098b8;letter-spacing:1.5px;
          margin-bottom:8px;display:grid;grid-template-columns:24px 1fr 72px 64px 52px;gap:8px;padding:0 10px">
        <div></div><div>Club</div><div style="text-align:right">Eur.#</div>
        <div style="text-align:right">Rating</div><div style="text-align:right">Δ</div>
      </div>
      {top5_rows}
      <div style="margin-top:8px;padding:8px 12px;background:#f8f9ff;border-radius:8px;
          font-family:'JetBrains Mono',monospace;font-size:12px;color:#7880a0">
        Bars show % of available points won in {c['season']} season
      </div>'''

    # Qualifiers card
    comp_colors = {'Champions League': '#1a6fc4', 'Conference League': '#3dba5e'}
    comp_bg     = {'Champions League': '#f0f5ff', 'Conference League': '#f0fff5'}
    comp_border = {'Champions League': 'rgba(26,111,196,0.2)', 'Conference League': 'rgba(61,186,94,0.2)'}
    qual_cols = ''.join(f'''<div style="text-align:center;padding:14px 10px;background:{comp_bg.get(q['comp'],'#f5f5f5')};
        border-radius:10px;border:1px solid {comp_border.get(q['comp'],'#ddd')}">
      <div style="font-size:16px;margin-bottom:5px">{"🏆" if q['comp']=="Champions League" else "🌍"}</div>
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:14px;font-weight:900;color:{comp_colors.get(q['comp'],'#333')};line-height:1.1">{q['club'].upper()}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{comp_colors.get(q['comp'],'#555')};font-weight:700;margin-top:5px">{q['comp']}</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#7880a0;margin-top:2px">{q['round']}</div>
      <div style="font-family:'Barlow Condensed',sans-serif;font-size:14px;color:#666;margin-top:4px">{q['note']}</div>
    </div>''' for q in c['qualifiers'])
    n_cols = len(c['qualifiers'])
    qual_body = f'''<div style="display:grid;grid-template-columns:{'1fr ' * n_cols};gap:12px">{qual_cols}</div>
      {'<div style="margin-top:10px;padding:8px 12px;background:#fff9f0;border-radius:8px;font-family:JetBrains Mono,monospace;font-size:12px;color:#7880a0">' + c['qualifiers_note'] + '</div>' if c.get('qualifiers_note') else ''}'''

    # Relegation card (optional)
    rel_section = ''
    if c['relegated']:
        rel_cols = ''.join(f'''<div>
          <div style="font-family:'Barlow Condensed',sans-serif;font-size:19px;font-weight:900;color:{RED_ACC}">{name.upper()}</div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:#888;margin-top:2px">{note}</div>
        </div>''' for name, note in c['relegated'])
        n = min(len(c['relegated']), 3)
        rel_body_html = f'<div style="display:grid;grid-template-columns:{"1fr " * n};gap:12px">{rel_cols}</div>'
        rel_section = f'''<div style="padding:0 40px;margin-bottom:16px">
          {card('Relegation', '⬇️', rel_body_html, RED_ACC)}
        </div>'''

    status_label = '⏳' if c['season_status'] == 'in_progress' else '🏆'
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:{BODY};width:1080px}}</style>
</head><body><div style="width:1080px;background:{BODY};overflow:hidden">
  {top_bottom_bars()}
  {header_bar(f"{c['country'].upper()} — {c['league_name']}", f"Day {c['day']:02d} / 55 · {c['season']} Season in Review")}
  <div style="padding:34px 40px 24px;background:{BODY}">
    <div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:{GREEN_ACC};letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">
      {status_label} {c['country']} · {c['league_name']} · {c['season']}
    </div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:80px;font-weight:900;color:{c['color_primary']};line-height:0.86;letter-spacing:-1px;margin-bottom:10px">{c['hero_club'].upper()}</div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:28px;font-weight:700;color:#7880a0;letter-spacing:0.5px;margin-bottom:8px">{c['country']}</div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:16px;color:#444;letter-spacing:0.3px">{c['hero_hook']}</div>
  </div>
  <div style="padding:0 40px;display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
    {card(c['champion_label'], '🏆', champ_body, c['color_primary'])}
    {card('Top Performer · Highest Rating Gain', '📈', perf_body, GREEN_ACC)}
    {card('Biggest Drop · Largest Rating Loss', '📉', drop_body, RED_ACC)}
    {card('European Picture · Top 5 with Points Won %', '🌍', euro_body, c['color_primary'])}
  </div>
  <div style="padding:0 40px;margin-bottom:16px">
    {card('European Qualifiers', '✈️', qual_body, GREEN_ACC)}
  </div>
  {rel_section}
  <div style="background:{DARK};padding:18px 40px;display:flex;align-items:center;justify-content:space-between">
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:20px;font-weight:700;color:#dde0ec">
      {c['country']} · Day {c['day']:02d} of 55 · #55LeaguesSummer
    </div>
    <div style="font-family:'Barlow Condensed',sans-serif;font-size:20px;font-weight:700;color:{GREEN_ACC}">
      matchdayinsights.github.io/MatchdayInsights
    </div>
  </div>
  {top_bottom_bars(reverse=True)}
</div></body></html>'''

# ─────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────
async def render_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for html, outpath, label in [
            (build_table_html(),   CONFIG['output_table'],   'Table'),
            (build_summary_html(), CONFIG['output_summary'], 'Summary'),
        ]:
            page = await browser.new_page(device_scale_factor=2)
            await page.set_viewport_size({"width": 1080, "height": 900})
            await page.set_content(html, wait_until='networkidle')
            h = await page.evaluate('document.body.scrollHeight')
            await page.set_viewport_size({"width": 1080, "height": h})
            await page.screenshot(path=outpath, full_page=True)
            await page.close()
            print(f'{label} → {outpath} ({h}px)')
        await browser.close()

asyncio.run(render_all())
