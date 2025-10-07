# bot/fetch.py
import json, hashlib, time, sys
from pathlib import Path
from datetime import datetime, timezone
from dateutil import parser as dtp
import feedparser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FEEDS = DATA / "feeds.yaml"
OUT = DATA / "items.json"
DATA.mkdir(exist_ok=True)

try:
    import yaml  # type: ignore
except Exception:
    print("\n[fetch] Missing PyYAML; using a tiny fallback parser for feeds.yaml (simple lists only).\n")
    yaml = None

from langdetect import detect, DetectorFactory
DetectorFactory.seed = 42  # deterministic language detection

DEFAULT_FEEDS = [
    "https://press.aarp.org/rss",
    "https://www.kff.org/topic/medicare/feed/",
    "https://www.cms.gov/about-cms/contact/newsroom/rss.xml",
    "https://www.ssa.gov/news/en/press/releases/index.rss",
    "https://oig.ssa.gov/rss/news-releases.xml",
    "https://acl.gov/news/rss.xml",
    "https://kffhealthnews.org/topic/aging/feed/",
    "https://www.nia.nih.gov/news/rss.xml",
    "https://tools.cdc.gov/api/v2/resources/media/403372.rss",
]

KEYWORDS = [
    "medicare", "medicaid", "social security", "ssa", "older adult", "senior", "aging", "retiree",
    "long-term care", "nursing home", "alzheim", "dementia", "falls", "scam", "fraud", "benefit",
    "rx", "drug price", "prescription", "caregiver", "pension", "ssi", "cost-of-living", "cola",
]

def _load_feeds() -> list[str]:
    if FEEDS.exists():
        if yaml:
            data = yaml.safe_load(FEEDS.read_text(encoding="utf-8"))
            feeds = list(dict.fromkeys([f.strip() for f in data.get("feeds", []) if isinstance(f, str)]))
            return feeds or DEFAULT_FEEDS
        else:
            lines = [ln.strip() for ln in FEEDS.read_text(encoding="utf-8").splitlines()]
            feeds = [ln.split("- ",1)[1] for ln in lines if ln.startswith("- ")]
            return feeds or DEFAULT_FEEDS
    return DEFAULT_FEEDS

def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def _norm_time(s):
    if not s:
        return None
    try:
        dt = dtp.parse(s)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def _match_us_senior(text: str) -> bool:
    text_low = (text or "").lower()
    return any(k in text_low for k in KEYWORDS)

def _is_spanish_or_not_english(text: str) -> bool:
    txt = (text or "").strip()
    if not txt:
        return False
    try:
        lang = detect(txt)
        # keep EN; explicitly filter ES
        if lang == "es":
            return True
        return lang != "en"
    except Exception:
        return False

def main():
    feeds = _load_feeds()
    all_items = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for url in feeds:
        parsed = feedparser.parse(url)
        for e in parsed.entries:
            title = getattr(e, "title", "").strip()
            summary = getattr(e, "summary", getattr(e, "description", "")).strip()
            link = getattr(e, "link", "").strip()
            published = _norm_time(getattr(e, "published", getattr(e, "updated", "")))

            content_text = title + "\n\n" + summary

            # 1) topical filter
            if not _match_us_senior(content_text):
                continue
            # 2) language filter
            if _is_spanish_or_not_english(content_text):
                continue

            uid = _hash(link or title or (published or "") )
            all_items.append({
                "id": uid,
                "title": title,
                "summary": summary,
                "link": link,
                "source": parsed.feed.get("title", ""),
                "published": published,
                "fetched": now_iso,
            })
        time.sleep(0.15)

    # Deduplicate by link/id
    dedup = {}
    for it in all_items:
        key = it.get("link") or it["id"]
        if key not in dedup:
            dedup[key] = it

    OUT.write_text(json.dumps({
        "updated": now_iso,
        "items": sorted(dedup.values(), key=lambda x: x.get("published") or x.get("fetched"), reverse=True)
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[fetch] Wrote {len(dedup)} items → {OUT}")

if __name__ == "__main__":
    sys.exit(main())
