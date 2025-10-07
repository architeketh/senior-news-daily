# bot/site_builder.py
from pathlib import Path
import json
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
ARCH = SITE / "archive"
SITE.mkdir(exist_ok=True)
ARCH.mkdir(parents=True, exist_ok=True)

ITEMS = json.loads((DATA / "items.json").read_text(encoding="utf-8")) if (DATA/"items.json").exists() else {"items":[]}
DIGEST = json.loads((DATA / "digest.json").read_text(encoding="utf-8")) if (DATA/"digest.json").exists() else {"summary":"", "alerts":[], "category_counts":{}}

now = datetime.now(timezone.utc)

def fmt_date(dt_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")

def group_by_period(items: list[dict]):
    today = now.date()
    this_week_start = today - timedelta(days=today.weekday())
    this_month_start = today.replace(day=1)
    this_year_start = today.replace(month=1, day=1)
    buckets = {"today":[], "week":[], "month":[], "year":[]}
    for it in items:
        d = it.get("published") or it.get("fetched")
        try:
            dt = datetime.fromisoformat(d.replace("Z","+00:00")).date()
        except Exception:
            continue
        if dt == today: buckets["today"].append(it)
        if dt >= this_week_start: buckets["week"].append(it)
        if dt >= this_month_start: buckets["month"].append(it)
        if dt >= this_year_start: buckets["year"].append(it)
    return buckets

def category_counts(items: list[dict]) -> dict:
    counts = {}
    for it in items:
        c = (it.get("category") or "General").strip() or "General"
        counts[c] = counts.get(c, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())))

