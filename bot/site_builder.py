# bot/site_builder.py
"""
Builds the Senior News Daily static site from data/items.json and data/digest.json.
Generates category-colored cards, hero banner, scam alerts, archives, and footer.
"""

import json, datetime, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True, parents=True)

ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------
def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fmt_date(dt_iso: str | None) -> str:
    if not dt_iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return dt_iso[:10]

def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "general").lower()).strip("-")

# ----------------------------------------------------------
# Load data
# ----------------------------------------------------------
items_blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8")) if ITEMS_PATH.exists() else {"items": []}
digest_blob = json.loads(DIGEST_PATH.read_text(encoding="utf-8")) if DIGEST_PATH.exists() else {}

items = items_blob.get("items", [])
summary_text = digest_blob.get("summary", "")
alerts = digest_blob.get("alerts", [])
cat_counts = digest_blob.get("category_counts", {})
generated = digest_blob.get("generated", datetime.datetime.utcnow().isoformat())

# ----------------------------------------------------------
# Build cards
# ----------------------------------------------------------
def render_card(it):
    cat = it.get("category", "General")
    cat_slug = slugify(cat)
    return f"""
    <div class="card cat-{cat_slug}" data-id="{esc(it.get('id',''))}">
      <a class="card-block" href="{esc(it.get('link',''))}" target="_blank" rel="noopener">
        <div class="card-title">{esc(it.get('title',''))}</div>
        <div class="card-meta">
          {esc(it.get('source',''))} · {fmt_date(it.get('published') or it.get('fetched'))}
          · <span class="badge cat-{cat_slug}">{esc(cat)}</span>
        </div>
        <div class="card-summary">{esc(it.get('summary','')[:250])}</div>
      </a>
      <button class="save" data-id="{esc(it.get('id',''))}" title="Save for later" aria-label="Save">&#9734;</button>
    </div>
    """

def render_cards(items):
    return "\n".join(render_card(it) for it in items)

# ----------------------------------------------------------
# Build Scam Alerts + Archives
# ----------------------------------------------------------
def render_alerts(alerts):
    if not alerts:
        return "<p>No current scam alerts.</p>"
    out = ["<ul class='alerts'>"]
    for a in alerts:
        out.append(
            f"<li><a href='{esc(a.get('link',''))}' target='_blank'>{esc(a.get('title',''))}</a> "
            f"<small>{fmt_date(a.get('published'))}</small></li>"
        )
    out.append("</ul>")
    return "\n".join(out)

def render_archive_links(items):
    days = {}
    for it in items:
        d = (it.get("published") or it.get("fetched") or "")[:10]
        if d:
            days.setdefault(d, 0)
            days[d] += 1
    out = ["<ul class='archives'>"]
    for d, n in sorted(days.items(), reverse=True):
        out.append(f"<li>{d} <span class='muted'>({n} articles)</span></li>")
    out.append("</ul>")
    return "\n".join(out)

# ----------------------------------------------------------
# Build HTML
# ----------------------------------------------------------
cards_html = render_cards(items)
alerts_html = render_alerts(alerts)
archives_html = render_archive_links(items)

html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Senior News Daily</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>

<header class="hero">
  <h1>Plan boldly. Retire confidently.</h1>
  <p class="subtitle">AI-powered daily insights for seniors — health, finance, leisure & scams.</p>
</header>

<main class="container">
  <section class="summary">
    <h2>Daily Summary</h2>
    <p>{esc(summary_text)}</p>
    <p class="muted">Last updated: {fmt_date(generated)}</p>
  </section>

  <section class="scam-alerts">
    <h2>⚠️ Scam Alerts</h2>
    {alerts_html}
  </section>

  <section class="articles">
    <h2>Latest Articles</h2>
    {cards_html}
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
  // Basic save-for-later toggles
  const KEY = "snd_saved";
  function getSaved(){{ try{{return JSON.parse(localStorage.getItem(KEY)||"[]");}}catch(e){{return [];}} }}
  function setSaved(v){{ localStorage.setItem(KEY, JSON.stringify(v)); }}
  function updateSaved() {{
    const saved = new Set(getSaved());
    document.querySelectorAll('.card .save').forEach(btn => {{
      const id = btn.dataset.id;
      btn.innerHTML = saved.has(id) ? "★" : "☆";
    }});
  }}
  document.addEventListener('click', e => {{
    if(e.target.classList.contains('save')) {{
      e.preventDefault();
      const id = e.target.dataset.id;
      const saved = new Set(getSaved());
      saved.has(id) ? saved.delete(id) : saved.add(id);
      setSaved([...saved]);
      updateSaved();
    }}
  }});
  updateSaved();
</script>

</body>
</html>
"""

(SITE / "index.html").write_text(html, encoding="utf-8")
print(f"[site_builder] Built site/index.html with {len(items)} articles.")
