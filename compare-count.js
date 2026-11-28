/* Compare page: how long each club has been ahead of the other, by rating
   and by world rank (Greg, 2026-11: "give me the count of how many times
   club A was ahead of club B ... for both rank and rating").
   Loaded by app_install.js when the page has the History chart; wraps the
   page's chart() so it redraws with it. Counted in DAYS: each club's last
   saved value holds until its next one (history isn't saved every day), from
   the first day both clubs have a value to the latest one. Look-only. */
(function () {
  if (typeof window.chart !== "function") return;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function days(ha, hb, key, lowerBetter) {
    var ma = {}, mb = {};
    ha.dates.forEach(function (d, i) { ma[d] = ha[key][i]; });
    hb.dates.forEach(function (d, i) { mb[d] = hb[key][i]; });
    var all = Object.keys(Object.assign({}, ma, mb)).sort(function (x, y) { return new Date(x) - new Date(y); });
    var va = null, vb = null, a = 0, b = 0, lv = 0, prev = null, prevA = null, prevB = null;
    all.forEach(function (d) {
      var t = new Date(d);
      if (prev && prevA != null && prevB != null) {
        var n = Math.max(0, Math.round((t - prev) / 864e5));
        if (prevA === prevB) lv += n;
        else if (lowerBetter ? prevA < prevB : prevA > prevB) a += n; else b += n;
      }
      if (ma[d] != null) va = ma[d];
      if (mb[d] != null) vb = mb[d];
      prev = t; prevA = va; prevB = vb;
    });
    if (prev && prevA != null && prevB != null) {            // the latest day counts too
      if (prevA === prevB) lv += 1; else if (lowerBetter ? prevA < prevB : prevA > prevB) a += 1; else b += 1;
    }
    return a + b + lv ? [a, b, lv] : null;
  }
  function fmt(n) { return n.toLocaleString("en-US"); }
  function row(label, c) {
    if (!c) return "";
    var t = c[0] + c[1] + c[2], wa = c[0] >= c[1];
    return '<div class="cc-row"><span class="cc-l">' + label + '</span>'
      + '<span class="cc-n" style="color:var(--ca)">' + (wa ? "<b>" : "") + fmt(c[0]) + (wa ? "</b>" : "") + '</span>'
      + '<span class="cc-bar"><i style="width:' + (100 * c[0] / t) + '%;background:var(--ca)"></i><i style="width:' + (100 * c[2] / t) + '%;background:#5a6888"></i><i style="width:' + (100 * c[1] / t) + '%;background:var(--cb)"></i></span>'
      + '<span class="cc-n" style="color:var(--cb)">' + (!wa ? "<b>" : "") + fmt(c[1]) + (!wa ? "</b>" : "") + '</span></div>';
  }
  function add() {
    var box = document.getElementById("chart"); if (!box) return;
    var old = document.getElementById("cc-box"); if (old) old.remove();
    var ha, hb, A_, B_;
    try { ha = H && H[A.team_id]; hb = H && H[B.team_id]; A_ = A; B_ = B; } catch (e) { return; }
    if (!ha || !hb || !ha.dates || !hb.dates) return;
    var e = ha.e && hb.e ? days(ha, hb, "e", false) : null;
    var r = ha.r && hb.r ? days(ha, hb, "r", true) : null;
    if (!e && !r) return;
    var d = document.createElement("div"); d.id = "cc-box";
    d.innerHTML = '<div class="cc-h">Days ahead of the other <small>since both were rated</small></div>'
      + '<div class="cc-row cc-top"><span class="cc-l"></span><span class="cc-n" style="color:var(--ca)">' + esc(A_.club) + '</span><span></span><span class="cc-n" style="color:var(--cb)">' + esc(B_.club) + '</span></div>'
      + row("Rating", e) + row("World rank", r);
    box.parentNode.insertBefore(d, box.nextSibling);
  }
  var css = document.createElement("style");
  css.textContent = "#cc-box{margin-top:14px;font-family:var(--mi-read,sans-serif)}"
    + "#cc-box .cc-h{font-size:13px;font-weight:600;margin-bottom:6px}#cc-box .cc-h small{font-weight:400;color:var(--muted)}"
    + "#cc-box .cc-row{display:grid;grid-template-columns:84px 1fr 2fr 1fr;align-items:center;gap:10px;padding:6px 0}"
    + "#cc-box .cc-top{padding:0;font-size:12px}#cc-box .cc-top .cc-n{font-size:12px;font-weight:600;overflow-wrap:normal;word-break:normal;line-height:1.25}"
    + "#cc-box .cc-l{font-size:13px;color:var(--text2);white-space:nowrap}#cc-box .cc-n{font-size:15px;text-align:center;font-variant-numeric:tabular-nums}"
    + "#cc-box .cc-n b{font-weight:700}#cc-box .cc-bar{display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--border2)}"
    + "@media(max-width:520px){#cc-box .cc-row{grid-template-columns:76px 1fr 1.2fr 1fr;gap:6px}}";
  document.head.appendChild(css);
  var orig = window.chart;
  window.chart = function () { var out = orig.apply(this, arguments); try { add(); } catch (e) {} return out; };
  try { add(); } catch (e) {}
})();
