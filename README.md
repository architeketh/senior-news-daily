# Senior News Daily

Daily, automated summaries of U.S. senior-related news (Medicare, Social Security, aging research, LTC, benefits, scams, safety, etc.).

## How it works
- `bot/fetch.py` pulls stories from trusted RSS feeds (AARP, CMS/Medicare, SSA, ACL/HHS, KFF Health News, NIA/NIH, CDC). It normalizes and deduplicates items.
- `bot/summarize.py` produces:
  - An **AI summary** if `OPENAI_API_KEY` is set (uses gpt-4o-mini in ~1K token mode), or
  - A **classical summary** (compact headlines) if no key is provided.
- `bot/site_builder.py` builds a static site with filter chips for **Today / Week / Month / Year**, a **Scam Alerts** focus box, and a dated archive page per day.
- GitHub Actions runs daily and deploys to GitHub Pages.

## Quick start
1) **Create repo** on GitHub → upload these files.
2) In repo → Settings → **Pages** → Build and deployment → Source: *GitHub Actions*.
3) (Optional) Add secret `OPENAI_API_KEY` → Settings → Secrets and variables → **Actions** → *New repository secret*.
4) Push to `main`. Actions will build and publish automatically.

## Local run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bot/fetch.py
python bot/summarize.py
python bot/site_builder.py
```
The site output appears in `site/`. Commit and push to publish.

## Feeds
See `data/feeds.yaml` to customize. Add/remove feeds as needed.

## License
MIT.
