/* Matchday Insights - the league table on a match page, live (Greg, 2026-11).
   While matches in that league are being played, the Table tab shows the
   table as it stands: played, won/drawn/lost, goal difference and points
   with the live scores counted, re-ordered, with an arrow for each club
   that moved and the score next to clubs playing. A note says it's live.
   When nothing is on it shows the official table, as before.
   Uses the live scores live.js already fetches every minute (its "mi-live"
   event). A match that finished is only counted while it isn't in the
   official table yet (it finished after this page was built).
   Loaded by app_install.js on match pages that have a table. */
(function () {
  var tables = [].slice.call(document.querySelectorAll('table.mt'));
  if (!tables.length || window.MI_MTLIVE) return;
  window.MI_MTLIVE = 1;
  var LIVE = {'1H':1,'HT':1,'2H':1,'ET':1,'BT':1,'P':1,'SUSP':1,'INT':1,'LIVE':1};
  var DONE = {'FT':1,'AET':1,'PEN':1};
  var tabM = document.getElementById('tab-m');
  var FID = tabM ? tabM.getAttribute('data-fid') : null;
  // When the table was made: its own stamp (pages from the full update have
  // one); else the page's date, which the site may refresh on any deploy -
  // too new is safe, it only means finished matches aren't added (Greg, 2026-11).
  var BUILT = Date.parse(tables[0].getAttribute('data-built') || '') || Date.parse(document.lastModified) || 0;
  var KICK = null;                                       // fixture id -> kick-off (ms), for finished matches

  var css = document.createElement('style');
  css.textContent =
    '.mt tr.mtl-on td.cl::after{content:attr(data-live);margin-left:6px;font-family:"JetBrains Mono",sans-serif;font-size:10.5px;' +
    'font-weight:700;color:#e5484d}' +
    '.mt tr.mtl-on td.cl a{display:inline-block;max-width:calc(100% - 82px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom}' +
    '.mt td:first-child{white-space:nowrap}' +
    '@media(max-width:360px){.mt tr.mtl-on td.cl a{display:inline;max-width:none}.mt tr.mtl-on td.cl::after{display:block;margin:1px 0 0 25px;font-size:10.5px}}' +
    '.mt .mtl-mv{display:inline-block;margin-left:2px;font-size:8px;font-weight:700;vertical-align:1px}' +
    '.mt .mtl-mv.u{color:#3dba5e}.mt .mtl-mv.d{color:#e5484d}' +
    '.mt td.mtl-ch{color:var(--text)!important;font-weight:700}' +
    '.mtl-note{font-family:"JetBrains Mono",sans-serif;font-size:12px;color:#e5484d;margin:8px 0 2px;display:flex;align-items:center;gap:6px}' +
    '.mtl-note i{width:7px;height:7px;border-radius:50%;background:#e5484d;animation:mtlb 1.4s infinite}@keyframes mtlb{50%{opacity:.25}}';
  document.head.appendChild(css);

  // Read each table once: its rows, columns and the official numbers.
  var T = tables.map(function (t) {
    var rows = [].slice.call(t.rows), head = rows.shift();
    var col = {};
    [].forEach.call(head.cells, function (c, i) { col[c.textContent.trim().toUpperCase()] = i; });
    var data = rows.map(function (tr, i) {
      var img = tr.querySelector('img'), m = img && (img.getAttribute('src') || '').match(/crests\/([^/]+)\.png/);
      var num = function (k) { var c = tr.cells[col[k]]; return c ? parseInt(c.textContent, 10) || 0 : 0; };
      var a = tr.querySelector('td.cl a, td.cl');
      return {tr: tr, id: m ? m[1].replace(/-/g, ':') : null, nm: a ? a.textContent.trim().toLowerCase() : '', pos: i, p: num('P'), w: num('W'), d: num('D'), l: num('L'),
              gd: num('GD'), pts: num('PTS')};
    });
    // Each club by its id (from its crest) and, if its crest is missing, by name.
    return {t: t, head: head, col: col, rows: data, ids: data.reduce(function (o, r) { if (r.id) o[r.id] = r; if (r.nm) o['n:' + r.nm] = r; return o; }, {})};
  });
  if (!T.some(function (x) { return x.rows.length && x.col.PTS != null; })) return;

  // Kick-off times: push_schedule.json only has matches still to come at the
  // last deploy, so also the Matches page's day files (named by UTC date) for
  // today and yesterday, which keep finished ones (Greg, 2026-11).
  function getJSON(u) { return fetch(u).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
  function kickoffs() {
    if (KICK) return Promise.resolve(KICK);
    var d0 = new Date(), d1 = new Date(Date.now() - 864e5), k = function (d) { return d.toISOString().slice(0, 10); };
    return Promise.all([getJSON('/push_schedule.json'), getJSON('/matches/' + k(d0) + '.json'), getJSON('/matches/' + k(d1) + '.json')])
      .then(function (r) {
        KICK = {};
        ((r[0] && r[0].f) || []).forEach(function (f) { KICK[String(f[0])] = Date.parse(f[1]); });
        [r[1], r[2]].forEach(function (ms) { (ms || []).forEach(function (m) { if (m && m.id != null && m.t) KICK[String(m.id)] = Date.parse(m.t); }); });
        return KICK;
      });
  }
  // A finished match counts only if it ended after this page was made.
  function notInTableYet(fid) {
    var k = KICK && KICK[String(fid)];
    if (!k || !BUILT) return false;                      // not sure: leave the official table alone
    return k + 115 * 60e3 > BUILT;
  }

  function find(x, id, name) { return x.ids[String(id)] || x.ids['n:' + String(name || '').trim().toLowerCase()] || null; }

  function cell(tr, i, v, changed) {
    var c = tr.cells[i]; if (!c) return;
    c.textContent = v; c.classList.toggle('mtl-ch', !!changed);
  }

  function draw(rows) {
    T.forEach(function (x) {
      if (!x.rows.length) return;
      // This table's league: the page's own match if it's on, else the
      // league most of the on-going matches between its clubs belong to.
      var both = rows.filter(function (r) { return find(x, r[6], r[8]) && find(x, r[7], r[9]) && (LIVE[r[2]] || DONE[r[2]]); });
      var own = rows.filter(function (r) { return String(r[0]) === String(FID); })[0];
      var lg = own && find(x, own[6], own[8]) ? own[1] : null;
      if (!lg && both.length) {
        var n = {}; both.forEach(function (r) { n[r[1]] = (n[r[1]] || 0) + 1; });
        lg = Object.keys(n).sort(function (a, b) { return n[b] - n[a]; })[0];
      }
      var use = both.filter(function (r) { return String(r[1]) === String(lg) && (LIVE[r[2]] || notInTableYet(r[0])); });
      var now = x.rows.map(function (o) { return {o: o, p: o.p, w: o.w, d: o.d, l: o.l, gd: o.gd, pts: o.pts, live: null}; });
      var by = new Map(); now.forEach(function (r) { by.set(r.o, r); });
      use.forEach(function (r) {
        var h = by.get(find(x, r[6], r[8])), a = by.get(find(x, r[7], r[9])), hg = r[4] || 0, ag = r[5] || 0;
        var min = r[2] === 'HT' ? 'HT' : DONE[r[2]] ? 'FT' : (r[3] != null ? r[3] + "'" : 'LIVE');
        [[h, hg, ag], [a, ag, hg]].forEach(function (s) {
          var c = s[0]; if (!c) return;
          c.p++; c.gd += s[1] - s[2];
          if (s[1] > s[2]) { c.w++; c.pts += 3; } else if (s[1] === s[2]) { c.d++; c.pts += 1; } else c.l++;
          c.live = hg + '-' + ag + ' ' + min;
        });
      });
      var order = now.slice();
      if (use.length) order.sort(function (a, b) { return b.pts - a.pts || b.gd - a.gd || a.o.pos - b.o.pos; });
      var body = x.head.parentNode;
      order.forEach(function (r, i) {
        var tr = r.o.tr;
        body.appendChild(tr);
        var moved = use.length ? r.o.pos - i : 0;
        tr.cells[0].innerHTML = (i + 1) + (moved ? '<span class="mtl-mv ' + (moved > 0 ? 'u">&#9650;' : 'd">&#9660;') + '</span>' : '');
        var col = x.col;
        if (col.P != null) cell(tr, col.P, r.p, r.p !== r.o.p);
        if (col.W != null) cell(tr, col.W, r.w, r.w !== r.o.w);
        if (col.D != null) cell(tr, col.D, r.d, r.d !== r.o.d);
        if (col.L != null) cell(tr, col.L, r.l, r.l !== r.o.l);
        if (col.GD != null) cell(tr, col.GD, r.gd, r.gd !== r.o.gd);
        if (col.PTS != null) cell(tr, col.PTS, r.pts, r.pts !== r.o.pts);
        tr.classList.toggle('mtl-on', !!r.live);
        var cl = tr.querySelector('td.cl'); if (cl) { if (r.live) cl.setAttribute('data-live', r.live); else cl.removeAttribute('data-live'); }
      });
      var note = x.t.parentNode.parentNode.querySelector('.mtl-note');
      if (use.length) {
        if (!note) { note = document.createElement('div'); note.className = 'mtl-note'; x.t.parentNode.parentNode.insertBefore(note, x.t.parentNode); }
        var on = use.filter(function (r) { return LIVE[r[2]]; }).length;
        note.innerHTML = '<i></i>' + (on ? 'Live table - as it stands with ' + on + ' match' + (on === 1 ? '' : 'es') + ' on'
                                         : 'Includes today\'s results - confirmed at the next update');
      } else if (note) note.remove();
    });
  }

  function onLive(d) {
    var rows = (d && d.m) || [];
    var needKick = rows.some(function (r) { return DONE[r[2]]; });
    (needKick ? kickoffs() : Promise.resolve()).then(function () { try { draw(rows); } catch (e) {} });
  }
  document.addEventListener('mi-live', function (e) { onLive(e.detail); });
  if (window.MI_LIVE) onLive(window.MI_LIVE);
})();
