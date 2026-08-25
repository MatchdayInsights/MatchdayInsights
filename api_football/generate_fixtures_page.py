"""
generate_fixtures_page.py

Standalone per-club fixtures page: every match a club has played that's
used in the ratings (all competitions), with a season dropdown. Sourced
directly from the raw fixtures CSVs (fixtures_full/) rather than
match_log, since that's the true complete record - not bounded by
whatever match_log samples happen to be on hand for a given club.

Upcoming/scheduled fixtures are NOT included - that data isn't pulled by
the current pipeline at all (run_ratings.py's source fixtures CSVs only
ever contain played matches). Deferred pending the separate live-pull
script.
"""

import csv
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("/mnt/user-data/uploads")
OUT_DATA_DIR = Path("/mnt/user-data/outputs")
FIXTURES_DIR = Path("/home/claude/fixtures_full")
OUT_DIR = Path("/home/claude/site_preview/clubs")
CSS_PATH = Path("/home/claude/club-page.css")
BASE_URL = "https://matchdayinsights.github.io/MatchdayInsights"

with open(DATA_DIR / "club_metadata.json") as f:
    META = json.load(f)
with open(OUT_DATA_DIR / "slug_registry.json") as f:
    SLUGS = json.load(f)


def find_all_fixtures_for_club(team_id: str) -> list[dict]:
    """Every played match this club appears in, across every fixtures
    CSV, tagged with season/league_id/competition_name from the
    filename (mirrors match_log's season-tagging logic)."""
    matches = []
    for path in FIXTURES_DIR.glob("*.csv"):
        parts = path.stem.split("_")
        league_id, season = parts[-2], parts[-1]
        # competition name is everything between country and league_id
        competition_name = " ".join(parts[1:-2]).replace("-", " ")
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r["status"] not in ("FT", "AET", "PEN"):
                continue
            if r["home_team_id"] != team_id and r["away_team_id"] != team_id:
                continue
            is_home = r["home_team_id"] == team_id
            opponent = r["away_team"] if is_home else r["home_team"]
            opponent_team_id = r["away_team_id"] if is_home else r["home_team_id"]
            gf = int(r["home_score"] or 0) if is_home else int(r["away_score"] or 0)
            ga = int(r["away_score"] or 0) if is_home else int(r["home_score"] or 0)
            result = "W" if gf > ga else ("L" if gf < ga else "D")
            matches.append({
                "date": r["date"][:10], "season": season,
                "competition_name": competition_name, "round": r["round"],
                "venue": "Home" if is_home else "Away",
                "opponent": opponent, "opponent_team_id": opponent_team_id,
                "gf": gf, "ga": ga, "result": result,
            })
    matches.sort(key=lambda m: m["date"], reverse=True)
    return matches


def build_season_options(matches: list[dict]) -> list[str]:
    seasons = sorted(set(m["season"] for m in matches), reverse=True)
    return seasons


MATCH_LOG_DIR = Path("/home/claude/match_log")


def load_real_elo_changes(team_id: str) -> dict:
    """
    Maps (date, opponent_team_id, gf, ga) -> real elo_change, from a
    genuine match_log/{team_id}.json export (i.e. NOT one reconstructed
    from raw fixtures data by build_real_matchlog.py, which can only ever
    have elo_change=0.0 placeholders since that requires actually running
    the Elo engine, not just knowing results). Returns {} if no match_log
    file exists for this club at all.
    """
    path = MATCH_LOG_DIR / f"{team_id}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        log = json.load(f)
    return {
        (m["date"], m["opponent_team_id"], m["gf"], m["ga"]): m["elo_change"]
        for m in log["matches"]
    }


def fixture_row_html(m: dict, elo_lookup: dict) -> str:
    badge_color = {"W": "green", "L": "red", "D": "blue"}[m["result"]]
    key = (m["date"], m.get("opponent_team_id"), m["gf"], m["ga"])
    elo_change = elo_lookup.get(key)
    if elo_change is None:
        pts_html = '<span style="color: var(--muted);">—</span>'
    else:
        sign = "+" if elo_change > 0 else ""
        pts_color = "green" if elo_change > 0 else ("red" if elo_change < 0 else "text2")
        pts_html = f'<span style="color: var(--{pts_color});">{sign}{elo_change:.1f}</span>'
    return f'''
        <tr>
          <td style="padding: 6px 8px; font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--muted);">{m["date"]}</td>
          <td style="padding: 6px 8px;">
            <span style="display: inline-block; width: 20px; height: 20px; line-height: 20px; text-align: center; border-radius: 4px; background: var(--{badge_color}); color: #050a07; font-weight: 700; font-size: 10px; margin-right: 8px;">{m["result"]}</span>
            {m["venue"]} vs {m["opponent"]}
          </td>
          <td style="padding: 6px 8px; text-align: center; font-family: 'JetBrains Mono', monospace; font-weight: 700;">{m["gf"]}-{m["ga"]}</td>
          <td style="padding: 6px 8px; text-align: center; font-family: 'JetBrains Mono', monospace; font-weight: 700;">{pts_html}</td>
          <td style="padding: 6px 8px; font-size: 11px; color: var(--muted);">{m["competition_name"]}</td>
          <td style="padding: 6px 8px; font-size: 11px; color: var(--muted);">{m["round"]}</td>
        </tr>'''


