"""
MATCHDAY INSIGHTS — Static Club Page Generator
================================================
Generates one SEO-indexed HTML page per club, plus sitemap.xml.
Called from update_site.py on every Monday/Thursday update cycle.

Usage (standalone):
    python generate_club_pages.py

Or called from update_site.py:
    from generate_club_pages import generate_all
    generate_all(CLUBS, output_dir='clubs', site_base_url='https://matchdayinsights.github.io/MatchdayInsights')
"""

import json, re, os, html as html_module
from datetime import datetime

SITE_BASE = 'https://matchdayinsights.github.io/MatchdayInsights'
SITE_NAME = 'Matchday Insights'

# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(name):
    s = name.lower()
    for src, dst in [('à','a'),('á','a'),('â','a'),('ã','a'),('ä','a'),('å','a'),
                     ('è','e'),('é','e'),('ê','e'),('ë','e'),
                     ('ì','i'),('í','i'),('î','i'),('ï','i'),
                     ('ò','o'),('ó','o'),('ô','o'),('õ','o'),('ö','o'),('ø','o'),
                     ('ù','u'),('ú','u'),('û','u'),('ü','u'),
                     ('ý','y'),('ÿ','y'),('ñ','n'),('ç','c'),
                     ('ß','ss'),('æ','ae'),('œ','oe'),
                     ('ğ','g'),('ş','s'),('ı','i'),('ć','c'),('č','c'),('ž','z'),
                     ('š','s'),('đ','d'),('ł','l'),('ő','o'),('ű','u'),]:
        s = s.replace(src, dst)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')

def fmt_date(d):
    if not d or d == 'None':
        return '—'
    try:
        return datetime.strptime(str(d), '%m/%d/%Y').strftime('%b %d, %Y')
    except:
        return str(d)

def rank_suffix(r):
    r = int(r)
    if 11 <= r % 100 <= 13: return f'#{r}th'
    return f'#{r}' + {1:'st',2:'nd',3:'rd'}.get(r%10,'th')

LEAGUE_NAMES = {
    'ENG':'Premier League','ENG_2':'Championship','ENG_3':'League One','ENG_4':'League Two',
    'ESP':'La Liga','ESP_2':'Segunda División','GER':'Bundesliga','GER_2':'2. Bundesliga',
    'GER_3':'3. Liga','ITA':'Serie A','ITA_2':'Serie B','FRA':'Ligue 1',
    'POR':'Primeira Liga','NED':'Eredivisie','TUR':'Süper Lig','BEL':'First Division A',
    'GRE':'Super League','NOR':'Eliteserien','SCO':'Scottish Premiership',
    'RUS':'Russian Premier League','UKR':'Ukrainian Premier League','CZE':'1. liga',
    'SUI':'Super League','AUT':'Bundesliga','DEN':'Superliga','SWE':'Allsvenskan',
    'POL':'Ekstraklasa','HUN':'OTP Bank Liga','ROU':'Liga I','BUL':'First League',
    'CRO':'HNL','SRB':'SuperLiga','SVK':'Fortuna Liga','SVN':'PrvaLiga',
    'BIH':'Premier League','MKD':'First Football League','MNE':'Meridian Premijer liga',
    'ALB':'Kategoria Superiore','GEO':'Erovnuli Liga','ARM':'Armenian Premier League',
    'AZE':'Premyer Liqa','KAZ':'Premier League','BLR':'Vysshaya Liga',
    'MLD':'Divizia Naţională','ISR':'Premier League','CYP':'First Division',
    'ISL':'Úrvalsdeild','IRL':'League of Ireland Premier Division','NIR':'NIFL Premiership',
    'WAL':'Cymru Premier','SCO':'Scottish Premiership','FRO':'Faroese Premier League',
    'LUX':'BGL Ligue','MLT':'Premier League','SMR':'Campionato Sammarinese',
    'AND':'Primera Divisió','KOS':'Football Superleague of Kosovo',
    'LTU':'A lyga','LVA':'Virsliga','EST':'Meistriliiga',
    'GBR':'Great Britain','NIR':'NIFL Premiership',
    'BRA':'Brasileirão Série A','BRA_2':'Série B','BRA_3':'Série C',
    'ARG':'Primera División','ARG_2':'Primera Nacional',
    'COL':'Liga BetPlay','CHI':'Primera División','URU':'Primera División',
    'PER':'Liga 1','ECU':'LigaPro','BOL':'División Profesional',
    'PAR':'División Profesional','VEN':'Liga FUTVE',
}

