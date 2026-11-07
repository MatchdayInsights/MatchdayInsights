/* Matchday Insights - "Top games" sorted by importance (Greg, 2026-11).
   On the Matches page, with the Top games button on, the top games show as
   one list, biggest match first, instead of grouped by league: importance
   is the two clubs' world ranks added together (No. 2 v No. 5 = 7 comes
   before No. 1 v No. 102 = 103). Each match keeps its league above it.
   The page's own rows are copied into the list, so tapping one works as
   before. Turn the button off and the league view is back.
   Loaded by app_install.js on the Matches page only. */
(function () {
  var list = document.getElementById('list'), btn = document.getElementById('top-only');
  if (!list || !btn || typeof window.filter !== 'function' || window.MI_TOPSORT) return;
  window.MI_TOPSORT = 1;

  var css = document.createElement('style');
  css.textContent =
    // the "Your competitions" / "All competitions" headings go too, or they'd
    // stand over nothing when a competition is starred (Greg, 2026-11)
    '#list.mi-topsort>.cont,#list.mi-topsort>.comp,#list.mi-topsort>.fav-h{display:none!important}' +
    '.mi-top{border:1px solid var(--border2);border-radius:12px;overflow:hidden;margin:0 0 14px;background:var(--surface)}' +
    '.mi-top-h,.mi-top-c{font-family:"JetBrains Mono",Inter,sans-serif}.mi-top-h{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--surface2);font-weight:700;font-size:14px;color:var(--text)}' +
    '.mi-top-h span{margin-left:auto;font-weight:500;font-size:11.5px;color:var(--muted)}' +
    '.mi-top-c{padding:9px 14px 0;font-size:11.5px;color:var(--muted);border-top:1px solid var(--border2)}' +
    '.mi-top-c:first-of-type{border-top:0}.mi-top .m{border-top:0!important}';
  document.head.appendChild(css);

  function rank(row, side) {
    var el = row.querySelectorAll('.side')[side];
    var t = el && el.querySelector('.rk') ? el.querySelector('.rk').textContent : '';
    var m = t.match(/#(\d+)/);                     // "#12" or "#12→#10" (live): the rank before the match
    return m ? +m[1] : 9999;
  }

  function build() {
    var old = list.querySelector('.mi-top'); if (old) old.remove();
    var on = btn.getAttribute('aria-pressed') === 'true';
    list.classList.toggle('mi-topsort', on);
    if (!on) return;
    var rows = [];
    list.querySelectorAll('.comp:not([hidden])').forEach(function (sec) {
      var nm = sec.querySelector('.comp-n'), cn = sec.querySelector('.comp-c');
      var label = (nm ? nm.textContent : '') + (cn && cn.textContent ? ' · ' + cn.textContent : '');
      sec.querySelectorAll('.m:not([hidden])').forEach(function (r) {
        rows.push({r: r, label: label, score: rank(r, 0) + rank(r, 1), order: rows.length});
      });
    });
    if (!rows.length) { list.classList.remove('mi-topsort'); return; }
    rows.sort(function (a, b) { return a.score - b.score || a.order - b.order; });
    var box = document.createElement('section');
    box.className = 'mi-top';
    box.innerHTML = '<div class="mi-top-h">&#9733; Top games<span>Biggest first</span></div>';
    rows.forEach(function (x) {
      var c = document.createElement('div'); c.className = 'mi-top-c'; c.textContent = x.label;
      var r = x.r.cloneNode(true); r.hidden = false;
      box.appendChild(c); box.appendChild(r);
    });
    var mine = list.querySelector('.my-box');
    list.insertBefore(box, mine ? mine.nextSibling : list.firstChild);
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
