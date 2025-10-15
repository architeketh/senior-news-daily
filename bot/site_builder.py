# bot/site_builder.py
import pathlib, json, datetime, re, random
from urllib.parse import urlparse

ROOT = pathlib.Path(".")
DATA = ROOT / "data"
SITE = ROOT / "site"
ASSETS = ROOT / "assets"

DATA.mkdir(exist_ok=True)
SITE.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

# ---------- Helpers ----------
def esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        # strip common "www."
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
    # accept several formats; prefer ISO
    try:
        return datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception:
        pass
    # fallback: RFC-ish
    try:
        return datetime.datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %z")
    except Exception:
        return None

def human_time(dt: datetime.datetime, now: datetime.datetime):
    # normalize tz (assume UTC if naive)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    local = dt.astimezone(now.tzinfo)
    today = now.date()
    d = local.date()

    tstr = local.strftime("%-I:%M %p") if hasattr(local, "strftime") else ""
    if d == today:
        return f"Today, {tstr}"
    elif d == (today - datetime.timedelta(days=1)):
        return f"Yesterday, {tstr}"
    else:
        return local.strftime("%b %-d, %-I:%M %p")

def pick_color(seed: str):
    # deterministic pastel-ish hue assignment
    rnd = random.Random(seed)
    h = rnd.randint(0, 360)
    return f"hsl({h} 70% 94%)", f"hsl({h} 70% 28%)"  # (bg, text)

# ---------- Load articles ----------
articles_path = DATA / "articles.json"
articles = load_json(articles_path, [])

# Expect each article to have fields like:
# { "title": "...", "link": "...", "published": "...(ISO/RFC)...", "source": "...(optional)...", "fetched_at": "...ISO..." }
# We'll gracefully handle missing fields.

# ---------- Compute "current" set ----------
# Definition: "current" = items from the last 7 days (adjust to your preference).
now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
window_start = now - datetime.timedelta(days=7)

def article_dt(a):
    # prefer published, else fetched_at
    return dtparse(a.get("published")) or dtparse(a.get("fetched_at")) or now

current_articles = [a for a in articles if article_dt(a) >= window_start]

# ---------- Per-source stats ----------
source_stats = {}
for a in current_articles:
    src = a.get("source") or domain_from_url(a.get("link",""))
    dom = domain_from_url(a.get("link",""))
    key = src or dom or "unknown"

    ts = article_dt(a)
    if key not in source_stats:
        source_stats[key] = {
            "domain": dom or "unknown",
            "display": src or dom or "unknown",
            "count": 0,
            "last_dt": ts,
            "last_title": a.get("title",""),
            "last_link": a.get("link",""),
        }
    source_stats[key]["count"] += 1
    if ts > source_stats[key]["last_dt"]:
        source_stats[key]["last_dt"] = ts
        source_stats[key]["last_title"] = a.get("title","")
        source_stats[key]["last_link"]  = a.get("link","")

# Persist for debugging/optional API-like use
with (DATA / "sources.json").open("w", encoding="utf-8") as f:
    json.dump(
        {
            "generated_at": now.isoformat(),
            "window_days": 7,
            "sources": [
                {
                    "key": k,
                    "domain": v["domain"],
                    "display": v["display"],
                    "count": v["count"],
                    "last_dt": v["last_dt"].isoformat(),
                    "last_title": v["last_title"],
                    "last_link": v["last_link"],
                }
                for k,v in sorted(source_stats.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
            ],
        },
        f,
        ensure_ascii=False,
        indent=2
    )

# ---------- Build Sources Pill Tray HTML ----------
def render_sources_pills():
    if not source_stats:
        return "<div class='muted small'>No sources in the last 7 days.</div>"

    parts = ["<div class='pill-tray' aria-label='Article sources in current window'>"]
    for key, v in sorted(source_stats.items(), key=lambda kv: (-kv[1]["count"], kv[0])):
        bg, fg = pick_color(v["domain"])
        last_human = human_time(v["last_dt"], now)
        title_attr = esc(f"{v['last_title']} ({v['last_link']})") if v.get("last_title") else esc(v.get("last_link",""))
        pill = (
            f"<a class='pill' href='https://{esc(v['domain'])}' target='_blank' rel='noopener'"
            f" style='--pill-bg:{bg};--pill-fg:{fg}'"
            f" title='Last article: {title_attr}'>"
            f"<span class='pill-site'>{esc(v['display'])}</span>"
            f"<span class='pill-dot' aria-hidden='true'>•</span>"
            f"<span class='pill-when'>{esc(last_human)}</span>"
            f"<span class='pill-count' title='Articles in window'>({int(v['count'])})</span>"
            f"</a>"
        )
        parts.append(pill)
    parts.append("</div>")
    return "\n".join(parts)

sources_html = render_sources_pills()

# ---------- Very simple page scaffold (injects sources tray) ----------
# If you already have a full index.html, you can:
#  1) keep this builder and only replace the <!-- SOURCES_PILLS --> marker in your template, or
#  2) use this minimal page.
index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Senior News Daily — Sources</title>
  <link rel="preload" href="../assets/styles.css" as="style" />
  <link rel="stylesheet" href="../assets/styles.css" />
  <meta name="color-scheme" content="light dark" />
  <style>
    /* Minimal reset for demo if your global CSS isn't present */
    :root {{ --radius: 999px; }}
    body {{ margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 8px; }}
    .muted {{ opacity: .7; }}
    .small {{ font-size: .9rem; }}
    .divider {{ height: 1px; background: color-mix(in oklab, canvastext 14%, canvas 86%); margin: 16px 0 12px; }}
  </style>
</head>
<body>
  <main>
    <h1>Senior News Daily</h1>
    <div class="muted small">Sources activity for the last 7 days</div>

    <div class="divider"></div>

    <!-- Sources pill tray -->
    {sources_html}

    <div class="divider"></div>

    <p class="muted small">This tray shows which sites your current articles came from and when each site last produced an article. Counts are limited to the current window (7 days by default).</p>
  </main>
</body>
</html>
"""

# Write page
(SITE / "index.html").write_text(index_html, encoding="utf-8")

print(f"Built {SITE/'index.html'} with {len(source_stats)} sources across {len(current_articles)} recent articles.")
