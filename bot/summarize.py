# bot/summarize.py
"""
Summarize articles, assign AI-based categories, and create digest.json.
"""

import json, re, pathlib, datetime
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

def load_items():
    if ITEMS_PATH.exists():
        with open(ITEMS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("items", [])
    return []

def assign_category(text: str, source: str = "") -> str:
    """Classify article text heuristically into a major category."""
    s = text.lower() + " " + source.lower()
    if any(k in s for k in ["golf", "leisure", "hobby"]):
        return "Golf & Leisure"
    if any(k in s for k in ["travel", "destination", "trip", "vacation"]):
        return "Travel"
    if any(k in s for k in ["cook", "recipe", "food", "nutrition", "diet"]):
        return "Cooking & Nutrition"
    if any(k in s for k in ["exercise", "fitness", "walk", "workout", "yoga"]):
        return "Exercise & Fitness"
    if any(k in s for k in ["social security", "ssa", "benefits"]):
        return "Social Security"
    if any(k in s for k in ["retire", "pension", "money", "finance", "investment", "401k"]):
        return "Finance & Retirement"
    if any(k in s for k in ["medicare", "health", "coverage", "plan b", "prescription"]):
        return "Medicare"
    if any(k in s for k in ["caregiver", "assisted living", "long-term care"]):
        return "Caregiving & LTC"
    if any(k in s for k in ["fraud", "scam", "phishing", "spam", "robocall"]):
        return "Safety & Scams"
    if any(k in s for k in ["aging", "research", "longevity", "alzheim", "dementia"]):
        return "Aging Research"
    if any(k in s for k in ["policy", "bill", "senate", "law", "regulation"]):
        return "Policy & Legislation"
    return "General"

def summarize_items(items):
    """Generate digest summary text + alerts list."""
    alerts = [it for it in items if "scam" in it.get("title", "").lower()]
    counts = Counter(assign_category(it.get("title","")+" "+it.get("summary",""), it.get("source","")) for it in items)
    top3 = counts.most_common(3)
    summary = "Today's highlights: " + ", ".join([f"{c} ({n})" for c, n in top3]) if top3 else "No major updates today."
    for it in items:
        it["category"] = assign_category(it.get("title", "") + " " + it.get("summary", ""), it.get("source", ""))
    return summary, alerts

def main():
    items = load_items()
    if not items:
        print("[summarize] No items found.")
        return
    summary, alerts = summarize_items(items)
    digest = {
        "generated": datetime.datetime.utcnow().isoformat(),
        "summary": summary,
        "alerts": alerts,
    }
    with open(DIGEST_PATH, "w", encoding="utf-8") as f:
        json.dump(digest, f, indent=2)
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, indent=2)
    print(f"[summarize] Digest created ({len(items)} items, {len(alerts)} alerts)")

if __name__ == "__main__":
    main()