COUNTRY_NAMES = {
    'ENG':'England','SCO':'Scotland','WAL':'Wales','NIR':'Northern Ireland',
    'GER':'Germany','ESP':'Spain','ITA':'Italy','FRA':'France','POR':'Portugal',
    'NED':'Netherlands','BEL':'Belgium','TUR':'Turkey','GRE':'Greece',
    'RUS':'Russia','UKR':'Ukraine','POL':'Poland','CZE':'Czech Republic',
    'AUT':'Austria','SUI':'Switzerland','NOR':'Norway','SWE':'Sweden',
    'DEN':'Denmark','FIN':'Finland','HUN':'Hungary','BUL':'Bulgaria',
    'ROU':'Romania','CRO':'Croatia','SRB':'Serbia','SVN':'Slovenia',
    'SVK':'Slovakia','ISR':'Israel','CYP':'Cyprus','KAZ':'Kazakhstan',
    'IRL':'Ireland','ISL':'Iceland','GEO':'Georgia','ALB':'Albania',
    'ARM':'Armenia','AZE':'Azerbaijan','BIH':'Bosnia & Herzegovina',
    'BLR':'Belarus','EST':'Estonia','MKD':'North Macedonia','MLT':'Malta',
    'FRO':'Faroe Islands','KOS':'Kosovo','LTU':'Lithuania','LVA':'Latvia',
    'GBR':'Great Britain','MLD':'Moldova','SMR':'San Marino','AND':'Andorra',
    'MNE':'Montenegro','LUX':'Luxembourg',
    'BRA':'Brazil','ARG':'Argentina','COL':'Colombia','CHI':'Chile',
    'URU':'Uruguay','PER':'Peru','ECU':'Ecuador','BOL':'Bolivia',
    'PAR':'Paraguay','VEN':'Venezuela',
}

# ── HTML template ─────────────────────────────────────────────────────────────

def make_club_page(club, slug, related_clubs, site_base):
    name      = html_module.escape(club['club'])
    rank      = club['rank']
    elo       = club['elo']
    elo_chg   = club.get('elo_change', 0) or 0
    chg_str   = f"+{elo_chg:.1f}" if elo_chg > 0 else f"{elo_chg:.1f}"
    chg_color = '#3dba5e' if elo_chg >= 0 else '#e84466'
    lc        = club.get('league_code', '')
    country   = club.get('country', lc)
    league    = LEAGUE_NAMES.get(lc, lc)
    country_n = COUNTRY_NAMES.get(country, country)
    ath_elo_v = club.get('all_time_high_elo')
    atl_elo_v = club.get('all_time_low_elo')
    ath_elo   = f"{ath_elo_v:.1f}" if ath_elo_v is not None else '—'
    atl_elo   = f"{atl_elo_v:.1f}" if atl_elo_v is not None else '—' 
    ath_rank  = club.get('all_time_high_rank', '—')
    atl_rank  = club.get('all_time_low_rank', '—')
    ath_elo_d = fmt_date(club.get('all_time_high_elo_date'))
    atl_elo_d = fmt_date(club.get('all_time_low_elo_date'))
    ath_rnk_d = fmt_date(club.get('all_time_high_rank_date'))
    atl_rnk_d = fmt_date(club.get('all_time_low_rank_date'))

    form5     = club.get('form5', [])
    form_html = ''
    for m in form5:
        r = m.get('result', '')
        opp = html_module.escape(m.get('opponent', ''))
        ec  = m.get('elo_change')
        ec_str  = f'+{ec:.1f}' if ec and ec >= 0 else (f'{ec:.1f}' if ec else '')
        ec_col  = '#3dba5e' if ec and ec >= 0 else '#e84466'
        res_col = {'W':'#3dba5e','D':'#7880a0','L':'#e84466'}.get(r,'#555')
        form_html += f'''<div class="form-row">
          <span class="form-badge" style="background:{res_col}">{r}</span>
          <span class="form-opp">{opp}</span>
          {'<span class="form-pts" style="color:'+ec_col+'">'+ec_str+'</span>' if ec_str else ''}
        </div>'''

    related_html = ''
    for rc in related_clubs:
        rc_slug = slugify(rc['club'])
        rc_name = html_module.escape(rc['club'])
        related_html += f'<a href="{site_base}/clubs/{rc_slug}.html" class="related-link">#{rc["rank"]} {rc_name}</a>\n'

    title       = f"{name} Rating & Ranking | {SITE_NAME}"
    description = (f"{name} is ranked #{rank} in the {SITE_NAME} Global Club Rankings "
                   f"with a rating of {elo:.1f}. Track their performance, history, and form.")
    canonical   = f"{site_base}/clubs/{slug}.html"
    spa_link    = f"{site_base}/index.html#club={slug}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<link rel="stylesheet" href="{site_base}/club-page.css">
