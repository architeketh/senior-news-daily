# bot/summarize.py
"""
Summarize + Categorize (expanded categories)
- Reads data/items.json
- Assigns robust categories including:
  Finance & Money; Travel & Leisure; Outdoors; People; Politics; Retail Trends
  (plus Medicare, Social Security, Safety & Scams, Caregiving & LTC, Aging Research,
   Exercise & Fitness, Cooking & Nutrition, Policy & Legislation, General)
- Writes categories back to items.json
- Writes digest.json with summary + scam alerts
"""

import json, re, pathlib, datetime
from collections import Counter
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ITEMS_PATH = DATA / "items.json"
DIGEST_PATH = DATA / "digest.json"

# ---------- Category rules (priority order) ----------
CATEGORY_RULES = [
    ("Safety & Scams", [
        r"\b(scams?|fraud|phish(?:ing)?|robocalls?|spoof(?:ing)?|identity theft|elder abuse)\b",
    ]),
    ("Medicare", [
        r"\bmedicare\b", r"\bpart\s*[abcd]\b", r"\bmedigap\b", r"\bcms\b",
        r"\b(premium|deductible|copay|prior authorization)s?\b",
    ]),
    ("Social Security", [
        r"\bsocial security\b", r"\bssa\b", r"\bssdi\b", r"\bssi\b", r"\bcola\b",
    ]),
    ("Finance & Money", [
        r"\bfinance\b", r"\bmoney\b", r"\bbudget(ing)?\b", r"\bsavings?\b", r"\btaxes?\b",
        r"\binvest(ment|ing|or)\b", r"\b401k\b", r"\b403b\b", r"\bira(s)?\b", r"\bpension(s)?\b",
        r"\bannuities?\b", r"\brequired minimum distribution\b|\brmds?\b",
    ]),
    ("Retail Trends", [
        r"\b(retail|grocery|shopping|consumer spending|foot traffic|store openings?|closures?)\b",
        r"\b(inflation|prices?)\b", r"\bpharmacy\b", r"\b(Walmart|Target|Costco|Amazon|CVS|Walgreens)\b",
    ]),
    ("Politics", [
        r"\b(congress|senate|house|white house|campaign|election|bipartisan)\b",
        r"\bpolitic(s|al)\b", r"\b(bill|act|amendment)\b",
    ]),
    ("Policy & Legislation", [
        r"\b(legislation|rule[-\s]?making|proposed rule|regulation|final rule)\b",
        r"\b(hhs|cms|acl|oig|nih|ftc|doj)\b",
    ]),
    ("Travel & Leisure", [
        r"\btravel(s|ing)?\b", r"\btrip(s)?\b", r"\bvacation(s)?\b", r"\bcruise(s)?\b",
        r"\bhotel(s)?\b", r"\bdestination(s)?\b", r"\bitinerary\b", r"\btour(s)?\b",
        r"\bleisure\b", r"\bentertainment\b",
    ]),
    ("Outdoors", [
        r"\boutdoor(s)?\b", r"\bhik(e|ing)\b", r"\btrail(s)?\b", r"\bpark(s)?\b",
        r"\bgarden(ing)?\b", r"\bnature\b", r"\bfishing\b", r"\bcamping\b", r"\bgolf(ing)?\b",
    ]),
    ("Exercise & Fitness", [
        r"\bexercise\b", r"\bfitness\b", r"\bworkout(s)?\b", r"\bwalking\b", r"\byoga\b", r"\bstretch(ing)?\b",
    ]),
    ("Cooking & Nutrition", [
        r"\bcook(ing)?\b", r"\brecipe(s)?\b", r"\bnutrition(al)?\b", r"\bdiet(ary)?\b", r"\bfood\b", r"\bmeal(s)?\b",
    ]),
    ("Caregiving & LTC", [
        r"\bcaregiving\b", r"\bcaregiver(s)?\b", r"\blong[-\s]?term care\b|\bltc\b",
        r"\bnursing home(s)?\b", r"\bhome health\b", r"\brespite\b",
    ]),
    ("Aging Research", [
        r"\baging\b", r"\blongevity\b", r"\balzheim(?:er'?s)?\b", r"\bdementia\b",
        r"\bclinical trial(s)?\b", r"\bnia\b|\bnih\b",
    ]),
    ("People", [
        r"\bprofile\b", r"\binterview\b", r"\bcentenarian\b", r"\bturns\s+\d{2,}\b",
        r"\bobituar(y|ies)\b", r"\bhonors?\b", r"\bcelebrates?\b",
        r"\bcommunity spotlight\b|\bhuman interest\b",
    ]),
]

DOMAIN_HINTS = {
    # Finance & Money / Retail
    "cnbc.com": "Finance & Money",
    "kiplinger.com": "Finance & Money",
    "nerdwallet.com": "Finance & Money",
    "wsj.com": "Finance & Money",
    "retaildive.com": "Retail Trends",
    "supermarketnews.com": "Retail Trends",
    "grocerydive.com": "Retail Trends",
    # Travel & Leisure / Outdoors
    "travelandleisure.com": "Travel & Leisure",
    "lonelyplanet.com": "Travel & Leisure",
    "cntraveler.com": "Travel & Leisure",
    "nationalparkstraveler.org": "Outdoors",
    # Cooking
    "eatingwell.com": "Cooking & Nutrition",
    "allrecipes.com": "Cooking & Nutrition",
    "foodnetwork.com": "Cooking & Nutrition",
    # Exercise
    "verywellfit.com": "Exercise & Fitness",
    # Medicare / Social Security / Policy
    "kff.org": "Medicare",
    "kffhealthnews.org": "Medicare",
    "cms.gov": "Medicare",
    "ssa.gov": "Social Security",
    "hhs.gov": "Policy & Legislation",
    "ftc.gov": "Safety & Scams",
    "justice.gov": "Safety & Scams",
}

SCAM_TERMS = ["scam", "fraud", "phishing", "robocall", "spoof", "identity theft", "elder abuse"]

_COMPILED = [(name, [re.compile(p, re.IGNORECASE) for p in pats]) for name, pats in CATEGORY_RULES]

def _category_for(title: str, summary: str, source: str, link: str) -> str:
    text = " ".join(x for x in [title or "", summary or "", source or ""] if x)
    for bucket, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return bucket
    try:
        host = (urlparse(link or "").hostname or "").lower().lstrip("www.")
        if host in DOMAIN_HINTS:
            return DOMAIN_HINTS[host]
    except Exception:
        pass
    return "General"

def _summary(items):
    counts = Counter(it.get("category", "General") for it in items)
    if not counts:
        return "No major updates today."
    parts = ", ".join(f"{c} ({n})" for c, n in counts.most_common(5))
    return f"Today’s highlights by topic — {parts}."

def _alerts(items):
    out = []
    for it in items:
        blob = (it.get("title","") + " " + it.get("summary","")).lower()
        if any(k in blob for k in SCAM_TERMS):
            out.append(it)
    return out[:10]

def main():
    blob = {"items": []}
    if ITEMS_PATH.exists():
        blob = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    items = blob.get("items", [])

    # Categorize
    for it in items:
        it["category"] = _category_for(
            it.get("title",""), it.get("summary",""), it.get("source",""), it.get("link","")
        )

    # Write back items with categories
    ITEMS_PATH.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Digest
    digest = {
        "generated": datetime.datetime.utcnow().isoformat(),
        "summary": _summary(items),
        "alerts": _alerts(items),
    }
    DIGEST_PATH.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[summarize] Wrote digest with {len(items)} items.")

if __name__ == "__main__":
    main()