def html_escape(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def render_cards(items: list[dict]) -> str:
    parts = []
    for it in items:
        title = html_escape(it.get("title",""))
        src = html_escape(it.get("source",""))
        link = html_escape(it.get("link",""))
        date = fmt_date(it.get("published") or it.get("fetched"))
        iid  = html_escape(it.get("id",""))
        cat  = html_escape(it.get("category","General"))
        parts.append(
            "<div class='card' data-id='"+iid+"'>"
            + "<a class='card-block' href='"+link+"' target='_blank' rel='noopener'>"
            +   "<div class='card-title'>"+title+"</div>"
            +   "<div class='card-meta'>"+src+" · "+date+" · <span class='badge'>"+cat+"</span></div>"
            + "</a>"
            + "<button class='save' data-id='"+iid+"' title='Save for later' aria-label='Save'>&#9734;</button>"
            + "</div>"
        )
    return "\n".join(parts)

def render_alerts(alerts: list[dict]) -> str:
    if not alerts: return "<p class='muted'>No new scam alerts detected.</p>"
    lis = []
    for it in alerts[:10]:
        title = html_escape(it.get("title",""))
        src = html_escape(it.get("source",""))
        link = html_escape(it.get("link",""))
        date = fmt_date(it.get("published") or it.get("fetched"))
        lis.append(f"<li><a href='{link}' target='_blank' rel='noopener'>{title}</a> <span class='muted'>({src} · {date})</span></li>")
    return "<ul class='alerts'>" + "\n".join(lis) + "</ul>"

def counts_bar(counts: dict) -> str:
    if not counts: return "<div class='counts muted'>No categories yet.</div>"
    chips = []
    for cat, n in counts.items():
        chips.append(f"<span class='count-chip'>{html_escape(cat)} <b>{n}</b></span>")
    return "<div class='counts'>" + " ".join(chips) + "</div>"

def build_index():
    items = ITEMS.get("items", [])
    buckets = group_by_period(items)
    summary_text = html_escape(DIGEST.get("summary",""))
    alerts_html = render_alerts(DIGEST.get("alerts", []))

    # per-bucket category counts JSON for the JS
    per_bucket_counts = {
        "today": category_counts(buckets["today"]),
        "week":  category_counts(buckets["week"]),
        "month": category_counts(buckets["month"]),
        "year":  category_counts(buckets["year"]),
    }
    counts_json = json.dumps(per_bucket_counts, ensure_ascii=False)

    hero_title = "Plan boldly. Retire confidently."
    venmo_footer = "Venmo donations are welcome! @MikeHnastchenko"
    updated = now.strftime("%Y-%m-%d %H:%M UTC")
    fetched_date = html_escape((ITEMS.get("updated") or "")[:10])
    default_tab = "today" if buckets["today"] else "week"

    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Senior News Daily</title>
<link rel="stylesheet" href="./styles.css" />
</head>
<body>
<header class="topbar">
  <div class="brand">
    <span class="logo">📰</span> <span class="brand-title">Senior News Daily</span>
  </div>
  <div class="actions">
    <a class="btn ghost" href="./archive/">Open Archive</a>
    <a class="btn ghost" href="./categories.html">Open Categories</a>
  </div>
</header>

<header class="site-header hero">
  <div class="hero-title">__HERO__</div>
  <p class="muted">Daily Summary • Grouped Articles • Today / Weekly / Monthly views</p>
  <div class="retrieved">Articles retrieved: <b>__FETCHED__</b></div>

  <div class="controls">
    <input id="extraUrl" class="input" placeholder="Paste a URL (RSS or article) and click Fetch Now" />
    <button id="fetchNow" class="btn primary">Download new articles</button>
    <button id="setPAT" class="btn">Set API token</button>
    <div class="hint muted">Tip: Token is stored in your browser only (localStorage). Scope: workflow (public repo).</div>
  </div>
</header>

<nav class="chips">
  <button data-filter="today" class="chip">Today</button>
  <button data-filter="week" class="chip">This Week</button>
  <button data-filter="month" class="chip">This Month</button>
  <button data-filter="year" class="chip">This Year</button>
  <button data-filter="saved" class="chip">Saved</button>
  <a class="chip" href="./archive/">Archive</a>
  <a class="chip" href="./categories.html">Categories</a>
</nav>

<section class="summary">
  <h2>Daily Summary</h2>
  <pre>__SUMMARY__</pre>
  <div id="bucketCounts" class="counts muted">Loading category counts...</div>
</section>

<section class="scams">
  <h2>Scam Alerts</h2>
  <p class="muted">Recent reports affecting older adults. Always verify requests for money, benefits, or personal info.</p>
  __ALERTS__
</section>

<section id="list" class="grid" data-active="__DEFAULT__">
  <div data-period="today" class="panel">__TODAY__</div>
  <div data-period="week"  class="panel">__WEEK__</div>
  <div data-period="month" class="panel">__MONTH__</div>
  <div data-period="year"  class="panel">__YEAR__</div>
  <div data-period="saved" class="panel"><div class="muted">No saved articles yet.</div></div>
</section>

<footer class="site-footer">
  <div>Updated __UPDATED__</div>
  <div class="muted">__VENMO__</div>
</footer>

<script>
(function(){
  const countsData = __COUNTS_JSON__;
  const chips = document.querySelectorAll('.chip[data-filter]');
  const panels = document.querySelectorAll('.panel');
  const countsBox = document.getElementById('bucketCounts');

  function renderCounts(tab){
    const data = countsData[tab] || {};
    const keys = Object.keys(data);
    if (!keys.length){ countsBox.classList.add('muted'); countsBox.innerHTML = 'No categories yet.'; return; }
    countsBox.classList.remove('muted');
    countsBox.innerHTML = keys.map(k => "<span class='count-chip'>"+k+" <b>"+data[k]+"</b></span>").join(" ");
  }
  function show(tab){
    chips.forEach(c => c.classList.toggle('active', c.getAttribute('data-filter')===tab));
    panels.forEach(p => p.classList.toggle('show', p.getAttribute('data-period')===tab));
    renderCounts(tab);
  }
  show('__DEFAULT__');
  chips.forEach(ch => ch.addEventListener('click', () => show(ch.getAttribute('data-filter'))));

  // Saved articles
  const SAVED_KEY="snd_saved_ids";
  function getSaved(){ try { return JSON.parse(localStorage.getItem(SAVED_KEY)||"[]"); } catch(e){ return []; } }
  function setSaved(arr){ localStorage.setItem(SAVED_KEY, JSON.stringify(Array.from(new Set(arr)))); }
  function updateSavedUI(){
    const cur = new Set(getSaved());
    document.querySelectorAll('.card .save').forEach(btn=>{
      const id = btn.getAttribute('data-id');
      btn.innerHTML = cur.has(id) ? "&#9733;" : "&#9734;";
    });
    const savedPanel = document.querySelector('.panel[data-period="saved"]');
    const cards = Array.from(document.querySelectorAll('.card'));
    const savedCards = cards.filter(c => cur.has(c.getAttribute('data-id')));
    savedPanel.innerHTML = savedCards.length ? savedCards.map(c=>c.outerHTML).join("") : '<div class="muted">No saved articles yet.</div>';
  }
  document.addEventListener('click', (e)=>{
    const t = e.target;
    if (t && t.classList.contains('save')) {
      e.preventDefault();
      const id = t.getAttribute('data-id');
      const cur = getSaved();
      if (cur.includes(id)) setSaved(cur.filter(x=>x!==id)); else { cur.push(id); setSaved(cur); }
      updateSavedUI();
    }
  });
  updateSavedUI();

  // Manual fetch trigger (workflow_dispatch)
  const BTN = document.getElementById('fetchNow');
  const SET = document.getElementById('setPAT');
  const URL = document.getElementById('extraUrl');
  const TOKEN_KEY='snd_pat_token';

  function setToken(){
    const cur = localStorage.getItem(TOKEN_KEY)||'';
    const val = prompt('Paste a GitHub Personal Access Token (workflow scope; stored locally only):', cur);
    if (val!==null){ localStorage.setItem(TOKEN_KEY, val.trim()); alert('Token saved in your browser.'); }
  }
  async function dispatch(){
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token){ alert('Set a GitHub token first. Click "Set API token".'); return; }
    const host = location.host; const path = location.pathname.replace(/^\\//,'');
    const owner = host.split('.')[0]; const repo = path.split('/')[0] || 'senior-news-daily';
    const endpoint = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/pages.yml/dispatches`;
    const body = { ref: "main", inputs: {} };
    const extra = (URL.value||'').trim(); if (extra) body.inputs = { extra_url: extra };
    const resp = await fetch(endpoint, { method:'POST',
      headers:{ 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github+json' },
      body: JSON.stringify(body) });
    if (resp.status===204){ alert('Workflow dispatched! Refresh in ~1–2 minutes.'); }
    else { alert('Dispatch failed: '+resp.status+'\\n'+await resp.text()); }
  }
  if (SET) SET.addEventListener('click', setToken);
  if (BTN) BTN.addEventListener('click', dispatch);
})();
</script>
</body>
</html>
"""
    html = (template
            .replace("__HERO__", hero_title)
            .replace("__SUMMARY__", summary_text)
            .replace("__ALERTS__", alerts_html)
            .replace("__DEFAULT__", default_tab)
            .replace("__UPDATED__", updated)
            .replace("__VENMO__", venmo_footer)
            .replace("__FETCHED__", fetched_date or "—")
            .replace("__COUNTS_JSON__", counts_json)
            .replace("__TODAY__", render_cards(buckets["today"]))
            .replace("__WEEK__",  render_cards(buckets["week"]))
            .replace("__MONTH__", render_cards(buckets["month"]))
            .replace("__YEAR__",  render_cards(buckets["year"]))
            )
    (SITE / "index.html").write_text(html, encoding="utf-8")

def build_categories_page():
    items = ITEMS.get("items", [])
    cats = {}
    for it in items:
        c = (it.get("category") or "General").strip() or "General"
        cats.setdefault(c, []).append(it)
    # Sort categories by count desc then name
    cat_order = sorted(cats.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))

    def section(cat, its):
        return ("<section class='cat-section'>"
                + f"<h2>{html_escape(cat)} <span class='count-badge'>{len(its)}</span></h2>"
                + "<div class='cat-grid'>"
                + render_cards(its)
                + "</div></section>")

    body = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            "<title>Categories — Senior News Daily</title>",
            "<link rel='stylesheet' href='./styles.css'>",
            "</head><body>",
            "<header class='topbar'><div class='brand'><span class='logo'>📰</span> <span class='brand-title'>Senior News Daily</span></div>",
            "<div class='actions'><a class='btn ghost' href='./index.html'>Back to Home</a> <a class='btn ghost' href='./archive/'>Open Archive</a></div></header>",
            "<main class='container'>"]
    for cat, its in cat_order:
        body.append(section(cat, its))
    body.append("</main><footer class='site-footer'><div class='muted'>Categories built on "
                + now.strftime('%Y-%m-%d %H:%M UTC') + "</div></footer></body></html>")
    (SITE / "categories.html").write_text("".join(body), encoding="utf-8")

def build_archive():
    items = ITEMS.get("items", [])
    by_day = {}
    for it in items:
        d = fmt_date(it.get("published") or it.get("fetched"))
        by_day.setdefault(d, []).append(it)
    links = []
    for day in sorted(by_day.keys(), reverse=True):
        links.append(f"<li><a href='{day}.html'>{day}</a> <span class='muted'>({len(by_day[day])})</span></li>")
    (ARCH / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><link rel=stylesheet href='../styles.css'>"
        + "<h1>Archive by Day</h1><ul>" + "\n".join(links) + "</ul>", encoding="utf-8")
    for day, its in by_day.items():
        (ARCH / f"{day}.html").write_text(
            "<!doctype html><meta charset='utf-8'><link rel=stylesheet href='../styles.css'>"
            + f"<h1>{day}</h1>" + render_cards(its), encoding="utf-8")

def main():
    build_index()
    build_categories_page()
    build_archive()
    print(f"[site] Built pages in {SITE}")

if __name__ == "__main__":
    main()
