/* Matchday Insights - club pages. Written by generate_club_page.py; don't edit by hand. */

function showChartTooltip(e, id, date, val) {
  var tip = document.getElementById(id);
  if (!tip) return;
  tip.innerHTML = '<div class="chart-tooltip-date">' + date + '</div><div class="chart-tooltip-val" style="color:var(--green)">' + val + '</div>';
  var wrap = tip.parentElement, rect = wrap.getBoundingClientRect();
  var x = e.clientX - rect.left + 10, y = e.clientY - rect.top - 40;
  if (x + 120 > wrap.offsetWidth) x = e.clientX - rect.left - 120;
  if (y < 0) y = e.clientY - rect.top + 12;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
  tip.classList.add('show');
}
function hideChartTooltip(id) {
  var tip = document.getElementById(id);
  if (tip) tip.classList.remove('show');
}

function mdiRenderChart(svgId, selectId, captionId, tooltipId, dates, values, opts) {
  opts = opts || {};
  var invert = !!opts.invert;
  var color = opts.color || '#3dba5e';
  var fmt = opts.fmt || function(v){ return v.toFixed(0); };

  function draw(windowSize) {
    var d = dates, v = values;
    if (windowSize !== 'all') {
      var n = parseInt(windowSize, 10);
      d = dates.slice(-n);
      v = values.slice(-n);
    }
    // Ported from Classic's buildSvgChart() - same viewBox/padding ratios,
    // same 4-line grid, same gradient fill, same start/end point sizing,
    // same hover tooltip. This exact proportion (400x160, not a wider
    // canvas) is what actually reads clearly at any display size - the
    // SVG scales via width="100%", so the coordinate system's size
    // relative to its own content matters far more than any single
    // font-size number tweaked in isolation.
    var W = 400, H = 160, PL = 48, PR = 10, PT = 14, PB = 28;
    var cw = W - PL - PR, ch = H - PT - PB;
    var n = v.length;
    var mn = Math.min.apply(null, v), mx = Math.max.apply(null, v);
    var range = (mx === mn) ? 1 : (mx - mn);

    function xp(i) { return n < 2 ? PL : PL + (i / (n - 1)) * cw; }
    function yp(val) {
      var norm = (val - mn) / range;
      var frac = invert ? norm : (1 - norm);
      return PT + frac * ch;
    }

    var pts = [];
    for (var i = 0; i < n; i++) pts.push(xp(i).toFixed(1) + ',' + yp(v[i]).toFixed(1));
    var points = pts.join(' ');
    var areaStart = xp(0).toFixed(1) + ',' + (PT + ch).toFixed(1);
    var areaEnd = xp(n - 1).toFixed(1) + ',' + (PT + ch).toFixed(1);

    var ytH = '';
    for (var g = 0; g <= 3; g++) {
      var val = mn + (range * g / 3), gy = yp(val);
      ytH += '<line x1="' + PL + '" y1="' + gy.toFixed(1) + '" x2="' + (PL + cw) + '" y2="' + gy.toFixed(1) +
        '" stroke="#1e2330" stroke-width="1"/>' +
        '<text x="' + (PL - 4) + '" y="' + (gy + 4).toFixed(1) + '" text-anchor="end" ' +
        'font-family="JetBrains Mono, monospace" font-size="12" fill="#565e78">' + fmt(val) + '</text>';
    }

    var gid = 'g' + Math.random().toString(36).substr(2, 6);

    var hits = '';
    for (var i = 0; i < n; i++) {
      var x = xp(i), y = yp(v[i]);
      var ds = new Date(d[i]).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
      var vs = fmt(v[i]);
      hits += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="7" fill="transparent" ' +
        'onmousemove="showChartTooltip(event,\'' + tooltipId + '\',\'' + ds + '\',\'' + vs + '\')" ' +
        'onmouseleave="hideChartTooltip(\'' + tooltipId + '\')"/>';
    }

    var svg = document.getElementById(svgId);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.innerHTML =
      '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + color + '" stop-opacity="0.25"/>' +
      '<stop offset="100%" stop-color="' + color + '" stop-opacity="0.02"/></linearGradient></defs>' +
      ytH +
      '<polygon points="' + areaStart + ' ' + points + ' ' + areaEnd + '" fill="url(#' + gid + ')"/>' +
      '<polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<circle cx="' + xp(0).toFixed(1) + '" cy="' + yp(v[0]).toFixed(1) + '" r="4" fill="' + color + '" stroke="#0c0d11" stroke-width="2"/>' +
      '<circle cx="' + xp(n-1).toFixed(1) + '" cy="' + yp(v[n-1]).toFixed(1) + '" r="5" fill="' + color + '" stroke="#0c0d11" stroke-width="2"/>' +
      hits;

    var firstDate = new Date(d[0]).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
    var lastDate = new Date(d[n-1]).toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'});
    var cap = document.getElementById(captionId);
    if (cap) cap.textContent = firstDate + ' – ' + lastDate;
  }

  document.getElementById(selectId).addEventListener('change', function(e) { draw(e.target.value); });
  draw('60');
}

