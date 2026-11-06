/* Matchday Insights app - service worker (Greg, 2026-11).
   Deliberately tiny: it never stores scores, rankings or pages, so the app
   can never show old numbers. Its only job is to make the site installable
   and to show a friendly "you're offline" screen instead of the browser's
   error page when there's no signal. */
const VERSION = "mi-app-1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const OFFLINE = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline - Matchday Insights</title>
<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#1a1a2e;color:#f3f1ec;font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;text-align:center;padding:24px}
img{width:110px;height:110px;border-radius:24px;margin-bottom:18px}h1{font-size:22px;margin:0 0 6px}
button{margin-top:18px;background:#3dba5e;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:15px}</style></head>
<body><div><img src="/app_icons/icon-192.png" alt=""><h1>No connection</h1>
<div>Matchday Insights needs the internet for live scores and rankings.</div>
<button onclick="location.reload()">Try again</button></div></body></html>`;

self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;          // everything else: straight to the network
  e.respondWith(fetch(e.request).catch(() =>
    new Response(OFFLINE, {headers: {"Content-Type": "text/html; charset=utf-8"}})));
});
