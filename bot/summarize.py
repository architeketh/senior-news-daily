# bot/summarize.py
"""
Summarize + Categorize
- Reads data/items.json
- Assigns robust categories (domain hints + strong regex rules)
- (Optional) Uses OpenAI to propose labels, but final bucket is always canonical
- Writes categories back to items.json
- Writes data/digest.json with summary paragraph, scam alerts, and category counts
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# ---------------- Canonical category rules (priority order) ----------------
CATEGORY_RULES = [
    ("Safety & Scams", [
        r"\b(scams?|fraud|phish(?:ing)?|robocalls?|spoof(?:ing)?|identity theft|elder abuse|smish(?:ing)?|vish(?:ing)?)\b",
    ]),
    ("Social Security", [
        r"\bsocial security\b", r"\bssa\b", r"\bssdi\b", r"\bssi\b", r"\bcola\b",
        r"\b(retire(?:ment)?|survivor|disability)\s+benefit(s)?\b",
        r"\brequired minimum distribution(s)?\b", r"\brmds?\b",
    ]),
    ("Medicare", [
        r"\bmedicare\b", r"\bmedicare advantage\b", r"\bpart\s*[abcd]\b", r"\bmedigap\b",
        r"\b(drug|rx|prescription)\b", r"\bpremium(s)?\b", r"\bdeductible(s)?\b", r"\bcms\b",
        r"\bprior authorization\b",
    ]),
    ("Finance & Retirement", [
        r"\bmoney\b", r"\bfinance\b", r"\bbudget(ing)?\b", r"\bsaving(s)?\b",
        r"\binvest(ing|ment|ments)?\b", r"\bannuit(y|ies)\b", r"\b401(k)?\b", r"\b403(b)\b",
        r"\bira(s)?\b", r"\broth\b", r"\bpension(s)?\b", r"\btax(es)?\b", r"\brmds?\b",
        r"\b(estate|legacy)\s+planning\b", r"\blong[-\s]?term\s+finances?\b",
    ]),
    ("Travel", [
        r"\btravel\b", r"\btrips?\b", r"\bvacations?\b", r"\btours?\b",
        r"\bhotels?\b", r"\bflights?\b", r"\bcruises?\b", r"\bdestinations?\b", r"\bitinerary\b",
    ]),
    ("Golf & Leisure", [
        r"\bgolf(ing)?\b", r"\bpickleball\b", r"\bleisure\b", r"\bhobby\b",
        r"\brecreation\b", r"\bfitness\b", r"\bexercise\b", r"\bwalking\b",
    ]),
    ("Cooking & Nutrition", [
        r"\bcook(ing)?\b", r"\brecipes?\b", r"\bnutrition(al)?\b", r"\bdiet(s|ary)?\b",
        r"\bfood\b", r"\bdining\b", r"\bmeal(s)?\b", r"\bkitchen\b", r"\bmeal\s+prep\b",
    ]),
    ("Caregiving & LTC", [
        r"\bcaregiver(s)?\b", r"\bcaregiving\b", r"\bnursing\s+home(s)?\b",
        r"\blong[-\s]?term\s+care\b", r"\bltc\b", r"\brespite\b", r"\bhome\s+health\b",
    ]),
    ("Aging Research", [
        r"\baging\b", r"\blongevity\b", r"\balzheim(?:er'?s)?\b", r"\bdementia\b",
        r"\bnia\b", r"\bnih\b", r"\bfalls?\b", r"\bclinical\s+trial(s)?\b", r"\bresearch\b",
    ]),
    ("Policy & Legislation", [
        r"\bbills?\b", r"\blegislation\b", r"\blaws?\b", r"\bcongress\b",
        r"\bregulation(s)?\b", r"\brule-?making\b", r"\bproposed rule\b", r"\bhhs\b", r"\bacl\b", r"\boig\b",
    ]),
]
COMPILED = [(name, [re.compile(p, re.IGNORECASE) for p in pats]) for name, pats in CATEGORY_RULES]

DOMAIN_HINTS = {
    # lifestyle
    "golf.com": "Golf & Leisure",
    "travelandleisure.com": "Travel",
    "epicurious.com": "Cooking & Nutrition",
    # finance
    "nerdwallet.com": "Finance & Retirement",
    "cnbc.com": "Finance & Retirement",
    # senior policy/health
    "kff.org": "Medicare",
    "kffhealthnews.org": "Medicare",
    "ssa.gov": "Social Security",
    "cms.gov": "Medicare",
    "acl.gov": "Caregiving & LTC",
    "nia.nih.gov": "Aging Research",
    "cdc.gov": "Aging Research",
    "ftc.gov": "Safety & Scams",
    "justice.gov": "Safety & Scams",
    "hhs.gov": "Policy & Legislation",
    "aarp.org": "Finance & Retirement",
}

SCAM_WORDS = ["scam", "fraud", "phishing", "impersonation", "robocall", "spoof", "identity theft", "elder abuse"]

# ---------------- Core helpers ----------------
def _is_today(dt_iso: str | None) -> bool:
    if not dt_iso:
        return False
    try:
        return dtp.parse(dt_iso).date() == datetime.now(timezone.utc).date()
    except Exception:
        return False

def _strong_rule_category(title: str, summary: str, source: str, link: str) -> str:
    text = " ".join(x for x in [title or "", summary or "", source or ""] if x)
    hits = []
    for idx, (bucket, patterns) in enumerate(COMPILED):
        score = sum(1 for p in patterns if p.search(text))
        if score:
            hits.append((score * (10 - idx), bucket))  # earlier buckets have priority
    # domain hint
    host = ""
    try:
        host = (urlparse(link or "").hostname or "").lower().lstrip("www.")
    except Exception:
        pass
    if host in DOMAIN_HINTS:
        hits.append((15, DOMAIN_HINTS[host]))  # boost for domain
    if not hits:
        return "General"
    hits.sort(reverse=True)
    return hits[0][1]

def _scam_alerts(items):
    out = []
    for it in items:
        t = (it.get("title","") + " " + it.get("summary","")).lower()
        if any(k in t for k in SCAM_WORDS):
            out.append(it)
    return out[:10]

def _summary_fallback(items: list[dict]) -> str:
    # Quick deterministic "state of play" + a few headlines
    cats = Counter([_strong_rule_category(it.get("title",""), it.get("summary",""), it.get("source",""), it.get("link","")) for it in items[:40]])
    parts = [f"{c}: {n}" for c, n in sorted(cats.items(), key=lambda x: -x[1])]
    lines = ["Today’s senior news at a glance — " + "; ".join(parts) + "."]
    for it in items[:6]:
        title = it.get("title","").strip()
        src = it.get("source","").strip()
        if title: lines.append(f"- {title} ({src})")
    return "\n".join(lines)

# ---------------- Optional OpenAI (safe to omit) ----------------
async def _ai_categorize(items: list[dict]) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    batch = [{"id": it.get("id"), "title": it.get("title",""), "summary": it.get("summary","")} for it in items[:60]]
    prompt = (
        "Assign one short topic label to each item for older-adult news. "
        "Use only these buckets when possible: Medicare; Social Security; Finance & Retirement; Travel; Golf & Leisure; "
        "Cooking & Nutrition; Caregiving & LTC; Aging Research; Safety & Scams; Policy & Legislation; General. "
        "Return JSON object {id: label}.\nItems:\n" + json.dumps(batch, ensure_ascii=False)
    )
    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
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

async def _ai_summary(items: list[dict]) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    bullets = [f"• {it.get('title','')} — {(it.get('summary','') or '')[:200]}" for it in items[:16]]
    prompt = ("Summarize key developments for U.S. older adults in 120–180 words. "
              "Cover Medicare, Social Security, Finance/Retirement, Aging Research, Caregiving/LTC, Travel/Leisure, "
              "Cooking/Nutrition, and Safety/Scams if present. Neutral, precise, plain English. "
              "Provide 3–5 crisp bullets after the paragraph.\n\nHeadlines:\n" + "\n".join(bullets))
    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role":"user","content":prompt}],
        temperature=0.2,
        max_tokens=400,
    )
    return resp.choices[0].message.content.strip()

# ---------------- Main ----------------
def main():
    blob = {"updated": None, "items": []}
    if ITEMS_PATH.exists():
        blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    items = blob.get("items", [])

    # (Optional) AI label proposals
    ai_map = {}
    if OPENAI_API_KEY and items:
        try:
            import asyncio
            ai_map = asyncio.run(_ai_categorize(items))
        except Exception as e:
            print(f"[summarize] AI categorize failed: {e}; proceeding with rules only.")

    # Categorize deterministically + counts
    cat_counts = defaultdict(int)
    for it in items:
        title = it.get("title","")
        summary = it.get("summary","")
        source = it.get("source","")
        link = it.get("link","")
        raw = ai_map.get(it.get("id")) if ai_map else None
        bucket = _strong_rule_category(title, summary, source, link)
        it["subcategory"] = raw or bucket
        it["category"] = bucket
        cat_counts[bucket] += 1

    # Build summary text
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

    # Scam alerts
    alerts = _scam_alerts(items)

    # Persist categories back to items.json
    ITEMS_PATH.write_text(json.dumps({
        "updated": blob.get("updated"),
        "items": items
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write digest.json
    DIGEST_PATH.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "alerts": alerts,
        "category_counts": dict(sorted(cat_counts.items(), key=lambda x: -x[1]))
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[summarize] Categorized {len(items)} items across {len(cat_counts)} buckets.")
    top = list(dict(sorted(cat_counts.items(), key=lambda x: -x[1])).items())[:5]
    print(f"[summarize] Top buckets: {top}")

if __name__ == "__main__":
    main()
