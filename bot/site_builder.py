# bot/site_builder.py
"""
Senior News Daily — Site Builder
Generates a complete static site with:
- Hero banner ("Plan boldly. Retire confidently.")
- Category filter chips
- Category-colored article cards
- Scam alerts & archive lists
- Venmo footer
- Auto-generated styles.css (ensures formatting never disappears)
"""

import json, datetime, pathlib, re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
SITE.mkdir(parents=True, exist_ok=True)

ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------
def esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def fmt_date(dt_iso: str | None) -> str:
    if not dt_iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(dt_iso.replace("Z","+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return dt_iso[:10]

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+","-", (s or "general").lower()).strip("-")

# -------------------------------------------------------------------
# Auto-generate stylesheet so formatting is never lost
# -------------------------------------------------------------------
CSS = r"""
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f9fafb;color:#111827;margin:0}
.container{width:min(1100px,90%);margin:0 auto;padding:1rem 0 3rem}h1,h2,h3{margin:0 0 .5rem}
.muted{color:#6b7280;font-size:.9em}
.hero{text-align:center;background:linear-gradient(135deg,#111827,#1e3a8a);color:#fff;padding:3rem 1rem 2rem}
.hero h1{font-size:2.3rem;margin-bottom:.3rem}.hero .subtitle{color:#cbd5e1;font-size:1.1rem}
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
.chip{border:1px solid #d1d5db;border-radius:9999px;padding:.4rem .9rem;cursor:pointer;font-weight:600;background:#f3f4f6;color:#111}
.chip b{font-weight:700}.chip.active{background:#111;color:#fff}
.alerts li,.archives li{margin:.4rem 0}
.footer{text-align:center;background:#111827;color:#cbd5e1;padding:2rem 1rem}
.footer a,.footer strong{color:#facc15}
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
.badge{display:inline-block;border:1px solid transparent;border-radius:4px;padding:0 .4em;font-size:.75rem;font-weight:600}
.badge.cat-medicare{background:#dbeafe;border-color:var(--cat-medicare)}
.badge.cat-social-security{background:#d1fae5;border-color:var(--cat-social-security)}
.badge.cat-finance-retirement{background:#cffafe;border-color:var(--cat-finance-retirement)}
.badge.cat-golf-leisure{background:#fef3c7;border-color:var(--cat-golf-leisure)}
.badge.cat-travel{background:#fee2e2;border-color:var(--cat-travel)}
.badge.cat-cooking-nutrition{background:#ffe4e6;border-color:var(--cat-cooking-nutrition)}
.badge.cat-caregiving-ltc{background:#ede9fe;border-color:var(--cat-caregiving-ltc)}
.badge.cat-aging-research{background:#cffafe;border-color:var(--cat-aging-research)}
.badge.cat-safety-scams{background:#fee2e2;border-color:var(--cat-safety-scams)}
.badge.cat-policy-legislation{background:#e5e7eb;border-color:var(--cat-policy-legislation)}
.badge.cat-general{background:#f3f4f6;border-color:var(--cat-general)}
"""
(SITE / "styles.css").write_text(CSS, encoding="utf-8")

# -------------------------------------------------------------------
# Load data
# -------------------------------------------------------------------
items_blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8")) if ITEMS_PATH.exists() else {"items": []}
digest_blob = json.loads(DIGEST_PATH.read_text(encoding="utf-8")) if DIGEST_PATH.exists() else {}

items = items_blob.get("items", [])
summary = digest_blob.get("summary", "")
alerts = digest_blob.get("alerts", [])
generated = digest_blob.get("generated", datetime.datetime.utcnow().isoformat())

# Ensure every item has a category
for it in items:
    it["category"] = it.get("category") or "General"

# -------------------------------------------------------------------
# Build components
# -------------------------------------------------------------------
def render_card(it):
    cat = it["category"]
    cat_slug = slugify(cat)
    return f"""
    <div class="card cat-{cat_slug}" data-id="{esc(it.get('id',''))}" data-cat="{esc(cat_slug)}">
      <a class="card-block" href="{esc(it.get('link',''))}" target="_blank" rel="noopener">
        <div class="card-title">{esc(it.get('title',''))}</div>
        <div class="card-meta">{esc(it.get('source',''))} · {fmt_date(it.get('published') or it.get('fetched'))}
          · <span class="badge cat-{cat_slug}">{esc(cat)}</span></div>
        <div class="card-summary">{esc(it.get('summary','')[:250])}</div>
      </a>
      <button class="save" data-id="{esc(it.get('id',''))}" aria-label="Save">&#9734;</button>
    </div>
    """

def render_cards(arr): return "\n".join(render_card(it) for it in arr)

def render_alerts(alerts):
    if not alerts: return "<p>No current scam alerts.</p>"
    out = ["<ul class='alerts'>"]
    for a in alerts:
        out.append(f"<li><a href='{esc(a.get('link',''))}' target='_blank'>{esc(a.get('title',''))}</a> <small>{fmt_date(a.get('published'))}</small></li>")
    out.append("</ul>")
    return "\n".join(out)

def render_archive_links(items):
    days = defaultdict(int)
    for it in items:
        d = (it.get("published") or it.get("fetched") or "")[:10]
        if d: days[d]+=1
    out = ["<ul class='archives'>"]
    for d,n in sorted(days.items(), reverse=True):
        out.append(f"<li>{d} <span class='muted'>({n} articles)</span></li>")
    out.append("</ul>")
    return "\n".join(out)

# Build category filter chips
cat_counts = Counter(it["category"] for it in items)
chips = ["<button class='chip active' data-cat='__all'>All <b>{}</b></button>".format(sum(cat_counts.values()))]
for cat, n in sorted(cat_counts.items(), key=lambda kv:(-kv[1], kv[0].lower())):
    chips.append(f"<button class='chip' data-cat='{esc(slugify(cat))}'>{esc(cat)} <b>{n}</b></button>")
chips_html = "\n".join(chips)

# -------------------------------------------------------------------
# Compose HTML
# -------------------------------------------------------------------
cards_html = render_cards(items)
alerts_html = render_alerts(alerts)
archives_html = render_archive_links(items)

html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Senior News Daily</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>

<header class="hero">
  <h1>Plan boldly. Retire confidently.</h1>
  <p class="subtitle">AI-powered daily insights for seniors — health, finance, leisure & scams.</p>
</header>

<main class="container">
  <section class="summary">
    <h2>Daily Summary</h2>
    <p>{esc(summary)}</p>
    <p class="muted">Last updated: {fmt_date(generated)}</p>
  </section>

  <section class="filters">
    <h2>Filter by Category</h2>
    <div class="filterbar">{chips_html}</div>
  </section>

  <section class="articles">
    <h2>Latest Articles</h2>
    <div id="cards">{cards_html}</div>
  </section>

  <section class="scam-alerts">
    <h2>⚠️ Scam Alerts</h2>
    {alerts_html}
  </section>

  <section class="archives">
    <h2>Archives</h2>
    {archives_html}
  </section>
</main>

<footer class="footer">
  <p>Venmo donations are welcome! <strong>@MikeHnastchenko</strong></p>
  <p class="muted">© {datetime.date.today().year} Senior News Daily — All Rights Reserved</p>
</footer>

<script>
const cards=[...document.querySelectorAll('#cards .card')];
const chips=[...document.querySelectorAll('.chip')];
function applyFilter(slug){cards.forEach(c=>c.style.display=(slug==='__all'||c.dataset.cat===slug)?'':'none');
chips.forEach(ch=>ch.classList.toggle('active',ch.dataset.cat===slug));}
chips.forEach(ch=>ch.addEventListener('click',()=>{const s=ch.dataset.cat;localStorage.setItem('snd_cat',s);applyFilter(s);}));
applyFilter(localStorage.getItem('snd_cat')||'__all');

// save-for-later
function getSaved(){try{return JSON.parse(localStorage.getItem('snd_saved')||'[]');}catch(e){return[]}}
function setSaved(v){localStorage.setItem('snd_saved',JSON.stringify([...new Set(v)]));}
function updateStars(){const cur=new Set(getSaved());document.querySelectorAll('.save').forEach(b=>{b.innerHTML=cur.has(b.dataset.id)?'★':'☆';});}
document.addEventListener('click',e=>{if(e.target.classList.contains('save')){const id=e.target.dataset.id;let cur=new Set(getSaved());
cur.has(id)?cur.delete(id):cur.add(id);setSaved([...cur]);updateStars();}});
updateStars();
</script>
</body>
</html>
"""

(SITE / "index.html").write_text(html, encoding="utf-8")
print(f"[site_builder] Built site/index.html with {len(items)} articles across {len(cat_counts)} categories.")
