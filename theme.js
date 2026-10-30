/* Matchday Insights - light / dark switch (Greg, 2026-10).
   Loaded in every page's <head> (deploy_to_site.py adds the tag), so the
   chosen look is set before anything is drawn - no flash of the wrong one.
   Dark unless the visitor picks light with the button (Greg, 2026-10:
   DARK BY DEFAULT).
   The choice is kept in this browser (localStorage "mi_theme"). */
(function () {
  var KEY = 'mi_theme', root = document.documentElement, saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  root.setAttribute('data-theme', saved === 'light' ? 'light' : 'dark');
  function now() {
    var t = root.getAttribute('data-theme');
    if (t) return t;
    return window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  var SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/></svg>';
  var MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7z"/></svg>';
  function add() {
    var nav = document.querySelector('.site-nav');
    if (!nav || nav.querySelector('.theme-btn')) return;
    var css = document.createElement('style');
    css.textContent = '.theme-btn{flex:none;width:34px;height:34px;margin-left:10px;border-radius:50%;border:1px solid #33374f;' +
      'background:transparent;color:#e6e8f2;cursor:pointer;display:grid;place-items:center;padding:0}' +
      '.theme-btn svg{width:17px;height:17px}.theme-btn:hover{color:#3dba5e;border-color:#3dba5e}' +
      '@media (max-width:640px){.theme-btn{margin-left:auto;width:32px;height:32px}.site-nav .nav-club~.theme-btn{margin-left:8px}}';
    document.head.appendChild(css);
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'theme-btn';
    function paint() {
      var light = now() === 'light';
      b.innerHTML = light ? MOON : SUN;
      b.title = light ? 'Switch to dark' : 'Switch to light';
      b.setAttribute('aria-label', b.title);
    }
    b.addEventListener('click', function () {
      var next = now() === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      paint();
    });
    paint();
    nav.appendChild(b);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
