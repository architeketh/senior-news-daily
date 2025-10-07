# bot/summarize.py
import os, json, re
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from dateutil import parser as dtp

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Canonical categories with robust keyword signals.
# Order matters: earlier buckets have higher priority when multiple match.
CATEGORY_RULES = [
    ("Safety & Scams", [
        r"\bscam(s)?\b", r"\bfraud\b", r"\bphishing\b", r"\brobocall(s)?\b",
        r"\bspoof(ing)?\b", r"\bidentity theft\b", r"\belder abuse\b", r"\brecall(s)?\b",
    ]),
    ("Social Security", [
        r"\bsocial security\b", r"\bssa\b", r"\bssdi\b", r"\bssi\b", r"\bcola\b",
        r"\bbenefit(s)?\b", r"\bretire(?:ment)?\s+benefit(s)?\b",
    ]),
    ("Medicare", [
        r"\bmedicare\b", r"\bcms\b", r"\bpart\s*d\b", r"\bmedigap\b",
        r"\bprescription\b", r"\bdrug(s)?\b", r"\brx\b", r"\bpremium(s)?\b",
    ]),
    ("Finance & Retirement", [
        r"\bmoney\b", r"\bfinance\b", r"\bbudget(ing)?\b", r"\bsaving(s)?\b",
        r"\binvest(ing|ment|ments)?\b", r"\bannuity\b", r"\b401(k)?\b", r"\bira\b",
        r"\bpension(s)?\b", r"\binflation\b",
    ]),
    ("Travel", [
        r"\btravel\b", r"\btrip(s)?\b", r"\bvacation(s)?\b", r"\btour(s)?\b",
        r"\bhotel(s)?\b", r"\bflight(s)?\b", r"\bcruise(s)?\b", r"\bdestination(s)?\b",
    ]),
    ("Golf & Leisure", [
        r"\bgolf\b", r"\bpickleball\b", r"\bleisure\b", r"\bhobby\b",
        r"\brecreation\b", r"\bfitness\b", r"\bexercise\b", r"\bwalking\b",
    ]),
    ("Cooking & Nutrition", [
        r"\bcooking\b", r"\brecipe(s)?\b", r"\bnutrition\b", r"\bdiet(s|ary)?\b",
        r"\bfood\b", r"\bdining\b", r"\bmeal(s)?\b", r"\bkitchen\b",
    ]),
    ("Caregiving & LTC", [
        r"\bcaregiver(s)?\b", r"\bcaregiving\b", r"\bnursing home(s)?\b",
        r"\blong-?term care\b", r"\bltc\b",
    ]),
    ("Aging Research", [
        r"\baging\b", r"\blongevity\b", r"\balzheim(er'?s)?\b", r"\bdementia\b",
        r"\bnia\b", r"\bnih\b", r"\bfalls?\b", r"\bresearch\b",
    ]),
    ("Policy & Legislation", [
        r"\bbill(s)?\b", r"\blegislation\b", r"\blaw(s)?\b", r"\bcongress\b",
        r"\bregulation(s)?\b", r"\brulemaking\b", r"\bhhs\b", r"\bacl\b", r"\boig\b",
    ]),
]

# Precompile regex patterns
COMPILED = [(name, [re.compile(pat, re.IGNORECASE) for pat in pats])
            for name, pats in CATEGORY_RULES]

SCAM_WORDS = ["scam", "fraud", "phishing", "impersonation", "robocall", "spoof", "identity theft", "elder abuse"]

def _is_today(dt_iso: str) -> bool:
    if not dt_iso:
        return False
    dt = dtp.parse(dt_iso)
    return dt.date() == datetime.now(timezone.utc).date()

def _rule_based_category(title: str, summary: str) -> str:
    text = f"{title or ''}\n{summary or ''}"
    for bucket, patterns in COMPILED:
        if any(p.search(text) for p in patterns):
            return bucket
    return "General"

