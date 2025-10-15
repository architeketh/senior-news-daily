# bot/site_builder.py
"""
Senior News Daily — Site Builder (with weekly trends)
- Generates site/index.html, site/saved.html, site/scams.html
- Generates site/archive/YYYY-MM-DD.html + site/archive/index.html
- Writes site/styles.css
- Weekly trends panel
- Color-matched chips/cards (includes Finance & Money; Travel & Leisure; Outdoors; People; Politics; Retail Trends)
"""

import json, datetime, pathlib, re
from collections import Counter, defaultdict
from datetime import datetime as dt, timezone, timedelta

import html  # add at top with other imports

TAG_RE = re.compile(r"<[^>]+>")
WS_RE  = re.compile(r"\s+")

def plaintext(s: str) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not s:
        return ""
    s = html.unescape(s)           # &amp; → &
    s = TAG_RE.sub(" ", s)         # drop tags
    s = WS_RE.sub(" ", s).strip()  # tidy spaces/newlines
    return s

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
ARCH = SITE / "archive"
SITE.mkdir(parents=True, exist_ok=True)
ARCH.mkdir(parents=True, exist_ok=True)

ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

# ---------- helpers ----------
def esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def fmt_date(dt_iso: str | None) -> str:
    if not dt_iso: return ""
    try:
        x = datetime.datetime.fromisoformat(dt_iso.replace("Z","+00:00"))
        return x.strftime("%b %d, %Y")
    except Exception:
        return (dt_iso or "")[:10]

def day_key(it: dict) -> str:
    return (it.get("published") or it.get("fetched") or "")[:10]

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+","-",(s or "general").lower()).strip("-") or "general"

