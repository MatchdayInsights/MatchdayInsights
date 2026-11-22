/* Matchday Insights - live ratings (Greg, 2026-10).
   While a match is on, works out each club's rating change and world rank
   "if it ends like this", with the same maths as run_ratings.py /
   elo_engine.py, and shows it:
     - match page: under the scoreboard
     - club page: next to the rank in the header
     - homepage: in the rankings table, next to the rating
     - Matches page: the rating change and new rank under each live score
   Provisional - confirmed by the next update. A match that has finished but
   isn't in an update yet shows too (NEW / RATING CHANGE, Greg 2026-11), so
   the ranking moves the moment a game ends. Loaded by live.js when a match
   is live (and by the Matches page); reads live_model.json and
   live_ranks.json. */
(function () {
  if (window.MILR) return;
  var me = document.currentScript;
  var base = (me && me.getAttribute('data-base')) || '';
  var MODEL = null, RANKS = null, READY = false, waiting = [];
  var LIVE = {'1H':1,'HT':1,'2H':1,'ET':1,'BT':1,'P':1,'SUSP':1,'INT':1,'LIVE':1};

  // ---- the maths (elo_engine.py) ----
  function gdm(m) { return m <= 1 ? 1 : m === 2 ? 1.5 : (11 + m) / 8; }
  function expected(a, b, ha) { return 1 / (Math.pow(10, -((a + ha) - b) / 400) + 1); }
  // One match: {home: change, away: change} for the score so far.
  function change(f, hg, ag, status) {
    var k = MODEL.k || 25, conf = MODEL.conf || 5;
    var ra = f[2], rb = f[3], ha = f[4];
    var res = hg > ag ? 1 : hg < ag ? 0 : 0.5;
    if (status === 'P') res = 0.5;                      // a shoot-out counts as a draw
    var margin = Math.abs(hg - ag);
    var ea = expected(ra, rb, ha);
    var da = k * gdm(margin) * (res - ea), db = -da, sh = 0, sa = 0;
    if (!f[6]) da = 0;                                  // an unranked side doesn't move
    if (!f[7]) db = 0;
    if (f[5]) {                                         // continental: shared across the division
      if (f[10] && f[8]) {                              // both clubs from the same division:
        var both = (da + db) * conf / f[8];             //   both shares land on both of them
        da += both; db += both;
        sh = both; sa = both;
      } else {
        if (f[8]) { sh = da * conf / f[8]; da += sh; }
        if (f[9]) { sa = db * conf / f[9]; db += sa; }
      }
    }
    // sh / sa: what each other club in the home / away side's division gets.
    return {home: da, away: db, sh: sh, sa: sa};
  }

  // Only a match whose pre-match ratings are the ratings this page has: if
  // the update that rated it is already here (a stale live_model.json), the
  // ratings differ and it's left out - a match is never counted twice
  // (Greg, 2026-11: "paramount that a match doesn't get double counted").
  function fresh(f) {
    var c = RANKS.c, a = c[f[0]], b = c[f[1]];
    if (f[6] && a && Math.abs(a[1] - f[2]) > 0.06) return false;
    if (f[7] && b && Math.abs(b[1] - f[3]) > 0.06) return false;
    return true;
  }

  // Every club's change from the given matches, league-mates' continental
  // shares included when the page knows the divisions (MILR_LG, rankings).
  function deltas(rows, finishedOnly) {
    var delta = {}, info = {}, on = {}, lg = window.MILR_LG, mates = null;
    rows.forEach(function (r) {
      var f = MODEL.f[String(r[0])], st = r[2];
      if (!f || !fresh(f)) return;
      var done = st === 'FT' || st === 'AET' || st === 'PEN';
      if (!LIVE[st] && !done) return;
      if (finishedOnly && !done) return;
      var c = change(f, r[4] || 0, r[5] || 0, st);
      delta[f[0]] = (delta[f[0]] || 0) + c.home; delta[f[1]] = (delta[f[1]] || 0) + c.away;
      if (lg && (c.sh || c.sa)) {
        if (!mates) { mates = {}; for (var t in lg) (mates[lg[t]] = mates[lg[t]] || []).push(t); }
        var add = function (club, share) {
          if (!share || !lg[club]) return;
          (mates[lg[club]] || []).forEach(function (m) {
            if (m !== f[0] && m !== f[1]) delta[m] = (delta[m] || 0) + share;
          });
        };
        if (f[10]) add(f[0], c.sh); else { add(f[0], c.sh); add(f[1], c.sa); }
      }
      if (LIVE[st]) { on[f[0]] = 1; on[f[1]] = 1; }    // still playing: "if it ends like this"
      info[String(r[0])] = {fid: String(r[0]), home: f[0], away: f[1], dh: c.home, da: c.away, live: !!LIVE[st]};
    });
    return {delta: delta, info: info, on: on};
  }

  // Live ranks: every club's rating, plus the live changes, re-ordered.
  function liveTable(rows) {
    var dd = deltas(rows, false), delta = dd.delta, info = dd.info, on = dd.on;
    var ids = [];
    for (var fid in info) { ids.push(info[fid].home); ids.push(info[fid].away); }
    if (!ids.length) return {matches: info, club: {}};
    var club = {};
    var all = RANKS.c, list = [];
    for (var t in all) list.push(all[t][1] + (delta[t] || 0));
    list.sort(function (a, b) { return b - a; });
    ids.forEach(function (t) {
      if (!all[t]) return;
      var r = all[t][1] + delta[t], lo = 0, hi = list.length;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (list[mid] > r) lo = mid + 1; else hi = mid; }
      club[t] = {d: delta[t], rank: lo + 1, was: all[t][0], rating: r, live: !!on[t]};
    });
    return {matches: info, club: club};
  }

  function sign(x) { return (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(1); }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var css = document.createElement('style');
  css.textContent = '.lr{font-family:"JetBrains Mono",monospace;font-size:12px;color:var(--text2)}' +
    '.lr b.p{color:var(--green,#3dba5e)}.lr b.n{color:#e5484d}.lr .lrt{color:#e5484d;font-weight:700;letter-spacing:.06em}' +
    '.lr .lrt.ft{color:var(--green,#3dba5e)}' +
    '.sb-lr{text-align:center;margin:8px 0 0;line-height:1.7}' +
    '.club-lr{display:block;margin-top:6px;letter-spacing:0;text-transform:none}' +
    '.row-lr{display:block;font-size:10.5px;margin-top:2px;white-space:nowrap}';
  document.head.appendChild(css);

  function rankMove(c) {
    if (!c) return '';
    return c.rank === c.was ? '#' + c.rank : '#' + c.was + ' → #' + c.rank;
  }

  // ---- the pages ----
  function draw(d) {
    if (!READY || !d || !d.m) return;
    var t = liveTable(d.m);
    // Match page.
    var fidEl = document.querySelector('script[data-fid]');
    var sb = document.querySelector('.sb');
    if (sb && fidEl) {
      var m = t.matches[fidEl.getAttribute('data-fid')], old = sb.querySelector('.sb-lr');
      if (old) old.remove();
      var row = d.m.filter(function (r) { return String(r[0]) === fidEl.getAttribute('data-fid'); })[0];
      if (m && row) {
        var names = sb.querySelectorAll('.sb-t span');
        var side = function (id, dv, nm) {
          return esc(nm) + ' <b class="' + (dv >= 0 ? 'p' : 'n') + '">' + sign(dv) + '</b>' +
            (t.club[id] ? ' (' + rankMove(t.club[id]) + ')' : '');
        };
        // Finished, not yet in an update: the change as it will be (Greg, 2026-11).
        sb.insertAdjacentHTML('beforeend', '<div class="lr sb-lr">' + (LIVE[row[2]] ? '<span class="lrt">IF IT ENDS LIKE THIS</span>'
          : '<span class="lrt ft">RATING CHANGE</span>') + '<br>' +
          side(m.home, m.dh, names[0] ? names[0].textContent : 'Home') + ' &middot; ' +
          side(m.away, m.da, names[1] ? names[1].textContent : 'Away') + '</div>');
      }
    }
    // Club page.
    var tidEl = document.querySelector('script[data-tid]');
    var rank = document.querySelector('.club-rank');
    if (rank && tidEl) {
      var old2 = rank.querySelector('.club-lr'); if (old2) old2.remove();
      var c = t.club[(tidEl.getAttribute('data-tid') || '').split('::')[0]];
      if (c) rank.insertAdjacentHTML('beforeend', '<span class="lr club-lr">' + (c.live ? '<span class="lrt">LIVE</span> '
        : '<span class="lrt ft">NEW</span> ') + rankMove(c) + ' <b class="' + (c.d >= 0 ? 'p' : 'n') + '">' + sign(c.d) + '</b>' +
        (c.live ? ' if it ends like this' : ' after the latest result') + '</span>');
    }
    // Homepage rankings table - with the score (Greg, 2026-11: "I want the
    // live score to show on the rankings"): "LIVE 0-1 v Fulham 33' -21.2 → #6",
    // the club's own goals first; "FT 0-1 v Fulham" once it's over.
    // Rankings page: results that have finished but aren't in an update yet
    // move clubs to their new places at once (Greg, 2026-11: "My wish is for
    // the ranking to update automatically upon match completion"). Matches
    // still on don't move anything - they keep "if it ends like this".
    if (window.MIRankLive) {
      var fin = deltas(d.m, true);
      window.MIRankLive(fin.delta, Object.keys(fin.info).length);
    }
    var rowsT = document.querySelectorAll('.table-wrap tbody tr');
    var game = {};
    d.m.forEach(function (r) {
      var f = MODEL.f[String(r[0])]; if (!f) return;
      if (!LIVE[r[2]] && r[2] !== 'FT' && r[2] !== 'AET' && r[2] !== 'PEN') return;
      var when = LIVE[r[2]] ? (r[2] === 'HT' ? ' HT' : r[3] ? ' ' + r[3] + "'" : '') : '';
      var hg = r[4] || 0, ag = r[5] || 0;
      game[f[0]] = {live: !!LIVE[r[2]], txt: hg + '-' + ag + ' v ' + (r[9] || '') + when};
      game[f[1]] = {live: !!LIVE[r[2]], txt: ag + '-' + hg + ' v ' + (r[8] || '') + when};
    });
    if (rowsT.length) {
      var bySlug = window.MILR_SLUGS || {};
      document.querySelectorAll('.row-lr').forEach(function (x) { x.remove(); });
      for (var i = 0; i < rowsT.length; i++) {
        var a = rowsT[i].querySelector('a[href*="clubs/"]');
        var src = a ? a.getAttribute('href') : (rowsT[i].getAttribute('onclick') || '');
        var mm = /clubs\/([^'".\/]+)\.html/.exec(src); if (!mm) continue;
        var slug = mm[1];
        var tid = bySlug[slug]; var cc = tid && t.club[tid]; if (!cc) continue;
        var cell = rowsT[i].querySelector('.elo-cell') || rowsT[i].lastElementChild;
        var gm = game[tid];
        cell.insertAdjacentHTML('beforeend', '<span class="lr row-lr">' + (cc.live ? '<span class="lrt">LIVE</span>'
          : '<span class="lrt ft">' + (gm ? 'FT' : 'NEW') + '</span>') + (gm ? ' ' + esc(gm.txt) + ' &middot;' : '') + ' <b class="' +
          (cc.d >= 0 ? 'p' : 'n') + '">' + sign(cc.d) + '</b> → #' + cc.rank + '</span>');
      }
    }
  }

  function load() {
    Promise.all([
      fetch(base + 'live_model.json', {cache: 'no-store'}).then(function (r) { return r.ok ? r.json() : null; }),
      fetch(base + 'live_ranks.json', {cache: 'no-cache'}).then(function (r) { return r.ok ? r.json() : null; }),
      document.querySelector('.table-wrap') ? fetch(base + 'rankings_table.json').then(function (r) { return r.ok ? r.json() : null; }) : null
    ]).then(function (x) {
      if (!x[0] || !x[1]) return;
      MODEL = x[0]; RANKS = x[1];
      if (x[2]) {
        var s = {}, lg = {};
        x[2].forEach(function (r) { s[r.slug] = String(r.team_id); if (r.league_code) lg[String(r.team_id)] = r.league_code; });
        window.MILR_SLUGS = s; window.MILR_LG = lg;
      }
      READY = true;
      waiting.forEach(function (f) { f(); }); waiting = [];
      if (window.MI_LIVE) draw(window.MI_LIVE);
      try { document.dispatchEvent(new CustomEvent('milr-ready')); } catch (e) {}
    }).catch(function () {});
  }

  window.MILR = {
    ready: function () { return READY; },
    // For the Matches page: {home:{d, rank, was}, away:{...}} for a live row, or null.
    forRow: function (row, all) {
      if (!READY) return null;
      var t = liveTable(all), m = t.matches[String(row[0])];
      if (!m) return null;
      var h = t.club[m.home], a = t.club[m.away];
      return {home: {d: m.dh, rank: h && h.rank, was: h && h.was}, away: {d: m.da, rank: a && a.rank, was: a && a.was}};
    },
    table: function (all) { return READY ? liveTable(all) : null; },
    change: function (f, hg, ag, st) { return change(f, hg, ag, st); },
    _setModel: function (m, r) { MODEL = m; RANKS = r; READY = true; }
  };
  document.addEventListener('mi-live', function (e) { draw(e.detail); });
  // The rankings table is redrawn by the page (paging, filters): add the live numbers again.
  var tb = document.querySelector('#table-body, .table-wrap tbody'), busy = false;
  if (tb && window.MutationObserver) new MutationObserver(function () {
    if (busy || !window.MI_LIVE) return;
    busy = true; setTimeout(function () { draw(window.MI_LIVE); busy = false; }, 50);
  }).observe(tb, {childList: true});
  load();
})();