def generate_fixtures_page(team_id: str, inline_css: bool = False) -> str:
    meta = META[team_id]
    slug = SLUGS["by_team_id"][team_id]["slug"]
    name = meta["name"]

    matches = find_all_fixtures_for_club(team_id)
    seasons = build_season_options(matches)

    elo_lookup = load_real_elo_changes(team_id)

    by_season = {}
    for m in matches:
        by_season.setdefault(m["season"], []).append(m)

    tables_json = json.dumps({
        s: "".join(fixture_row_html(m, elo_lookup) for m in ms)
        for s, ms in by_season.items()
    })

    options_html = "\n".join(
        f'<option value="{s}"{" selected" if i == 0 else ""}>{s}</option>'
        for i, s in enumerate(seasons)
    )

    if inline_css:
        css_tag = f"<style>\n{CSS_PATH.read_text()}\n</style>"
    else:
        css_tag = '<link rel="stylesheet" href="../club-page.css">'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — All Fixtures | Matchday Insights</title>
<link rel="canonical" href="{BASE_URL}/clubs/{slug}-fixtures.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
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
    <div class="club-meta"><a href="{slug}.html">← {name}</a></div>
    <h1 class="club-name">All Fixtures</h1>
    <div class="club-rank">{len(matches)} matches on record (all competitions, historical only)</div>
  </div>

  <div class="section">
    <script type="application/json" id="fixtures-data">{tables_json}</script>
    <div style="padding: 6px 0 14px;">
      <select id="season-select" class="chart-select" style="width: 100%; max-width: 200px;">
        {options_html}
      </select>
    </div>
    <div class="stat-card" style="padding: 8px; overflow-x: auto;">
      <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
        <thead>
          <tr style="border-bottom: 1px solid var(--border2); color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: 9px; text-transform: uppercase;">
            <th style="padding: 6px 8px; text-align: left;">Date</th>
            <th style="padding: 6px 8px; text-align: left;">Match</th>
            <th style="padding: 6px 8px; text-align: center;">Score</th>
            <th style="padding: 6px 8px; text-align: center;">Elo Δ</th>
            <th style="padding: 6px 8px; text-align: left;">Competition</th>
            <th style="padding: 6px 8px; text-align: left;">Round</th>
          </tr>
        </thead>
        <tbody id="fixtures-body"></tbody>
      </table>
    </div>
  </div>
</main>

<footer class="site-footer">
  <p>&copy; 2026 Matchday Insights &nbsp;·&nbsp; <a href="{BASE_URL}/index.html">Home</a></p>
</footer>

<style>
  .chart-select {{
    appearance: none; -webkit-appearance: none; -moz-appearance: none;
    background-color: var(--surface2);
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%237880a0' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 12px center;
    color: var(--text); border: 1px solid var(--border2);
    border-radius: 7px; font-family: 'Barlow Condensed', sans-serif; font-size: 14px;
    font-weight: 500; padding: 7px 32px 7px 12px; letter-spacing: 0.3px; cursor: pointer;
    color-scheme: dark;
  }}
  .chart-select option {{
    background-color: var(--surface2);
    color: var(--text);
  }}
  .chart-select:hover {{ border-color: var(--green-dim); }}
  .chart-select:focus {{ outline: none; border-color: var(--green); }}
</style>
<script>
  (function() {{
    var tables = JSON.parse(document.getElementById('fixtures-data').textContent);
    var sel = document.getElementById('season-select');
    var body = document.getElementById('fixtures-body');
    function render() {{ body.innerHTML = tables[sel.value]; }}
    sel.addEventListener('change', render);
    render();
  }})();
</script>

</body>
</html>'''
    return html


if __name__ == "__main__":
    import sys
    team_id = sys.argv[1] if len(sys.argv) > 1 else "157"
    inline = "--inline-css" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = generate_fixtures_page(team_id, inline_css=inline)
    slug = SLUGS["by_team_id"][team_id]["slug"]
    suffix = "_preview" if inline else ""
    out_path = OUT_DIR / f"{slug}-fixtures{suffix}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")
