/* Matchday Insights - live scores on the national team pages (Greg, 2026-11).
   The match cards (.nt-fx[data-fid]) get the score and the minute from the
   same live worker as the Matches page (/live). It only asks while a match on
   the page is on or about to start (kicked off in the last 3 hours, or within
   the next 10 minutes), once a minute, and not while the page is hidden. */
(function () {
  var me = document.currentScript, api = me && me.getAttribute('data-api');
  var cards = document.querySelectorAll('.nt-fx[data-fid]');
  if (!api || !cards.length) return;
  var LIVE = {'1H': 1, 'HT': 1, '2H': 1, 'ET': 1, 'BT': 1, 'P': 1, 'LIVE': 1, 'INT': 1, 'SUSP': 1};
  var DONE = {'FT': 'FT', 'AET': 'FT (aet)', 'PEN': 'FT (pens)'};
  var by = {};
  [].forEach.call(cards, function (c) { by[c.getAttribute('data-fid')] = c; });

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function onSoon() {
    var now = Date.now();
    return [].some.call(cards, function (c) {
      var k = Date.parse(c.getAttribute('data-kick'));
      return k && k - now < 10 * 60e3 && now - k < 3 * 3600e3;
    });
  }
  function score(row, h, a) {                           // "1 - 0" between the two teams
    var g = row.querySelector('.nt-sc');
    if (!g) { g = document.createElement('b'); g.className = 'nt-sc'; row.insertBefore(g, row.children[1]); }
    g.textContent = h + ' \u2013 ' + a;
  }
  function show(c, r) {
    var st = r[2], when = c.querySelector('.nt-when'), row = c.querySelector('.nt-fx-t');
    if (!when || !row || row.children.length < 2) return;
    if (!when.getAttribute('data-was')) when.setAttribute('data-was', when.innerHTML);
    var label = st === 'HT' ? 'HALF TIME' : LIVE[st] ? 'LIVE ' + (r[3] != null ? r[3] + "'" : '') : DONE[st];
    if (!label) return;                                   // not started yet
    when.innerHTML = (LIVE[st] ? '<i class="nt-dot"></i>' : '') + esc(label);
    c.classList.toggle('nt-on', !!LIVE[st]);
    c.classList.toggle('nt-ft', !!DONE[st]);
    score(row, r[4] || 0, r[5] || 0);
  }
  function poll() {
    if (document.hidden || !onSoon()) return;
    fetch(api + '/live', {cache: 'no-store'}).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { (d && d.m || []).forEach(function (r) { var c = by[String(r[0])]; if (c) show(c, r); }); })
      .catch(function () {});
  }
  poll();
  setInterval(poll, 60000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
})();