(function(){
  var tabs=document.querySelectorAll('.club-tab'); if(!tabs.length) return;
  var over=document.getElementById('tab-overview'), panel=document.getElementById('tab-matches');
  var DATA=null, shown=0, PAGE=25, rows=[], res='';
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]});}
  function show(name, push){
    tabs.forEach(function(t){t.classList.toggle('on', t.getAttribute('data-tab')===name);});
    over.hidden = name!=='overview'; panel.hidden = name!=='matches';
    if(push!==false){ try{history.replaceState(null,'',name==='matches'?'#matches':location.pathname+location.search);}catch(e){} }
    if(name==='matches') load();
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){show(t.getAttribute('data-tab'));});});
  function load(){
    if(DATA) return;
    DATA=[];
    fetch(panel.getAttribute('data-src')).then(function(r){return r.ok?r.json():null}).then(function(d){
      if(!d){document.getElementById('am-list').innerHTML='<div class="am-empty">Couldn’t load the matches - try again later.</div>';return;}
      DATA=d.m; fill(); apply();
    }).catch(function(){document.getElementById('am-list').innerHTML='<div class="am-empty">Couldn’t load the matches - try again later.</div>';});
  }
  function fill(){
    var seasons=[], comps={};
    DATA.forEach(function(m){ if(seasons.indexOf(m[3])<0) seasons.push(m[3]); comps[m[1]]=(comps[m[1]]||0)+1; });
    var s=document.getElementById('am-season'), c=document.getElementById('am-comp');
    seasons.forEach(function(x){ s.insertAdjacentHTML('beforeend','<option>'+esc(x)+'</option>'); });
    Object.keys(comps).sort(function(a,b){return comps[b]-comps[a];}).forEach(function(x){
      c.insertAdjacentHTML('beforeend','<option>'+esc(x)+'</option>'); });
    s.onchange=c.onchange=document.getElementById('am-opp').onchange=apply;
    document.querySelectorAll('#am-res button').forEach(function(b){ b.onclick=function(){
      res=b.getAttribute('data-r');
      document.querySelectorAll('#am-res button').forEach(function(x){x.classList.toggle('on',x===b);});
      apply(); }; });
    document.getElementById('am-more').onclick=function(){ render(shown+PAGE); };
  }
  function apply(){
    var s=document.getElementById('am-season').value, c=document.getElementById('am-comp').value;
    // v Top N: the opponent's rank at the time of the match (Greg, 2026-10).
    var top=+document.getElementById('am-opp').value||0;
    var base=DATA.filter(function(m){return (!s||m[3]===s)&&(!c||m[1]===c)&&(!top||(m[7]&&m[7]<=top));});
    rows=base.filter(function(m){return !res||m[10]===res;});
    var w=0,d=0,l=0,ch=0,gf=0,ga=0;
    base.forEach(function(m){ if(m[10]==='W')w++; else if(m[10]==='D')d++; else l++; ch+=m[11]||0; gf+=m[8]; ga+=m[9]; });
    document.getElementById('am-sum').innerHTML=
      '<span><b>'+base.length+'</b> played</span><span><b class="w">'+w+'</b> W</span><span><b class="d">'+d+'</b> D</span>'+
      '<span><b class="l">'+l+'</b> L</span><span><b>'+gf+'-'+ga+'</b> goals</span>'+
      '<span><b class="'+(ch>=0?'w':'l')+'">'+(ch>=0?'+':'')+ch.toFixed(1)+'</b> rating</span>';
    render(PAGE);
  }
  var MON=['January','February','March','April','May','June','July','August','September','October','November','December'];
  var DAY=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  function render(n){
    shown=Math.min(n, rows.length);
    var out=[], month='';
    for(var i=0;i<shown;i++){
      var m=rows[i], dt=new Date(m[0]+'T12:00:00Z'), mo=MON[dt.getUTCMonth()]+' '+dt.getUTCFullYear();
      if(mo!==month){ month=mo; out.push('<div class="am-month">'+mo+'</div>'); }
      var opp=m[6]?'<a href="'+esc(m[6])+'.html">'+esc(m[5])+'</a>':esc(m[5]);
      var ven=m[4]==='H'?'v':(m[4]==='A'?'at':'v');
      var venTxt={H:'Home',A:'Away',N:'Neutral'}[m[4]]||'';
      var odds=m[13]!=null?'<small class="am-p" title="Our odds before the game: '+Math.round(m[13]*100)+'% to win">'+Math.round(m[13]*100)+'%</small>':'';
      var ch=m[11]==null?'':'<span class="'+(m[11]>=0?'w':'l')+'">'+(m[11]>=0?'+':'')+m[11].toFixed(1)+'</span>';
      out.push('<div class="am-row">'+
        '<span class="am-date">'+DAY[dt.getUTCDay()]+' '+dt.getUTCDate()+' '+MON[dt.getUTCMonth()].slice(0,3)+'</span>'+
        '<span class="am-comp"><i>'+esc(m[1])+'</i></span>'+
        '<span class="am-ven" title="'+venTxt+'">'+(m[4]||'')+'</span>'+
        '<span class="am-opp"><em>'+ven+'</em> '+opp+(m[7]?' <small>#'+m[7]+'</small>':'')+'</span>'+
        '<span class="am-res"><b class="r'+m[10]+'">'+m[10]+' '+m[8]+'-'+m[9]+'</b>'+odds+'</span>'+
        '<span class="am-ch">'+ch+(m[12]?'<small class="am-rk2"> &middot; #'+m[12]+'</small>':'')+'</span>'+
        '<span class="am-rk">'+(m[12]?'#'+m[12]:'')+'</span>'+
        '<span class="am-meta">'+DAY[dt.getUTCDay()]+' '+dt.getUTCDate()+' '+MON[dt.getUTCMonth()].slice(0,3)+' &middot; '+esc(m[1])+'</span>'+
        '</div>');
    }
    var list=document.getElementById('am-list');
    list.innerHTML = out.length ? '<div class="am-th"><span>Date</span><span>Competition</span><span>H/A</span><span>Opponent <small>(rank then)</small></span><span>Result <small>(our win odds)</small></span><span>Rating</span><span>Rank after</span></div>'+out.join('')
                                : '<div class="am-empty">No matches for this choice.</div>';
    var more=document.getElementById('am-more');
    more.hidden = shown>=rows.length;
    more.textContent='Show '+Math.min(PAGE, rows.length-shown)+' more ('+(rows.length-shown)+' left)';
  }
  if(location.hash==='#matches') show('matches', false);
})();
(function(){
  // The charts and the other seasons' tables, from club_data/<slug>.json.
  var main=document.querySelector('main.club-page'); if(!main) return;
  var src=main.getAttribute('data-data'), tid=main.getAttribute('data-tid'); if(!src) return;
  var P=null;
  function data(){ if(!P) P=fetch(src).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;}); return P; }
  function e(v){return String(v==null?'':v).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function rows(t){
    var out=t.n?'<tr class="note"><td colspan="10">'+e(t.n)+'</td></tr>':'';
    t.r.forEach(function(r){
      var club=r[2]?'<a href="'+e(r[2])+'.html">'+e(r[1])+'</a>':e(r[1]), cells='';
      for(var i=3;i<10;i++) cells+='<td>'+e(r[i])+'</td>';
      out+='<tr'+(r[11]?' class="me"':'')+'><td>'+e(r[0])+'</td><td class="c">'+club+'</td>'+cells+'<td class="p">'+e(r[10])+'</td></tr>';
    });
    return out;
  }
  if(document.getElementById('rating-svg-'+tid)) data().then(function(d){
    if(!d||!d.h) return;
    mdiRenderChart('rating-svg-'+tid,'rating-select-'+tid,'rating-caption-'+tid,'rating-tooltip-'+tid,
      d.h.dates,d.h.e,{invert:false,color:'#3dba5e',fmt:function(v){return v.toFixed(1);}});
    mdiRenderChart('rank-svg-'+tid,'rank-select-'+tid,'rank-caption-'+tid,'rank-tooltip-'+tid,
      d.h.dates,d.h.r,{invert:true,color:'#7880a0',fmt:function(v){return '#'+v.toFixed(0);}});
  });
  var sel=document.getElementById('table-select-'+tid), body=document.getElementById('table-body-'+tid);
  if(sel&&body) sel.addEventListener('change',function(){
    var k=sel.value;
    data().then(function(d){ var t=d&&d.t&&d.t[k]; if(t&&sel.value===k) body.innerHTML=rows(t); });
  });
})();
