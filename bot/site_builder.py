# bot/site_builder.py
from pathlib import Path
import json
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE = ROOT / "site"
ARCH = SITE / "archive"
CSS = SITE / "styles.css"
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
        if dt == today:
            buckets["today"].append(it)
        if dt >= this_week_start:
            buckets["week"].append(it)
        if dt >= this_month_start:
            buckets["month"].append(it)
        if dt >= this_year_start:
            buckets["year"].append(it)
    return buckets

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
    if not alerts:
        return "<p class='muted'>No new scam alerts detected.</p>"
    lis = []
    for it in alerts[:10]:
        title = html_escape(it.get("title",""))
        src = html_escape(it.get("source",""))
        link = html_escape(it.get("link",""))
        date = fmt_date(it.get("published") or it.get("fetched"))
        lis.append(f"<li><a href='{link}' target='_blank' rel='noopener'>{title}</a> <span class='muted'>({src} · {date})</span></li>")
    return "<ul class='alerts'>" + "\n".join(lis) + "</ul>"

def render_category_counts(counts: dict) -> str:
    if not counts:
        return ""
    chips = []
    for cat, n in counts.items():
        chips.append(f"<span class='count-chip'>{html_escape(cat)}: <b>{n}</b></span>")
    return "<div class='counts'>" + " ".join(chips) + "</div>"

def build_index():
    items = ITEMS.get("items", [])
    buckets = group_by_period(items)
    summary_text = html_escape(DIGEST.get("summary",""))
    alerts_html = render_alerts(DIGEST.get("alerts", []))
    counts_html = render_category_counts(DIGEST.get("category_counts", {}))

    hero_title = "Plan boldly. Retire confidently."
    venmo_footer = "Venmo donations are welcome! @MikeHnastchenko"
    updated = now.strftime("%Y-%m-%d %H:%M UTC")
    fetched_date = html_escape((ITEMS.get("updated") or "")[:10])  # Articles retrieved date (YYYY-MM-DD)

    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Senior News Daily</title>
<link rel="stylesheet" href="./styles.css" />
</head>
<body>
<header class="site-header hero">
  <div class="hero-title">__HERO__</div>
  <p class="muted">Daily AI-generated summary on U.S. senior news.</p>
  <div class="retrieved">Articles retrieved: <b>__FETCHED__</b></div>
</header>

<nav class="chips">
  <button data-filter="today" class="chip active">Today</button>
  <button data-filter="week" class="chip">This Week</button>
  <button data-filter="month" class="chip">This Month</button>
  <button data-filter="year" class="chip">This Year</button>
  <button data-filter="saved" class="chip">Saved</button>
  <a class="chip" href="./archive/">Archive</a>
</nav>

<section class="summary">
  <h2>Daily Summary</h2>
  <pre>__SUMMARY__</pre>
  __COUNTS__
</section>

<section class="scams">
  <h2>Scam Alerts</h2>
  <p class="muted">Recent reports affecting older adults. Always verify requests for money, benefits, or personal info.</p>
  __ALERTS__
</section>

<section id="list" class="grid" data-active="today">
  <div data-period="today" class="panel show">
    __TODAY__
  </div>
  <div data-period="week" class="panel">
    __WEEK__
  </div>
  <div data-period="month" class="panel">
    __MONTH__
  </div>
  <div data-period="year" class="panel">
    __YEAR__
  </div>
  <div data-period="saved" class="panel">
    <div class="muted">No saved articles yet.</div>
  </div>
</section>

<footer class="site-footer">
  <div>Updated __UPDATED__</div>
  <div class="muted">__VENMO__</div>
</footer>

<script>
// Filter chips
const chips = document.querySelectorAll('.chip[data-filter]');
const panels = document.querySelectorAll('.panel');
chips.forEach(ch => ch.addEventListener('click', () => {
  chips.forEach(c => c.classList.remove('active'));
  ch.classList.add('active');
  const f = ch.getAttribute('data-filter');
  panels.forEach(p => p.classList.remove('show'));
  const sel = ".panel[data-period='" + f + "']";
  document.querySelector(sel).classList.add('show');
}));

// Saved articles (localStorage)
const SAVED_KEY = "snd_saved_ids";
function getSaved() {
  try { return JSON.parse(localStorage.getItem(SAVED_KEY) || "[]"); } catch(e) { return []; }
}
function setSaved(arr) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(Array.from(new Set(arr))));
}
function toggleSave(id) {
  const cur = getSaved();
  if (cur.includes(id)) {
    setSaved(cur.filter(x => x !== id));
  } else {
    cur.push(id);
    setSaved(cur);
  }
  updateSavedUI();
}
function updateSavedUI() {
  const cur = new Set(getSaved());
  document.querySelectorAll('.card .save').forEach(btn => {
    const id = btn.getAttribute('data-id');
    btn.innerHTML = cur.has(id) ? "&#9733;" : "&#9734;"; // filled vs hollow star
  });

  // Build saved panel content
  const savedPanel = document.querySelector('.panel[data-period="saved"]');
  const cards = Array.from(document.querySelectorAll('.card'));
  const savedCards = cards.filter(c => cur.has(c.getAttribute('data-id')));
  if (savedCards.length) {
    savedPanel.innerHTML = savedCards.map(c => c.outerHTML).join("");
  } else {
    savedPanel.innerHTML = '<div class="muted">No saved articles yet.</div>';
  }
}
document.addEventListener('click', (e) => {
  const t = e.target;
  if (t && t.classList.contains('save')) {
    e.preventDefault();
    const id = t.getAttribute('data-id');
    toggleSave(id);
  }
});
updateSavedUI();
</script>
</body>
</html>
"""
    html = (template
            .replace("__HERO__", hero_title)
            .replace("__SUMMARY__", summary_text)
            .replace("__ALERTS__", alerts_html)
            .replace("__COUNTS__", counts_html)
            .replace("__TODAY__", render_cards(buckets["today"]))
            .replace("__WEEK__", render_cards(buckets["week"]))
            .replace("__MONTH__", render_cards(buckets["month"]))
            .replace("__YEAR__", render_cards(buckets["year"]))
            .replace("__UPDATED__", updated)
            .replace("__VENMO__", venmo_footer)
            .replace("__FETCHED__", fetched_date or "—")
            )
    (SITE / "index.html").write_text(html, encoding="utf-8")

def build_archive():
    items = ITEMS.get("items", [])
    by_day = {}
    for it in items:
        d = fmt_date(it.get("published") or it.get("fetched"))
        by_day.setdefault(d, []).append(it)

    # Archive index
    links = []
    for day in sorted(by_day.keys(), reverse=True):
        links.append(f"<li><a href='{day}.html'>{day}</a> <span class='muted'>({len(by_day[day])})</span></li>")
    (ARCH / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><link rel=stylesheet href='../styles.css'>"
        + "<h1>Archive by Day</h1><ul>" + "\n".join(links) + "</ul>", encoding="utf-8")

    # Daily pages
    for day, its in by_day.items():
        (ARCH / f"{day}.html").write_text(
            "<!doctype html><meta charset='utf-8'><link rel=stylesheet href='../styles.css'>"
            + f"<h1>{day}</h1>" + render_cards(its), encoding="utf-8")

def main():
    build_index()
    build_archive()
    print(f"[site] Built pages in {SITE}")

if __name__ == "__main__":
    main()
