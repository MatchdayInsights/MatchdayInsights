/* Matchday Insights - the "My clubs" screen, my.html (Greg, 2026-11).
   The clubs you follow (the same list as the star on club pages, saved on
   this phone), each with:
     - world rank and move, rating and change (same numbers as Rankings)
     - while it plays: the live score, and its rating and rank "if it ends
       like this" (live.js + live_ratings.js, the same as everywhere else)
     - the last result and form, the next match with our odds
   Data: my_clubs/<team_id>.json (written at each deploy). Follow more clubs
   with the search box; unfollow with the star. Alerts: see push section. */
(function () {
  var KEY = 'mi_myclubs';
  var LIVE = {'1H':1,'HT':1,'2H':1,'ET':1,'BT':1,'P':1,'SUSP':1,'INT':1,'LIVE':1};
  var DONE = {'FT':1,'AET':1,'PEN':1};
  var listEl = document.getElementById('myp-list');
  if (!listEl) return;

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; } }
  function save(l) {
    try { localStorage.setItem(KEY, JSON.stringify(l)); } catch (e) {}
    try { document.dispatchEvent(new CustomEvent('mi-myclubs')); } catch (e) {}
  }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function fname(id) { return String(id).replace(/:/g, '-'); }
  function sign(x, d) { return (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(d == null ? 1 : d); }
  function rk(n) { return 'No. ' + Number(n).toLocaleString('en-US'); }

  var css = document.createElement('style');
  css.textContent =
    '.myp{max-width:760px;margin:0 auto;padding:18px 16px 28px}' +
    '.myp-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}' +
    '.myp-title{font-size:clamp(30px,8vw,40px);font-weight:900;line-height:.95;text-transform:uppercase;margin:0;color:var(--green)}' +
    '.myp-title em{font-style:normal;color:var(--text)}' +
    '.myp-bell{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--border2);background:none;color:var(--text2);' +
    'border-radius:20px;padding:7px 13px 7px 10px;font:600 12px "JetBrains Mono",sans-serif;cursor:pointer}' +
    '.myp-bell svg{width:16px;height:16px}.myp-bell.on{color:var(--green);border-color:var(--green-dim)}' +
    '.myp-list{display:flex;flex-direction:column;gap:12px}' +
    '.myp-empty{padding:26px 18px;text-align:center;color:var(--text2);border:1px dashed var(--border2);border-radius:14px;' +
    'font-family:"JetBrains Mono",sans-serif;font-size:13px;line-height:1.6}.myp-empty b{display:block;color:var(--text);font-size:15px;margin-bottom:4px}' +
    '.mc{background:var(--surface2);border:1px solid var(--border2);border-radius:14px;overflow:hidden}' +
    '.mc.live{border-color:rgba(229,72,77,.55)}' +
    '.mc-top{display:flex;align-items:center;gap:12px;padding:13px 14px 11px;text-decoration:none!important;color:var(--text)}' +
    '.mc-top img{width:44px;height:44px;object-fit:contain;flex:none}' +
    '.mc-nm{flex:1;min-width:0}.mc-nm b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;' +
    'font-family:"JetBrains Mono",Inter,sans-serif;font-size:18px;font-weight:700;line-height:1.15;letter-spacing:-.01em;overflow-wrap:anywhere}' +
    '.mc-nm span{font-family:"JetBrains Mono",sans-serif;font-size:11.5px;color:var(--text2)}' +
    '.mc-rk{text-align:right;flex:none}.mc-rk b{display:block;font-size:26px;font-weight:900;line-height:1}' +
    '.mc-rk span{font-family:"JetBrains Mono",sans-serif;font-size:12px;font-weight:700}' +
    '.mcx-up{color:var(--green)}.mcx-dn{color:var(--red,#e84466)}.mcx-same{color:var(--muted)}' +
    '.mc-star{flex:none;background:none;border:0;padding:4px;margin:-4px -4px -4px 0;color:#f2c200;cursor:pointer}.mc-star svg{width:20px;height:20px;display:block}' +
    '.mc-row{display:flex;align-items:center;gap:10px;padding:9px 14px;border-top:1px solid var(--border2);' +
    'font-family:"JetBrains Mono",sans-serif;font-size:12.5px;color:var(--text2);text-decoration:none!important}' +
    'a.mc-row:active{background:rgba(127,127,127,.08)}' +
    '.mc-row .mck{flex:none;width:38px;font-size:11.5px;font-weight:600;color:var(--muted)}' +
    '.mc-row .mcv{flex:1;min-width:0;color:var(--text)}.mc-row .mcv small{display:block;color:var(--text2);font-size:11px;margin-top:2px}' +
    '.mc-row .mcx-gt{flex:none;color:var(--muted);font-size:16px}' +
    '.mcx-res{display:inline-block;min-width:18px;text-align:center;border-radius:4px;font-weight:800;color:#fff;margin-right:6px;padding:0 3px}' +
    '.mcx-res.W{background:#1f9a46}.mcx-res.D{background:#8a90a8}.mcx-res.L{background:#d0364f}' +
    '.mcx-form{display:inline-flex;gap:3px;margin-left:8px;vertical-align:1px}.mcx-form i{width:7px;height:7px;border-radius:50%;display:inline-block}' +
    '.mcx-form i.W{background:#3dba5e}.mcx-form i.D{background:#8a90a8}.mcx-form i.L{background:#e5484d}' +
    '.mcx-odds{display:flex;height:5px;border-radius:3px;overflow:hidden;margin-top:6px;max-width:240px}' +
    '.mcx-odds i{display:block}.mcx-odds .w{background:#3dba5e}.mcx-odds .d{background:#8a90a8}.mcx-odds .l{background:#e5484d}' +
    '.mc-live{background:rgba(229,72,77,.09)}.mc-live .mck{color:#e5484d}' +
    '.mc-live .mcx-sc{font-size:17px;font-weight:800;color:var(--text)}' +
    '.ldot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#e5484d;margin-right:5px;animation:mcb 1.4s infinite;vertical-align:1px}' +
    '@keyframes mcb{50%{opacity:.25}}' +
    '.myp-add{margin-top:22px}.myp-add-h{font-family:"JetBrains Mono",sans-serif;font-size:12.5px;font-weight:600;color:var(--muted);margin-bottom:8px}' +
    '#myp-q{width:100%;box-sizing:border-box;padding:11px 14px;border-radius:10px;border:1px solid var(--border2);background:var(--surface2);' +
    'color:var(--text);font-size:16px;font-family:inherit}' +
    '.myp-res{margin-top:6px}.myp-res button{display:flex;align-items:center;gap:10px;width:100%;padding:9px 6px;background:none;border:0;' +
    'border-bottom:1px solid var(--border2);color:var(--text);font-family:inherit;font-size:16px;font-weight:600;cursor:pointer;text-align:left}' +
    '.myp-res img{width:26px;height:26px;object-fit:contain}.myp-res span{margin-left:auto;font:500 12px "JetBrains Mono",sans-serif;color:var(--text2)}' +
    '.myp-res .on span{color:#f2c200}' +
    '.myp-alerts{margin:0 0 14px;padding:14px;border:1px solid var(--border2);border-radius:14px;background:var(--surface2);' +
    'font-family:"JetBrains Mono",sans-serif;font-size:12.5px;color:var(--text2);line-height:1.55}' +
    '.myp-alerts b{color:var(--text)}.myp-alerts label{display:flex;align-items:center;gap:10px;padding:7px 0;color:var(--text);font-size:13px}' +
    '.myp-alerts input{width:18px;height:18px;accent-color:#3dba5e}' +
    '.myp-alerts .go{margin-top:8px;background:#3dba5e;color:#fff;border:0;border-radius:8px;padding:9px 14px;font-family:inherit;font-size:14px;font-weight:700;cursor:pointer}' +
    '.myp-alerts .off{margin-left:10px;background:none;border:0;color:var(--text2);text-decoration:underline;cursor:pointer;font:inherit}';
  document.head.appendChild(css);

  var STAR = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3 6.1 20.6l1.3-6.6L2.5 9.4l6.6-.8z"/></svg>';

  // ---- dates in the visitor's own time zone ----
  function day(iso) {
    var d = new Date(iso.length <= 10 ? iso + 'T12:00:00' : iso);
    return d.toLocaleDateString(undefined, {weekday: 'short', day: 'numeric', month: 'short'});
  }
  function kick(iso) {
    var d = new Date(iso), now = new Date(), t = d.toLocaleTimeString(undefined, {hour: 'numeric', minute: '2-digit'});
    var dd = Math.round((new Date(d.toDateString()) - new Date(now.toDateString())) / 864e5);
    return (dd === 0 ? 'Today' : dd === 1 ? 'Tomorrow' : day(iso)) + ' ' + t;
  }

  var DATA = {}, LIVEROWS = null;
  function card(m) {
    var c = DATA[m.i] || {};
    var name = c.n || m.n, slug = c.s || m.s;
    var mv = c.m > 0 ? '<span class="mcx-up">&#9650;' + c.m + '</span>' : c.m < 0 ? '<span class="mcx-dn">&#9660;' + (-c.m) + '</span>'
             : '<span class="mcx-same">&mdash;</span>';
    var ch = c.c != null ? ' &middot; <span class="' + (c.c >= 0 ? 'mcx-up' : 'mcx-dn') + '">' + sign(c.c) + '</span>' : '';
    var h = '<div class="mc" data-i="' + esc(m.i) + '">' +
      '<div class="mc-top"><a href="/clubs/' + esc(slug) + '.html" style="display:contents;color:inherit">' +
      '<img src="/crests/' + esc(fname(m.i)) + '.png" alt="" onerror="this.style.visibility=\'hidden\'">' +
      '<div class="mc-nm"><b>' + esc(name) + '</b><span>' + (c.e != null ? 'Rating ' + c.e.toFixed(1) + ch : 'Not ranked') + '</span></div>' +
      '<div class="mc-rk">' + (c.r ? '<b>' + rk(c.r) + '</b>' + mv : '') + '</div></a>' +
      '<button class="mc-star" type="button" aria-label="Unfollow ' + esc(name) + '">' + STAR + '</button></div>';
    h += liveRow(m.i, name);
    var l = c.l;
    if (l && l.r) {
      var where = l.v === 'H' ? 'v' : l.v === 'A' ? 'at' : 'v';
      var form = c.f ? '<span class="mcx-form">' + c.f.split('').map(function (x) { return '<i class="' + x + '"></i>'; }).join('') + '</span>' : '';
      h += (l.pg ? '<a class="mc-row" href="/predictions/' + esc(l.pg) + '.html">' : '<div class="mc-row">') +
        '<span class="mck">Last</span><span class="mcv"><span class="mcx-res ' + esc(l.r) + '">' + esc(l.r) + '</span>' + esc(l.s) + ' ' + where + ' ' +
        esc(l.o) + '<small>' + (l.d ? day(l.d) : '') + (l.c != null ? ' &middot; <span class="' + (l.c >= 0 ? 'mcx-up' : 'mcx-dn') + '">' + sign(l.c) + '</span>' : '') +
        form + '</small></span>' + (l.pg ? '<span class="mcx-gt">&rsaquo;</span></a>' : '</div>');
    }
    var x = c.x;
    if (x && !(LIVEROWS && findRow(m.i) && findRow(m.i).fid == x.fid)) {
      var p = x.p || [];
      var odds = p[0] != null ? '<span class="mcx-odds"><i class="w" style="width:' + (p[0] * 100) + '%"></i><i class="d" style="width:' +
        (p[1] * 100) + '%"></i><i class="l" style="width:' + (p[2] * 100) + '%"></i></span>' +
        '<small>Win ' + Math.round(p[0] * 100) + '% &middot; Draw ' + Math.round(p[1] * 100) + '% &middot; Lose ' + Math.round(p[2] * 100) + '%</small>' : '';
      h += (x.pg ? '<a class="mc-row" href="/predictions/' + esc(x.pg) + '.html">' : '<div class="mc-row">') +
        '<span class="mck">Next</span><span class="mcv">' + (x.v === 'A' ? 'at ' : 'v ') + esc(x.o) +
        (x.or ? ' <span style="color:var(--muted)">' + rk(x.or) + '</span>' : '') +
        '<small>' + kick(x.d) + ' &middot; ' + esc(x.co || '') + '</small>' + odds + '</span>' +
        (x.pg ? '<span class="mcx-gt">&rsaquo;</span></a>' : '</div>');
    }
    return h + '</div>';
  }

  // ---- live: the score, and "if it ends like this" ----
  function findRow(id) {
    if (!LIVEROWS) return null;
    for (var k = 0; k < LIVEROWS.length; k++) {
      var r = LIVEROWS[k];
      if ((LIVE[r[2]] || DONE[r[2]]) && (String(r[6]) === String(id) || String(r[7]) === String(id))) {
        return {fid: r[0], row: r, home: String(r[6]) === String(id)};
      }
    }
    return null;
  }
  function liveRow(id, name) {
    var f = findRow(id); if (!f) return '';
    var r = f.row, on = LIVE[r[2]];
    var min = r[2] === 'HT' ? 'HT' : r[2] === 'P' ? 'Pens' : DONE[r[2]] ? 'FT' : (r[3] != null ? r[3] + "'" : 'LIVE');
    var sc = esc(r[8]) + ' <span class="mcx-sc">' + (r[4] || 0) + '-' + (r[5] || 0) + '</span> ' + esc(r[9]);
    var lr = '';
    if (window.MILR && MILR.ready()) {
      var t = MILR.table(LIVEROWS), c = t && t.club[String(id)];
      if (c) {
        lr = '<small>' + (on ? 'If it ends like this: ' : 'Provisional: ') + '<span class="' + (c.d >= 0 ? 'mcx-up' : 'mcx-dn') + '">' + sign(c.d) + '</span>' +
          ' &middot; ' + (c.rank === c.was ? 'stays ' + rk(c.rank) : rk(c.was) + ' &rarr; <b>' + rk(c.rank) + '</b>') + '</small>';
      }
    }
    return '<div class="mc-row mc-live"><span class="mck">' + (on ? '<span class="ldot"></span>' : '') + min + '</span>' +
      '<span class="mcv">' + sc + lr + '</span></div>';
  }

  // ---- drawing ----
  function draw() {
    var mine = load();
    if (!mine.length) {
      listEl.innerHTML = '<div class="myp-empty"><b>Follow your clubs</b>Search below and tap a club. Its rank, live score, ' +
        'last result and next match will live here.</div>';
      return;
    }
    var live = mine.filter(function (m) { var f = findRow(m.i); return f && LIVE[f.row[2]]; });
    var rest = mine.filter(function (m) { return live.indexOf(m) < 0; });
    listEl.innerHTML = live.concat(rest).map(card).join('');
    listEl.querySelectorAll('.mc').forEach(function (el) {
      var f = findRow(el.getAttribute('data-i'));
      if (f && LIVE[f.row[2]]) el.classList.add('live');
    });
  }
  listEl.addEventListener('click', function (e) {
    var b = e.target.closest('.mc-star'); if (!b) return;
    e.preventDefault();
    var id = b.closest('.mc').getAttribute('data-i');
    save(load().filter(function (m) { return String(m.i) !== String(id); }));
    draw(); search();
  });

  function fetchClubs() {
    var mine = load(), need = mine.filter(function (m) { return !DATA[m.i]; });
    if (!need.length) { draw(); return; }
    Promise.all(need.map(function (m) {
      return fetch('/my_clubs/' + encodeURIComponent(fname(m.i)) + '.json').then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { DATA[m.i] = d || {n: m.n, s: m.s}; }).catch(function () { DATA[m.i] = {n: m.n, s: m.s}; });
    })).then(draw);
  }
  draw(); fetchClubs();

  document.addEventListener('mi-live', function (e) { LIVEROWS = (e.detail && e.detail.m) || null; draw(); });
  document.addEventListener('milr-ready', draw);
  if (window.MI_LIVE) LIVEROWS = window.MI_LIVE.m;

  // ---- follow a club: search every ranked club ----
  var q = document.getElementById('myp-q'), res = document.getElementById('myp-res'), ALL = null, asking = false, after = [];
  function norm(t) { return String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function all(cb) {
    if (ALL) return cb();
    after.push(cb);
    if (asking) return; asking = true;
    fetch('/rankings_table.json').then(function (r) { return r.json(); }).then(function (rows) {
      ALL = rows.map(function (c) { return {i: String(c.team_id), n: c.club, s: c.slug, r: c.rank, k: norm(c.club), co: c.country}; });
      var w = after; after = []; w.forEach(function (f) { f(); });
    }).catch(function () { asking = false; after = []; });
  }
  function search() {
    if (!q) return;
    var t = norm(q.value.trim());
    if (!t) { res.innerHTML = ''; return; }
    all(function () {
      var mine = {}; load().forEach(function (m) { mine[String(m.i)] = 1; });
      var hits = ALL.filter(function (c) { return c.k.indexOf(t) >= 0; })
        .sort(function (a, b) { return (a.k.indexOf(t) === 0 ? 0 : 1) - (b.k.indexOf(t) === 0 ? 0 : 1) || a.r - b.r; }).slice(0, 8);
      res.innerHTML = hits.length ? hits.map(function (c) {
        return '<button type="button" data-i="' + esc(c.i) + '"' + (mine[c.i] ? ' class="on"' : '') + '><img src="/crests/' + esc(fname(c.i)) +
          '.png" alt="" onerror="this.style.visibility=\'hidden\'">' + esc(c.n) + '<span>' + (mine[c.i] ? '&#9733; Following' : rk(c.r) + ' &middot; Follow') + '</span></button>';
      }).join('') : '<div style="padding:10px 4px;color:var(--text2);font-size:13px">No club found</div>';
    });
  }
  if (q) {
    q.addEventListener('input', search);
    q.addEventListener('focus', function () { all(function () {}); });
    res.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-i]'); if (!b) return;
      var id = b.getAttribute('data-i'), list = load();
      if (list.some(function (m) { return String(m.i) === id; })) list = list.filter(function (m) { return String(m.i) !== id; });
      else { var c = ALL.filter(function (x) { return x.i === id; })[0]; list.push({i: id, n: c.n, s: c.s}); }
      save(list); search(); fetchClubs();
    });
  }
  window.addEventListener('pageshow', function (e) { if (e.persisted) { DATA = {}; fetchClubs(); } });

  // ---- alerts (app_install.js's MIPush does the work) ----
  var bell = document.getElementById('myp-bell'), panel = document.getElementById('myp-alerts');
  var P = window.MIPush;
  function paintBell() { if (bell && P) bell.classList.toggle('on', P.on()); }
  function panelHtml(msg) {
    if (!P.supported()) {
      return P.needsInstall()
        ? '<b>Alerts work in the app.</b><br>Add MD Insights to your Home Screen (tap Share, then <b>Add to Home Screen</b>), open it from there, and turn alerts on here.'
        : '<b>This browser can\'t show alerts.</b> Try Chrome, or the app on your phone.';
    }
    if (P.blocked()) return '<b>Alerts are blocked for this site.</b><br>Turn notifications on for it in your phone or browser settings, then come back here.';
    var p = P.prefs(), on = P.on();
    var opt = function (k, t, d) {
      return '<label><input type="checkbox" data-k="' + k + '"' + (p[k] ? ' checked' : '') + '><span>' + t +
        '<br><small style="color:var(--text2);font-size:11.5px">' + d + '</small></span></label>';
    };
    return '<b>' + (on ? 'Alerts are on' : 'Alerts for the clubs you follow') + '</b>' +
      (load().length ? '' : '<br>Follow a club first - alerts are only for your clubs.') +
      opt('ft', 'Full time', 'The result, and how it moves their rating and rank') +
      opt('rk', 'Ranking moves', 'When their world rank changes - at most once a day') +
      opt('ko', 'Kick-off in 1 hour', 'With our odds for the match') +
      opt('gl', 'Goals', 'As they go in, with the live rank') +
      (on ? '<button class="off" type="button" data-off>Turn alerts off</button>'
          : '<button class="go" type="button" data-on>Turn on alerts</button>') +
      (msg ? '<div style="margin-top:8px;color:var(--red,#e84466)">' + msg + '</div>' : '');
  }
  function openPanel(msg) { panel.innerHTML = panelHtml(msg); panel.hidden = false; }
  if (bell && panel && P) {
    P.config().then(function (cfg) {
      if (!cfg) return;                      // alerts not set up yet: no bell
      bell.hidden = false; paintBell();
    });
    bell.addEventListener('click', function () { if (panel.hidden) openPanel(); else panel.hidden = true; });
    panel.addEventListener('change', function (e) {
      var k = e.target.getAttribute('data-k'); if (!k) return;
      var p = P.prefs(); p[k] = e.target.checked ? 1 : 0; P.setPrefs(p);
    });
    panel.addEventListener('click', function (e) {
      if (e.target.hasAttribute('data-on')) {
        e.target.disabled = true; e.target.textContent = 'Turning on...';
        P.enable().then(function () { paintBell(); openPanel(); })
          .catch(function (err) { paintBell(); openPanel(String(err && err.message || err) === 'blocked' ? '' : 'Couldn\'t turn alerts on: ' + esc(err && err.message || err)); });
      } else if (e.target.hasAttribute('data-off')) {
        P.disable().then(function () { paintBell(); openPanel(); });
      }
    });
  }
})();
