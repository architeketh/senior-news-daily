# bot/summarize.py
"""
Summarize + Categorize for Senior News Daily
--------------------------------------------
- Reads data/items.json
- Classifies articles into broader senior-friendly categories
  (Medicare, Finance, Travel, Cooking, Exercise, etc.)
- Generates a concise daily summary
- Writes digest.json with summary, alerts, and counts
"""

import os, json, re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
from dateutil import parser as dtp
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------------- Category Rules ----------------
CATEGORY_RULES = [
    ("Safety & Scams", [r"scam", r"fraud", r"phish", r"identity theft", r"robocall", r"spoof", r"elder abuse"]),
    ("Social Security", [r"social security", r"ssa", r"cola", r"ssdi", r"ssi"]),
    ("Medicare", [r"medicare", r"part\s*[abcd]", r"medigap", r"cms", r"prescription"]),
    ("Finance & Retirement", [r"401k", r"ira", r"pension", r"tax", r"invest", r"annuit", r"money", r"savings?"]),
    ("Travel", [r"travel", r"trip", r"vacation", r"cruise", r"hotel", r"destination", r"flight"]),
    ("Golf & Leisure", [r"golf", r"leisure", r"pickleball", r"hobby", r"recreation"]),
    ("Exercise & Fitness", [r"exercise", r"fitness", r"walking", r"workout", r"yoga", r"stretch", r"activity"]),
    ("Cooking & Nutrition", [r"cook", r"recipe", r"nutrition", r"meal", r"diet", r"food", r"healthy eating"]),
    ("Caregiving & LTC", [r"caregiver", r"long[-\s]?term care", r"nursing home", r"home health"]),
    ("Aging Research", [r"aging", r"longevity", r"alzheim", r"dementia", r"nih", r"nia", r"clinical trial"]),
    ("Policy & Legislation", [r"law", r"bill", r"regulation", r"legislation", r"congress"]),
]

DOMAIN_HINTS = {
    # Lifestyle & Food
    "foodnetwork.com": "Cooking & Nutrition",
    "allrecipes.com": "Cooking & Nutrition",
    "eatingwell.com": "Cooking & Nutrition",
    "bonappetit.com": "Cooking & Nutrition",
    # Travel
    "travelandleisure.com": "Travel",
    "lonelyplanet.com": "Travel",
    "usatoday.com": "Travel",
    "nytimes.com": "Travel",
    # Exercise & Leisure
    "aarp.org/health/fitness": "Exercise & Fitness",
    "menshealth.com": "Exercise & Fitness",
    "verywellfit.com": "Exercise & Fitness",
    # Finance
    "nerdwallet.com": "Finance & Retirement",
    "cnbc.com": "Finance & Retirement",
    "kiplinger.com": "Finance & Retirement",
    # Senior Policy
    "kff.org": "Medicare",
    "kffhealthnews.org": "Medicare",
    "ssa.gov": "Social Security",
    "cms.gov": "Medicare",
    "acl.gov": "Caregiving & LTC",
    "nia.nih.gov": "Aging Research",
    "ftc.gov": "Safety & Scams",
    "justice.gov": "Safety & Scams",
    "hhs.gov": "Policy & Legislation",
}

SCAM_WORDS = ["scam", "fraud", "phishing", "robocall", "spoof", "identity theft", "elder abuse"]

# ---------------- Helpers ----------------
def _strong_category(title, summary, source, link):
    text = " ".join([title or "", summary or "", source or ""]).lower()
    for cat, patterns in CATEGORY_RULES:
        if any(re.search(p, text) for p in patterns):
            return cat
    try:
        host = (urlparse(link or "").hostname or "").lower().lstrip("www.")
        if host in DOMAIN_HINTS:
            return DOMAIN_HINTS[host]
    except Exception:
        pass
    return "General"

def _scam_alerts(items):
    return [it for it in items if any(k in (it.get("title","")+it.get("summary","")).lower() for k in SCAM_WORDS)][:10]

def _summary_fallback(items):
    cats = Counter(_strong_category(it.get("title",""), it.get("summary",""), it.get("source",""), it.get("link","")) for it in items)
    parts = [f"{c}: {n}" for c,n in cats.most_common(6)]
    lines = ["Today’s senior news highlights — " + "; ".join(parts) + "."]
    for it in items[:5]:
        lines.append(f"- {it.get('title','')} ({it.get('source','')})")
    return "\n".join(lines)

# ---------------- Main ----------------
def main():
    blob = json.loads(ITEMS_PATH.read_text()) if ITEMS_PATH.exists() else {"items":[]}
    items = blob.get("items", [])

    cat_counts = defaultdict(int)
    for it in items:
        bucket = _strong_category(it.get("title",""), it.get("summary",""), it.get("source",""), it.get("link",""))
        it["category"] = bucket
        cat_counts[bucket] += 1

    summary = _summary_fallback(items)
    alerts = _scam_alerts(items)

    DIGEST_PATH.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "alerts": alerts,
        "category_counts": dict(sorted(cat_counts.items(), key=lambda x: -x[1]))
    }, indent=2))

    ITEMS_PATH.write_text(json.dumps({"items": items}, indent=2))
    print(f"[summarize] Categorized {len(items)} items → {len(cat_counts)} categories")

if __name__ == "__main__":
    main()
