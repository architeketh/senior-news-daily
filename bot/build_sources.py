# bot/build_sources.py
import pathlib, json, datetime
from urllib.parse import urlparse
from typing import Any, Dict, Iterable, List, Optional

ROOT = pathlib.Path(".")
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

ITEMS = DATA / "items.json"
OUT   = DATA / "sources.json"

def domain(u: str) -> str:
    try:
        netloc = urlparse(u or "").netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return "unknown"

def load_json(p: pathlib.Path, default):
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default

def dtparse(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s or not isinstance(s, str): return None
    s = s.strip()
    try:
        return datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception:
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z","%a, %d %b %Y %H:%M:%S GMT","%Y-%m-%d %H:%M:%S %z","%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.datetime.strptime(s, fmt)
            if d.tzinfo is None: d = d.replace(tzinfo=datetime.timezone.utc)
            return d
        except Exception:
            continue
    return None

def norm(rec: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(rec, dict): return None
    link = rec.get("link") or rec.get("url") or rec.get("href") or ""
    src  = rec.get("source") or rec.get("site") or rec.get("feed") or domain(link)
    dtx  = (
        dtparse(rec.get("published")) or dtparse(rec.get("pubDate")) or dtparse(rec.get("isoDate")) or
        dtparse(rec.get("updated"))   or dtparse(rec.get("date"))    or dtparse(rec.get("created_at")) or
        dtparse(rec.get("fetched_at"))
    )
    return {
        "title": rec.get("title") or rec.get("headline") or rec.get("name") or "",
        "link": link,
        "source": src,
        "_dt": dtx
    }

def iter_items(container: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(container, list):
        for x in container:
            n = norm(x)
            if n: yield n
        return
    if isinstance(container, dict):
        for k in ("items","articles","entries","results","data"):
            v = container.get(k)
            if isinstance(v, list):
                for x in v:
                    n = norm(x)
                    if n: yield n
                return
        n = norm(container)
        if n: yield n

raw = load_json(ITEMS, [])
items: List[Dict[str, Any]] = list(iter_items(raw))
now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
window_start = now - datetime.timedelta(days=7)

def safe_dt(it: Dict[str, Any]) -> datetime.datetime:
    return it.get("_dt") or now

curr = [a for a in items if safe_dt(a) >= window_start]

stats: Dict[str, Dict[str, Any]] = {}
for a in curr:
    dom = domain(a.get("link",""))
    key = (a.get("source") or dom or "unknown").lower()
    ts  = safe_dt(a)
    if key not in stats:
        stats[key] = {"display": a.get("source") or dom or "unknown", "domain": dom or "unknown",
                      "count": 0, "last_dt": ts, "last_title": a.get("title",""), "last_link": a.get("link","")}
    s = stats[key]
    s["count"] += 1
    if ts > s["last_dt"]:
        s["last_dt"] = ts; s["last_title"] = a.get("title",""); s["last_link"] = a.get("link","")

OUT.write_text(json.dumps({
    "generated_at": now.isoformat(),
    "window_days": 7,
    "sources": [
        {"key": k, "display": v["display"], "domain": v["domain"], "count": v["count"],
         "last_dt": v["last_dt"].isoformat(), "last_title": v["last_title"], "last_link": v["last_link"]}
        for k,v in sorted(stats.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    ]
}, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"[build_sources] items={len(items)} current={len(curr)} sources={len(stats)} -> data/sources.json")
