/* Matchday Insights - live scores on any page (Greg, 2026-10).
   <script src="live.js" data-api="https://...workers.dev" data-tid="327"></script>
   With data-tid (a club page): a LIVE strip at the top while that club plays.
   Without (the homepage): "N matches live now" linking to the Matches page.
   Asks once a minute, only while the page is on screen. */
(function () {
  var me = document.currentScript; if (!me || !window.fetch) return;
  var api = me.getAttribute('data-api'); if (!api) return;
  var tid = (me.getAttribute('data-tid') || '').split('::')[0];
  var base = me.getAttribute('data-base') || '';
  var LIVE = {'1H':1,'HT':1,'2H':1,'ET':1,'BT':1,'P':1,'SUSP':1,'INT':1,'LIVE':1};
  var box = document.createElement('div');
  box.className = 'live-strip'; box.hidden = true;
  var css = document.createElement('style');
  css.textContent = '.live-strip{display:flex;align-items:center;gap:10px;justify-content:center;flex-wrap:wrap;' +
    'padding:9px 16px;background:rgba(229,72,77,.12);border-bottom:1px solid rgba(229,72,77,.35);' +
    "font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text,#fff)}" +
    '.live-strip b{font-weight:700}.live-strip a{color:inherit;text-decoration:none}' +
    '.live-strip .lv{color:#e5484d;font-weight:700;letter-spacing:1px}' +
    '.live-strip .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#e5484d;margin-right:6px;' +
    'animation:lsb 1.4s infinite;vertical-align:1px}@keyframes lsb{50%{opacity:.25}}';
  document.head.appendChild(css);
  var nav = document.querySelector('.site-nav');
  if (nav && nav.parentNode) nav.parentNode.insertBefore(box, nav.nextSibling);
  else document.body.insertBefore(box, document.body.firstChild);
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function poll() {
    if (document.hidden) return;
    fetch(api + '/live', {cache: 'no-store'}).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.m) { retry(); return; }
        fails = 0;
        var live = d.m.filter(function (r) { return LIVE[r[2]]; });
        if (tid) {
          var g = live.filter(function (r) { return String(r[6]) === tid || String(r[7]) === tid; })[0];
          if (!g) { box.hidden = true; return; }
          var min = g[2] === 'HT' ? 'HALF TIME' : (g[3] != null ? g[3] + "'" : 'LIVE');
          box.innerHTML = '<span class="lv"><i class="dot"></i>' + esc(min) + '</span>' +
            '<a href="' + base + 'matches.html"><b>' + esc(g[8]) + ' ' + esc(g[4] == null ? 0 : g[4]) +
            ' - ' + esc(g[5] == null ? 0 : g[5]) + ' ' + esc(g[9]) + '</b> &rsaquo;</a>';
          box.hidden = false;
        } else {
          if (!live.length) { box.hidden = true; return; }
          box.innerHTML = '<a href="' + base + 'matches.html"><span class="lv"><i class="dot"></i>LIVE</span> ' +
            '<b>' + live.length + '</b> match' + (live.length === 1 ? '' : 'es') +
            ' on now in our competitions &rsaquo;</a>';
          box.hidden = false;
        }
      }).catch(retry);
  }
  // No answer: try again in 10 seconds, up to 3 times in a row (Greg, 2026-10).
  var fails = 0, again = null;
  function retry() {
    if (again || ++fails > 3) return;
    again = setTimeout(function () { again = null; poll(); }, 10000);
  }
  poll(); setInterval(poll, 60000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
})();