async def _ai_categorize(items: list[dict]) -> dict:
    """Optional: ask the model for a category label, then we still canonize via rules."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    batch = items[:60]
    payload = [{"id": it.get("id"), "title": it.get("title",""), "summary": it.get("summary","")} for it in batch]
    prompt = (
        "Assign ONE short topic label (3-5 words) to each item for older-adult news. "
        "Examples: 'Medicare', 'Social Security', 'Finance & Retirement', 'Travel', "
        "'Golf & Leisure', 'Cooking & Nutrition', 'Caregiving & LTC', 'Aging Research', "
        "'Safety & Scams', 'Policy & Legislation'. "
        "Return strict JSON mapping id -> label. Input:\n" + json.dumps(payload, ensure_ascii=False)
    )
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.1,
        max_tokens=900,
    )
    text = resp.choices[0].message.content.strip()
    try:
        start = text.find("{"); end = text.rfind("}")
        return json.loads(text[start:end+1])
    except Exception:
        return {}

def _scam_alerts(items):
    def is_scam(it):
        t = (it.get("title","") + " " + it.get("summary","")).lower()
        return any(k in t for k in SCAM_WORDS)
    return [it for it in items if is_scam(it)][:10]

def _summary_fallback(items: list[dict]) -> str:
    # Very short deterministic summary + top headlines
    cats = defaultdict(int)
    for it in items[:20]:
        cats[_rule_based_category(it.get("title",""), it.get("summary",""))] += 1
    parts = [f"{c}: {n}" for c, n in sorted(cats.items(), key=lambda x: -x[1])]
    lines = ["Today’s senior news at a glance — " + "; ".join(parts) + "."]
    for it in items[:6]:
        title = it.get("title","").strip()
        src = it.get("source","").strip()
        lines.append(f"- {title} ({src})")
    return "\n".join(lines)

async def _ai_summary(items: list[dict]) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    bullets = []
    for it in items[:16]:
        bullets.append(f"• {it.get('title','')} — {it.get('summary','')[:200]}")
    prompt = (
        "Summarize key developments for U.S. older adults in 120-180 words. Cover Medicare, "
        "Social Security, Finance/Retirement, Aging Research, Caregiving/LTC, Travel/Leisure, "
        "Cooking/Nutrition, and Safety/Scams if present. Neutral, precise, plain English. "
        "Provide 3-5 crisp bullets after the paragraph.\n\nHeadlines:\n" + "\n".join(bullets)
    )
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.2,
        max_tokens=400,
    )
    return resp.choices[0].message.content.strip()

def main():
    items_blob = {"updated": None, "items": []}
    if ITEMS_PATH.exists():
        items_blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    items = items_blob.get("items", [])

    # 1) Categorize each item (AI optional, always canonize with rules)
    if OPENAI_API_KEY and items:
        try:
            import asyncio
            ai_map = asyncio.run(_ai_categorize(items))
        except Exception as e:
            print(f"[summarize] AI categorize failed: {e}; proceeding with rules only.")
            ai_map = {}
    else:
        ai_map = {}

    cat_counts = defaultdict(int)
    for it in items:
        title = it.get("title","")
        summary = it.get("summary","")
        raw = ai_map.get(it.get("id"))  # optional label
        # First: deterministic rule-based bucket so words like 'golf'/'money'/'social security' always map
        rule_bucket = _rule_based_category(title, summary)
        # If AI provided something, keep it as subcategory for display/debug; bucket stays deterministic
        it["subcategory"] = (raw or rule_bucket)
        it["category"] = rule_bucket
        cat_counts[rule_bucket] += 1

    # 2) Build summary text (AI or fallback)
    todays = [it for it in items if _is_today(it.get("published") or it.get("fetched"))]
    if OPENAI_API_KEY:
        try:
            import asyncio
            summary = asyncio.run(_ai_summary(todays or items))
        except Exception as e:
            print(f"[summarize] AI summary failed: {e}; using fallback.")
            summary = _summary_fallback(todays or items)
    else:
        summary = _summary_fallback(todays or items)

    # 3) Scam alerts
    alerts = _scam_alerts(items)

    # 4) Persist results:
    #    a) Write categories back into items.json (so site_builder can show them on the cards)
    ITEMS_PATH.write_text(json.dumps({
        "updated": items_blob.get("updated"),
        "items": items
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    #    b) Write digest.json with counts + summary + alerts
    DIGEST_PATH.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "alerts": alerts,
        "category_counts": dict(sorted(cat_counts.items(), key=lambda x: -x[1]))
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[summarize] Categorized {len(items)} items. Top buckets: {list(dict(sorted(cat_counts.items(), key=lambda x: -x[1])) )[:5]}")
    print(f"[summarize] Wrote categories back to {ITEMS_PATH}")
    print(f"[summarize] Wrote digest → {DIGEST_PATH}")

if __name__ == "__main__":
    main()
