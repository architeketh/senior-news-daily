# bot/site_builder.py
"""
Builds the Senior News Daily static site from data/items.json and data/digest.json.
Adds a category filter bar (chips with counts), category-colored cards, scam alerts,
archives, hero banner, and save-for-later stars.
"""

import json, datetime, pathlib, re
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True, parents=True)

ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

# ----------------------------- Helpers ---------------------------------
def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fmt_date(dt_iso: str | None) -> str:
    if not dt_iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return (dt_iso or "")[:10]

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "general").lower()).strip("-") or "general"

# ------------------------------ Load -----------------------------------
items_blob = {"items": []}
if ITEMS_PATH.exists():
    items_blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))

digest_blob = {}
if DIGEST_PATH.exists():
    digest_blob = json.loads(DIGEST_PATH.read_text(encoding="utf-8"))

items = items_blob.get("items", [])
summary_text = digest_blob.get("summary", "")
alerts = digest_blob.get("alerts", [])
generated = digest_blob.get("generated", datetime.datetime.utcnow().isoformat())

# Normalize category field (fallback to General)
for it in items:
    if not it.get("category"):
        it["category"] = "General"

# ------------------------ Build chips + cards ---------------------------
# Category counts (for chips)
cat_counts = Counter([it.get("category", "General") for it in items])
# Sort by count desc, then alpha
ordered_cats = sorted(cat_counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
# Build chips HTML (All + each category)
def render_chips():
    chips = ["<button class='chip active' data-cat='__all'>All <b>{}</b></button>".format(sum(cat_counts.values()))]
    for cat, n in ordered_cats:
        chips.append(
            "<button class='chip' data-cat='{}'>{} <b>{}</b></button>".format(
                esc(slugify(cat)), esc(cat), n
            )
        )
    return "\n".join(chips)

def render_card(it):
    cat = it.get("category", "General")
    cat_slug = slugify(cat)
    return (
        "<div class='card cat-{}' data-id='{}' data-cat='{}'>"
        "<a class='card-block' href='{}' target='_blank' rel='noopener'>"
        "<div class='card-title'>{}</div>"
        "<div class='card-meta'>{} · {} · <span class='badge cat-{}'>{}</span></div>"
        "<div class='card-summary'>{}</div>"
        "</a>"
        "<button class='save' data-id='{}' title='Save for later' aria-label='Save'>&#9734;</button>"
        "</div>"
    ).format(
        esc(cat_slug),
        esc(it.get("id","")),
        esc(cat_slug),
        esc(it.get("link","")),
        esc(it.get("title","")),
        esc(it.get("source","")),
        esc(fmt_date(it.get("published") or it.get("fetched"))),
        esc(cat_slug),
        esc(cat),
        esc((it.get("summary","") or "")[:250]),
        esc(it.get("id","")),
    )

def render_cards(arr):
    return "\n".join(render_card(it) for it in arr)

def render_alerts(arr):
    if not arr:
        return "<p>No current scam alerts.</p>"
    out = ["<ul class='alerts'>"]
    for a in arr:
        out.append(
            "<li><a href='{link}' target='_blank'>{title}</a> "
            "<small>{date}</small></li>".format(
                link=esc(a.get("link","")),
                title=esc(a.get("title","")),
                date=esc(fmt_date(a.get("published") or a.get("fetched")))
            )
        )
    out.append("</ul>")
    return "\n".join(out)

def render_archive_links(arr):
    days = defaultdict(int)
    for it in arr:
        d = (it.get("published") or it.get("fetched") or "")[:10]
        if d:
            days[d] += 1
    out = ["<ul class='archives'>"]
    for d, n in sorted(days.items(), reverse=True):
        out.append("<li>{} <span class='muted'>({} articles)</span></li>".format(esc(d), n))
    out.append("</ul>")
    return "\n".join(out)

chips_html = render_chips()
cards_html = render_cards(items)
alerts_html = render_alerts(alerts)
archives_html = render_archive_links(items)

# ------------------------------- HTML -----------------------------------
# Use marker replacement (no f-strings) to avoid brace issues with JS.
template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Senior News Daily</title>
  <link rel="stylesheet" href="styles.css" />
  <style>
    /* Optional tiny helpers if your CSS doesn't already define .chips */
    .filterbar { display:flex; flex-wrap:wrap; gap:8px; padding:12px 0; }
    .chip { display:inline-block; padding:8px 12px; border-radius:999px; background:#f3f4f6;
            cursor:pointer; border:1px solid #e5e7eb; text-decoration:none; color:inherit; font-weight:700; }
    .chip.active { background:#111; color:#fff; }
    .card-summary { margin-top:8px; color:#374151; font-size:14px; }
  </style>
</head>
<body>

<header class="hero">
  <h1>Plan boldly. Retire confidently.</h1>
  <p class="subtitle">AI-powered daily insights for seniors — health, finance, leisure & scams.</p>
</header>

<main class="container">

  <section class="summary">
    <h2>Daily Summary</h2>
    <p>__SUMMARY__</p>
    <p class="muted">Last updated: __UPDATED__</p>
  </section>

  <section class="filters">
    <h2>Filter by Category</h2>
    <div class="filterbar">
      __CHIPS__
    </div>
  </section>

  <section class="articles">
    <h2>Latest Articles</h2>
    <div id="cards">
      __CARDS__
    </div>
  </section>

  <section class="scam-alerts">
    <h2>⚠️ Scam Alerts</h2>
    __ALERTS__
  </section>

  <section class="archives">
    <h2>Archives</h2>
    __ARCHIVES__
  </section>
</main>

<footer class="footer">
  <p>Venmo donations are welcome! <strong>@MikeHnastchenko</strong></p>
  <p class="muted">© __YEAR__ Senior News Daily — All Rights Reserved</p>
</footer>

<script>
  // Persisted category filter
  const FILTER_KEY = "snd_active_cat"; // stores slug or "__all"
  function getActiveCat(){ try { return localStorage.getItem(FILTER_KEY) || "__all"; } catch(e) { return "__all"; } }
  function setActiveCat(slug){ try { localStorage.setItem(FILTER_KEY, slug); } catch(e) {} }

  // Initial render
  const cards = Array.from(document.querySelectorAll('#cards .card'));
  const chips = Array.from(document.querySelectorAll('.chip'));
  function applyFilter(slug) {
    cards.forEach(c => {
      const ok = (slug === "__all") || (c.getAttribute('data-cat') === slug);
      c.style.display = ok ? "" : "none";
    });
    chips.forEach(ch => ch.classList.toggle('active', ch.getAttribute('data-cat') === slug));
  }

  // Hook up chip clicks
  chips.forEach(ch => {
    ch.addEventListener('click', () => {
      const slug = ch.getAttribute('data-cat');
      setActiveCat(slug);
      applyFilter(slug);
    });
  });

  // Save-for-later (★/☆) de-duped by id
  const SAVE_KEY = "snd_saved_ids";
  function getSaved(){ try { return JSON.parse(localStorage.getItem(SAVE_KEY) || "[]"); } catch(e) { return []; } }
  function setSaved(a){ localStorage.setItem(SAVE_KEY, JSON.stringify(Array.from(new Set(a)))); }
  function updateStars(){
    const cur = new Set(getSaved());
    document.querySelectorAll('.card .save').forEach(btn => {
      const id = btn.getAttribute('data-id');
      btn.innerHTML = cur.has(id) ? "★" : "☆";
    });
  }
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.classList.contains('save')) {
      e.preventDefault();
      const id = t.getAttribute('data-id');
      const cur = new Set(getSaved());
      cur.has(id) ? cur.delete(id) : cur.add(id);
      setSaved(Array.from(cur));
      updateStars();
    }
  });

  // First load: honor last selection
  const initial = getActiveCat();
  // Mark the right chip active (in case "__all" wasn't the first element)
  chips.forEach(ch => ch.classList.toggle('active', ch.getAttribute('data-cat') === initial));
  applyFilter(initial);
  updateStars();
</script>

</body>
</html>
"""

html = (template
        .replace("__SUMMARY__", esc(summary_text))
        .replace("__UPDATED__", esc(fmt_date(generated)))
        .replace("__CHIPS__", chips_html)
        .replace("__CARDS__", cards_html)
        .replace("__ALERTS__", alerts_html)
        .replace("__ARCHIVES__", archives_html)
        .replace("__YEAR__", str(datetime.date.today().year))
        )

(SITE / "index.html").write_text(html, encoding="utf-8")
print(f"[site_builder] Built site/index.html with {len(items)} articles and {len(ordered_cats)} categories.")
