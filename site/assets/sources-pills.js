// site/assets/sources-pills.js
(function(){
  function esc(s){ return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function human(dtStr){
    try {
      const dt = new Date(dtStr);
      const now = new Date();
      const sameDay = dt.toDateString() === now.toDateString();
      const yest = new Date(now); yest.setDate(now.getDate()-1);
      const t = dt.toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
      if (sameDay) return `Today, ${t}`;
      if (dt.toDateString() === yest.toDateString()) return `Yesterday, ${t}`;
      return dt.toLocaleString([], {month:'short', day:'numeric'}) + ", " + t;
    } catch(e){ return dtStr || ""; }
  }
  function color(seed){
    let h = 0; for (let i=0;i<seed.length;i++) h = (h*31 + seed.charCodeAt(i)) % 360;
    return [`hsl(${h} 70% 94%)`, `hsl(${h} 70% 28%)`];
  }
  function render(sources){
    if (!sources || !sources.length) return document.createElement('div');
    const tray = document.createElement('div'); tray.className = 'pill-tray';
    for (const v of sources){
      const [bg, fg] = color(v.domain || v.display || "x");
      const a = document.createElement('a');
      a.className = 'pill';
      a.style.setProperty('--pill-bg', bg);
      a.style.setProperty('--pill-fg', fg);
      a.href = v.domain ? `https://${v.domain}` : '#';
      a.target = '_blank'; a.rel = 'noopener';
      a.title = v.last_title ? `${v.last_title} (${v.last_link || ''})` : (v.last_link || '');

      a.innerHTML = `
        <span class="pill-site">${esc(v.display || v.domain || "unknown")}</span>
        <span class="pill-dot" aria-hidden="true">•</span>
        <span class="pill-when">${esc(human(v.last_dt))}</span>
        <span class="pill-count" title="Articles in window">(${Number(v.count||0)})</span>
      `;
      tray.appendChild(a);
    }
    return tray;
  }

  function ensureCss(){
    if (![...document.styleSheets].some(s=>s.href && s.href.includes('assets/pills.css'))){
      const link = document.createElement('link');
      link.rel='stylesheet'; link.href='assets/pills.css';
      document.head.appendChild(link);
    }
  }

  async function init(){
    ensureCss();
    try{
      const res = await fetch('../data/sources.json', {cache:'no-store'});
      if(!res.ok) return;
      const data = await res.json();
      const tray = render(data.sources || []);
      // insert at marker or after first <h1>
      const marker = document.querySelector('main')?.querySelector('<!-- SOURCES_PILLS -->');
      let target = null;
      if (marker){ target = marker.parentNode; target.insertBefore(tray, marker.nextSibling); }
      else {
        const h1 = document.querySelector('main h1') || document.querySelector('h1');
        if (h1 && h1.parentNode) h1.parentNode.insertBefore(tray, h1.nextSibling);
        else document.body.prepend(tray);
      }
    } catch(e){ console.warn('sources-pills:', e); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
