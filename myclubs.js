/* Matchday Insights - "My clubs" (Greg, 2026-10).
   Star a club on its page; starred clubs then show first:
     - homepage: a strip of your clubs with rank, rating and last move
     - matches page: a "My clubs" box at the top with their matches that day
   Saved in this browser only (localStorage), nothing on our side.
   <script src="myclubs.js" defer></script>  (club pages: ../myclubs.js) */
(function () {
  var KEY = 'mi_myclubs';
  var me = document.currentScript;
  var base = (me && me.getAttribute('src') || '').replace(/myclubs\.js.*$/, '');
  function load() { try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; } }
  function save(list) { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {} }
  function has(id) { return load().some(function (c) { return String(c.i) === String(id); }); }
  function esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var css = document.createElement('style');
  css.textContent =
    '.star{display:inline-flex;align-items:center;gap:7px;background:none;border:1px solid var(--border2);border-radius:20px;' +
    'padding:6px 13px 6px 10px;cursor:pointer;color:var(--text2);font-family:"JetBrains Mono",sans-serif;font-size:12px;font-weight:600}' +
    '.star svg{width:16px;height:16px}.star:hover{border-color:var(--green-dim);color:var(--text)}' +
    '.star.on{color:#f2c200;border-color:rgba(242,194,0,.5);background:rgba(242,194,0,.08)}' +
    '.my-strip{padding:14px 20px 4px}.my-h{font-family:"JetBrains Mono",sans-serif;font-size:10px;font-weight:600;letter-spacing:.14em;' +
    'text-transform:uppercase;color:var(--muted);margin-bottom:10px;display:flex;align-items:center;gap:7px}' +
    '.my-h svg{width:13px;height:13px;color:#f2c200}' +
    '.my-row{display:flex;gap:10px;overflow-x:auto;padding-bottom:10px;scrollbar-width:thin}' +
    '.my-c{flex:none;display:flex;align-items:center;gap:10px;min-width:180px;background:var(--surface2);border:1px solid var(--border2);' +
    'border-radius:10px;padding:9px 12px;text-decoration:none!important;color:var(--text)}.my-c:hover{border-color:var(--green-dim)}' +
    '.my-c img{width:28px;height:28px;object-fit:contain}.my-c b{display:block;font-size:15px;font-weight:800;text-transform:uppercase;' +
    'letter-spacing:.03em;white-space:nowrap}.my-c span{font-family:"JetBrains Mono",sans-serif;font-size:11px;color:var(--text2)}' +
    '.my-c .up{color:var(--green)}.my-c .dn{color:var(--red)}' +
    '.my-box{margin:0 0 14px;border:1px solid rgba(242,194,0,.35);border-radius:12px;overflow:hidden}' +
    '.my-box .my-h{padding:10px 14px 0;margin-bottom:4px}';
  document.head.appendChild(css);
  var STAR = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3 6.1 20.6l1.3-6.6L2.5 9.4l6.6-.8z"/></svg>';
  var STAR_O = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3 6.1 20.6l1.3-6.6L2.5 9.4l6.6-.8z"/></svg>';

  // Club page: the star button.
  document.querySelectorAll('[data-star]').forEach(function (b) {
    function paint() {
      var on = has(b.dataset.i);
      b.classList.toggle('on', on);
      b.innerHTML = (on ? STAR : STAR_O) + (on ? 'My club' : 'Add to my clubs');
      b.setAttribute('aria-pressed', on);
    }
    b.addEventListener('click', function () {
      var list = load(), id = String(b.dataset.i);
      if (has(id)) list = list.filter(function (c) { return String(c.i) !== id; });
      else list.push({i: id, n: b.dataset.n, s: b.dataset.s});
      save(list); paint();
    });
    paint();
  });

  var mine = load();
  if (!mine.length) return;

  // Homepage: a strip of your clubs, from the same ranking file the table uses.
  var strip = document.getElementById('my-clubs');
  if (strip && window.fetch) {
    fetch(base + 'rankings_table.json').then(function (r) { return r.ok ? r.json() : []; }).then(function (all) {
      var by = {}; all.forEach(function (c) { by[String(c.team_id)] = c; });
      strip.className = 'my-strip';
      strip.innerHTML = '<div class="my-h">' + STAR + 'My clubs</div><div class="my-row">' + mine.map(function (m) {
        var c = by[String(m.i)] || {};
        var mv = c.rank_change > 0 ? '<span class="up">&#9650;' + c.rank_change + '</span>'
               : c.rank_change < 0 ? '<span class="dn">&#9660;' + (-c.rank_change) + '</span>' : '';
        return '<a class="my-c" href="' + base + 'clubs/' + esc(m.s) + '.html"><img src="' + base + 'crests/' + esc(m.i) +
          '.png" alt="" onerror="this.remove()"><div><b>' + esc(c.club || m.n) + '</b><span>' +
          (c.rank ? '#' + c.rank + ' &middot; ' + c.elo.toFixed(0) + ' ' : 'Unranked ') + mv + '</span></div></a>';
      }).join('') + '</div>';
    }).catch(function () {});
  }

  // Matches page: your clubs' matches that day in a box at the top. The rows
  // carry both clubs' ids (data-hi / data-ai); copies of them go in the box,
  // so tapping one works just like the original.
  var list = document.getElementById('list');
  if (list && window.MutationObserver) {
    var ids = {}; mine.forEach(function (m) { ids[String(m.i)] = 1; });
    var busy = false;
    function mark() {
      if (busy) return; busy = true;
      var old = list.querySelector('.my-box'); if (old) old.remove();
      var rows = [].slice.call(list.querySelectorAll('.m')).filter(function (r) {
        return ids[r.dataset.hi] || ids[r.dataset.ai]; });
      if (rows.length) {
        var box = document.createElement('section');
        box.className = 'my-box';
        box.innerHTML = '<div class="my-h">' + STAR + 'My clubs</div>';
        rows.forEach(function (r) { var c = r.cloneNode(true); c.hidden = false;
          var d = c.querySelector('.md'); if (d) d.remove(); box.appendChild(c); });
        list.insertBefore(box, list.firstChild);
      }
      setTimeout(function () { busy = false; }, 0);
    }
    new MutationObserver(mark).observe(list, {childList: true});
    mark();
  }
})();
