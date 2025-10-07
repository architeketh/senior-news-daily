# bot/site_builder.py
"""
Senior News Daily — Clean Site Builder
Outputs:
- site/styles.css  (auto-generated each build)
- site/index.html
- site/archive/YYYY-MM-DD.html (+ site/archive/index.html)
- site/saved.html

Features:
- Hero banner ("Plan boldly. Retire confidently.")
- Category chips (color matches card/badge) + "Saved" chip
- Colored cards & badges by category
- Scam Alerts section
- Per-day archive pages with correct links on both home & archive index
- "Next update in Xh Ym · <UTC time>" badge
"""

import json, datetime, pathlib, re
from collections import Counter, defaultdict
from datetime import datetime as dt, timezone, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
ARCH = SITE / "archive"
SITE.mkdir(parents=True, exist_ok=True)
ARCH.mkdir(parents=True, exist_ok=True)

ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

# ----------------------- Helpers -----------------------
def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fmt_date(dt_iso: str | None) -> str:
    if not dt_iso:
        return ""
    try:
        x = datetime.datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        return x.strftime("%b %d, %Y")
    except Exception:
        return (dt_iso or "")[:10]

def day_key(it: dict) -> str:
    return (it.get("published") or it.get("fetched") or "")[:10]

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "general").lower()).strip("-") or "general"

