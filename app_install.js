/* Player names as people write them (names.py has the same rules; keep the
   two alike): broken accents ("LÃ¤hteenmÃ¤ki"), odd dots ("Samuel·Pancotti"),
   lower case ("adrian svanback"), and the events' names spelt as in the
   line-ups ("Adrian Svanbäck") (Greg, 2026-11: "these all need to work
   flawlessly"). window.MIFixNames(details) tidies a match's details in
   place - the match pages, the Matches page and club pages call it. */
(function () {
  var PART = {de:1,da:1,das:1,"do":1,dos:1,del:1,della:1,di:1,du:1,van:1,von:1,der:1,den:1,le:1,la:1,el:1,al:1,bin:1,ben:1,y:1,e:1,ter:1,ten:1,op:1,st:1};
  var MOJI = /[ÃÂÅÄÆÐÑ][\u0080-¿]/;
  function plain(s) { return String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^\x00-\x7f]/g, "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim(); }
  function demoji(s) {
    if (!MOJI.test(s)) return s;
    try { var t = decodeURIComponent(escape(s)); if (!MOJI.test(t)) return t; } catch (e) {}
    return s;
  }
  function cap(w, first) {
    if (!w || w !== w.toLowerCase() || w === w.toUpperCase()) return w;
    if (!first && PART[w]) return w;
    return w.split("-").map(function (p) { return p.charAt(0).toUpperCase() + p.slice(1); }).join("-");
  }
  function clean(n) {
    if (typeof n !== "string" || !n.trim()) return n;
    var s = demoji(n).replace(/[·•‧・_]+/g, " ").replace(/\s+/g, " ").trim();
    return s.split(" ").map(function (w, i) { return cap(w, i === 0); }).join(" ");
  }
  function surname(full) {
    var p = full.split(" ");
    if (p.length > 1 && /^[^\s.]{1,2}\.$/.test(p[0])) return [p.slice(1).join(" "), p[0].charAt(0)];
    return [full, null];
  }
  function match(name, roster) {
    var s = clean(name);
    if (!s) return s;
    var toks = s.split(" "), pt = toks.map(plain);
    for (var i = 0; i < roster.length; i++) {
      var su = surname(roster[i]), st = su[0].split(" "), ps = st.map(plain), n = ps.length, ini = su[1];
      if (!n || ps.join("").length < 3) continue;
      if (pt.slice(-n).join(" ") === ps.join(" ")) {
        var rest = toks.slice(0, toks.length - n);
        if (!rest.length || !ini || plain(rest[0]).charAt(0) === plain(ini)) return rest.concat(st).join(" ");
      }
      if (n > 1 && toks.length > n && ps.every(function (p) { return pt.indexOf(p) >= 0; })) {
        var r2 = toks.filter(function (t, j) { return ps.indexOf(pt[j]) < 0; });
        if (r2.length && (!ini || plain(r2[0]).charAt(0) === plain(ini))) return r2.concat(st).join(" ");
      }
    }
    return s;
  }
  window.MIFixNames = function (d) {
    if (!d || typeof d !== "object" || d._nm) return d;
    var R = {h: [], a: []}, lu = d.lu || {};
    ["h", "a"].forEach(function (sd) {
      var t = lu[sd]; if (!t) return;
      if (t.c) t.c = clean(t.c);
      (t.xi || []).concat(t.bn || []).forEach(function (r) { if (r && typeof r[1] === "string") { r[1] = clean(r[1]); R[sd].push(r[1]); } });
    });
    var both = R.h.concat(R.a);
    (d.ev || []).forEach(function (e) {
      if (!e || e.length < 5) return;
      var mine = (R[e[2]] || []).concat(both);
      e[4] = match(e[4], mine);
      if (e.length > 5 && e[3] !== "v" && typeof e[5] === "string" && e[5]) e[5] = match(e[5], mine);
    });
    if (d.tp && typeof d.tp[2] === "string") d.tp[2] = clean(d.tp[2]);
    if (typeof d.ref === "string") d.ref = clean(d.ref);
    if (typeof d.ven === "string") d.ven = demoji(d.ven);
    try { Object.defineProperty(d, "_nm", {value: 1}); } catch (e) {}
    return d;
  };
})();

/* Matchday Insights - "get the app" (Greg, 2026-11).
   Registers the service worker, and after a few visits offers to install:
   Android/Chrome gets an Install button; iPhone Safari gets the
   Share -> Add to Home Screen tip. Closing it hides it for 30 days.
   Nothing shows inside the installed app. */
