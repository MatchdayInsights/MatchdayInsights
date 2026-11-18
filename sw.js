/* Matchday Insights app - service worker (Greg, 2026-11).
   Deliberately tiny: it never stores scores, rankings or pages, so the app
   can never show old numbers. Its only job is to make the site installable
   and to show a friendly "you're offline" screen instead of the browser's
   error page when there's no signal. */
const VERSION = "mi-app-3";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

/* The no-connection screen (Greg, 2026-11, for the store apps: never a
   blank page or the browser's error). Light or dark like the phone, "Try
   again" and "Back", and it reloads by itself when the signal returns. The
   icon is written in (an SVG), so it shows even with no connection. */
const OFFLINE = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>No connection - Matchday Insights</title>
<style>:root{--bg:#f5f6f2;--fg:#1d2329;--mu:#5f6b75;--b2:#d9ddd8}
@media (prefers-color-scheme:dark){:root{--bg:#1a1a2e;--fg:#f3f1ec;--mu:#9aa2bd;--b2:#34344e}}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--fg);
font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;text-align:center;padding:24px;box-sizing:border-box}
svg{width:72px;height:72px;margin-bottom:14px}h1{font-size:22px;margin:0 0 6px}p{margin:0;color:var(--mu)}
.b{margin-top:20px;display:flex;gap:10px;justify-content:center}
button{font:inherit;font-size:15px;font-weight:600;border-radius:10px;padding:10px 18px;border:0;cursor:pointer}
.go{background:#3dba5e;color:#fff}.bk{background:none;color:var(--fg);border:1px solid var(--b2)}</style></head>
<body><div><svg viewBox="0 0 24 24" fill="none" stroke="#3dba5e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<path d="M2 8.8a15 15 0 0 1 20 0M5.5 12.4a10 10 0 0 1 13 0M9 16a5 5 0 0 1 6 0"/><circle cx="12" cy="19.5" r="1" fill="#3dba5e"/><path d="M3 3l18 18" stroke="#e5484d"/></svg>
<h1>No connection</h1><p>Live scores and rankings need the internet. We'll reload as soon as you're back online.</p>
<div class="b"><button class="bk" onclick="history.length>1?history.back():location.reload()">Back</button>
<button class="go" onclick="location.reload()">Try again</button></div></div>
<script>addEventListener("online",function(){location.reload()})</script></body></html>`;

self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;          // everything else: straight to the network
  e.respondWith(fetch(e.request).catch(() =>
    new Response(OFFLINE, {headers: {"Content-Type": "text/html; charset=utf-8"}})));
});

/* Alerts (Greg, 2026-11): show what the alerts worker sends, and open the
   right page when one is tapped. */
self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = {body: e.data && e.data.text()}; }
  e.waitUntil(self.registration.showNotification(d.title || "Matchday Insights", {
    body: d.body || "", icon: "/app_icons/icon-192.png", tag: d.tag || undefined,
    renotify: !!d.tag, data: {url: d.url || "/my.html"}
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "/my.html", self.location.origin).href;
  e.waitUntil(clients.matchAll({type: "window", includeUncontrolled: true}).then(list => {
    for (const c of list) {
      if (c.url.indexOf(self.location.origin) === 0 && "focus" in c) {
        return c.focus().then(w => (w || c).navigate ? (w || c).navigate(url) : clients.openWindow(url)).catch(() => clients.openWindow(url));
      }
    }
    return clients.openWindow(url);
  }));
});
