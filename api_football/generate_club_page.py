"""
generate_club_page.py

Generates one static club profile page (HTML) using club-page.css.
This is the SINGLE-PAGE prototype for review before batch-generating all
~4,116 pages. Run standalone: python3 generate_club_page.py <team_id>
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from last_12_months import compute_last_12_months
from season_by_season import compute_season_by_season, get_league_lookup
from league_table import load_league_table, list_available_seasons, find_continental_competitions, load_table_from_path
from league_lookup import format_season_display
from group_ranks import compute_group_ranks
from country_codes import flag_span, country_name
from streaks import compute_active_streaks
from bracket import build_bracket, load_fixtures_rows, FIXTURES_DIR, find_continental_competitions_in_fixtures

DATA_DIR = Path("/mnt/user-data/uploads")
OUT_DATA_DIR = Path("/mnt/user-data/outputs")
HISTORY_DIR = Path("/home/claude/history_full")
if not HISTORY_DIR.exists() or not any(HISTORY_DIR.iterdir()):
    HISTORY_DIR = Path("/home/claude/history")
MATCH_LOG_DIR = Path("/home/claude/match_log")
OUT_DIR = Path("/home/claude/site_preview/clubs")
BASE_URL = "https://matchdayinsights.github.io/MatchdayInsights"

with open(DATA_DIR / "club_metadata.json") as f:
    META = json.load(f)
RANKINGS_PATH = Path("/home/claude/rankings_run/rankings.json")
if not RANKINGS_PATH.exists():
    RANKINGS_PATH = DATA_DIR / "rankings.json"
with open(RANKINGS_PATH) as f:
    RANKINGS = json.load(f)
with open(OUT_DATA_DIR / "slug_registry.json") as f:
    SLUGS = json.load(f)
GROUP_RANKS = compute_group_ranks(RANKINGS)

# rank-ordered list of tracked team_ids, for "related clubs" (nearby rank)
TRACKED_BY_RANK = sorted(
    (tid for tid, r in RANKINGS.items() if "rank" in r),
    key=lambda tid: RANKINGS[tid]["rank"],
)


def fmt_elo(v):
    return f"{v:.1f}"


def fmt_date_short(mdY):
    # "10/27/2025" -> "Oct 27, 2025"
    dt = datetime.strptime(mdY, "%m/%d/%Y")
    return dt.strftime("%b %-d, %Y")


TIER_THRESHOLDS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]


def pick_relevant_tiers(tier_counts, best_rank, n=3):
    """
    Returns n consecutive (threshold, count) pairs anchored around the
    club's actual all-time-high rank, instead of always showing the
    hardcoded elite Top5/10/50 brackets (which read 0/0/0 for the vast
    majority of clubs and tell you nothing about that club specifically).

    Threshold 1 is deliberately excluded here - the "Times #1" stat card
    already covers that exact case, so including "Top 1" as one of these
    three would just duplicate it.
    """
    thresholds = TIER_THRESHOLDS[1:]
    counts = tier_counts[1:]
    idx = next((i for i, t in enumerate(thresholds) if best_rank <= t),
               len(thresholds) - 1)
    start = max(0, min(idx, len(thresholds) - n))
    return list(zip(thresholds[start:start + n], counts[start:start + n]))


def build_season_by_season_section(team_id: str) -> str:
    log_path = MATCH_LOG_DIR / f"{team_id}.json"
    if not log_path.exists():
        return ""
    with open(log_path) as f:
        log = json.load(f)
    rows = compute_season_by_season(log["matches"])
    if not rows:
        return ""

    bars = []
    for r in rows:
        bars.append(f'''
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 7px;">
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700; width: 52px; flex-shrink: 0;">{r["season_display"]}</div>
        <div style="font-size: 8.5px; color: var(--muted); background: var(--surface2); border: 1px solid var(--border2); border-radius: 4px; padding: 2px 5px; flex-shrink: 0; max-width: 96px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{r["league_name"]}">{r["league_name"]}</div>
        <div style="flex: 1; height: 14px; background: var(--surface2); border-radius: 3px; overflow: hidden;">
          <div style="width: {r["pts_pct"]:.1f}%; height: 100%; background: var(--green);"></div>
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: var(--text2); width: 40px; text-align: right; flex-shrink: 0;">{r["pts_pct"]:.0f}%</div>
      </div>''')

    return f'''
    <div class="section">
      <h2>Points Won — Season by Season</h2>
      <div class="stat-card" style="padding: 12px 14px; max-width: 60%;">
        {"".join(bars)}
      </div>
    </div>'''


def _table_html(table: dict, team_id: str) -> str:
    rows_html = []
    for r in table["rows"]:
        is_this_club = r["team_id"] == team_id
        row_style = 'background: var(--green-dim); font-weight: 700;' if is_this_club else ''
        rows_html.append(f'''
        <tr style="{row_style}">
          <td style="padding: 6px 8px; text-align: center;">{r["rank"]}</td>
          <td style="padding: 6px 8px;">{r["team"]}</td>
          <td style="padding: 6px 8px; text-align: center;">{r["played"]}</td>
          <td style="padding: 6px 8px; text-align: center;">{r["won"]}</td>
          <td style="padding: 6px 8px; text-align: center;">{r["drawn"]}</td>
          <td style="padding: 6px 8px; text-align: center;">{r["lost"]}</td>
          <td style="padding: 6px 8px; text-align: center;">{r["goal_diff"]}</td>
          <td style="padding: 6px 8px; text-align: center; font-weight: 700;">{r["points"]}</td>
        </tr>''')
    return "".join(rows_html)


def build_league_table_section(team_id: str) -> str:
    log_path = MATCH_LOG_DIR / f"{team_id}.json"
    if not log_path.exists():
        return ""
    with open(log_path) as f:
        log = json.load(f)
    league_matches = [m for m in log["matches"] if m.get("competition_type") == "league"]
    if not league_matches:
        return ""

    most_recent = max(league_matches, key=lambda m: m["date"])
    league_id, current_season = most_recent.get("league_id"), most_recent.get("season")
    if not league_id or not current_season:
        return ""

    lookup = get_league_lookup()
    league_info = lookup.get(league_id, {})
    country = league_info.get("country")
    if not country:
        return ""

    # gather every available domestic season for this league_id
    seasons = list_available_seasons(country, league_id)
    domestic_tables = {}
    for season in seasons:
        t = load_league_table(country, league_id, season, team_id=team_id)
        if t:
            domestic_tables[season] = t

    if not domestic_tables:
        return ""

    default_season = current_season if current_season in domestic_tables else seasons[0]

    # gather continental competitions this club appears in
    continental = find_continental_competitions(team_id)
    continental_tables = {}
    for c in continental:
        t = load_table_from_path(c["path"], team_id=team_id)
        if t:
            # continental competitions run on UEFA's Jul-Jun cycle -
            # "World" isn't in SINGLE_CALENDAR_YEAR_COUNTRIES so this
            # correctly renders e.g. "2025-26" instead of the raw "2025"
            season_display = format_season_display(c["season"], "World", c["competition_name"])
            key = f'{c["competition_name"]} {season_display}'
            continental_tables[key] = t

    # build embedded data: {option_value: {group_name, rows_html}}
    all_tables = {}
    for season, t in domestic_tables.items():
        all_tables[f"league:{season}"] = {
            "label": f"{league_info.get('name', 'League')} — {t['group_name']} ({format_season_display(season, country)})",
            "html": _table_html(t, team_id),
        }
    for key, t in continental_tables.items():
        all_tables[f"continental:{key}"] = {
            "label": f"{key} — {t['group_name']}",
            "html": _table_html(t, team_id),
        }

    default_key = f"league:{default_season}"

    options_html = "\n".join(
        f'<option value="{key}"{" selected" if key == default_key else ""}>{data["label"]}</option>'
        for key, data in all_tables.items()
    )

    tables_json = json.dumps({k: v["html"] for k, v in all_tables.items()})

    header = '''
        <tr style="border-bottom: 1px solid var(--border2); color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 9px; text-transform: uppercase;">
          <th style="padding: 6px 8px; text-align: center;">#</th>
          <th style="padding: 6px 8px; text-align: left;">Club</th>
          <th style="padding: 6px 8px; text-align: center;">GP</th>
          <th style="padding: 6px 8px; text-align: center;">W</th>
          <th style="padding: 6px 8px; text-align: center;">D</th>
          <th style="padding: 6px 8px; text-align: center;">L</th>
          <th style="padding: 6px 8px; text-align: center;">GD</th>
          <th style="padding: 6px 8px; text-align: center;">Pts</th>
        </tr>'''

    return f'''
    <div class="section">
      <h2>League Table</h2>
      <script type="application/json" id="tables-{team_id}">{tables_json}</script>
      <div class="stat-card" style="padding: 8px; overflow-x: auto;">
        <div style="padding: 6px 6px 10px;">
          <select id="table-select-{team_id}" class="chart-select" style="width: 100%; max-width: 420px;">
            {options_html}
          </select>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
          <thead>{header}</thead>
          <tbody id="table-body-{team_id}"></tbody>
        </table>
      </div>
    </div>
    <script>
      (function() {{
        var tables = JSON.parse(document.getElementById('tables-{team_id}').textContent);
        var sel = document.getElementById('table-select-{team_id}');
        var body = document.getElementById('table-body-{team_id}');
        function render() {{ body.innerHTML = tables[sel.value]; }}
        sel.addEventListener('change', render);
        render();
      }})();
    </script>'''


def build_bracket_section(team_id: str) -> str:
    """Shows a knockout bracket for any continental competition this club
    appears in AND that has knockout-round data (not every continental
    competition uses a bracket format - some are pure group/league
    tables, e.g. the current FIFA Club World Cup)."""
    continental = find_continental_competitions_in_fixtures(team_id)
    if not continental:
        return ""

    sections = []
    for c in continental:
        fixtures_path = c["path"]
        rows = load_fixtures_rows(fixtures_path)
        bracket = build_bracket(rows, league_id=c["league_id"], season=c["season"])
        if not bracket:
            continue  # this competition has no knockout-round data

        rounds_html = []
        for rnd in bracket:
            ties_html = []
            for t in rnd["ties"]:
                is_a_this_club = t["team_a_id"] == team_id
                is_b_this_club = t["team_b_id"] == team_id
                if t["winner_id"] == t["team_a_id"]:
                    winner_note = "a"
                elif t["winner_id"] == t["team_b_id"]:
                    winner_note = "b"
                else:
                    winner_note = None

                def team_row(name, is_this_club, is_winner):
                    style = 'font-weight: 700;' if is_winner else 'color: var(--text2);'
                    if is_this_club:
                        style += ' background: var(--green-dim);'
                    return f'<div style="padding: 3px 6px; border-radius: 3px; {style}">{name}</div>'

                ties_html.append(f'''
                <div style="background: var(--surface2); border: 1px solid var(--border2); border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; font-size: 11px;">
                  {team_row(t["team_a"], is_a_this_club, winner_note == "a")}
                  <div style="text-align: center; font-family: 'JetBrains Mono', monospace; color: var(--muted); font-size: 9px; margin: 2px 0;">{t["agg_a"]} – {t["agg_b"]}{" (pen.)" if winner_note is None else ""}</div>
                  {team_row(t["team_b"], is_b_this_club, winner_note == "b")}
                </div>''')

            rounds_html.append(f'''
            <div style="min-width: 160px; flex-shrink: 0; display: flex; flex-direction: column; justify-content: center;">
              <div class="stat-label" style="text-align: center; margin-bottom: 8px;">{rnd["round"]}</div>
              {"".join(ties_html)}
            </div>''')

        sections.append(f'''
        <details style="margin-bottom: 14px;">
          <summary style="cursor: pointer; font-size: 13px; font-weight: 600; color: var(--green); padding: 8px 0;">{c["competition_name"]} {format_season_display(c["season"], "World", c["competition_name"])}</summary>
          <div style="display: flex; gap: 14px; overflow-x: auto; padding: 10px 4px;">
            {"".join(rounds_html)}
          </div>
        </details>''')

    if not sections:
        return ""

    return f'''
    <div class="section">
      <h2>Knockout Bracket</h2>
      {"".join(sections)}
    </div>'''


def build_form_rows(form_matches):
    items = []
    for m in form_matches:
        result = m["result"]
        change = m["elo_change"]
        sign = "+" if change > 0 else ""
        pts_class = "green" if change > 0 else ("red" if change < 0 else "")
        items.append(f'''
      <div style="display: flex; align-items: center; gap: 6px; background: var(--surface); border: 1px solid var(--border2); border-radius: 6px; padding: 4px 8px 4px 4px;" title="vs {m["opponent"]}">
        <div class="form-badge {result}" style="width: 20px; height: 20px; font-size: 10px; border-radius: 4px;">{result}</div>
        <div style="font-size: 12px; max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{m["opponent"]}</div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; {f'color: var(--{pts_class})' if pts_class else 'color: var(--text2)'}">{sign}{change:.1f}</div>
      </div>''')
    return "".join(items)


def build_related(team_id, limit=6):
    if team_id not in RANKINGS or "rank" not in RANKINGS[team_id]:
        return ""
    idx = TRACKED_BY_RANK.index(team_id)
    lo = max(0, idx - limit // 2)
    neighbors = [t for t in TRACKED_BY_RANK[lo: lo + limit + 1] if t != team_id][:limit]
    links = []
    for t in neighbors:
        name = RANKINGS[t]["club"]
        slug = SLUGS["by_team_id"][t]["slug"]
        rank = RANKINGS[t]["rank"]
        links.append(f'<a class="related-link" href="{slug}.html">#{rank} {name}</a>')
    return "\n      ".join(links)


CSS_PATH = Path("/home/claude/club-page.css")
if not CSS_PATH.exists():
    CSS_PATH = DATA_DIR / "club-page.css"


def build_l12m_section(team_id: str) -> str:
    log_path = MATCH_LOG_DIR / f"{team_id}.json"
    if not log_path.exists():
        return ""
    with open(log_path) as f:
        log = json.load(f)
    rec = compute_last_12_months(log["matches"])
    if rec is None:
        return ""

    w, d, l, gp = rec["w"], rec["d"], rec["l"], rec["gp"]
    max_pts = gp * 3
    win_w = 100 * (w * 3) / max_pts
    draw_w = 100 * d / max_pts

    return f'''
    <div class="section">
      <h2>Last 12 Months</h2>
      <div class="stat-card" style="padding: 14px 16px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
          <div style="font-size: 14px;">
            <span style="color: var(--green); font-weight: 700;">{w}W</span>
            &nbsp;<span style="color: var(--blue); font-weight: 700;">{d}D</span>
            &nbsp;<span style="color: var(--red); font-weight: 700;">{l}L</span>
            <span style="color: var(--text2);"> &nbsp;·&nbsp; {rec["win_pct"]}% win rate</span>
          </div>
          <div class="stat-date" style="margin-top: 0;">{rec["pts"]} pts · {rec["pts_pct"]}%</div>
        </div>
        <div style="height: 6px; border-radius: 3px; overflow: hidden; display: flex; background: var(--surface2); border: 1px solid var(--border2);">
          <div style="width: {win_w:.2f}%; background: var(--green);"></div>
          <div style="width: {draw_w:.2f}%; background: var(--blue);"></div>
        </div>
      </div>
    </div>'''


CHART_JS = '''
function mdiRenderChart(svgId, selectId, captionId, dates, values, opts) {
  opts = opts || {};
  var invert = !!opts.invert;
  var color = opts.color || 'var(--green)';
  var fmt = opts.fmt || function(v){ return v.toFixed(0); };

  function draw(windowSize) {
    var d = dates, v = values;
    if (windowSize !== 'all') {
      var n = parseInt(windowSize, 10);
      d = dates.slice(-n);
      v = values.slice(-n);
    }
    var n = v.length;
    var width = 780, height = 180, padL = 8, padR = 8, padT = 12, padB = 16;
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
    var span = (hi === lo) ? 1 : (hi - lo);

    function x(i) { return n < 2 ? padL : padL + (width - padL - padR) * i / (n - 1); }
    function y(val) {
      var norm = (val - lo) / span;
      var frac = invert ? norm : (1 - norm);
      return padT + (height - padT - padB) * frac;
    }

    var pts = [];
    for (var i = 0; i < n; i++) pts.push(x(i).toFixed(1) + ',' + y(v[i]).toFixed(1));
    var points = pts.join(' ');
    var areaPoints = x(0).toFixed(1) + ',' + (height - padB) + ' ' + points + ' ' + x(n - 1).toFixed(1) + ',' + (height - padB);

    var mid = (hi + lo) / 2;
    var gridlines = '';
    [hi, mid, lo].forEach(function(val) {
      var gy = y(val).toFixed(1);
      gridlines += '<line x1="' + padL + '" y1="' + gy + '" x2="' + (width - padR) + '" y2="' + gy +
        '" stroke="var(--border)" stroke-width="1"/>' +
        '<text x="' + (width - padR) + '" y="' + (gy - 4) + '" text-anchor="end" ' +
        'font-family="JetBrains Mono, monospace" font-size="9" fill="var(--muted)">' + fmt(val) + '</text>';
    });

    var firstDate = new Date(d[0]).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
    var lastDate = new Date(d[n-1]).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});

    var svg = document.getElementById(svgId);
    svg.innerHTML =
      gridlines +
      '<polygon points="' + areaPoints + '" fill="' + color + '" opacity="0.08"/>' +
      '<polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<circle cx="' + x(0) + '" cy="' + y(v[0]) + '" r="3.5" fill="' + color + '"/>' +
      '<circle cx="' + x(n-1) + '" cy="' + y(v[n-1]) + '" r="3.5" fill="' + color + '"/>' +
      '<text x="' + padL + '" y="' + (height - 2) + '" font-family="JetBrains Mono, monospace" font-size="9" fill="var(--muted)">' + firstDate + '</text>' +
      '<text x="' + (width - padR) + '" y="' + (height - 2) + '" text-anchor="end" font-family="JetBrains Mono, monospace" font-size="9" fill="var(--muted)">' + lastDate + '</text>';

    var cap = document.getElementById(captionId);
    if (cap) cap.textContent = firstDate + ' \u2013 ' + lastDate + ' \u00b7 ' + n + ' updates';
  }

  document.getElementById(selectId).addEventListener('change', function(e) { draw(e.target.value); });
  draw('50');
}
'''


def build_chart_section(team_id: str) -> str:
    history_path = HISTORY_DIR / f"{team_id}.json"
    if not history_path.exists():
        return ""
    with open(history_path) as f:
        hist = json.load(f)

    dates, elos, ranks = hist["dates"], hist["e"], hist["r"]
    total = len(dates)
    if total < 2:
        return ""

    # ISO dates for JS Date() parsing regardless of source format
    dates_iso = [datetime.strptime(d, "%m/%d/%Y").strftime("%Y-%m-%d") for d in dates]

    def options_html(select_id):
        opts = [("50", "Last 50 updates"), ("100", "Last 100 updates"),
                ("250", "Last 250 updates"), ("500", "Last 500 updates"),
                ("all", "All-time")]
        return "\n".join(
            f'<option value="{v}"{" selected" if v == "50" else ""}>{label}</option>'
            for v, label in opts
        )

    data_json = json.dumps({"dates": dates_iso, "e": elos, "r": ranks})

    return f'''
    <div class="section">
      <h2>Rating &amp; Ranking Trend</h2>
      <script type="application/json" id="hist-{team_id}">{data_json}</script>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
        <div class="stat-card" style="padding: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div class="stat-label" style="margin-bottom:0;">Rating</div>
            <select id="rating-select-{team_id}" class="chart-select">
              {options_html(f"rating-select-{team_id}")}
            </select>
          </div>
          <svg id="rating-svg-{team_id}" viewBox="0 0 780 180" width="100%" height="180" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Elo rating trend"></svg>
          <div id="rating-caption-{team_id}" class="stat-date"></div>
        </div>
        <div class="stat-card" style="padding: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div class="stat-label" style="margin-bottom:0;">Ranking</div>
            <select id="rank-select-{team_id}" class="chart-select">
              {options_html(f"rank-select-{team_id}")}
            </select>
          </div>
          <svg id="rank-svg-{team_id}" viewBox="0 0 780 180" width="100%" height="180" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Ranking trend"></svg>
          <div id="rank-caption-{team_id}" class="stat-date"></div>
        </div>
      </div>
    </div>
    <style>
      .chart-select {{
        appearance: none; -webkit-appearance: none; -moz-appearance: none;
        background-color: var(--surface2);
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%237880a0' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 12px center;
        color: var(--text); border: 1px solid var(--border2);
        border-radius: 7px; font-family: 'Barlow Condensed', sans-serif; font-size: 14px;
        font-weight: 500; padding: 7px 32px 7px 12px; letter-spacing: 0.3px;
        cursor: pointer; transition: border-color 0.15s;
        color-scheme: dark;
      }}
      .chart-select option {{
        background-color: var(--surface2);
        color: var(--text);
      }}
      .chart-select:hover {{ border-color: var(--green-dim); }}
      .chart-select:focus {{ outline: none; border-color: var(--green); }}
    </style>
    <script>{CHART_JS}
      (function() {{
        var d = JSON.parse(document.getElementById('hist-{team_id}').textContent);
        mdiRenderChart('rating-svg-{team_id}', 'rating-select-{team_id}', 'rating-caption-{team_id}',
          d.dates, d.e, {{invert: false, color: 'var(--green)', fmt: function(v){{return v.toFixed(0);}}}});
        mdiRenderChart('rank-svg-{team_id}', 'rank-select-{team_id}', 'rank-caption-{team_id}',
          d.dates, d.r, {{invert: true, color: 'var(--blue)', fmt: function(v){{return '#' + v.toFixed(0);}}}});
      }})();
    </script>'''


def generate_page(team_id: str, inline_css: bool = False) -> str:
    meta = META[team_id]
    slug_info = SLUGS["by_team_id"][team_id]
    slug = slug_info["slug"]
    r = RANKINGS.get(team_id)

    name = meta["name"]
    country = meta["country"]

    history_path = HISTORY_DIR / f"{team_id}.json"
    chart_section = build_chart_section(team_id)

    if r:
        gr = GROUP_RANKS.get(team_id, {})
        rank_parts = [f'Rank #{r["rank"]}']
        if gr.get("confederation_rank"):
            rank_parts.append(f'{gr["confederation"]} #{gr["confederation_rank"]}')
        if gr.get("country_rank"):
            rank_parts.append(f'{country_name(country)} #{gr["country_rank"]}')
        rank_line = ' &nbsp;·&nbsp; '.join(rank_parts) + f' &nbsp;·&nbsp; Elo {fmt_elo(r["elo"])}'
        tiers = pick_relevant_tiers(r["tier_counts"], r["all_time_high_rank"])

        streaks = {}
        if history_path.exists():
            with open(history_path) as f:
                hist_for_streak = json.load(f)
            streaks = compute_active_streaks(hist_for_streak["r"])

        def streak_note(threshold):
            s = streaks.get(threshold, 0)
            if s <= 1:
                return ""
            return f'<div class="stat-date">🔥 {s} updates in a row</div>'

        tier_cards = "\n      ".join(
            f'''<div class="stat-card">
        <div class="stat-label">Top {threshold}</div>
        <div class="stat-val">{count}</div>
        {streak_note(threshold)}
      </div>''' for threshold, count in tiers
        )
        stats_cards = f'''
      <div class="stat-card">
        <div class="stat-label">All-Time High Elo</div>
        <div class="stat-val green">{fmt_elo(r["all_time_high_elo"])}</div>
        <div class="stat-date">{r["all_time_high_elo_date"]}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">All-Time Low Elo</div>
        <div class="stat-val red">{fmt_elo(r["all_time_low_elo"])}</div>
        <div class="stat-date">{r["all_time_low_elo_date"]}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">All-Time High Rank</div>
        <div class="stat-val gold">#{r["all_time_high_rank"]}</div>
        <div class="stat-date">{r["all_time_high_rank_date"]}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">All-Time Low Rank</div>
        <div class="stat-val">#{r["all_time_low_rank"]}</div>
        <div class="stat-date">{r["all_time_low_rank_date"]}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Times #1</div>
        <div class="stat-val">{r["times_no1"]}</div>
        {streak_note(1)}
      </div>
      {tier_cards}'''
        form_rows = build_form_rows(r["form5"])
        related_links = build_related(team_id)
    else:
        rank_line = "Untracked"
        stats_cards = ""
        form_rows = ""
        related_links = ""

    l12m_section = build_l12m_section(team_id)
    season_by_season_section = build_season_by_season_section(team_id)
    league_table_section = build_league_table_section(team_id)
    bracket_section = build_bracket_section(team_id)

    form_section = ""
    if form_rows:
        form_section = f'''
    <div class="section">
      <h2>Recent Form</h2>
      <div style="display: flex; flex-wrap: wrap; gap: 6px;">
{form_rows}
      </div>
    </div>'''

    related_section = ""
    if related_links:
        related_section = f'''
    <div class="section">
      <h2>Nearby in Rankings</h2>
      <div class="related-grid">
      {related_links}
      </div>
    </div>'''

    description = f"{name} ({country}) football club Elo rating, ranking history, and recent form on Matchday Insights."

    if inline_css:
        css_tag = f"<style>\n{CSS_PATH.read_text()}\n</style>"
    else:
        css_tag = '<link rel="stylesheet" href="../club-page.css">'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — Elo Rating &amp; Ranking | Matchday Insights</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{BASE_URL}/clubs/{slug}.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.3.2/css/flag-icons.min.css">
{css_tag}
</head>
<body>

<nav class="site-nav">
  <div class="nav-logo">
    <div class="nav-brand">Matchday Insights</div>
    <div class="nav-sub">Global Club Elo Ratings</div>
  </div>
</nav>

<main class="club-page">
  <div class="club-header">
    <div class="club-meta">{flag_span(country)} {country_name(country)} &nbsp;·&nbsp; {meta.get("league_code", country)}</div>
    <h1 class="club-name">{name}</h1>
    <div class="club-rank">{rank_line}</div>
  </div>

  <div class="stats-grid">{stats_cards}
  </div>
{l12m_section}
{season_by_season_section}
{league_table_section}
{bracket_section}
{chart_section}
{form_section}
{related_section}

  <div class="cta-box">
    <p>See where every tracked club stands in the global Elo rankings.</p>
    <a class="cta-btn" href="../index.html">View Full Rankings</a>
  </div>
</main>

<footer class="site-footer">
  <p>&copy; 2026 Matchday Insights &nbsp;·&nbsp; <a href="{BASE_URL}/index.html">Home</a></p>
</footer>

</body>
</html>'''
    return html


if __name__ == "__main__":
    team_id = sys.argv[1] if len(sys.argv) > 1 else "4924"
    inline = "--inline-css" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = generate_page(team_id, inline_css=inline)
    slug = SLUGS["by_team_id"][team_id]["slug"]
    suffix = "_preview" if inline else ""
    out_path = OUT_DIR / f"{slug}{suffix}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")