(function () {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
  var standalone = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone;

  /* Start loading a page the moment a finger lands on its link, so it's
     (nearly) there by the time the finger lifts. Chrome does this itself
     (the speculation rules in each page); this covers Safari. */
  (function () {
    if (window.HTMLScriptElement && HTMLScriptElement.supports && HTMLScriptElement.supports("speculationrules")) return;
    var done = {};
    function pre(e) {
      var a = e.target && e.target.closest && e.target.closest("a[href]");
      if (!a || a.target || a.origin !== location.origin || a.hasAttribute("download")) return;
      var u = a.href.split("#")[0];
      if (done[u] || u === location.href.split("#")[0] || /\.(json|png|jpg|svg|mp4)(\?|$)/i.test(u)) return;
      done[u] = 1;
      fetch(u, {credentials: "same-origin"}).catch(function () {});
    }
    // On a phone, only when the finger stays on the link for a moment - not
    // for every link a finger touches while scrolling a long list (Greg, 2026-11).
    var wait = null;
    document.addEventListener("touchstart", function (e) {
      clearTimeout(wait); wait = setTimeout(function () { pre(e); }, 80);
    }, {passive: true, capture: true});
    document.addEventListener("touchmove", function () { clearTimeout(wait); }, {passive: true, capture: true});
    document.addEventListener("mousedown", pre, true);
  })();

  /* ---- Alerts (Greg, 2026-11): window.MIPush, used by the My clubs screen.
     The phone's push subscription, the clubs it follows and which alerts it
     wants are sent to our alerts worker (push_config.json says where).
     Following or unfollowing a club anywhere on the site updates it. ---- */
  var MIPush = window.MIPush = (function () {
    var CFG = null, asked = null;
    function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
    function set(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }
    function clubs() { try { return (JSON.parse(get("mi_myclubs") || "[]") || []).map(function (c) { return String(c.i); }); } catch (e) { return []; } }
    function prefs() {
      var p = {ft: 1, rk: 1, ko: 0, gl: 0};
      try { var s = JSON.parse(get("mi_push_prefs") || "null"); if (s) for (var k in p) if (k in s) p[k] = s[k] ? 1 : 0; } catch (e) {}
      return p;
    }
    function key(b64) {
      var pad = "=".repeat((4 - b64.length % 4) % 4), raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
      var out = new Uint8Array(raw.length); for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i); return out;
    }
    function config() {
      if (!asked) asked = fetch("/push_config.json", {cache: "no-cache"}).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (c) { CFG = c && c.vapid && c.api ? c : null; return CFG; }).catch(function () { return null; });
      return asked;
    }
    function supported() { return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window; }
    var ua = navigator.userAgent || "";
    var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    function stamp() { return JSON.stringify([clubs().sort(), prefs()]); }
    function send(sub) {
      return fetch(CFG.api + "/subscribe", {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({sub: sub.toJSON(), clubs: clubs(), p: prefs(),
          tz: (Intl.DateTimeFormat().resolvedOptions().timeZone || "")})})
        .then(function (r) { if (!r.ok) throw new Error("alerts server said " + r.status); set("mi_push_sync", stamp()); return true; });
    }
    function subscription(make) {
      return navigator.serviceWorker.register("/sw.js").then(function () { return navigator.serviceWorker.ready; })
        .then(function (reg) {
          return reg.pushManager.getSubscription().then(function (s) {
            if (s || !make) return s;
            return reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: key(CFG.vapid)});
          });
        });
    }
    return {
      config: config,
      supported: supported,
      needsInstall: function () { return ios && !standalone; },
      on: function () { return get("mi_push_on") === "1" && window.Notification && Notification.permission === "granted"; },
      blocked: function () { return window.Notification && Notification.permission === "denied"; },
      prefs: prefs,
      setPrefs: function (p) { set("mi_push_prefs", JSON.stringify(p)); return this.sync(); },
      enable: function () {
        // Asked straight from the tap (phones only allow it then).
        var perm = Notification.requestPermission();
        return Promise.resolve(perm).then(function (p) {
          if (p !== "granted") throw new Error(p === "denied" ? "blocked" : "not allowed");
          return config();
        }).then(function () {
          if (!CFG) throw new Error("alerts aren't set up yet");
          return subscription(true);
        }).then(function (s) { return send(s); }).then(function () { set("mi_push_on", "1"); return true; });
      },
      disable: function () {
        set("mi_push_on", null); set("mi_push_sync", null);
        return config().then(function () { return subscription(false); }).then(function (s) {
          if (!s) return;
          var ep = s.endpoint;
          return s.unsubscribe().then(function () {
            if (CFG) return fetch(CFG.api + "/unsubscribe", {method: "POST", headers: {"Content-Type": "application/json"},
              body: JSON.stringify({endpoint: ep})});
          });
        }).catch(function () {});
      },
      sync: function () {
        if (!this.on() || get("mi_push_sync") === stamp()) return Promise.resolve(false);
        return config().then(function () {
          if (!CFG) return false;
          return subscription(true).then(send);
        }).catch(function () { return false; });
      }
    };
  })();
  function resync() { setTimeout(function () { MIPush.sync(); }, 300); }
  document.addEventListener("mi-myclubs", resync);
  document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("[data-star]")) resync(); }, true);
  if (MIPush.supported()) window.addEventListener("load", function () { MIPush.sync(); });

  // Matches page: "Top games" sorted Biggest / Time / League (Greg, 2026-11).
  if (document.getElementById("top-only")) {
    var ts = document.createElement("script"); ts.src = "/matches-top.js"; document.head.appendChild(ts);
  }
  // Match pages: the league table live while its matches are on (Greg, 2026-11).
  if (document.querySelector("table.mt")) {
    var tl = document.createElement("script"); tl.src = "/mt-live.js"; document.head.appendChild(tl);
  }
  // Match pages: player of the match, scorers' faces, the line-ups on a pitch (Greg, 2026-11).
  if (document.getElementById("tab-m")) {
    var mp = document.createElement("script"); mp.src = "/match-plus.js"; document.head.appendChild(mp);
  }
  // A way to our track record from the odds, for app users too - the app
  // hides the Rankings intro that links it (Greg, 2026-11).
  if (/\/predictions\//.test(location.pathname)) {
    var od = document.querySelector(".oddslab") || document.querySelector("main .nt-odds");
    if (od && !document.querySelector(".mi-acc")) {
      var acc = document.createElement("a"); acc.className = "mi-acc"; acc.href = "/track-record.html";
      acc.textContent = "How accurate are our odds? \u203a";
      acc.style.cssText = "display:inline-block;margin:8px 0 2px;font-size:13px;font-weight:600;color:var(--green,#3dba5e);text-decoration:none";
      od.insertAdjacentElement("afterend", acc);
    }
  }

  if (standalone) { backButton(); return; }

  /* Inside the installed app there's no browser back arrow, so the top bar
     gets one (Greg, 2026-11). It goes back a page when you came from
     another page of the site; otherwise it takes you to Rankings. Not shown
     on Rankings when there's nothing to go back to. */
  function backButton() {
    var ref = document.referrer || "";
    var fromSite = ref.indexOf(location.origin) === 0 && ref !== location.href;
    var home = /^\/(index\.html|my\.html)?$/.test(location.pathname);
    if (home && !fromSite) return;
    function add() {
      var nav = document.querySelector(".site-nav");
      if (!nav || document.getElementById("mi-back")) return;
      var st = document.createElement("style");
      st.textContent = "#mi-back{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;" +
        "width:34px;height:40px;margin:0 4px 0 -8px;padding:0;background:none;border:0;color:#f5f6f2;cursor:pointer;" +
        "-webkit-tap-highlight-color:transparent}#mi-back svg{width:24px;height:24px}#mi-back:active{opacity:.6}";
      document.head.appendChild(st);
      var b = document.createElement("button");
      b.id = "mi-back"; b.type = "button"; b.setAttribute("aria-label", "Back");
      b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>';
      b.onclick = function () {
        if (fromSite && history.length > 1) history.back();
        else location.href = "/";
      };
      nav.insertBefore(b, nav.firstChild);
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add); else add();
  }

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var views = (parseInt(get("mi_app_views") || "0", 10) || 0) + 1;
  set("mi_app_views", String(views));
  var hidden = parseInt(get("mi_app_hide") || "0", 10) || 0;
  if (views < 3 || Date.now() < hidden) return;

  var ua = navigator.userAgent || "";
  var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var iosSafari = ios && !/CriOS|FxiOS|EdgiOS|OPiOS|GSA\//.test(ua);

  function bar(html, onGo) {
    if (document.getElementById("mi-app-bar")) return;
    var st = document.createElement("style");
    st.textContent = "#mi-app-bar{position:fixed;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom));" +
      "z-index:9999;max-width:460px;margin:0 auto;display:flex;align-items:center;gap:10px;padding:10px 12px;" +
      "background:#1a1a2e;color:#f3f1ec;border:1px solid #1f9a46;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.35);" +
      "font:14px/1.35 system-ui,-apple-system,Segoe UI,sans-serif}" +
      "#mi-app-bar img{width:40px;height:40px;border-radius:9px;flex:0 0 auto}#mi-app-bar .t{flex:1 1 auto}" +
      "#mi-app-bar b{display:block;font-size:14.5px}#mi-app-bar .go{background:#3dba5e;color:#fff;border:0;border-radius:8px;" +
      "padding:8px 12px;font-weight:700;font-size:14px;cursor:pointer}#mi-app-bar .x{background:none;border:0;color:#9fb3bb;" +
      "font-size:22px;line-height:1;padding:4px 6px;cursor:pointer}";
    document.head.appendChild(st);
    var d = document.createElement("div");
    d.id = "mi-app-bar";
    d.innerHTML = '<img src="/app_icons/icon-192.png" alt=""><div class="t">' + html + "</div>" +
      (onGo ? '<button class="go" type="button">Install</button>' : "") +
      '<button class="x" type="button" aria-label="Close">&times;</button>';
    document.body.appendChild(d);
    d.querySelector(".x").onclick = function () {
      set("mi_app_hide", String(Date.now() + 30 * 864e5));
      d.remove();
    };
    if (onGo) d.querySelector(".go").onclick = function () { onGo(d); };
  }

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    var ask = e;
    bar("<b>Get the MD Insights app</b>Live scores and the world ranking, one tap away.", function (d) {
      ask.prompt();
      ask.userChoice.then(function () { d.remove(); set("mi_app_hide", String(Date.now() + 30 * 864e5)); });
    });
  });

  if (iosSafari) {
    var show = function () {
      bar("<b>Get the MD Insights app</b>Tap <span aria-label=\"Share\">Share &#x2191;&#xFE0E;</span> then <b style=\"display:inline\">Add to Home Screen</b>.", null);
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", show); else show();
  }
})();