</head>
<body>
<nav class="site-nav">
  <a href="{site_base}/index.html" class="nav-logo">
    <span class="nav-brand">MATCHDAY INSIGHTS</span>
    <span class="nav-sub">Global Club Rankings</span>
  </a>
</nav>

<main class="club-page">
  <div class="club-header">
    <div class="club-meta">{country_n} · {league}</div>
    <h1 class="club-name">{name}</h1>
    <div class="club-rank">#{rank} Global Ranking</div>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Rating</div>
      <div class="stat-val">{elo:.1f}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">This Update</div>
      <div class="stat-val" style="color:{chg_color}">{chg_str}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">All-Time High Rating</div>
      <div class="stat-val">{ath_elo}</div>
      <div class="stat-date">{ath_elo_d}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">All-Time Low Rating</div>
      <div class="stat-val">{atl_elo}</div>
      <div class="stat-date">{atl_elo_d}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Best Rank</div>
      <div class="stat-val">#{ath_rank}</div>
      <div class="stat-date">{ath_rnk_d}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Worst Rank</div>
      <div class="stat-val">#{atl_rank}</div>
      <div class="stat-date">{atl_rnk_d}</div>
    </div>
  </div>

  {f'''<div class="section">
    <h2>Last 5 Results</h2>
    <div class="form-list">{form_html}</div>
  </div>''' if form5 else ''}

  <div class="cta-box">
    <p>View {name}'s full rating history, charts, and comparisons on the live rankings.</p>
    <a href="{spa_link}" class="cta-btn">Open Full Profile →</a>
  </div>

  {f'''<div class="section">
    <h2>Similar Clubs</h2>
    <div class="related-grid">{related_html}</div>
  </div>''' if related_clubs else ''}
</main>

<footer class="site-footer">
  <p>© {SITE_NAME} · <a href="{site_base}/index.html">Global Club Rankings</a> · Updated Mon &amp; Thu</p>
</footer>
</body>
</html>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --dark: #1a1a2e;
  --body: #f5f6f2;
  --green: #3dba5e;
  --red: #e84466;
  --muted: #7880a0;
  --text: #1a1a2e;
  --card: #ffffff;
  --border: #e0e4ee;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: var(--body); color: var(--text); }
a { color: var(--green); text-decoration: none; }
a:hover { text-decoration: underline; }

