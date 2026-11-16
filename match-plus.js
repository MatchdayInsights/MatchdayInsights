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
  // Player pages by the API's player id first (pl.id from match_details /
  // live_feeder, or read off the page names, which end in -<id>), then by
  // name - so "D. Dumfries" links even when the list says "Denzel Dumfries"
  // (Greg, 2026-11: "some of the pictures don't link").
  function byId(id) {
    if (!id) return null;
    id = String(id);
    var P = CUR && CUR.pl, L = window.MI_PL;
    if (P && P.id && P.id[id]) return P.id[id];
    if (L && L.id && L.id[id]) return L.id[id];
    var re = new RegExp("-" + id + "$"), hit = null;
    [L, P].forEach(function (M) {
      if (!M || hit) return;
      ["h", "a"].forEach(function (sd) {
        var m = M[sd]; if (!m || hit) return;
        for (var k in m) if (re.test(m[k])) { hit = m[k]; break; }
      });
    });
    return hit;
  }
  function page(side, name, id) {
    var b = byId(id); if (b) return b;
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
  function named(side, name, text, id) {
    var p = page(side, name, id), t = esc(text == null ? name : text);
    return p ? '<a href="../players/' + p + '.html">' + t + "</a>" : t;
  }
  // The face links to the player's page too, like the name (Greg, 2026-11).
  function linked(side, name, html, id) {
    var p = page(side, name, id);
    return p ? '<a class="mp-fl" href="../players/' + p + '.html" aria-label="' + esc(name) + '">' + html + "</a>" : html;
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
    ".mp-pw{max-width:560px;margin:10px auto 6px;border-radius:16px;overflow:hidden;background:#3d8f5a}" +
    ".mp-tb{display:flex;align-items:center;gap:10px;padding:12px 14px;background:#47a066;color:#fff;font-size:15px}" +
    ".mp-tb b{font-weight:700}.mp-tb span:not(.rt){color:rgba(255,255,255,.75);font-weight:600;margin-left:2px}" +
    ".mp-tb .rt{font-size:13px;font-weight:800;border-radius:999px;padding:3px 9px;color:#fff}" +
    ".mp-pitch{position:relative;aspect-ratio:68/150;background:#3d8f5a;overflow:hidden}" +
    ".mp-pitch .ln{position:absolute;border:2px solid rgba(255,255,255,.18);pointer-events:none}" +
    ".mp-pitch .half{left:0;right:0;top:50%;height:0;border-width:2px 0 0}" +
    ".mp-pitch .cc{left:50%;top:50%;width:30%;aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%}" +
    ".mp-pitch .bx{left:20%;right:20%;height:11%;border-radius:0 0 6px 6px}.mp-pitch .bx.t{top:-2px}.mp-pitch .bx.b{bottom:-2px;border-radius:6px 6px 0 0}" +
    ".mp-pitch .gx{left:36%;right:36%;height:4%}.mp-pitch .gx.t{top:-2px}.mp-pitch .gx.b{bottom:-2px}" +
    ".mp-pl{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;width:25%;text-align:center}" +
    ".mp-pl .mk{position:relative;width:52px;height:52px}" +
    ".mp-pl a.mp-fl{display:block;width:100%;height:100%}" +
    ".mp-pl .ph{position:relative;display:flex;align-items:center;justify-content:center;width:100%;height:100%;border-radius:50%;overflow:hidden;background:#eef0f2;box-shadow:0 1px 4px rgba(0,0,0,.25)}" +
    ".mp-pl .ph b{font-size:15px;font-weight:800;color:#3d8f5a}" +
    ".mp-pl .ph img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 12%;background:#eef0f2}" +
    ".mp-pl .rt{position:absolute;top:-6px;right:-14px;font-size:11.5px;font-weight:800;color:#fff;border-radius:999px;padding:2px 7px;line-height:1.25;z-index:2}" +
    ".mp-pl .so{position:absolute;top:-4px;left:-6px;width:19px;height:19px;z-index:2}" +
    ".mp-pl .sm{position:absolute;top:-21px;left:-10px;font-size:11px;font-weight:600;color:#fff;z-index:2}" +
    ".mp-pl .br{position:absolute;bottom:-4px;right:-8px;display:flex;z-index:2}.mp-pl .br .bi{width:18px;height:18px;margin-left:-5px;display:block}" +
    ".mp-pl .cd{position:absolute;bottom:-2px;left:-4px;width:11px;height:15px;border-radius:2px;z-index:2;box-shadow:0 0 0 1.5px #fff}.mp-pl .cd.y{background:#f5c518}.mp-pl .cd.r{background:#e5484d}" +
    ".mp-pl .nm{display:block;width:100%;margin-top:7px;font-size:13px;font-weight:600;color:#fff;line-height:1.15;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".mp-pl .nm i{font-style:normal;color:rgba(255,255,255,.65);font-weight:500}.mp-pl .nm a{color:#fff;text-decoration:none}" +
    "@media (max-width:600px){.mp-pl .mk{width:46px;height:46px}.mp-pl .nm{font-size:11.5px}.mp-pl .nm i{font-size:10.5px}.mp-pl .rt{font-size:10.5px;right:-12px}}" +
    ".r8{background:#1a9b55}.r7{background:#4caf50}.r6{background:#ef8a2e}.r5{background:#e5484d}" +
    ".mp-tm{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);max-width:520px;margin:10px auto 0}" +
    ".mp-tm b{color:var(--text)}" +
    ".mp-hidexi .lus ol{display:none}.mp-hidexi .lus .bn{margin-top:2px}" +
    ".mf .strow .v.lead{font-weight:800}.mf .strow .v.lead.h{color:" + HOME + "}.mf .strow .v.lead.a{color:" + AWAY + "}" +
    "a.mp-fl{display:inline-flex;color:inherit;text-decoration:none;border:0;-webkit-tap-highlight-color:transparent}a.mp-fl:active{opacity:.7}" +
    "";
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
      h += '<div class="mp-motm">' + linked(tp[0], tp[2], face(tp[1], tp[2]), tp[1]) +
        '<div><div class="mt">Player of the match</div><div class="mn">' + named(tp[0], tp[2], null, tp[1]) +
        '</div><div class="ms">' + esc(tm) + " &middot; top match rating</div></div>" +
        '<div class="mr ' + rateCls(tp[3]) + '">' + Number(tp[3]).toFixed(1) + "</div></div>";
    }
    var g = goalsBy(d);
    if (g.h.length || g.a.length) {
      var col = function (list, side) {
        return list.map(function (x) {
          return '<div class="mp-g">' + linked(x.from, x.n, face(x.id, x.n), x.id) + "<span>" + named(x.from, x.n, null, x.id) +
            "<small>" + esc(x.m.join(", ")) + "</small></span></div>";
        }).join("");
      };
      h += '<div class="mp-goals"><div class="h">' + col(g.h, "h") + '</div><div class="a">' + col(g.a, "a") + "</div></div>";
    }
    return h ? '<div class="mp-key">' + h + "</div>" : "";
  }

  // Goals, assists, cards and the minute subbed off, per player (side|name).
  function marks(d) {
    var m = {};
    function get(side, n) { var k = side + "|" + n; return m[k] || (m[k] = {g: 0, a: 0, y: 0, r: 0, off: null}); }
    (d.ev || []).forEach(function (e) {
      var k = e[3], t = e[0] + (e[1] ? "+" + e[1] : "") + "'";
      if (k === "g" || k === "p") { get(e[2], e[4]).g++; if (e[5]) get(e[2], e[5]).a++; }
      else if (k === "y") get(e[2], e[4]).y++;
      else if (k === "r" || k === "yr") get(e[2], e[4]).r++;
      else if (k === "s" && e[5]) get(e[2], e[5]).off = t;
    });
    return m;
  }

  /* The pitch, FotMob-style (Greg, 2026-11: "look at fotmob, look at mine.
     Mine looks amateur"): one tall pitch, home keeper at the top and the
     away keeper at the bottom, each team's bar (average rating, name,
     formation) at its end; big headshots on white with the rating at the
     top right, the minute and a red arrow when subbed off, balls for goals,
     a boot for assists, cards; "13 Treu" under each face. */
  var BALL = '<svg viewBox="0 0 24 24" width="100%" height="100%"><circle cx="12" cy="12" r="11" fill="#fff" stroke="#222" stroke-width="1.5"/><path d="M12 7l4 3-1.5 4.6h-5L8 10z" fill="#222"/><path d="M12 7V3.5M16 10l3.4-1.2M14.5 14.6l2.2 3M9.5 14.6l-2.2 3M8 10L4.6 8.8" stroke="#222" stroke-width="1.3"/></svg>';
  var BOOT = '<svg viewBox="0 0 24 24" width="100%" height="100%"><circle cx="12" cy="12" r="11.5" fill="#fff"/><path d="M5 9h5l1.5 3.5c2.5.4 5.5 1 7 2.2.6.5.5 1.8-.4 1.8H5.5A1 1 0 0 1 4.5 15z" fill="#222"/></svg>';
  var OFF = '<svg viewBox="0 0 24 24" width="100%" height="100%"><circle cx="12" cy="12" r="11.5" fill="#fff"/><circle cx="12" cy="12" r="9" fill="#e5484d"/><path d="M16 12H8.5M11.5 8.5L8 12l3.5 3.5" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function avg(xi) {
    var r = xi.map(function (x) { return +x[5] || 0; }).filter(function (v) { return v > 0; });
    return r.length ? r.reduce(function (a, b) { return a + b; }, 0) / r.length : 0;
  }
  function bar(side, t) {
    var a = avg(t.xi), nm = side === "h" ? H : A;
    return '<div class="mp-tb ' + side + '">' + (a ? '<span class="rt ' + rateCls(a) + '">' + a.toFixed(1) + "</span>" : "") +
      "<b>" + esc(nm) + "</b>" + (t.f ? "<span>" + esc(t.f) + "</span>" : "") + "</div>";
  }
  function pitch(d) {
    var lu = d.lu || {};
    var ok = function (s) { var t = lu[s]; return t && t.xi && t.xi.length >= 7 && t.xi.every(function (r) { return r[3] && /^\d+:\d+$/.test(r[3]); }); };
    if (!ok("h") && !ok("a")) return "";
    var mk = marks(d), out = "";
    ["h", "a"].forEach(function (s) {
      if (!ok(s)) return;
      var xi = lu[s].xi, rows = {};
      xi.forEach(function (r) { var g = r[3].split(":"), row = +g[0]; (rows[row] = rows[row] || []).push([+g[1], r]); });
      var nrows = Math.max.apply(null, Object.keys(rows).map(Number));
      Object.keys(rows).forEach(function (rk) {
        var list = rows[rk].sort(function (x, y) { return x[0] - y[0]; }), n = list.length, row = +rk;
        list.forEach(function (c, i) {
          var r = c[1], m = mk[s + "|" + r[1]] || {};
          // Home: keeper at the top, attack down to the middle; away mirrored.
          var depth = nrows > 1 ? (row - 1) / (nrows - 1) : 0;
          var y = s === "h" ? 6 + depth * 37 : 94 - depth * 37;
          var x = (i + 1) / (n + 1) * 100;
          if (s === "h") x = 100 - x;                    // the home side faces down the page
          var badges = "";
          if (r[5]) badges += '<span class="rt ' + rateCls(r[5]) + '">' + Number(r[5]).toFixed(1) + "</span>";
          if (m.off) badges += '<span class="so">' + OFF + '</span><span class="sm">' + esc(m.off) + "</span>";
          var bl = "";
          for (var gi = 0; gi < Math.min(m.g || 0, 3); gi++) bl += '<i class="bi">' + BALL + "</i>";
          for (var ai = 0; ai < Math.min(m.a || 0, 2); ai++) bl += '<i class="bi">' + BOOT + "</i>";
          if (bl) badges += '<span class="br">' + bl + "</span>";
          if (m.r) badges += '<span class="cd r"></span>'; else if (m.y) badges += '<span class="cd y"></span>';
          var ph = '<span class="ph"><b>' + esc(r[0] == null ? "" : r[0]) + "</b>" +
            (r[4] ? '<img src="' + photo(r[4]) + '" alt="" loading="lazy" onerror="this.remove()">' : "") + "</span>";
          out += '<div class="mp-pl" style="left:' + x.toFixed(1) + "%;top:" + y.toFixed(1) + '%">' +
            '<div class="mk">' + linked(s, r[1], ph, r[4]) + badges + "</div>" +
            '<span class="nm">' + (r[0] != null ? "<i>" + esc(r[0]) + "</i> " : "") + named(s, r[1], surname(r[1]), r[4]) + "</span></div>";
        });
      });
    });
    var lines = '<span class="ln half"></span><span class="ln cc"></span><span class="ln bx t"></span><span class="ln bx b"></span>' +
      '<span class="ln gx t"></span><span class="ln gx b"></span>';
    return '<div class="mp-pw">' + (ok("h") ? bar("h", lu.h) : "") + '<div class="mp-pitch">' + lines + out + "</div>" +
      (ok("a") ? bar("a", lu.a) : "") + "</div>";
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
    var oldp = box.querySelectorAll(".mp-tm,.mp-pitch,.mp-pw"); oldp.forEach(function (x) { x.remove(); });
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

  /* Tabs like FotMob's (Greg, 2026-11: "the full match data ... called
     Facts, and then a tab up top that lists table, lineup, and all the
     other data found in the facts"): Facts (everything, as before) |
     Lineup | Stats | Table | Preview. Lineup and Stats show just that part
     of the Facts tab; they appear once the match has them. National match
     pages' group table becomes the Table tab. Look-only: no rebuild. */
  var SEC = {"Match events": "ev", "Stats": "st", "Lineups": "lu", "Lineup": "lu"};
  function markSections() {
    var cur = "key";
    [].forEach.call(box.children, function (c) {
      if (c.tagName === "H3") cur = SEC[c.textContent.trim()] || "other";
      else if (c.classList.contains("meta")) cur = "meta";
      else if (c.classList.contains("mp-key")) cur = "key";
      c.setAttribute("data-sec", cur);
    });
  }
  var tabsBar = document.querySelector(".mtabs"), btnLu = null, btnSt = null;
  function setView(v) {
    ["lu", "st"].forEach(function (k) { box.classList.toggle("mv-" + k, v === k); });
  }
  function initTabs() {
    if (!tabsBar || tabsBar.getAttribute("data-mi")) return;
    tabsBar.setAttribute("data-mi", "1");
    var facts = tabsBar.querySelector('button[data-t="m"]'); if (!facts) return;
    facts.lastChild && facts.lastChild.nodeType === 3 ? (facts.lastChild.textContent = "Facts") : (facts.textContent = "Facts");
    function mk(label, v) {
      var b = document.createElement("button"); b.type = "button"; b.setAttribute("data-t", "m"); b.setAttribute("data-v", v);
      b.textContent = label; b.hidden = true; return b;
    }
    btnLu = mk("Lineup", "lu"); btnSt = mk("Stats", "st");
    facts.after(btnLu); btnLu.after(btnSt);
    // National pages: the group table sits under the tabs - give it its own tab.
    if (!document.getElementById("tab-t")) {
      var tw = document.querySelector(".nt-mtw");
      if (tw) {
        var panel = document.createElement("div"); panel.className = "mpanel"; panel.id = "tab-t"; panel.hidden = true;
        var h2 = tw.previousElementSibling && tw.previousElementSibling.tagName === "H2" ? tw.previousElementSibling : null;
        tw.parentNode.insertBefore(panel, h2 || tw);
        if (h2) panel.appendChild(h2);
        panel.appendChild(tw);
        var tb = document.createElement("button"); tb.type = "button"; tb.setAttribute("data-t", "t"); tb.textContent = "Table";
        var prev = tabsBar.querySelector('button[data-t="p"]');
        prev ? tabsBar.insertBefore(tb, prev) : tabsBar.appendChild(tb);
      }
    }
    tabsBar.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      // The page's own handler shows the panel; this picks the part of Facts.
      setView(b.getAttribute("data-v") || "");
      tabsBar.querySelectorAll("button").forEach(function (x) { x.classList.toggle("on", x === b); });
    });
    var st = document.createElement("style");
    st.textContent = ".mtabs[data-mi]{display:flex;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}" +
      ".mtabs[data-mi]::-webkit-scrollbar{display:none}.mtabs[data-mi] button{flex:1 0 auto;white-space:nowrap}" +
      "@media(max-width:640px){.mtabs[data-mi] button{padding-left:6px!important;padding-right:6px!important;font-size:15px!important}}" +
      "#tab-m.mv-lu>:not([data-sec=lu]),#tab-m.mv-st>:not([data-sec=st]){display:none!important}" +
      "#tab-m.mv-lu>h3[data-sec=lu],#tab-m.mv-st>h3[data-sec=st]{margin-top:4px}" +
      "#tab-t>h2{margin-top:6px}";
    document.head.appendChild(st);
  }
  function updateTabs() {
    markSections();
    if (!btnLu) return;
    btnLu.hidden = !box.querySelector('[data-sec=lu]:not(h3)');
    btnSt.hidden = !box.querySelector('[data-sec=st]:not(h3)');
    var on = tabsBar.querySelector("button.on");
    if (on && on.hidden) { var f = tabsBar.querySelector('button[data-t="m"]'); f.classList.add("on"); on.classList.remove("on"); setView(""); }
  }
  try { initTabs(); updateTabs(); } catch (e) {}
  var f2 = window.MIRenderMatch;
  if (typeof f2 === "function") {
    window.MIRenderMatch = function () { var r = f2.apply(this, arguments); try { updateTabs(); } catch (e) {} return r; };
  }
  new MutationObserver(function () { try { updateTabs(); } catch (e) {} }).observe(box, {childList: true});
})();
