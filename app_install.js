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

  // Matches page: "Top games" as one list, biggest match first (Greg, 2026-11).
  if (document.getElementById("top-only")) {
    var ts = document.createElement("script"); ts.src = "/matches-top.js"; document.head.appendChild(ts);
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
