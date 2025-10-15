# bot/site_builder.py
import pathlib, json, datetime, random
from urllib.parse import urlparse

ROOT = pathlib.Path(".")
DATA = ROOT / "data"
SITE = ROOT / "site"
ASSETS = SITE / "assets"

DATA.mkdir(exist_ok=True)
SITE.mkdir(exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

ITEMS_PATH = DATA / "items.json"     # your current feed dump
SOURCES_OUT = DATA / "sources.json"  # helpful for debugging / reuse

# ----------------- helpers -----------------
def esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return "unknown"

def load_json(p: pathlib.Path, default):
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default

def dtparse(s: str|None):
    if not s:
        return None
    # ISO first
    try:
        return datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception:
        pass
    # RFC-ish fallback
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except Exception:
            continue
    return None

def safe_dt(a: dict, now_utc: datetime.datetime):
    # prefer 'published', then 'updated', then 'fetched_at'
    for k in ("published", "updated", "fetched_at"):
        dt = dtparse(a.get(k))
        if dt:
            return dt
    return now_utc

def human_time(dt: datetime.datetime, now: datetime.datetime):
    # normalize tz to 'now'
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    local = dt.astimezone(now.tzinfo)
    today = now.date()
    d = local.date()
    tstr = local.strftime("%I:%M %p").lstrip("0")
    if d == today:
        return f"Today, {tstr}"
    if d == (today - datetime.timedelta(days=1)):
        return f"Yesterday, {tstr}"
    return local.strftime("%b %d, ") + tstr

def pick_color(seed: str):
    rnd = random.Random(seed)
    h = rnd.randint(0, 360)
    # (bg, text)
    return f"hsl({h} 70% 94%)", f"hsl({h} 70% 28%)"

# ----------------- load items -----------------
items = load_json(ITEMS_PATH, [])
now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

# "current articles" window — 7 days (adjust if you like)
window_start = now_utc - datetime.timedelta(days=7)
def in_window(a: dict) -> bool:
    return safe_dt(a, now_utc) >= window_start

current_items = [a for a in items if in_window(a)]

# ----------------- per-source stats -----------------
source_stats = {}
for a in current_items:
    src = a.get("source") or ""  # some bots set this
    link = a.get("link") or a.get("url") or ""
    dom = domain_from_url(link)
    key = (src or dom or "unknown").lower()

    ts = safe_dt(a, now_utc)
    if key not in source_stats:
        source_stats[key] = {
            "display": src or dom or "unknown",
            "domain": dom or "unknown",
            "count": 0,
            "last_dt": ts,
            "last_title": a.get("title",""),
            "last_link": link,
        }
    source_stats[key]["count"] += 1
    if ts > source_stats[key]["last_dt"]:
        source_stats[key]["last_dt"] = ts
        source_stats[key]["last_title"] = a.get("title","")
        source_stats[key]["last_link"]  = link

# write a small JSON for reference / other pages
SOURCES_OUT.write_text(
    json.dumps(
        {
            "generated_at": now_utc.isoformat(),
            "window_days": 7,
            "sources": [
                {
                    "key": k,
                    "display": v["display"],
                    "domain": v["domain"],
                    "count": v["count"],
                    "last_dt": v["last_dt"].isoformat(),
                    "last_title": v["last_title"],
                    "last_link": v["last_link"],
                }
                for k,v in sorted(source_stats.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
            ],
        },
        ensure_ascii=False, indent=2
    ),
    encoding="utf-8"
)

# ----------------- HTML fragments -----------------
def render_sources_pills(now: datetime.datetime):
    if not source_stats:
        return "<div class='muted small'>No sources in the last 7 days.</div>"
    parts = ["<div class='pill-tray' aria-label='Article sources in current window'>"]
    for _, v in sorted(source_stats.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        bg, fg = pick_color(v["domain"])
        last_human = human_time(v["last_dt"], now)
        title_attr = esc(f"{v['last_title']} ({v['last_link']})") if v.get("last_title") else esc(v.get("last_link",""))
        href = f"https://{esc(v['domain'])}" if v["domain"] not in ("", "unknown") else "#"
        parts.append(
            f"<a class='pill' href='{href}' target='_blank' rel='noopener'"
            f" style='--pill-bg:{bg};--pill-fg:{fg}'"
            f" title='Last article: {title_attr}'>"
            f"<span class='pill-site'>{esc(v['display'])}</span>"
            f"<span class='pill-dot' aria-hidden='true'>•</span>"
            f"<span class='pill-when'>{esc(last_human)}</span>"
            f"<span class='pill-count' title='Articles in window'>({int(v['count'])})</span>"
            f"</a>"
        )
    parts.append("</div>")
    return "\n".join(parts)

def render_article_card(a: dict):
    # very simple list so the page doesn't look empty
    link = a.get("link") or a.get("url") or "#"
    title = esc(a.get("title","(untitled)"))
    src = esc(a.get("source") or domain_from_url(link) or "unknown")
    when = human_time(safe_dt(a, now_utc), now_utc)
    return (
        "<article class='card'>"
        f"<a href='{esc(link)}' target='_blank' rel='noopener' class='card-title'>{title}</a>"
        f"<div class='card-meta'>{src} • {when}</div>"
        "</article>"
    )

# ----------------- page building -----------------
sources_html = render_sources_pills(now_utc)
articles_html = "\n".join(render_article_card(a) for a in current_items[:200])

# Simple, standalone page (safe to overwrite site/index.html)
INDEX_HTML = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Senior News Daily</title>
  <meta name="color-scheme" content="light dark" />
  <link rel="stylesheet" href="assets/pills.css" />
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 6px; font-size: 1.6rem; }}
    .sub {{ opacity:.75; margin-bottom: 14px; }}
    .grid {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}

    .card {{ border: 1px solid color-mix(in oklab, canvastext 14%, transparent);
             border-radius: 14px; padding: 10px 12px; }}
    .card-title {{ text-decoration:none; font-weight:600; display:block; margin-bottom:6px; }}
    .card-title:hover {{ text-decoration:underline; }}
    .card-meta {{ font-size:.9rem; opacity:.8; }}
    .section-title {{ margin: 18px 0 8px; font-size: 1.1rem; }}
    .divider {{ height:1px; background:color-mix(in oklab, canvastext 14%, canvas 86%); margin:12px 0; }}
  </style>
</head>
<body>
  <main>
    <h1>Senior News Daily</h1>
    <div class="sub">Latest sources (past 7 days) with last-seen time and article counts.</div>

    <!-- Sources tray -->
    {sources_html}

    <div class="divider"></div>
    <div class="section-title">Recent Articles</div>
    <section class="grid">
      {articles_html}
    </section>
  </main>
</body>
</html>
"""

(SITE / "index.html").write_text(INDEX_HTML, encoding="utf-8")
print(f"Built index with {len(current_items)} current articles from {len(source_stats)} sources.")
