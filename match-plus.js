/* match-plus.js - more colour on a match page's Match tab (Greg, 2026-11:
   "pretty dense ... not a lot of color. A lineup on a soccer field ... the
   face of the goalscorers and top performer by rating").

   Loaded by app_install.js when the page has a Match tab (#tab-m). It wraps
   the page's own MIRenderMatch, so old pages get it too without a rebuild,
   and live updates redraw it. Adds, from match_details.compact()'s data:
     - Player of the match (the best rating, "tp") and the goalscorers, with
       their photos (API-Football's player pictures, as on the player pages);
     - both line-ups on a pitch from the line-ups' grid ("row:col"), each
       player's number, surname, rating and goals / cards / subs, names
       linked to player pages (window.MI_PL, from live_tags.py);
     - the bigger number in each stat in its side's colour.
   Matches saved before 2026-11-15 have no grid, ratings or scorer ids: then
   only what can be drawn is (the plain line-up list stays as it was). */
(function () {
  var box = document.getElementById("tab-m");
  if (!box || window.MI_PLUS) return;
  window.MI_PLUS = 1;
  var HOME = "#3dba5e", AWAY = "#e5484d";
  var H = box.dataset.h || "Home", A = box.dataset.a || "Away";
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function key(n) { return String(n || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^\x00-\x7f]/g, "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim(); }
  var CUR = null;            // the details being drawn: their own "pl" links too
  function page(side, name) {
    var k = key(name), L = window.MI_PL, P = CUR && CUR.pl;
    var t = k.split(" "), k2 = t.length > 1 ? t[0].charAt(0) + " " + t.slice(1).join(" ") : k;   // "adrian svanback" -> "a svanback"
    if (k2 !== k) return page2(side, k, L, P) || page2(side, k2, L, P);
    return page2(side, k, L, P);
  }
  function page2(side, k, L, P) {
    // National match pages and older pages have no MI_PL: the details file's
    // own "pl" (match_details.py) links the names then (Greg, 2026-11).
    return (L && L[side] && L[side][k]) || (P && P[side] && P[side][k]) || null;
  }
  function named(side, name, text) {
    var p = page(side, name), t = esc(text == null ? name : text);
    return p ? '<a href="../players/' + p + '.html">' + t + "</a>" : t;
  }
  function photo(id) { return id ? "https://media.api-sports.io/football/players/" + id + ".png" : ""; }
  function face(id, name, cls) {
    var ini = String(name || "?").split(" ").map(function (w) { return w[0] || ""; }).join("").slice(0, 2).toUpperCase();
    return '<span class="mp-face ' + (cls || "") + '"><b>' + esc(ini) + "</b>" +
      (id ? '<img src="' + photo(id) + '" alt="" loading="lazy" onerror="this.remove()">' : "") + "</span>";
  }
  function surname(n) {
    var p = String(n || "").split(" ");
    return p.length > 1 && p[p.length - 1].length > 2 ? p.slice(1).join(" ") : n;
  }
  function rateCls(r) { return r >= 8 ? "r8" : r >= 7 ? "r7" : r >= 6 ? "r6" : "r5"; }

  var CSS = "" +
    "#tab-m .ev a{color:inherit;text-decoration:none;border-bottom:1px dotted currentColor}" +
    ".mp-key{display:grid;grid-template-columns:1fr;gap:10px;margin:18px 0 6px}" +
    ".mp-motm{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:14px;background:linear-gradient(120deg,rgba(61,186,94,.16),rgba(61,186,94,.04));border:1px solid rgba(61,186,94,.35)}" +
    ".mp-motm .mp-face{width:58px;height:58px}" +
    ".mp-motm .mt{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--green);font-weight:700}" +
    ".mp-motm .mn{font-size:17px;font-weight:700;color:var(--text);line-height:1.2}.mp-motm .mn a{color:inherit;text-decoration:none}" +
    ".mp-motm .ms{font-size:12px;color:var(--muted)}" +
    ".mp-motm .mr{margin-left:auto;font-size:22px;font-weight:800;color:#fff;border-radius:10px;padding:6px 10px}" +
    ".mp-goals{display:grid;grid-template-columns:1fr 1fr;gap:8px}" +
    ".mp-goals>div{display:flex;flex-direction:column;gap:6px}.mp-goals>div.a{align-items:flex-end}" +
    ".mp-g{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--text)}.mp-goals .a .mp-g{flex-direction:row-reverse;text-align:right}" +
    ".mp-g a{color:inherit;text-decoration:none;font-weight:600}.mp-g small{display:block;color:var(--muted);font-size:11px}" +
    ".mp-g .mp-face{width:34px;height:34px}" +
    ".mp-face{position:relative;flex:none;border-radius:50%;overflow:hidden;background:var(--surface2);border:2px solid var(--border2);display:inline-flex;align-items:center;justify-content:center}" +
    ".mp-face b{font-size:12px;color:var(--muted)}.mp-face img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:var(--surface2)}" +
    ".mp-pitch{position:relative;margin:8px auto 4px;max-width:520px;aspect-ratio:68/105;border-radius:14px;overflow:hidden;" +
    "background:repeating-linear-gradient(180deg,#2f8f4e 0 9.5%,#2a8447 9.5% 19%);box-shadow:inset 0 0 0 2px rgba(255,255,255,.55)}" +
    ".mp-pitch .ln{position:absolute;border:2px solid rgba(255,255,255,.55);pointer-events:none}" +
    ".mp-pitch .half{left:0;right:0;top:50%;height:0;border-width:2px 0 0}" +
    ".mp-pitch .cc{left:50%;top:50%;width:26%;aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%}" +
    ".mp-pitch .bx{left:22%;right:22%;height:15%}.mp-pitch .bx.t{top:-2px}.mp-pitch .bx.b{bottom:-2px}" +
    ".mp-pitch .gx{left:37%;right:37%;height:5.5%}.mp-pitch .gx.t{top:-2px}.mp-pitch .gx.b{bottom:-2px}" +
    ".mp-pl{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;width:23%;text-align:center}" +
    ".mp-pl .sh{position:relative;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;color:#fff;border:2px solid rgba(255,255,255,.9);box-shadow:0 2px 6px rgba(0,0,0,.35)}" +
    ".mp-pl .nm{margin-top:3px;font-size:10.5px;font-weight:600;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.7);line-height:1.15;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".mp-pl .nm a{color:#fff;text-decoration:none}" +
    ".mp-pl .rt{position:absolute;top:-7px;right:-16px;font-size:9.5px;font-weight:800;color:#fff;border-radius:6px;padding:1px 4px;line-height:1.3}" +
    ".mp-pl .ic{position:absolute;bottom:-5px;left:-12px;font-size:11px;line-height:1;white-space:nowrap;text-shadow:none}" +
    ".mp-pl .ic i{display:inline-block;width:7px;height:10px;border-radius:1px;margin-left:1px}" +
    ".r8{background:#1a9b55}.r7{background:#5bb85c}.r6{background:#e6a817}.r5{background:#e5484d}" +
    ".mp-tm{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);max-width:520px;margin:10px auto 0}" +
    ".mp-tm b{color:var(--text)}" +
    ".mp-hidexi .lus ol{display:none}.mp-hidexi .lus .bn{margin-top:2px}" +
    ".mf .strow .v.lead{font-weight:800}.mf .strow .v.lead.h{color:" + HOME + "}.mf .strow .v.lead.a{color:" + AWAY + "}" +
    "@media (max-width:600px){.mp-pl .sh{width:26px;height:26px;font-size:11px}.mp-pl .nm{font-size:9.5px}.mp-pl .rt{right:-14px;font-size:9px}}";
  var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);

  function goalsBy(d) {
    var g = { h: [], a: [] };
    (d.ev || []).forEach(function (e) {
      var k = e[3]; if (k !== "g" && k !== "p" && k !== "og") return;
      // An own goal counts for the other side.
      var side = k === "og" ? (e[2] === "h" ? "a" : "h") : e[2];
      var nm = e[4] || "?", prev = null;
      g[side].forEach(function (x) { if (x.n === nm && x.og === (k === "og")) prev = x; });
      var m = e[0] + (e[1] ? "+" + e[1] : "") + "'" + (k === "p" ? " pen" : k === "og" ? " og" : "");
      if (prev) prev.m.push(m); else g[side].push({ n: nm, id: e[6], m: [m], og: k === "og", from: e[2] });
    });
    return g;
  }

  function keyPlayers(d) {
    var h = "", tp = d.tp;
    if (tp && tp[3]) {
      var tm = tp[0] === "h" ? H : A;
      h += '<div class="mp-motm">' + face(tp[1], tp[2]) +
        '<div><div class="mt">Player of the match</div><div class="mn">' + named(tp[0], tp[2]) +
        '</div><div class="ms">' + esc(tm) + " &middot; top match rating</div></div>" +
        '<div class="mr ' + rateCls(tp[3]) + '">' + Number(tp[3]).toFixed(1) + "</div></div>";
    }
    var g = goalsBy(d);
    if (g.h.length || g.a.length) {
      var col = function (list, side) {
        return list.map(function (x) {
          return '<div class="mp-g">' + face(x.id, x.n) + "<span>" + named(x.from, x.n) +
            "<small>" + esc(x.m.join(", ")) + "</small></span></div>";
        }).join("");
      };
      h += '<div class="mp-goals"><div class="h">' + col(g.h, "h") + '</div><div class="a">' + col(g.a, "a") + "</div></div>";
    }
    return h ? '<div class="mp-key">' + h + "</div>" : "";
  }

  // Goals, cards and subs per player, for the icons on the pitch.
  function marks(d) {
    var m = {};
    function add(side, n, s) { var k = side + "|" + n; m[k] = (m[k] || "") + s; }
    (d.ev || []).forEach(function (e) {
      var k = e[3];
      if (k === "g" || k === "p") add(e[2], e[4], "&#9917;");
      else if (k === "y") add(e[2], e[4], '<i style="background:#f2c200"></i>');
      else if (k === "r" || k === "yr") add(e[2], e[4], '<i style="background:#e5484d"></i>');
      else if (k === "s") add(e[2], e[5], '<span style="color:#ffb3b3">&#9660;</span>');
    });
    return m;
  }

  function pitch(d) {
    var lu = d.lu || {};
    var sides = ["h", "a"].filter(function (s) {
      var t = lu[s]; return t && t.xi && t.xi.length >= 7 && t.xi.every(function (r) { return r[3] && /^\d+:\d+$/.test(r[3]); });
    });
    if (!sides.length) return "";
    var mk = marks(d), out = "";
    sides.forEach(function (s) {
      var xi = lu[s].xi, rows = {};
      xi.forEach(function (r) { var g = r[3].split(":"), row = +g[0]; (rows[row] = rows[row] || []).push([+g[1], r]); });
      var nrows = Math.max.apply(null, Object.keys(rows).map(Number));
      Object.keys(rows).forEach(function (rk) {
        var list = rows[rk].sort(function (x, y) { return x[0] - y[0]; }), n = list.length, row = +rk;
        list.forEach(function (c, i) {
          var r = c[1];
          // Home in the bottom half, keeper at the bottom; away mirrored at the top.
          var depth = nrows > 1 ? (row - 1) / (nrows - 1) : 0;         // 0 keeper .. 1 front line
          var y = s === "h" ? 94.5 - depth * 36 : 5.5 + depth * 36;
          var x = (i + 1) / (n + 1) * 100;
          if (s === "a") x = 100 - x;                                   // facing the other way
          var rt = r[5] ? '<span class="rt ' + rateCls(r[5]) + '">' + Number(r[5]).toFixed(1) + "</span>" : "";
          var ic = mk[s + "|" + r[1]] ? '<span class="ic">' + mk[s + "|" + r[1]] + "</span>" : "";
          out += '<div class="mp-pl" style="left:' + x.toFixed(1) + "%;top:" + y.toFixed(1) + '%">' +
            '<span class="sh" style="background:' + (s === "h" ? HOME : AWAY) + '">' + esc(r[0] == null ? "" : r[0]) + rt + ic + "</span>" +
            '<span class="nm">' + named(s, r[1], surname(r[1])) + "</span></div>";
        });
      });
    });
    var lines = '<span class="ln half"></span><span class="ln cc"></span><span class="ln bx t"></span><span class="ln bx b"></span>' +
      '<span class="ln gx t"></span><span class="ln gx b"></span>';
    var tm = '<div class="mp-tm"><span><b style="color:' + AWAY + '">&#9679;</b> ' + esc(A) + (lu.a && lu.a.f ? " &middot; " + esc(lu.a.f) : "") +
      '</span><span><b style="color:' + HOME + '">&#9679;</b> ' + esc(H) + (lu.h && lu.h.f ? " &middot; " + esc(lu.h.f) : "") + "</span></div>";
    return tm + '<div class="mp-pitch">' + lines + out + "</div>";
  }

  function decorate(d) {
    if (!d) return;
    var mf = box.querySelector(".mf") || box;
    // Player of the match + scorers, just under the live note / at the top.
    var old = box.querySelector(".mp-key"); if (old) old.remove();
    var kp = keyPlayers(d);
    if (kp) {
      var first = box.querySelector("h3");
      if (first) first.insertAdjacentHTML("beforebegin", kp); else box.insertAdjacentHTML("afterbegin", kp);
    }
    // The pitch, in place of the starting XI lists (the bench stays).
    var oldp = box.querySelectorAll(".mp-tm,.mp-pitch"); oldp.forEach(function (x) { x.remove(); });
    var p = pitch(d), lus = box.querySelector(".lus");
    if (p && lus) { lus.insertAdjacentHTML("beforebegin", p); box.classList.add("mp-hidexi"); }
    else box.classList.remove("mp-hidexi");
    // The bigger number in each stat in its side's colour.
    box.querySelectorAll(".strow").forEach(function (r) {
      var v = r.querySelectorAll(".v"); if (v.length < 2) return;
      var n = function (el) { return parseFloat(String(el.textContent).replace("%", "")) || 0; };
      var a = n(v[0]), b = n(v[1]);
      v[0].classList.toggle("lead", a > b); v[0].classList.toggle("h", a > b);
      v[1].classList.toggle("lead", b > a); v[1].classList.toggle("a", b > a);
    });
    void mf;
  }

  // The names in the match events link to player pages too: scorer,
  // assist, cards, both players of a sub (Greg, 2026-11: "everything should
  // link everywhere").
  function linkEvents() {
    box.querySelectorAll(".ev").forEach(function (ev) {
      var cells = ev.children; if (cells.length < 3) return;
      var side = cells[0].textContent.trim() ? "h" : "a";
      ev.querySelectorAll(".who, .sub2").forEach(function (sp) {
        if (sp.querySelector("a") || /^(VAR|missed pen)/.test(sp.textContent)) return;
        var txt = sp.textContent, pre = "";
        if (/^assist /.test(txt)) { pre = "assist "; txt = txt.slice(7); }
        var p = page(side, txt);
        if (p) sp.innerHTML = esc(pre) + '<a href="../players/' + p + '.html">' + esc(txt) + "</a>";
      });
    });
  }

  var f = window.MIRenderMatch;
  if (typeof f === "function") {
    // Names tidied first (window.MIFixNames, app_install.js), then the page's
    // own drawing, then ours - live updates too (live.js calls this).
    window.MIRenderMatch = function (d, live) {
      if (d && window.MIFixNames) try { window.MIFixNames(d); } catch (e) {}
      CUR = d || CUR;
      var r = f.apply(this, arguments); try { decorate(d); } catch (e) {} try { linkEvents(); } catch (e) {} return r;
    };
  }
  // Already drawn from the page's own data (finished matches): drawn again,
  // with the names tidied and the extras.
  var md = document.getElementById("md-data");
  // Live: live.js drew the latest details before this file loaded - drawn
  // again now with the pitch, photos and tidy names (Greg, 2026-11).
  if (window.MI_LASTDET) { try { window.MIRenderMatch(window.MI_LASTDET[0], window.MI_LASTDET[1]); } catch (e) {} }
  else if (md) { try { window.MIRenderMatch(JSON.parse(md.textContent)); } catch (e) {} }
  else if (box.dataset.got !== "1") {
    // Drawn from match_details/<id>.json: fetch the same file (cached) and draw it again.
    fetch("../match_details/" + encodeURIComponent(box.dataset.fid) + ".json").then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && box.querySelector(".mf,h3,.lus") && !box.querySelector(".mlive")) try { window.MIRenderMatch(d); } catch (e) {} }).catch(function () {});
  }
})();
