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
DIGEST = json.loads((DATA / "digest.json").read_text(encoding="utf-8")) if (DATA/"digest.json").exists() else {"summary":""}

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
        parts.append(
            "<a class='card' href='"+link+"' target='_blank' rel='noopener'>"
            + "<div class='card-title'>"+title+"</div>"
            + "<div class='card-meta'>"+src+" · "+date+"</div>"
            + "</a>"
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

def build_index():
    items = ITEMS.get("items", [])
    buckets = group_by_period(items)
    summary = html_escape(DIGEST.get("summary",""))
    alerts = DIGEST.get("alerts", [])

    hero_title = "Plan boldly. Retire confidently."  # requested hero
    venmo_footer = "Venmo donations are welcome! @MikeHnastchenko"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Senior News Daily</title>
<link rel="stylesheet" href="./styles.css" />
</head>
<body>
<header class="site-header">
  <h1>Senior News Daily</h1>
  <p class="tagline">{hero_title}</p>
  <p class="muted">Daily AI-generated summary on U.S. senior news.</p>
</header>

<nav class="chips">
  <button data-filter="today" class="chip active">Today</button>
  <button data-filter="week" class="chip">This Week</button>
  <button data-filter="month" class="chip">This Month</button>
  <button data-filter="year" class="chip">This Year</button>
  <a class="chip" href="./archive/">Archive</a>
</nav>

<section class="summary">
  <h2>Daily Summary</h2>
  <pre>{summary}</pre>
</section>

<section class="scams">
  <h2>Scam Alerts</h2>
  <p class="muted">Recent reports affecting older adults. Always verify requests for money, benefits, or personal info.</p>
  {render_alerts(alerts)}
</section>

<section id="list" class="grid" data-active="today">
  <div data-period="today" class="panel show">
    {render_cards(buckets['today'])}
  </div>
  <div data-period="week" class="panel">
    {render_cards(buckets['week'])}
  </div>
  <div data-period="month" class="panel">
    {render_cards(buckets['month'])}
  </div>
  <div data-period="year" class="panel">
    {render_cards(buckets['year'])}
  </div>
</section>

<footer class="site-footer">
  <div>Updated {now.strftime('%Y-%m-%d %H:%M UTC')}</div>
  <div class="muted">{venmo_footer}</div>
</footer>

<script>
const chips = document.querySelectorAll('.chip[data-filter]');
const panels = document.querySelectorAll('.panel');
chips.forEach(ch => ch.addEventListener('click', () => {
  chips.forEach(c => c.classList.remove('active'));
  ch.classList.add('active');
  const f = ch.getAttribute('data-filter');
  panels.forEach(p => p.classList.remove('show'));
  document.querySelector(`.panel[data-period="${'{'}f{'}'}"]`).classList.add('show');
}));
</script>
</body>
</html>
"""
    (SITE / "index.html").write_text(html, encoding="utf-8")

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
        + "<h1>Archive</h1><ul>" + "\n".join(links) + "</ul>", encoding="utf-8")

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