def next_update_badge(now: dt | None = None) -> str:
    now = now or dt.now(timezone.utc)
    base = now.replace(minute=0, second=0, microsecond=0)
    slots = [base.replace(hour=0), base.replace(hour=12), (base + timedelta(days=1)).replace(hour=0)]
    nxt = min([s for s in slots if s > now], key=lambda d: d)
    delta = nxt - now
    hrs = int(delta.total_seconds() // 3600)
    mins = int((delta.total_seconds() % 3600) // 60)
    label = f"{hrs}h {mins}m" if hrs else f"{mins}m"
    when = nxt.strftime("%b %d, %H:%M UTC")
    return f"<span class='badge' style='margin-left:.5rem;'>Next update in {label} · {when}</span>"

# ---------- CSS ----------
CSS = r"""
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f9fafb;color:#111827;margin:0}
.container{width:min(1100px,90%);margin:0 auto;padding:1rem 0 3rem}h1,h2,h3{margin:0 0 .5rem}
a{color:inherit;text-decoration:none}.muted{color:#6b7280;font-size:.9em}
.hero{text-align:center;background:linear-gradient(135deg,#111827,#1e3a8a);color:#fff;padding:3rem 1rem 2rem}
.hero h1{font-size:2.3rem;margin-bottom:.3rem}.hero .subtitle{color:#cbd5e1;font-size:1.1rem}
.topnav{background:#1118270d;border-bottom:1px solid #e5e7eb}
.topnav .container{display:flex;gap:1rem;align-items:center;justify-content:space-between;padding:0.6rem 0;}
.topnav a{font-weight:700;text-decoration:none}
section{margin-top:2rem}
.articles #cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;box-shadow:0 2px 5px rgba(0,0,0,.04);
padding:1rem 1.25rem;position:relative;transition:.2s}
.card:hover{transform:translateY(-2px);box-shadow:0 4px 10px rgba(0,0,0,.08)}
.card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:6px;border-radius:16px 0 0 16px}
.card-title{font-weight:700;margin-bottom:.2rem}.card-meta{font-size:.9em;color:#4b5563}
.card-summary{margin-top:.4rem;color:#374151;font-size:.95em;line-height:1.4}
.save{position:absolute;top:8px;right:10px;background:none;border:none;font-size:1.4rem;cursor:pointer;color:#9ca3af}
.save:hover{color:#111827}
.filterbar{display:flex;flex-wrap:wrap;gap:.5rem;margin:.5rem 0 1rem}
.chip{border:1px solid #d1d5db;border-radius:9999px;padding:.4rem .9rem;cursor:pointer;font-weight:700;background:#f3f4f6;color:#111}
.chip b{font-weight:800}.chip.active{outline:2px solid #111;color:#111;background:#fff}
.alerts li,.archives li{margin:.4rem 0}
.footer{text-align:center;background:#111827;color:#cbd5e1;padding:2rem 1rem}
.footer a,.footer strong{color:#facc15}

/* Category palette (added new slugs) */
:root{
--cat-medicare:#2563eb;--cat-social-security:#059669;--cat-finance-retirement:#0ea5e9; /* legacy name */
--cat-finance-money:#0ea5e9;
--cat-travel:#ef4444;--cat-travel-leisure:#ef4444;
--cat-golf-leisure:#f59e0b;--cat-outdoors:#10b981;
--cat-cooking-nutrition:#e11d48;--cat-exercise-fitness:#16a34a;
--cat-caregiving-ltc:#7c3aed;--cat-aging-research:#0891b2;
--cat-safety-scams:#dc2626;--cat-policy-legislation:#4b5563;
--cat-people:#8b5cf6;--cat-politics:#0f172a;--cat-retail-trends:#f97316;
--cat-general:#6b7280}

/* Card strip colors */
.card[class*="cat-"]::before{background:var(--cat-general)}
.card.cat-medicare::before{background:var(--cat-medicare)}
.card.cat-social-security::before{background:var(--cat-social-security)}
.card.cat-finance-retirement::before{background:var(--cat-finance-retirement)}
.card.cat-finance-money::before{background:var(--cat-finance-money)}
.card.cat-travel::before{background:var(--cat-travel)}
.card.cat-travel-leisure::before{background:var(--cat-travel-leisure)}
.card.cat-golf-leisure::before{background:var(--cat-golf-leisure)}
.card.cat-outdoors::before{background:var(--cat-outdoors)}
.card.cat-cooking-nutrition::before{background:var(--cat-cooking-nutrition)}
.card.cat-exercise-fitness::before{background:var(--cat-exercise-fitness)}
.card.cat-caregiving-ltc::before{background:var(--cat-caregiving-ltc)}
.card.cat-aging-research::before{background:var(--cat-aging-research)}
.card.cat-safety-scams::before{background:var(--cat-safety-scams)}
.card.cat-policy-legislation::before{background:var(--cat-policy-legislation)}
.card.cat-people::before{background:var(--cat-people)}
.card.cat-politics::before{background:var(--cat-politics)}
.card.cat-retail-trends::before{background:var(--cat-retail-trends)}

/* Chips color hint */
.chip[data-cat="finance-money"]{background:#e0f2fe;border-color:var(--cat-finance-money)}
.chip[data-cat="travel-leisure"]{background:#fee2e2;border-color:var(--cat-travel-leisure)}
.chip[data-cat="outdoors"]{background:#dcfce7;border-color:var(--cat-outdoors)}
.chip[data-cat="people"]{background:#ede9fe;border-color:var(--cat-people)}
.chip[data-cat="politics"]{background:#e5e7eb;border-color:var(--cat-politics);color:#0f172a}
.chip[data-cat="retail-trends"]{background:#ffedd5;border-color:var(--cat-retail-trends)}
/* existing */
.chip[data-cat="medicare"]{background:#dbeafe;border-color:var(--cat-medicare)}
.chip[data-cat="social-security"]{background:#d1fae5;border-color:var(--cat-social-security)}
.chip[data-cat="finance-retirement"]{background:#e0f2fe;border-color:var(--cat-finance-retirement)}
.chip[data-cat="travel"]{background:#fee2e2;border-color:var(--cat-travel)}
.chip[data-cat="golf-leisure"]{background:#fef3c7;border-color:var(--cat-golf-leisure)}
.chip[data-cat="cooking-nutrition"]{background:#ffe4e6;border-color:var(--cat-cooking-nutrition)}
.chip[data-cat="exercise-fitness"]{background:#dcfce7;border-color:var(--cat-exercise-fitness)}
.chip[data-cat="caregiving-ltc"]{background:#ede9fe;border-color:var(--cat-caregiving-ltc)}
.chip[data-cat="aging-research"]{background:#cffafe;border-color:var(--cat-aging-research)}
.chip[data-cat="safety-scams"]{background:#fee2e2;border-color:var(--cat-safety-scams)}
.chip[data-cat="policy-legislation"]{background:#e5e7eb;border-color:var(--cat-policy-legislation)}
.chip[data-cat="general"]{background:#f3f4f6;border-color:var(--cat-general)}
.chip[data-cat="__saved"]{background:#e0f2fe;border-color:#0284c7}

/* Trends bars */
.trends{margin-top:1.5rem}
.trend{display:flex;align-items:center;gap:.6rem;margin:.35rem 0}
.trend b{min-width:180px}
.trend .bar{height:8px;flex:1;background:#e5e7eb;border-radius:999px;position:relative;overflow:hidden}
.trend .bar>span{position:absolute;left:0;top:0;bottom:0;background:#2563eb;border-radius:999px}
.trend .val{color:#6b7280;font-size:.9em;min-width:38px;text-align:right}
"""
(SITE / "styles.css").write_text(CSS, encoding="utf-8")

# ---------- load data ----------
items_blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8")) if ITEMS_PATH.exists() else {"items": []}
digest_blob = json.loads(DIGEST_PATH.read_text(encoding="utf-8")) if DIGEST_PATH.exists() else {}
items = items_blob.get("items", [])
summary = digest_blob.get("summary", "")
alerts = digest_blob.get("alerts", [])
generated = digest_blob.get("generated", datetime.datetime.utcnow().isoformat())

for it in items:
    it["category"] = it.get("category") or "General"

# ---------- weekly trends ----------
def weekly_trends(items: list[dict]) -> str:
    now = dt.now(timezone.utc); since = now - timedelta(days=7)
    def to_dt(s):
        if not s: return None
        try: return dt.fromisoformat(s.replace("Z","+00:00"))
        except Exception: return None
    recent = [it for it in items if (to_dt(it.get("published") or it.get("fetched")) or dt.min) >= since]
    counts = Counter((it.get("category") or "General") for it in recent)
    if not counts: return "<p class='muted'>No articles in the last 7 days.</p>"
    top = counts.most_common(10); maxv = max(v for _,v in top)
    rows=[]
    for cat,v in top:
        slug = slugify(cat)
        rows.append(
            f"<div class='trend'><b>{esc(cat)}</b>"
            f"<div class='bar'><span style='width:{int(v/maxv*100)}%;background:var(--cat-{slug},#2563eb)'></span></div>"
            f"<div class='val'>{v}</div></div>"
        )
    return "<div class='trends'>" + "\n".join(rows) + "</div>"

# ---------- components ----------
def render_card(it):
    cat = it["category"]; slug = slugify(cat)
    title = esc(plaintext(it.get('title','')))
    summary_txt = esc(plaintext(it.get('summary',''))[:280])  # trim to ~280 chars

    return (
        f"<div class='card cat-{slug}' data-id='{esc(it.get('id',''))}' data-cat='{slug}'>"
        f"<a href='{esc(it.get('link',''))}' target='_blank' rel='noopener'>"
        f"<div class='card-title'>{title}</div>"
        f"<div class='card-meta'>{esc(it.get('source',''))} · {fmt_date(it.get('published') or it.get('fetched'))} · "
        f"<span class='badge cat-{slug}'>{esc(cat)}</span></div>"
        f"<div class='card-summary'>{summary_txt}</div></a>"
        f"<button class='save' data-id='{esc(it.get('id',''))}' title='Save'>&#9734;</button></div>"
    )

def render_cards(arr): 
    return "\n".join(render_card(it) for it in arr)

def render_alerts(alerts):
    aarp = ("<p><strong>📍 Track scams nationwide:</strong> "
            "<a href='https://www.aarp.org/money/scams-fraud/tracking-map/' target='_blank' rel='noopener'>AARP Scam Tracking Map</a></p>")
    if not alerts: return aarp + "<p>No current scam alerts.</p>"
    out = [aarp, "<ul class='alerts'>"]
    for a in alerts:
        out.append(f"<li><a href='{esc(a.get('link',''))}' target='_blank' rel='noopener'>{esc(a.get('title',''))}</a> "
                   f"<small>{fmt_date(a.get('published') or a.get('fetched'))}</small></li>")
    out.append("</ul>"); return "\n".join(out)

def build_archive_pages(items):
    by_day = defaultdict(list)
    for it in items:
        d = day_key(it)
        if d: by_day[d].append(it)
    # day pages
    for d, its in by_day.items():
        (ARCH / f"{d}.html").write_text(
            f"<!doctype html><meta charset='utf-8'><link rel='stylesheet' href='../styles.css'>"
            f"<div class='topnav'><div class='container'><a href='../index.html'>← Home</a><a href='./'>Archive</a></div></div>"
            f"<main class='container'><h1>Archive — {esc(d)}</h1><div id='cards'>{render_cards(its)}</div></main>"
            f"<footer class='footer'><p>Venmo: <strong>@MikeHnastchenko</strong></p></footer>",
            encoding="utf-8"
        )
    def list_html(prefix):
        return "<ul class='archives'>" + "".join(
            f"<li><a href='{prefix}{d}.html'>{d}</a> <span class='muted'>({len(v)} articles)</span></li>"
            for d, v in sorted(by_day.items(), reverse=True)
        ) + "</ul>"
    return list_html("archive/"), list_html("")

def build_scams_page():
    html = """<!doctype html><meta charset='utf-8'><title>Scam Resources — Senior News Daily</title>
<link rel='stylesheet' href='styles.css'><div class='topnav'><div class='container'>
<a href='index.html'>← Home</a><div class='muted'>Scam Resources</div></div></div>
<main class='container'><h1>Scam Resources for Older Adults</h1><ul class='alerts'>
<li><a href='https://reportfraud.ftc.gov/' target='_blank' rel='noopener'>FTC: ReportFraud.ftc.gov</a></li>
<li><a href='https://www.ic3.gov/' target='_blank' rel='noopener'>FBI Internet Crime Complaint Center</a></li>
<li><a href='https://oig.ssa.gov/report/' target='_blank' rel='noopener'>SSA OIG: Report Fraud</a></li>
<li><a href='https://www.medicare.gov/fraud' target='_blank' rel='noopener'>Medicare: Preventing Fraud</a></li>
<li><a href='https://www.aarp.org/money/scams-fraud/tracking-map/' target='_blank' rel='noopener'>AARP Scam Tracking Map</a></li>
</ul></main><footer class='footer'><p>Venmo: <strong>@MikeHnastchenko</strong></p></footer>"""
    (SITE / "scams.html").write_text(html, encoding="utf-8")

# ---------- build ----------
cat_counts = Counter(it["category"] for it in items)
chips = [
    "<button class='chip active' data-cat='__all'>All <b>{}</b></button>".format(sum(cat_counts.values())),
    "<button class='chip' data-cat='__saved'>Saved <b>★</b></button>",
]
for c, n in sorted(cat_counts.items(), key=lambda kv:(-kv[1], kv[0].lower())):
    chips.append(f"<button class='chip' data-cat='{slugify(c)}'>{esc(c)} <b>{n}</b></button>")
chips_html = "\n".join(chips)

archives_home, archives_index = build_archive_pages(items)
build_scams_page()
badge_html = next_update_badge()
trends_html = weekly_trends(items)

template = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Senior News Daily</title><link rel='stylesheet' href='styles.css'></head>
<body><header class='hero'><h1>Plan boldly. Retire confidently.</h1>
<p class='subtitle'>AI-powered daily insights for seniors — health, finance, leisure & scams.</p></header>
<div class='topnav'><div class='container'><a href='index.html'>Home</a><a href='saved.html'>Saved</a><a href='scams.html'>Scam Resources</a><a href='archive/'>Archive</a></div></div>
<main class='container'>
<section class='summary'><h2>Daily Summary</h2><p>__SUMMARY__</p><p class='muted'>Last updated: __UPDATED__ __BADGE__</p></section>
<section class='filters'><h2>Filter by Category</h2><div class='filterbar'>__CHIPS__</div></section>
<section class='articles'><h2>Latest Articles</h2><div id='cards'>__CARDS__</div></section>
<section class='scam-alerts'><h2>⚠️ Scam Alerts</h2>__ALERTS__</section>
<section class='trends'><h2>This Week’s Trends</h2>__TRENDS__</section>
<section class='archives'><h2>Archives</h2>__ARCHIVES__</section>
</main>
<footer class='footer'><p>Venmo: <strong>@MikeHnastchenko</strong></p>
<p class='muted'>© __YEAR__ Senior News Daily — All Rights Reserved</p></footer>
<script>
const cards=[...document.querySelectorAll('#cards .card')];
const chips=[...document.querySelectorAll('.chip')];
function getSaved(){try{return JSON.parse(localStorage.getItem('snd_saved')||'[]');}catch(e){return[]}}
function setSaved(v){localStorage.setItem('snd_saved',JSON.stringify([...new Set(v)]));}
function updateStars(){const cur=new Set(getSaved());document.querySelectorAll('.save').forEach(b=>b.innerHTML=cur.has(b.dataset.id)?'★':'☆');}
function applyFilter(slug){
  if(slug==='__saved'){const cur=new Set(getSaved());cards.forEach(c=>c.style.display=cur.has(c.dataset.id)?'':'none');}
  else{cards.forEach(c=>c.style.display=(slug==='__all'||c.dataset.cat===slug)?'':'none');}
  chips.forEach(ch=>ch.classList.toggle('active',ch.dataset.cat===slug));
  localStorage.setItem('snd_cat',slug);
}
chips.forEach(ch=>ch.addEventListener('click',()=>applyFilter(ch.dataset.cat)));
document.addEventListener('click',e=>{
  if(e.target.classList.contains('save')){
    const id=e.target.dataset.id;const cur=new Set(getSaved());
    cur.has(id)?cur.delete(id):cur.add(id);setSaved([...cur]);updateStars();
  }
});
updateStars();applyFilter(localStorage.getItem('snd_cat')||'__all');
</script></body></html>"""

home_html = (template
    .replace("__SUMMARY__", esc(summary))
    .replace("__UPDATED__", fmt_date(generated))
    .replace("__BADGE__", badge_html)
    .replace("__CHIPS__", chips_html)
    .replace("__CARDS__", render_cards(items))
    .replace("__ALERTS__", render_alerts(alerts))
    .replace("__TRENDS__", trends_html)
    .replace("__ARCHIVES__", archives_home)
    .replace("__YEAR__", str(datetime.date.today().year))
)
(SITE / "index.html").write_text(home_html, encoding="utf-8")

arch_index = f"<!doctype html><meta charset='utf-8'><link rel='stylesheet' href='../styles.css'>" \
             f"<div class='topnav'><div class='container'><a href='../index.html'>← Home</a><div class='muted'>Archive</div></div></div>" \
             f"<main class='container'><h1>Archive</h1>{archives_index}</main>" \
             f"<footer class='footer'><p>Venmo: <strong>@MikeHnastchenko</strong></p></footer>"
(ARCH / "index.html").write_text(arch_index, encoding="utf-8")

# Saved page
saved_html = """<!doctype html><meta charset='utf-8'><title>Saved Articles — Senior News Daily</title>
<link rel='stylesheet' href='styles.css'>
<div class='topnav'><div class='container'><a href='index.html'>← Home</a><div class='muted'>Saved Articles</div></div></div>
<main class='container'><h1>Saved Articles</h1><div id='savedCards'><p class='muted'>Loading your saved items…</p></div></main>
<footer class='footer'><p>Venmo: <strong>@MikeHnastchenko</strong></p></footer>
<script>
const savedIds=new Set(JSON.parse(localStorage.getItem('snd_saved')||'[]'));
fetch('index.html').then(r=>r.text()).then(t=>{
 const doc=new DOMParser().parseFromString(t,'text/html');
 const cards=[...doc.querySelectorAll('.card')].filter(c=>savedIds.has(c.dataset.id));
 document.querySelector('#savedCards').innerHTML=cards.length?cards.map(c=>c.outerHTML).join(''):'<p>No saved articles yet.</p>';
});
</script>"""
(SITE / "saved.html").write_text(saved_html, encoding="utf-8")

print(f"[site_builder] Built site with {len(items)} items and {len(Counter(it['category'] for it in items))} categories.")