def next_update_badge(now: dt | None = None) -> str:
    """Workflow: every 12 hours (00:00 & 12:00 UTC). Show time until next run."""
    now = now or dt.now(timezone.utc)
    base = now.replace(minute=0, second=0, microsecond=0)
    slots = [
        base.replace(hour=0),
        base.replace(hour=12),
        (base + timedelta(days=1)).replace(hour=0),
    ]
    nxt = min([s for s in slots if s > now], key=lambda d: d)
    delta = nxt - now
    hrs = int(delta.total_seconds() // 3600)
    mins = int((delta.total_seconds() % 3600) // 60)
    label = f"{hrs}h {mins}m" if hrs else f"{mins}m"
    when = nxt.strftime("%b %d, %H:%M UTC")
    return f"<span class='badge' style='margin-left:.5rem;'>Next update in {label} · {when}</span>"

# ----------------------- CSS (auto-emitted) ---------------------------
CSS = r"""
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f9fafb;color:#111827;margin:0}
.container{width:min(1100px,90%);margin:0 auto;padding:1rem 0 3rem}h1,h2,h3{margin:0 0 .5rem}
a{color:inherit}
.muted{color:#6b7280;font-size:.9em}
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
/* Category palette (cards, badges, and chips share colors) */
:root{
--cat-medicare:#2563eb;--cat-social-security:#059669;--cat-finance-retirement:#0ea5e9;
--cat-golf-leisure:#f59e0b;--cat-travel:#ef4444;--cat-cooking-nutrition:#e11d48;
--cat-caregiving-ltc:#7c3aed;--cat-aging-research:#0891b2;--cat-safety-scams:#dc2626;
--cat-policy-legislation:#4b5563;--cat-general:#6b7280}
.card.cat-medicare::before{background:var(--cat-medicare)}
.card.cat-social-security::before{background:var(--cat-social-security)}
.card.cat-finance-retirement::before{background:var(--cat-finance-retirement)}
.card.cat-golf-leisure::before{background:var(--cat-golf-leisure)}
.card.cat-travel::before{background:var(--cat-travel)}
.card.cat-cooking-nutrition::before{background:var(--cat-cooking-nutrition)}
.card.cat-caregiving-ltc::before{background:var(--cat-caregiving-ltc)}
.card.cat-aging-research::before{background:var(--cat-aging-research)}
.card.cat-safety-scams::before{background:var(--cat-safety-scams)}
.card.cat-policy-legislation::before{background:var(--cat-policy-legislation)}
.card.cat-general::before{background:var(--cat-general)}
.badge{display:inline-block;border:1px solid transparent;border-radius:4px;padding:0 .4em;font-size:.75rem;font-weight:700}
.badge[class*="cat-"]{background:#f3f4f6;border-color:#d1d5db}
/* Color chips to match categories */
.chip[data-cat="medicare"]{background:#dbeafe;border-color:var(--cat-medicare)}
.chip[data-cat="social-security"]{background:#d1fae5;border-color:var(--cat-social-security)}
.chip[data-cat="finance-retirement"]{background:#cffafe;border-color:var(--cat-finance-retirement)}
.chip[data-cat="golf-leisure"]{background:#fef3c7;border-color:var(--cat-golf-leisure)}
.chip[data-cat="travel"]{background:#fee2e2;border-color:var(--cat-travel)}
.chip[data-cat="cooking-nutrition"]{background:#ffe4e6;border-color:var(--cat-cooking-nutrition)}
.chip[data-cat="caregiving-ltc"]{background:#ede9fe;border-color:var(--cat-caregiving-ltc)}
.chip[data-cat="aging-research"]{background:#cffafe;border-color:var(--cat-aging-research)}
.chip[data-cat="safety-scams"]{background:#fee2e2;border-color:var(--cat-safety-scams)}
.chip[data-cat="policy-legislation"]{background:#e5e7eb;border-color:var(--cat-policy-legislation)}
.chip[data-cat="general"]{background:#f3f4f6;border-color:var(--cat-general)}
.chip[data-cat="__saved"]{background:#e0f2fe;border-color:#0284c7}
"""
(SITE / "styles.css").write_text(CSS, encoding="utf-8")

# ----------------------- Load Data ----------------------
items_blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8")) if ITEMS_PATH.exists() else {"items": []}
digest_blob = json.loads(DIGEST_PATH.read_text(encoding="utf-8")) if DIGEST_PATH.exists() else {}
items = items_blob.get("items", [])
summary = digest_blob.get("summary", "")
alerts = digest_blob.get("alerts", [])
generated = digest_blob.get("generated", datetime.datetime.utcnow().isoformat())

for it in items:
    it["category"] = it.get("category") or "General"

# -------------------- Components ------------------------
def render_card(it):
    cat = it["category"]
    slug = slugify(cat)
    return (
        f"<div class='card cat-{slug}' data-id='{esc(it.get('id',''))}' data-cat='{slug}'>"
        f"<a class='card-block' href='{esc(it.get('link',''))}' target='_blank' rel='noopener'>"
        f"<div class='card-title'>{esc(it.get('title',''))}</div>"
        f"<div class='card-meta'>{esc(it.get('source',''))} · {fmt_date(it.get('published') or it.get('fetched'))} · "
        f"<span class='badge cat-{slug}'>{esc(cat)}</span></div>"
        f"<div class='card-summary'>{esc(it.get('summary','')[:250])}</div></a>"
        f"<button class='save' data-id='{esc(it.get('id',''))}' title='Save' aria-label='Save'>&#9734;</button></div>"
    )

def render_cards(arr): 
    return "\n".join(render_card(it) for it in arr)

def render_alerts(alerts):
    if not alerts: return "<p>No current scam alerts.</p>"
    out = ["<ul class='alerts'>"]
    for a in alerts:
        out.append(
            f"<li><a href='{esc(a.get('link',''))}' target='_blank'>{esc(a.get('title',''))}</a> "
            f"<small>{fmt_date(a.get('published') or a.get('fetched'))}</small></li>"
        )
    out.append("</ul>")
    return "\n".join(out)

def build_archive_pages(items):
    """
    Write site/archive/YYYY-MM-DD.html and return two lists:
    - home_list: links prefixed with 'archive/' for homepage
    - index_list: links with no prefix for /archive/index.html
    """
    by_day = defaultdict(list)
    for it in items:
        d = day_key(it)
        if d:
            by_day[d].append(it)

    # write day pages
    for d, its in by_day.items():
        body = f"""<!doctype html><meta charset='utf-8'>
<link rel='stylesheet' href='../styles.css'>
<div class='topnav'><div class='container'>
  <a href='../index.html'>← Home</a>
  <a href='./'>Archive</a>
</div></div>
<main class='container'>
  <h1>Archive — {esc(d)}</h1>
  <div id='cards'>{render_cards(its)}</div>
</main>
<footer class='footer'><p>Venmo: <strong>@MikeHnastchenko</strong></p></footer>"""
        (ARCH / f"{d}.html").write_text(body, encoding="utf-8")

    def list_html(prefix: str) -> str:
        out = ["<ul class='archives'>"]
        for d in sorted(by_day.keys(), reverse=True):
            n = len(by_day[d])
            out.append(
                f"<li><a href='{prefix}{esc(d)}.html'>{esc(d)}</a> "
                f"<span class='muted'>({n} articles)</span></li>"
            )
        out.append("</ul>")
        return "\n".join(out)

    home_list = list_html("archive/")  # used on /
    index_list = list_html("")         # used on /archive/
    return home_list, index_list

# Chips (+ Saved)
cat_counts = Counter(it["category"] for it in items)
chips = [
    "<button class='chip active' data-cat='__all'>All <b>{}</b></button>".format(sum(cat_counts.values())),
    "<button class='chip' data-cat='__saved'>Saved <b>★</b></button>",
]
for cat, n in sorted(cat_counts.items(), key=lambda kv:(-kv[1], kv[0].lower())):
    chips.append(f"<button class='chip' data-cat='{slugify(cat)}'>{esc(cat)} <b>{n}</b></button>")
chips_html = "\n".join(chips)

# -------------------- Templates -------------------------
template = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Senior News Daily</title><link rel="stylesheet" href="styles.css"></head>
<body>
<header class="hero"><h1>Plan boldly. Retire confidently.</h1>
<p class="subtitle">AI-powered daily insights for seniors — health, finance, leisure & scams.</p></header>
<div class="topnav"><div class="container">
<a href="index.html">Home</a><a href="saved.html">Saved</a><a href="archive/">Archive</a></div></div>
<main class="container">
<section class="summary"><h2>Daily Summary</h2><p>__SUMMARY__</p>
<p class="muted">Last updated: __UPDATED__ __BADGE__</p></section>
<section class="filters"><h2>Filter by Category</h2><div class="filterbar">__CHIPS__</div></section>
<section class="articles"><h2>Latest Articles</h2><div id="cards">__CARDS__</div></section>
<section class="scam-alerts"><h2>⚠️ Scam Alerts</h2>__ALERTS__</section>
<section class="archives"><h2>Archives</h2>__ARCHIVES__</section></main>
<footer class="footer"><p>Venmo: <strong>@MikeHnastchenko</strong></p>
<p class="muted">© __YEAR__ Senior News Daily — All Rights Reserved</p></footer>
<script>
const cards=[...document.querySelectorAll('#cards .card')];
const chips=[...document.querySelectorAll('.chip')];
function getSaved(){try{return JSON.parse(localStorage.getItem('snd_saved')||'[]');}catch(e){return[]}}
function setSaved(v){localStorage.setItem('snd_saved',JSON.stringify([...new Set(v)]));}
function updateStars(){const cur=new Set(getSaved());document.querySelectorAll('.save').forEach(b=>{b.innerHTML=cur.has(b.dataset.id)?'★':'☆';});}
function applyFilter(slug){
 if(slug==='__saved'){const cur=new Set(getSaved());cards.forEach(c=>c.style.display=cur.has(c.dataset.id)?'':'none');}
 else{cards.forEach(c=>c.style.display=(slug==='__all'||c.dataset.cat===slug)?'':'none');}
 chips.forEach(ch=>ch.classList.toggle('active',ch.dataset.cat===slug));
 localStorage.setItem('snd_cat',slug);}
chips.forEach(ch=>ch.addEventListener('click',()=>applyFilter(ch.dataset.cat)));
document.addEventListener('click',e=>{if(e.target.classList.contains('save')){const id=e.target.dataset.id;
 const cur=new Set(getSaved());cur.has(id)?cur.delete(id):cur.add(id);setSaved([...cur]);updateStars();}});
updateStars();applyFilter(localStorage.getItem('snd_cat')||'__all');
</script></body></html>"""

# -------------------- Build -----------------------------
archives_home_html, archives_index_html = build_archive_pages(items)
badge_html = next_update_badge()

home_html = (template
    .replace("__SUMMARY__", esc(summary))
    .replace("__UPDATED__", fmt_date(generated))
    .replace("__BADGE__", badge_html)
    .replace("__CHIPS__", chips_html)
    .replace("__CARDS__", render_cards(items))
    .replace("__ALERTS__", render_alerts(alerts))
    .replace("__ARCHIVES__", archives_home_html)
    .replace("__YEAR__", str(datetime.date.today().year))
)
(SITE / "index.html").write_text(home_html, encoding="utf-8")

# Archive index page
arch_index = """<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="../styles.css">
<div class="topnav"><div class="container">
  <a href="../index.html">← Home</a>
  <div class="muted">Archive</div>
</div></div>
<main class="container">
  <h1>Archive</h1>
  __ARCHIVES_INDEX__
</main>
<footer class="footer"><p>Venmo: <strong>@MikeHnastchenko</strong></p></footer>
""".replace("__ARCHIVES_INDEX__", archives_index_html)
(ARCH / "index.html").write_text(arch_index, encoding="utf-8")

# Saved Articles page (renders user's local saved set by reusing cards from index)
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
 const area=document.querySelector('#savedCards');
 area.innerHTML=cards.length?cards.map(c=>c.outerHTML).join(''):'<p>No saved articles yet.</p>';
});
</script>"""
(SITE / "saved.html").write_text(saved_html, encoding="utf-8")

print(f"[site_builder] Built site with {len(items)} articles, {len(cat_counts:=Counter(it['category'] for it in items))} categories, archives + saved page.")
