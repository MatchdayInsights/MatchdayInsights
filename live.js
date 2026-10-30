/* Matchday Insights - live scores on any page (Greg, 2026-10).
   <script src="live.js" data-api="https://...workers.dev" [data-tid="327"] [data-fid="1234"] [data-base="../"]></script>

   Asks the live-scores worker once a minute, only while the page is on
   screen, and fills in whatever this page has:
     - a red LIVE strip under the menu: on a club page (data-tid) while that
       club plays; elsewhere "N matches on now"; not on match pages
     - a match page (data-fid): the scoreboard shows the live score and minute,
       then the final score once it ends (until the page is rebuilt)
     - a club page: its next match in "Upcoming" shows the live score
     - the homepage: "Biggest matches" cards being played show the score
   Other scripts can use the same data: it is kept in window.MI_LIVE and a
   "mi-live" event is sent each time it arrives. When a match is on it also
   loads live_ratings.js (rating changes and ranks "if it ends like this"). */
(function () {
  var me = document.currentScript; if (!me || !window.fetch) return;
  var api = me.getAttribute('data-api'); if (!api) return;
  var tid = (me.getAttribute('data-tid') || '').split('::')[0];
  var fid = me.getAttribute('data-fid') || '';
  var base = me.getAttribute('data-base') || '';
  var LIVE = {'1H':1,'HT':1,'2H':1,'ET':1,'BT':1,'P':1,'SUSP':1,'INT':1,'LIVE':1};
  var DONE = {'FT':1,'AET':1,'PEN':1};
  var RED = '#e5484d';
  var css = document.createElement('style');
  css.textContent = '.live-strip{display:flex;align-items:center;gap:10px;justify-content:center;flex-wrap:wrap;' +
    'padding:9px 16px;background:rgba(229,72,77,.12);border-bottom:1px solid rgba(229,72,77,.35);' +
    "font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text,#fff)}" +
    '.live-strip[hidden]{display:none}.live-strip b{font-weight:700}.live-strip a{color:inherit;text-decoration:none}' +
    '.lv{color:' + RED + ';font-weight:700;letter-spacing:1px}' +
    '.lv .dot,.live-strip .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:' + RED + ';margin-right:6px;' +
    'animation:lsb 1.4s infinite;vertical-align:1px}@keyframes lsb{50%{opacity:.25}}' +
    '.sb-mid .sb-st.lv{font-size:12px}.up-live{display:block;color:' + RED + ';font-weight:700}' +
    '.fmatch-meta.lv{color:' + RED + '}';
  document.head.appendChild(css);

  var box = null;
  if (!fid) {
    box = document.createElement('div');
    box.className = 'live-strip'; box.hidden = true;
    var nav = document.querySelector('.site-nav');
    if (nav && nav.parentNode) nav.parentNode.insertBefore(box, nav.nextSibling);
    else document.body.insertBefore(box, document.body.firstChild);
  }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function minute(r) { return r[2] === 'HT' ? 'HT' : (r[3] != null ? r[3] + "'" : 'LIVE'); }
  function score(r) { return (r[4] == null ? 0 : r[4]) + ' - ' + (r[5] == null ? 0 : r[5]); }
  function norm(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }

  function strip(live) {
    if (!box) return;
    if (tid) {
      var g = live.filter(function (r) { return String(r[6]) === tid || String(r[7]) === tid; })[0];
      if (!g) { box.hidden = true; return; }
      box.innerHTML = '<span class="lv"><i class="dot"></i>' + esc(g[2] === 'HT' ? 'HALF TIME' : minute(g)) + '</span>' +
        '<a href="' + base + 'matches.html"><b>' + esc(g[8]) + ' ' + esc(score(g)) + ' ' + esc(g[9]) + '</b> &rsaquo;</a>';
      box.hidden = false;
    } else {
      if (!live.length) { box.hidden = true; return; }
      box.innerHTML = '<a href="' + base + 'matches.html"><span class="lv"><i class="dot"></i>LIVE</span> ' +
        '<b>' + live.length + '</b> match' + (live.length === 1 ? '' : 'es') +
        ' on now in our competitions &rsaquo;</a>';
      box.hidden = false;
    }
  }

  // Match page: the scoreboard in the middle.
  function matchPage(all) {
    if (!fid) return;
    var mid = document.querySelector('.sb-mid'); if (!mid) return;
    var r = all.filter(function (x) { return String(x[0]) === fid; })[0]; if (!r) return;
    if (LIVE[r[2]]) {
      mid.innerHTML = '<div class="sb-score">' + esc(score(r)) + '</div>' +
        '<div class="sb-st lv"><i class="dot"></i>' + esc(minute(r)) + '</div>';
    } else if (DONE[r[2]] && !mid.getAttribute('data-final')) {
      mid.setAttribute('data-final', '1');
      mid.innerHTML = '<div class="sb-score">' + esc(score(r)) + '</div>' +
        '<div class="sb-st">' + (r[2] === 'FT' ? 'Full time' : r[2] === 'AET' ? 'After extra time' : 'Penalties') + '</div>';
    }
  }

  // Club page: the next match in "Upcoming" - the one that has kicked off.
  function clubPage(live) {
    if (!tid) return;
    var g = live.filter(function (r) { return String(r[6]) === tid || String(r[7]) === tid; })[0];
    var rows = document.querySelectorAll('.upcoming-row[data-kickoff]');
    for (var i = 0; i < rows.length; i++) {
      var el = rows[i].querySelector('.up-when'); if (!el) continue;
      var old = el.parentNode.querySelector('.up-live');
      if (old) old.remove();
      if (g && new Date(rows[i].getAttribute('data-kickoff')) <= new Date(Date.now() + 15 * 60000)) {
        el.insertAdjacentHTML('afterend', '<span class="up-live">' + esc(minute(g)) + ' ' + esc(score(g)) + '</span>');
        break;
      }
    }
  }

  // Homepage: "Biggest matches" cards (found by the two club names).
  function cards(live) {
    var cs = document.querySelectorAll('.fmatch'); if (!cs.length) return;
    var by = {};
    live.forEach(function (r) { by[norm(r[8]) + '|' + norm(r[9])] = r; });
    for (var i = 0; i < cs.length; i++) {
      var n = cs[i].querySelectorAll('.fmatch-name'); if (n.length < 2) continue;
      var r = by[norm(n[0].textContent) + '|' + norm(n[1].textContent)];
      var meta = cs[i].querySelector('.fmatch-meta'); if (!meta) continue;
      if (!meta.getAttribute('data-was')) meta.setAttribute('data-was', meta.innerHTML);
      if (r) { meta.innerHTML = '<i class="dot"></i>LIVE ' + esc(minute(r)) + ' &middot; ' + esc(score(r)); meta.classList.add('lv'); }
      else { meta.innerHTML = meta.getAttribute('data-was'); meta.classList.remove('lv'); }
    }
  }

  var last = null, lrAsked = false;
  function draw() {
    if (!last) return;
    var live = last.m.filter(function (r) { return LIVE[r[2]]; });
    strip(live); matchPage(last.m); clubPage(live); cards(live);
  }

  var fails = 0, again = null;
  function retry() {
    if (again || ++fails > 3) return;
    again = setTimeout(function () { again = null; poll(); }, 10000);
  }
  function poll() {
    if (document.hidden) return;
    fetch(api + '/live', {cache: 'no-store'}).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.m) { retry(); return; }
        fails = 0; last = d; window.MI_LIVE = d;
        draw();
        // Live ratings ("if it ends like this"): loaded the first time a match is on.
        if (!window.MILR && !lrAsked && d.m.some(function (r) { return LIVE[r[2]]; })) {
          lrAsked = true;
          var sc = document.createElement('script');
          sc.src = base + 'live_ratings.js'; sc.setAttribute('data-base', base);
          document.head.appendChild(sc);
        }
        setTimeout(draw, 2500);            // cards drawn by the page after its own data loads
        try { document.dispatchEvent(new CustomEvent('mi-live', {detail: d})); } catch (e) {}
      }).catch(retry);
  }
  poll(); setInterval(poll, 60000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
})();
