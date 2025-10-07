# bot/fetch.py
"""
Flexible feed fetcher for Senior News Daily
- Broaden accepted sites:   set env BROADEN_SITES=true (adds lifestyle feeds), or ADDITIONAL_FEEDS="url1,url2"
- Broaden accepted keywords: set env FILTER_MODE=loose (default), strict, or none (accept all from feeds)
- One-off manual URL:       set env EXTRA_URL (workflow_dispatch input) to an RSS or article URL
- Language filter:          drops non-English (explicitly removes Spanish)

Env vars typically wired in .github/workflows/pages.yml:
  EXTRA_URL: ${{ github.event.inputs.extra_url }}
  FILTER_MODE: none | loose | strict      (default: loose)
  BROADEN_SITES: "true" | "false"         (default: false)
  ADDITIONAL_FEEDS: "https://a.com/rss,https://b.com/feed"
"""

from __future__ import annotations
import os, json, hashlib, time, sys
from pathlib import Path
from datetime import datetime, timezone
from dateutil import parser as dtp

import feedparser, requests
from bs4 import BeautifulSoup
from readability import Document
from langdetect import detect, DetectorFactory

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FEEDS_FILE = DATA / "feeds.yaml"
OUT = DATA / "items.json"
DATA.mkdir(exist_ok=True)

# ---------- Config via env ----------
FILTER_MODE = os.getenv("FILTER_MODE", "loose").lower().strip()   # "strict" | "loose" | "none"
BROADEN_SITES = os.getenv("BROADEN_SITES", "false").lower().strip() in {"1","true","yes","on"}
ADDITIONAL_FEEDS = [u.strip() for u in os.getenv("ADDITIONAL_FEEDS", "").split(",") if u.strip()]
EXTRA_URL = os.getenv("EXTRA_URL", "").strip()   # populated by workflow_dispatch input

DetectorFactory.seed = 42  # deterministic language detection

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# ---------- Trusted base feeds (policy/health/seniors) ----------
BASE_FEEDS = [
    "https://press.aarp.org/rss",
    "https://www.kff.org/topic/medicare/feed/",
    "https://www.kff.org/topic/medicaid/feed/",
    "https://kffhealthnews.org/topic/aging/feed/",
    "https://www.ssa.gov/news/en/press/releases/index.rss",
    "https://oig.ssa.gov/rss/news-releases.xml",
    "https://www.cms.gov/about-cms/contact/newsroom/rss.xml",
    "https://acl.gov/news/rss.xml",
    "https://www.nia.nih.gov/news/rss.xml",
    "https://tools.cdc.gov/api/v2/resources/media/403372.rss",
    "https://www.consumerfinance.gov/about-us/blog/rss/",
    "https://www.ftc.gov/news-events/news/rss",
    "https://www.justice.gov/elderjustice/rss.xml",
    "https://www.hhs.gov/about/news/rss.xml",
]

# ---------- Optional lifestyle feeds (golf, travel, cooking, finance, etc.) ----------
LIFESTYLE_FEEDS = [
    # Golf / leisure
    "https://golf.com/feed/",
    # Travel
    "https://www.travelandleisure.com/rss",
    # Cooking / food
    "https://www.epicurious.com/services/rss/feeds/latest.xml",
    # Finance (retirement/savings, general consumer finance)
    "https://www.nerdwallet.com/blog/feed/",
    "https://www.cnbc.com/id/10000354/device/rss/rss.html",           # Personal Finance (CNBC)
    # Aging lifestyle (broad U.S. news to catch relevant human-interest)
    "https://feeds.npr.org/1001/rss.xml"
]

# ---------- Keyword filters ----------
STRICT_KEYS = [
    "medicare","medicaid","social security","ssa","senior","older adult","retiree",
    "long-term care","nursing home","alzheim","dementia","caregiver","ltc","cola","benefit",
    "scam","fraud","prescription","drug","rx","price","premium","cms","nia","nih","acl","hhs",
]
LOOSE_KEYS = STRICT_KEYS + [
    # lifestyle
    "golf","pickleball","leisure","hobby","recreation","fitness","walking","exercise",
    "travel","trip","vacation","tour","hotel","flight","cruise","destination",
    "cooking","recipe","nutrition","diet","food","dining","restaurant","meal",
    "finance","retirement","retire","annuity","401k","ira","invest","savings","budget","inflation"
]

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def _norm_time(s: str | None) -> str | None:
    if not s: return None
    try:
        dt = dtp.parse(s)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def _is_non_english(text: str) -> bool:
    txt = (text or "").strip()
    if not txt: return False
    try:
        lang = detect(txt)
        return lang != "en"   # explicitly drop Spanish & all non-English
    except Exception:
        return False

