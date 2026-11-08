/* Matchday Insights - sortable tables on the league stats pages (2026-11).
   Tap a column heading to sort by it (again to flip). Long player lists
   show the first 50, with a "Show all players" button. */
(function () {
  document.querySelectorAll('table[data-sort]').forEach(function (t) {
    var head = t.rows[0], body = [].slice.call(t.rows, 1), col = -1, down = true;
    var btn = t.parentNode.querySelector('.pl-all'), all = false;
    function val(r, i) {
      var c = r.cells[i]; if (!c) return '';
      var s = c.textContent.replace(/,/g, '').trim(), n = parseFloat(s);
      return /^-?\d/.test(s) ? n : s.toLowerCase();
    }
    function show() {
      body.forEach(function (r, i) { r.hidden = btn && !all && i >= 50; t.tBodies[0].appendChild(r); });
      if (btn) btn.hidden = all || body.length <= 50;
    }
    [].forEach.call(head.cells, function (th, i) {
      th.addEventListener('click', function () {
        down = col === i ? !down : (typeof val(body[0] || head, i) === 'number');
        col = i;
        [].forEach.call(head.cells, function (h) { h.classList.toggle('on', h === th); });
        body.sort(function (a, b) {
          var x = val(a, i), y = val(b, i);
          if (x === y) return 0;
          return (x > y ? 1 : -1) * (down ? -1 : 1);
        });
        show();
      });
    });
    if (btn) btn.addEventListener('click', function () { all = true; show(); });
    show();
  });
})();
