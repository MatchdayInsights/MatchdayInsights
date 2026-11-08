/* Matchday Insights - "Top games" on the Matches page, sorted three ways
   (Greg, 2026-11). With the Top games button on, a small bar offers:
     Biggest - one list, biggest match first: the two clubs' world ranks
               added together, lowest first (No. 2 v No. 5 = 7 comes before
               No. 1 v No. 102 = 103)
     Time    - one list in kick-off order
     League  - the usual view, grouped by continent and league
   The choice is remembered on this phone. In the one-list views each match
   keeps its league above it, and the page's own rows are copied in, so
   tapping one works as before. Turn the button off and everything is back.
   Loaded by app_install.js on the Matches page only. */
(function () {
  var list = document.getElementById('list'), btn = document.getElementById('top-only');
  if (!list || !btn || typeof window.filter !== 'function' || window.MI_TOPSORT) return;
  window.MI_TOPSORT = 1;
  var KEY = 'mi_top_sort', MODE = 'big';
  try { MODE = localStorage.getItem(KEY) || 'big'; } catch (e) {}
  if (['big', 'time', 'league'].indexOf(MODE) < 0) MODE = 'big';

  var css = document.createElement('style');
  css.textContent =
    // the "Your competitions" / "All competitions" headings go too, or they'd
    // stand over nothing when a competition is starred (Greg, 2026-11)
    '#list.mi-topsort>.cont,#list.mi-topsort>.comp,#list.mi-topsort>.fav-h{display:none!important}' +
    '.mi-topbar,.mi-top-c{font-family:"JetBrains Mono",Inter,sans-serif}' +
    '.mi-topbar{display:flex;align-items:center;gap:8px;margin:0 0 10px;font-size:12px;color:var(--muted)}' +
    '.mi-seg{display:inline-flex;border:1px solid var(--border2);border-radius:9px;overflow:hidden}' +
    '.mi-seg button{background:none;border:0;padding:7px 13px;font:inherit;font-size:13px;font-weight:600;color:var(--text2);cursor:pointer}' +
    '.mi-seg button+button{border-left:1px solid var(--border2)}' +
    '.mi-seg button.on{background:var(--green,#3dba5e);color:#fff}' +
    '.mi-top{border:1px solid var(--border2);border-radius:12px;overflow:hidden;margin:0 0 14px;background:var(--surface)}' +
    '.mi-top-c{padding:9px 14px 0;font-size:11.5px;color:var(--muted);border-top:1px solid var(--border2)}' +
    '.mi-top-c:first-child{border-top:0}.mi-top .m{border-top:0!important}';
  document.head.appendChild(css);

  function rank(row, side) {
    var el = row.querySelectorAll('.side')[side];
    var t = el && el.querySelector('.rk') ? el.querySelector('.rk').textContent : '';
    var m = t.match(/#(\d+)/);                     // "#12" or "#12→#10" (live): the rank before the match
    return m ? +m[1] : 9999;
  }

  // Kick-off times: from the day's own file (the page has just loaded it,
  // so it comes from the browser's cache), matched on the two club names.
  var TIMES = {}, timesFor = null;
  function dayKey() { var on = document.querySelector('#days .day.on'); return on ? on.getAttribute('data-k') : null; }
  function loadTimes(k, done) {
    if (!k || timesFor === k) return done();
    fetch('matches/' + k + '.json').then(function (r) { return r.ok ? r.json() : []; }).then(function (ms) {
      TIMES = {}; timesFor = k;
      (ms || []).forEach(function (m) {
        if (m && m.h && m.a) TIMES[(m.h.n + ' ' + m.a.n).toLowerCase()] = m.t || '';
      });
      done();
    }).catch(done);
  }

  function bar() {
    var b = list.querySelector('.mi-topbar');
    if (!b) {
      b = document.createElement('div'); b.className = 'mi-topbar';
      b.innerHTML = 'Sort <span class="mi-seg"><button type="button" data-s="big">Biggest</button>' +
        '<button type="button" data-s="time">Time</button><button type="button" data-s="league">League</button></span>';
      b.addEventListener('click', function (e) {
        var s = e.target.getAttribute('data-s'); if (!s || s === MODE) return;
        MODE = s; try { localStorage.setItem(KEY, s); } catch (x) {}
        build();
      });
    }
    b.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x.getAttribute('data-s') === MODE); });
    var mine = list.querySelector('.my-box');
    list.insertBefore(b, mine ? mine.nextSibling : list.firstChild);
    return b;
  }

  function build() {
    var old = list.querySelector('.mi-top'); if (old) old.remove();
    var on = btn.getAttribute('aria-pressed') === 'true';
    if (!on) {
      var ob = list.querySelector('.mi-topbar'); if (ob) ob.remove();
      list.classList.remove('mi-topsort');
      return;
    }
    var rows = [];
    list.querySelectorAll('.comp:not([hidden])').forEach(function (sec) {
      var nm = sec.querySelector('.comp-n'), cn = sec.querySelector('.comp-c');
      var label = (nm ? nm.textContent : '') + (cn && cn.textContent ? ' · ' + cn.textContent : '');
      sec.querySelectorAll('.m:not([hidden])').forEach(function (r) {
        rows.push({r: r, label: label, score: rank(r, 0) + rank(r, 1), q: r.getAttribute('data-q') || '', order: rows.length});
      });
    });
    if (!rows.length) { var nb = list.querySelector('.mi-topbar'); if (nb) nb.remove(); list.classList.remove('mi-topsort'); return; }
    var b = bar();
    if (MODE === 'league') { list.classList.remove('mi-topsort'); return; }
    function draw() {
      if (MODE === 'time') {
        rows.sort(function (a, c) { var x = TIMES[a.q] || '~', y = TIMES[c.q] || '~'; return x < y ? -1 : x > y ? 1 : a.order - c.order; });
      } else {
        rows.sort(function (a, c) { return a.score - c.score || a.order - c.order; });
      }
      var gone = list.querySelector('.mi-top'); if (gone) gone.remove();
      var box = document.createElement('section');
      box.className = 'mi-top';
      rows.forEach(function (x) {
        var c = document.createElement('div'); c.className = 'mi-top-c'; c.textContent = x.label;
        var r = x.r.cloneNode(true); r.hidden = false;
        box.appendChild(c); box.appendChild(r);
      });
      list.insertBefore(box, b.nextSibling);
      list.classList.add('mi-topsort');
    }
    if (MODE === 'time') loadTimes(dayKey(), draw); else draw();
  }

  var orig = window.filter;
  window.filter = function () { var out = orig.apply(this, arguments); try { build(); } catch (e) {} return out; };
  // The search box calls the page's own filter() directly: rebuild after it.
  var q = document.getElementById('q');
  if (q) q.addEventListener('input', function () { setTimeout(function () { try { build(); } catch (e) {} }, 0); });
  // The page redraws #list when the day changes or live scores arrive;
  // filter() runs after each redraw, so the list is rebuilt with it.
  if (btn.getAttribute('aria-pressed') === 'true') build();
})();