def _match_topic(text: str) -> bool:
    """Apply FILTER_MODE to decide if we keep an item."""
    if FILTER_MODE == "none":
        return True
    t = (text or "").lower()
    keys = STRICT_KEYS if FILTER_MODE == "strict" else LOOSE_KEYS
    return any(k in t for k in keys)

def _load_feeds_from_yaml() -> list[str]:
    if FEEDS_FILE.exists():
        if yaml:
            data = yaml.safe_load(FEEDS_FILE.read_text(encoding="utf-8")) or {}
            feeds = [f.strip() for f in (data.get("feeds") or []) if isinstance(f, str)]
            return list(dict.fromkeys(feeds))
        # fallback very simple parser: lines starting with "- "
        feeds = []
        for ln in FEEDS_FILE.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln.startswith("- "):
                feeds.append(ln[2:].strip())
        return list(dict.fromkeys(feeds))
    return []

def _compose_feed_list() -> list[str]:
    feeds = _load_feeds_from_yaml()
    if not feeds:
        feeds = list(BASE_FEEDS)
    if BROADEN_SITES:
        feeds += LIFESTYLE_FEEDS
    if ADDITIONAL_FEEDS:
        feeds += ADDITIONAL_FEEDS
    # de-dupe while preserving order
    return list(dict.fromkeys([u for u in feeds if u]))

def _discover_rss(url: str) -> str | None:
    """Try to find a feed <link rel=alternate type=rss|atom> from a web page."""
    try:
        html = requests.get(url, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("link"):
            rels = (link.get("rel") or [])
            if not isinstance(rels, (list, tuple)): continue
            if "alternate" not in [r.lower() for r in rels]: continue
            t = (link.get("type") or "").lower()
            href = link.get("href")
            if href and ("rss" in t or "atom" in t or href.endswith(".xml")):
                return requests.compat.urljoin(url, href)
    except Exception:
        return None
    return None

def _make_item_from_page(url: str) -> dict | None:
    """Extract a title/summary from a single article URL."""
    try:
        r = requests.get(url, timeout=25)
        r.raise_for_status()
        doc = Document(r.text)
        title = (doc.short_title() or "").strip()
        summary = BeautifulSoup(doc.summary(html_partial=True), "html.parser").get_text(" ", strip=True)
        if not title and not summary:
            return None
        text = f"{title}\n{summary}"
        if _is_non_english(text):
            return None
        if not _match_topic(text):
            return None
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "id": _hash(url),
            "title": title[:240],
            "summary": summary[:1200],
            "link": url,
            "source": "Custom URL",
            "published": None,
            "fetched": now_iso,
        }
    except Exception:
        return None

def _ingest_feed(url: str, now_iso: str, out_items: list[dict]) -> None:
    """Parse an RSS/Atom feed, filter, and append items."""
    parsed = feedparser.parse(url)
    src_title = parsed.feed.get("title", "")
    for e in parsed.entries:
        title = getattr(e, "title", "").strip()
        summary = getattr(e, "summary", getattr(e, "description", "")).strip()
        link = getattr(e, "link", "").strip()
        published = _norm_time(getattr(e, "published", getattr(e, "updated", "")))
        content_text = (title + "\n\n" + summary).strip()

        if _is_non_english(content_text):
            continue
        if not _match_topic(content_text):
            continue

        uid = _hash(link or title or (published or ""))
        out_items.append({
            "id": uid,
            "title": title,
            "summary": summary,
            "link": link,
            "source": src_title,
            "published": published,
            "fetched": now_iso,
        })

def main():
    feeds = _compose_feed_list()
    all_items: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Ingest normal feeds
    for url in feeds:
        try:
            _ingest_feed(url, now_iso, all_items)
        except Exception:
            # continue on individual feed failure
            pass
        time.sleep(0.12)  # be polite to hosts

    # Optional one-off source
    if EXTRA_URL:
        rss = _discover_rss(EXTRA_URL)
        if rss:
            try:
                _ingest_feed(rss, now_iso, all_items)
            except Exception:
                pass
        else:
            single = _make_item_from_page(EXTRA_URL)
            if single:
                all_items.append(single)

    # De-duplicate by link (prefer published items), then id
    dedup: dict[str, dict] = {}
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
