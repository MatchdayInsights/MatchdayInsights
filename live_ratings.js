/* Matchday Insights - live ratings (Greg, 2026-10).
   While a match is on, works out each club's rating change and world rank
   "if it ends like this", with the same maths as run_ratings.py /
   elo_engine.py, and shows it:
     - match page: under the scoreboard
     - club page: next to the rank in the header
     - homepage: in the rankings table, next to the rating
     - Matches page: the rating change and new rank under each live score
   Provisional - confirmed by the next update. Loaded by live.js when a match
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
    var da = k * gdm(margin) * (res - ea), db = -da;
    if (!f[6]) da = 0;                                  // an unranked side doesn't move
    if (!f[7]) db = 0;
    if (f[5]) {                                         // continental: shared across the division
      if (f[10] && f[8]) {                              // both clubs from the same division:
        var both = (da + db) * conf / f[8];             //   both shares land on both of them
        da += both; db += both;
      } else {
        if (f[8]) da += da * conf / f[8];
        if (f[9]) db += db * conf / f[9];
      }
    }
    return {home: da, away: db};
  }

  // Live ranks: every club's rating, plus the live changes, re-ordered.
  function liveTable(rows) {
    var delta = {}, info = {};
    rows.forEach(function (r) {
      var f = MODEL.f[String(r[0])]; if (!f || !LIVE[r[2]] && r[2] !== 'FT' && r[2] !== 'AET' && r[2] !== 'PEN') return;
      var c = change(f, r[4] || 0, r[5] || 0, r[2]);
      delta[f[0]] = (delta[f[0]] || 0) + c.home; delta[f[1]] = (delta[f[1]] || 0) + c.away;
      info[String(r[0])] = {fid: String(r[0]), home: f[0], away: f[1], dh: c.home, da: c.away};
    });
    var ids = Object.keys(delta);
    if (!ids.length) return {matches: info, club: {}};
    var club = {};
    var all = RANKS.c, list = [];
    for (var t in all) list.push(all[t][1] + (delta[t] || 0));
    list.sort(function (a, b) { return b - a; });
    ids.forEach(function (t) {
      if (!all[t]) return;
      var r = all[t][1] + delta[t], lo = 0, hi = list.length;
      while (lo < hi) { var mid = (lo + hi) >> 1; if (list[mid] > r) lo = mid + 1; else hi = mid; }
      club[t] = {d: delta[t], rank: lo + 1, was: all[t][0], rating: r};
    });
    return {matches: info, club: club};
  }

  function sign(x) { return (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(1); }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var css = document.createElement('style');
  css.textContent = '.lr{font-family:"JetBrains Mono",monospace;font-size:12px;color:var(--text2)}' +
    '.lr b.p{color:var(--green,#3dba5e)}.lr b.n{color:#e5484d}.lr .lrt{color:#e5484d;font-weight:700;letter-spacing:.06em}' +
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
      if (m && row && LIVE[row[2]]) {
        var names = sb.querySelectorAll('.sb-t span');
        var side = function (id, dv, nm) {
          return esc(nm) + ' <b class="' + (dv >= 0 ? 'p' : 'n') + '">' + sign(dv) + '</b>' +
            (t.club[id] ? ' (' + rankMove(t.club[id]) + ')' : '');
        };
        sb.insertAdjacentHTML('beforeend', '<div class="lr sb-lr"><span class="lrt">IF IT ENDS LIKE THIS</span><br>' +
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
      if (c) rank.insertAdjacentHTML('beforeend', '<span class="lr club-lr"><span class="lrt">LIVE</span> ' +
        rankMove(c) + ' <b class="' + (c.d >= 0 ? 'p' : 'n') + '">' + sign(c.d) + '</b> if it ends like this</span>');
    }
    // Homepage rankings table.
    var rowsT = document.querySelectorAll('.table-wrap tbody tr');
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
        cell.insertAdjacentHTML('beforeend', '<span class="lr row-lr"><span class="lrt">LIVE</span> <b class="' +
          (cc.d >= 0 ? 'p' : 'n') + '">' + sign(cc.d) + '</b> → #' + cc.rank + '</span>');
      }
    }
  }

  function load() {
    Promise.all([
      fetch(base + 'live_model.json', {cache: 'no-store'}).then(function (r) { return r.ok ? r.json() : null; }),
      fetch(base + 'live_ranks.json').then(function (r) { return r.ok ? r.json() : null; }),
      document.querySelector('.table-wrap') ? fetch(base + 'rankings_table.json').then(function (r) { return r.ok ? r.json() : null; }) : null
    ]).then(function (x) {
      if (!x[0] || !x[1]) return;
      MODEL = x[0]; RANKS = x[1];
      if (x[2]) { var s = {}; x[2].forEach(function (r) { s[r.slug] = String(r.team_id); }); window.MILR_SLUGS = s; }
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