.site-nav { background: var(--dark); padding: 14px 24px; display: flex; align-items: center; }
.nav-logo { display: flex; flex-direction: column; }
.nav-brand { font-size: 18px; font-weight: 900; color: #dde0ec; letter-spacing: 1px; }
.nav-sub { font-size: 11px; color: var(--green); letter-spacing: 1px; }

.club-page { max-width: 860px; margin: 0 auto; padding: 32px 20px 60px; }
.club-header { margin-bottom: 28px; }
.club-meta { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.club-name { font-size: 42px; font-weight: 900; line-height: 1; letter-spacing: -1px; }
.club-rank { font-size: 16px; color: var(--muted); margin-top: 6px; }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 32px; }
.stat-card { background: var(--card); border-radius: 10px; padding: 16px; border: 1px solid var(--border); }
.stat-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.stat-val { font-size: 28px; font-weight: 700; line-height: 1; }
.stat-date { font-size: 11px; color: var(--muted); margin-top: 4px; }

.section { margin-bottom: 32px; }
.section h2 { font-size: 18px; font-weight: 700; margin-bottom: 14px; }
.form-list { display: flex; flex-direction: column; gap: 8px; }
.form-row { display: flex; align-items: center; gap: 10px; background: var(--card); border-radius: 8px; padding: 10px 14px; border: 1px solid var(--border); }
.form-badge { width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; color: #fff; flex-shrink: 0; }
.form-opp { font-size: 15px; flex: 1; }
.form-pts { font-size: 14px; font-weight: 700; }

.cta-box { background: var(--dark); border-radius: 12px; padding: 28px; text-align: center; margin-bottom: 32px; }
.cta-box p { color: #dde0ec; margin-bottom: 16px; font-size: 15px; }
.cta-btn { background: var(--green); color: #fff; padding: 12px 28px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block; }
.cta-btn:hover { text-decoration: none; opacity: 0.9; }

.related-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.related-link { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; font-size: 14px; color: var(--text); }
.related-link:hover { border-color: var(--green); text-decoration: none; }

.site-footer { background: var(--dark); padding: 20px 24px; text-align: center; }
.site-footer p { color: var(--muted); font-size: 13px; }
.site-footer a { color: var(--green); }

@media (max-width: 600px) {
  .club-name { font-size: 30px; }
  .stats-grid { grid-template-columns: 1fr 1fr; }
}
"""

# ── Sitemap ───────────────────────────────────────────────────────────────────

def make_sitemap(clubs, slugs, site_base):
    today = datetime.now().strftime('%Y-%m-%d')
    urls  = [f"""  <url>
    <loc>{site_base}/index.html</loc>
    <lastmod>{today}</lastmod>
    <priority>1.0</priority>
  </url>"""]
    for club in clubs:
        slug = slugs[club['club']]
        urls.append(f"""  <url>
    <loc>{site_base}/clubs/{slug}.html</loc>
    <lastmod>{today}</lastmod>
    <priority>0.7</priority>
  </url>""")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(urls) + '\n</urlset>'


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_all(clubs, output_dir='clubs', site_base_url=SITE_BASE, verbose=True):
    """
    Generate all club pages, sitemap.xml, and club-page.css.
    Call from update_site.py after building CLUBS.

    Args:
        clubs:          The CLUBS list (already sorted by rank)
        output_dir:     Where to write club HTML files (relative to script dir)
        site_base_url:  Base URL for canonical/OG tags
    """
    os.makedirs(output_dir, exist_ok=True)

    # Build slug map (club name → slug, disambiguated by league if needed)
    slug_map = {}
    seen = {}
    for c in clubs:
        slug = slugify(c['club'])
        if slug in seen:
            slug = f"{slug}-{c['league_code'].lower().replace('_','-')}"
        seen[slug] = True
        slug_map[c['club']] = slug

    # Build lookup by league and country for related clubs
    by_league   = {}
    by_country  = {}
    by_rank     = sorted(clubs, key=lambda x: x['rank'])
    for c in clubs:
        by_league.setdefault(c['league_code'], []).append(c)
        by_country.setdefault(c['country'], []).append(c)

    # Generate pages
    count = 0
    for c in clubs:
        slug = slug_map[c['club']]

        # Related: up to 2 from same league, then 2 from same country, then nearest rank
        related = []
        for rc in by_league.get(c['league_code'], []):
            if rc['club'] != c['club'] and len(related) < 2:
                related.append(rc)
        for rc in by_country.get(c['country'], []):
            if rc['club'] != c['club'] and rc not in related and len(related) < 4:
                related.append(rc)
        if len(related) < 4:
            rank_pos = next((i for i,x in enumerate(by_rank) if x['club']==c['club']), 0)
            for offset in [-2,-1,1,2,3,-3]:
                idx = rank_pos + offset
                if 0 <= idx < len(by_rank):
                    rc = by_rank[idx]
                    if rc['club'] != c['club'] and rc not in related and len(related) < 4:
                        related.append(rc)

        page_html = make_club_page(c, slug, related[:4], site_base_url)
        out_path  = os.path.join(output_dir, f"{slug}.html")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(page_html)
        count += 1

    # Write sitemap
    sitemap = make_sitemap(clubs, slug_map, site_base_url)
    with open('sitemap.xml', 'w', encoding='utf-8') as f:
        f.write(sitemap)

    # Write CSS
    with open('club-page.css', 'w', encoding='utf-8') as f:
        f.write(CSS)

    if verbose:
        print(f"    Generated {count} club pages → {output_dir}/")
        print(f"    Generated sitemap.xml ({count+1} URLs)")
        print(f"    Generated club-page.css")

    return slug_map


if __name__ == '__main__':
    # Standalone run — reads clubs from index.html in same folder
    import sys
    script_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(script_dir, 'index.html')

    if not os.path.exists(index_path):
        print("ERROR: index.html not found in script folder")
        sys.exit(1)

    with open(index_path, encoding='utf-8') as f:
        html_src = f.read()

    idx = html_src.find('const CLUBS=[')
    i   = idx + len('const CLUBS=')
    depth=0; in_str=False; esc=False; start=i
    while i < len(html_src):
        c = html_src[i]
        if esc: esc=False
        elif c=='\\' and in_str: esc=True
        elif c=='"' and not esc: in_str=not in_str
        elif not in_str:
            if c=='[': depth+=1
            elif c==']':
                depth-=1
                if depth==0: end=i+1; break
        i+=1

    clubs_data = json.loads(html_src[start:end])
    print(f"Loaded {len(clubs_data)} clubs from index.html")
    generate_all(clubs_data, output_dir=os.path.join(script_dir, 'clubs'), verbose=True)
    print("Done.")
