// site/assets/pills_home.js
(function () {
  function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
  function human(dtStr){
    try{
      const dt=new Date(dtStr), now=new Date();
      const t=dt.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
      const y=new Date(now); y.setDate(now.getDate()-1);
      if (dt.toDateString()===now.toDateString()) return `Today, ${t}`;
      if (dt.toDateString()===y.toDateString())   return `Yesterday, ${t}`;
      return dt.toLocaleString([], {month:'short', day:'numeric'}) + ", " + t;
    }catch(e){ return dtStr||""; }
  }
  function color(seed){
    seed = seed || "x"; let h=0; for(let i=0;i<seed.length;i++) h=(h*31+seed.charCodeAt(i))%360;
    return [`hsl(${h} 70% 94%)`,`hsl(${h} 70% 28%)`];
  }
  function ensureCss(){
    if (![...document.styleSheets].some(s=>s.href && s.href.includes('assets/pills.css'))){
      const link=document.createElement('link'); link.rel='stylesheet'; link.href='assets/pills.css';
      document.head.appendChild(link);
    }
  }
  function pickMount(){
    const marker = document.querySelector('[data-sources-marker]');
    if (marker) return marker;
    const h1 = document.querySelector('main h1') || document.querySelector('h1');
    return h1 || document.body;
  }
  function baseUrl(){
    const {origin, pathname} = window.location;
    // drop filename from path if present (e.g., index.html)
    const root = pathname.replace(/[^/]*$/, "");
    return origin + root; // ends with /
  }
  function renderTray(sources, includeCTA=true){
    const wrap = document.createElement('div');
    wrap.className = 'pill-tray';

    if (includeCTA){
      const cta = document.createElement('a');
      cta.className = 'pill pill-cta';
      cta.href = baseUrl() + "sources.html";
      cta.textContent = 'View all sources';
      wrap.appendChild(cta);
    }

    for (const v of sources){
      const [bg,fg]=color(v.domain||v.display||"x");
      const a=document.createElement('a');
      a.className='pill';
      a.style.setProperty('--pill-bg',bg);
      a.style.setProperty('--pill-fg',fg);
      a.href=v.domain?`https://${v.domain}`:'#'; a.target='_blank'; a.rel='noopener';
      a.title=v.last_title ? `${v.last_title} (${v.last_link||''})` : (v.last_link||'');
      a.innerHTML=`
        <span class="pill-site">${esc(v.display||v.domain||"unknown")}</span>
        <span class="pill-dot" aria-hidden="true">•</span>
        <span class="pill-when">${esc(human(v.last_dt))}</span>
        <span class="pill-count" title="Articles in window">(${Number(v.count||0)})</span>
      `;
      wrap.appendChild(a);
    }
    return wrap;
  }

  function mount() {
    ensureCss();
    const data = (window.SOURCES_DATA || {});
    const sources = Array.isArray(data.sources) ? data.sources : [];
    const target = pickMount();

    // If we have embedded data, use it; otherwise try fetching as a fallback.
    if (sources.length){
      const tray = renderTray(sources, /* includeCTA */ true);
      if (target.tagName && target.tagName.toLowerCase()==='h1') {
        target.parentNode.insertBefore(tray, target.nextSibling);
      } else {
        target.appendChild(tray);
      }
      return;
    }

    // Fallback: fetch JSON if embedded script missing
    fetch(baseUrl() + "data/sources.json", {cache:"no-store"})
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        const arr = (j && Array.isArray(j.sources)) ? j.sources : [];
        if (!arr.length) return;
        const tray = renderTray(arr, /* includeCTA */ true);
        if (target.tagName && target.tagName.toLowerCase()==='h1') {
          target.parentNode.insertBefore(tray, target.nextSibling);
        } else {
          target.appendChild(tray);
        }
      })
      .catch(()=>{ /* silent */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
