# bot/site_builder.py
import pathlib, json, datetime, random, re
from urllib.parse import urlparse
from typing import Any, Dict, Iterable, List, Optional

ROOT = pathlib.Path(".")
DATA = ROOT / "data"
SITE = ROOT / "site"
ASSETS = SITE / "assets"

DATA.mkdir(exist_ok=True)
SITE.mkdir(exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

ITEMS_PATH   = DATA / "items.json"
SOURCES_JSON = DATA / "sources.json"
INDEX_HTML   = SITE / "index.html"          # your real page (we will inject into it)
PILLS_CSS    = ASSETS / "pills.css"         # stylesheet for the pills

# ----------------- helpers -----------------
def esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url or "").netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return "unknown"

def load_json(p: pathlib.Path, default):
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default

def dtparse(s: Any) -> Optional[datetime.datetime]:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            continue
    return None

def normalize_record(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    title = raw.get("title") or raw.get("headline") or raw.get("name") or ""
    link  = raw.get("link") or raw.get("url") or raw.get("href") or ""
    src   = raw.get("source") or raw.get("site") or raw.get("feed") or domain_from_url(link)
    dt = (
        dtparse(raw.get("published"))
        or dtparse(raw.get("pubDate"))
        or dtparse(raw.get("isoDate"))
        or dtparse(raw.get("updated"))
        or dtparse(raw.get("date"))
        or dtparse(raw.get("created_at"))
        or dtparse(raw.get("fetched_at"))
    )
    return {
        "title": title, "link": link, "source": src,
        "published": raw.get("published") or raw.get("pubDate") or raw.get("isoDate") or raw.get("date"),
        "updated": raw.get("updated"),
        "fetched_at": raw.get("fetched_at"),
        "_dt": dt,
    }

def iter_items(container: Any) -> Iterable[Dict[str, Any]]:
    """Accepts list, or dict with items/articles/entries/results/data, or a single-object dict."""
    if isinstance(container, list):
        for it in container:
            n = normalize_record(it)
            if n: yield n
        return
    if isinstance(container, dict):
        for key in ("items", "articles", "entries", "results", "data"):
            val = container.get(key)
            if isinstance(val, list):
                for it in val:
                    n = normalize_record(it)
                    if n: yield n
                return
        n = normalize_record(container)
        if n: yield n
        return
    return

def human_time(dt: datetime.datetime, now: datetime.datetime):
    if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
    if now.tzinfo is None: now = now.replace(tzinfo=datetime.timezone.utc)
    local = dt.astimezone(now.tzinfo)
    today = now.date()
    t = local.strftime("%I:%M %p").lstrip("0")
    if local.date() == today: return f"Today, {t}"
    if local.date() == (today - datetime.timedelta(days=1)): return f"Yesterday, {t}"
    return local.strftime("%b %d, ") + t

def pick_color(seed: str):
    rnd = random.Random(seed)
    h = rnd.randint(0, 360)
    return f"hsl({h} 70% 94%)", f"hsl({h} 70% 28%)"   # (bg, text)

# ----------------- load & normalize -----------------
raw = load_json(ITEMS_PATH, [])
all_items: List[Dict[str, Any]] = list(iter_items(raw))

now_utc = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
window_start = now_utc - datetime.timedelta(days=7)  # current = last 7 days

def safe_dt(item: Dict[str, Any]) -> datetime.datetime:
    return item.get("_dt") or now_utc

current_items = [a for a in all_items if safe_dt(a) >= window_start]

# ----------------- per-source stats -----------------
source_stats: Dict[str, Dict[str, Any]] = {}
for a in current_items:
    link = a.get("link") or ""
    dom  = domain_from_url(link)
    src  = (a.get("source") or dom or "unknown").strip()
    key  = (src or dom or "unknown").lower()

    ts = safe_dt(a)
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

# write a small JSON for reuse/debug
SOURCES_JSON.write_text(
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

pills_html = render_sources_pills(now_utc)

# ----------------- inject into your existing site/index.html -----------------
# Strategy:
#  1) Ensure <link rel="stylesheet" href="assets/pills.css"> is present (add if missing).
#  2) Insert pills where you put <!-- SOURCES_PILLS -->.
#  3) If no marker, try to inject right after the first <h1>…</h1>.
#  4) If still no joy, prepend inside first <main>…</main>.
html = INDEX_HTML.read_text(encoding="utf-8")

# 1) ensure CSS link
if 'assets/pills.css' not in html:
    # add before closing </head> if possible
    if '</head>' in html:
        html = html.replace('</head>', '  <link rel="stylesheet" href="assets/pills.css" />\n</head>', 1)

# 2) preferred: explicit marker
if '<!-- SOURCES_PILLS -->' in html:
    html = html.replace('<!-- SOURCES_PILLS -->', pills_html, 1)
else:
    # 3) after first <h1>…</h1>
    m = re.search(r'</h1\s*>', html, flags=re.IGNORECASE)
    if m:
        idx = m.end()
        html = html[:idx] + "\n" + pills_html + "\n" + html[idx:]
    else:
        # 4) inside first <main>
        m2 = re.search(r'<main[^>]*>', html, flags=re.IGNORECASE)
        if m2:
            idx = m2.end()
            html = html[:idx] + "\n" + pills_html + "\n" + html[idx:]
        else:
            # last fallback: append at top of body
            m3 = re.search(r'<body[^>]*>', html, flags=re.IGNORECASE)
            if m3:
                idx = m3.end()
                html = html[:idx] + "\n" + pills_html + "\n" + html[idx:]
            else:
                # give up: just prefix file (rare)
                html = pills_html + "\n" + html

INDEX_HTML.write_text(html, encoding="utf-8")

# ----------------- ensure pills.css exists (don’t crash if already there) -----------------
if not PILLS_CSS.exists():
    PILLS_CSS.write_text("""/* site/assets/pills.css */
.pill-tray { display:flex; flex-wrap:wrap; gap:8px; padding:6px 0 10px; }
.pill {
  --pill-bg: color-mix(in oklab, canvas 90%, canvastext 10%);
  --pill-fg: color-mix(in oklab, canvastext 60%, canvas 40%);
  background: var(--pill-bg); color: var(--pill-fg);
  border-radius:999px; padding:6px 10px; text-decoration:none;
  display:inline-flex; align-items:baseline; gap:6px; line-height:1;
  border:1px solid color-mix(in oklab, var(--pill-fg) 16%, transparent);
  transition: transform .08s ease, background .2s ease, color .2s ease, border-color .2s ease;
  white-space:nowrap;
}
.pill:hover {
  transform: translateY(-1px);
  background: color-mix(in oklab, var(--pill-bg) 80%, var(--pill-fg) 20%);
  color: color-mix(in oklab, var(--pill-fg) 90%, canvas 10%);
  border-color: color-mix(in oklab, var(--pill-fg) 30%, transparent);
}
.pill-site{ font-weight:600; letter-spacing:.2px; }
.pill-dot{ opacity:.6; }
.pill-when{ opacity:.9; font-variant-numeric: tabular-nums; }
.pill-count{ opacity:.7; }
@media (max-width:640px){ .pill{ font-size:.95rem; } }
""", encoding="utf-8")

print(f"[site_builder] normalized={len(all_items)} in_window={len(current_items)} sources={len(source_stats)}; injected pills & ensured pills.css")
