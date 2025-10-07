# bot/summarize.py
import os, json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from dateutil import parser as dtp

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INP = DATA / "items.json"
OUT = DATA / "digest.json"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

CATEGORIES = {
    "Medicare & Health Policy": ["medicare", "medicaid", "drug", "rx", "cms", "price", "premium"],
    "Social Security & Benefits": ["social security", "ssa", "cola", "benefit", "pension", "ssi"],
    "Aging & Research": ["aging", "alzheim", "dementia", "nia", "falls", "longevity"],
    "Caregiving & LTC": ["caregiver", "nursing home", "long-term care", "ltc"],
    "Safety, Scams & Consumer": ["scam", "fraud", "safety", "recall"],
}

SCAM_WORDS = ["scam", "fraud", "phishing", "impersonation", "robocall", "spoof", "identity theft", "elder abuse"]

def _is_today(dt_iso: str) -> bool:
    if not dt_iso:
        return False
    dt = dtp.parse(dt_iso)
    today = datetime.now(timezone.utc).date()
    return dt.date() == today

def _bucket(title: str, summary: str) -> str:
    t = (title + "\n" + summary).lower()
    for b, keys in CATEGORIES.items():
        if any(k in t for k in keys):
            return b
    return "General"

def _classical_summary(items: list[dict]) -> str:
    lines = []
    cats = defaultdict(int)
    for it in items[:16]:
        cats[_bucket(it.get("title",""), it.get("summary",""))] += 1
    parts = [f"{c}: {n}" for c, n in sorted(cats.items(), key=lambda x: -x[1])]
    lines.append("Today’s senior news at a glance — " + "; ".join(parts) + ".")
    for it in items[:6]:
        title = (it.get("title", "").strip())
        src = (it.get("source", "").strip())
        lines.append(f"- {title} ({src})")
    return "\n".join(lines)

async def _openai_summary_async(items: list[dict]) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    bullets = []
    for it in items[:16]:
        bullets.append(f"• {it.get('title','')} — {it.get('summary','')[:200]}")
    prompt = (
        "You are a senior policy news editor. Summarize the key developments for U.S. older adults "
        "in 120-180 words. Cover Medicare/CMS, Social Security/SSA, aging research (NIA/NIH), "
        "caregiving/LTC, and safety/scams if present. Write neutral, precise, plain English. "
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
    data = json.loads(INP.read_text(encoding="utf-8")) if INP.exists() else {"items": []}
    items = data.get("items", [])
    today_items = [it for it in items if _is_today(it.get("published") or it.get("fetched"))]

    # Category tagging + counts
    category_counts = defaultdict(int)
    for it in items:
        cat = _bucket(it.get("title",""), it.get("summary",""))
        it["category"] = cat
        category_counts[cat] += 1

    if OPENAI_API_KEY:
        try:
            import asyncio
            summary = asyncio.run(_openai_summary_async(today_items or items))
        except Exception as e:
            print(f"[summarize] OpenAI failed: {e}; falling back.")
            summary = _classical_summary(today_items or items)
    else:
        summary = _classical_summary(today_items or items)

    # Scam alerts (recent top 10 by appearance order)
    def is_scam(it):
        t = (it.get("title","") + " " + it.get("summary","")).lower()
        return any(k in t for k in SCAM_WORDS)
    alerts = [it for it in items if is_scam(it)][:10]

    OUT.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "alerts": alerts,
        "category_counts": dict(sorted(category_counts.items(), key=lambda x: -x[1]))
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[summarize] Wrote digest → {OUT}")

if __name__ == "__main__":
    main()