// Club pages on phones show the written summary cut to three lines
// (mi-type.css); a tap opens the rest (Greg, 2026-11).
document.addEventListener("click", function (e) {
  var p = e.target.closest && e.target.closest("p.club-summary");
  if (p && !e.target.closest("a")) p.classList.toggle("open");
});

// Share button on club and match pages (Greg, 2026-11): one tap opens the
// phone's own share menu (WhatsApp, Messages...) with a line and the link;
// computers without one copy the link instead.
(function () {
  function add() {
    if (document.getElementById("mi-share")) return;
    var text = "", spot = null, after = true;
    var club = document.querySelector("main.club-page .club-name");
    var sbh = document.querySelector("h1.sb-h1");
    var nt = /\/predictions\//.test(location.pathname) && document.querySelector("main.pl > h1 + .pl-f");
    if (club) {
      var rk = document.querySelector('[data-live="rank"]');
      text = club.textContent.trim() + (rk ? " - " + rk.textContent.trim() + " in the world" : "") +
        " in the Matchday Insights club ranking";
      var star = document.querySelector(".club-header [data-star]");
      spot = star ? star.parentNode : club; after = !star;
    } else if (sbh) {
      var sc = document.querySelector(".sb-score"), st = document.querySelector(".sb-st");
      var t = document.querySelectorAll(".sb-t span");
      var done = sc && st && /full|ft|aet|pen/i.test(st.textContent) && t.length === 2;
      text = done ? t[0].textContent + " " + sc.textContent.replace(/\s+/g, "") + " " + t[1].textContent +
        " - stats, line-ups and our odds" : sbh.textContent.replace(/:.*$/, "").trim() + " - our prediction and odds";
      spot = sbh;
    } else if (nt) {
      text = nt.previousElementSibling.textContent.trim() + " - our prediction and odds";
      spot = nt;
    }
    if (!spot) return;
    var css = document.createElement("style");
    css.textContent = "#mi-share{display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;" +
      "-webkit-tap-highlight-color:transparent;vertical-align:middle}#mi-share svg{width:15px;height:15px}#mi-share:active{opacity:.6}" +
      "#mi-share:not(.star){font:600 13px/1 Inter,system-ui,sans-serif;padding:7px 13px;border-radius:999px;" +
      "border:1px solid var(--green,#3dba5e);background:none;color:var(--green,#3dba5e)}.mi-share-row{text-align:center;margin:8px 0 4px}" +
      // Next to "Add to my clubs" and "Compare" it takes their look, icon
      // only, so the three fit on one line on a phone.
      ".club-header #mi-share.star span{display:none}";
    document.head.appendChild(css);
    var b = document.createElement("button");
    b.id = "mi-share"; b.type = "button";
    b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" ' +
      'stroke-linejoin="round"><path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg><span>Share</span>';
    var url = location.origin + location.pathname;
    b.onclick = function () {
      if (navigator.share) {
        navigator.share({title: document.title, text: text, url: url}).catch(function () {});
        return;
      }
      var lab = b.querySelector("span");
      var ok = function () { lab.textContent = "Link copied"; setTimeout(function () { lab.textContent = "Share"; }, 2000); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(ok, function () { prompt("Copy this link:", url); });
      else prompt("Copy this link:", url);
    };
    if (club && !after) { b.className = "star"; b.setAttribute("aria-label", "Share"); spot.appendChild(b); return; }
    var row = document.createElement("div");
    row.className = "mi-share-row"; row.appendChild(b);
    if (nt) row.style.textAlign = "left";            // national pages' titles sit on the left
    spot.parentNode.insertBefore(row, spot.nextSibling);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add); else add();
})();
