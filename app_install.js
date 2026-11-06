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
  if (standalone) return;

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
