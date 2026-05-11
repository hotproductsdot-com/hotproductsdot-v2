# Growth Engine — BabyLoveGrowth Clone for hotproductsdot.com

A self-hosted Python automation suite that replicates the four core services of
[babylovegrowth.ai](https://www.babylovegrowth.ai/) for a single site —
**hotproductsdot.com**. Powered by Claude (Anthropic) using forced tool-use for
guaranteed structured output, plugs into the existing Next.js site, CSV product
database, and rsync deploy pipeline.

## What it does

| BabyLoveGrowth feature        | Local equivalent                                       | Script                          |
|-------------------------------|--------------------------------------------------------|---------------------------------|
| 30-day content plan           | Competitor + SERP gap analysis → JSON brief queue      | `scripts/1_keyword_research.py` |
| Daily SEO + LLM articles      | Claude-written guides → `site/content/guides-generated/` | `scripts/2_generate_article.py` |
| Backlink exchange network     | Outreach prospect finder + email drafter (SQLite)      | `scripts/3_backlink_finder.py`  |
| AI visibility tracker         | Polls Claude/GPT/Perplexity for brand citations        | `scripts/4_ai_visibility.py`    |
| Auto-publish to CMS           | `git commit` + optional `npm run deploy:rsync`         | `scripts/5_publish.py`          |
| Facebook Page posting         | Posts new article link to Facebook Page feed via Graph API | `scripts/6_facebook_post.py` |
| Whole thing on autopilot      | 3× daily orchestrator + Windows Task Scheduler installer | `scripts/run_daily.py`        |

## Architecture

```
growth-engine/
├── config.yaml                 # site facts, target categories, schedule
├── requirements.txt
├── .env.example                # API keys (also see repo root .env)
│
├── scripts/                    # numbered for run order
│   ├── 1_keyword_research.py   # builds content_plan.json
│   ├── 2_generate_article.py   # writes one article
│   ├── 3_backlink_finder.py    # adds prospects to SQLite
│   ├── 4_ai_visibility.py      # logs LLM citations
│   ├── 5_publish.py            # commit + push + (optional) deploy
│   ├── 6_facebook_post.py      # posts new article to Facebook Page feed
│   └── run_daily.py            # runs all six in sequence
│
├── lib/
│   ├── claude_client.py        # Anthropic SDK wrapper, with forced tool-use
│   ├── seo.py                  # Tavily + Serper SERP API
│   ├── article_template.py     # JSON guide builder (matches site schema)
│   ├── publish.py              # git operations
│   ├── tracking.py             # SQLite for visibility + backlink pipeline
│   ├── site_inspector.py       # reads products CSV + existing guide slugs
│   └── facebook.py             # Facebook Graph API — post link to Page feed
│
├── data/                       # generated, gitignored
│   ├── content_plan.json
│   ├── ai_visibility.db
│   ├── backlinks.db
│   ├── visibility_report.html
│   └── published.json
│
└── windows/
    ├── run_daily.bat           # entry point for Task Scheduler
    ├── install_task.ps1        # one-line scheduled-task installer
    └── INSTALL_TASK_SCHEDULER.md
```

## How it integrates with the Next.js site

- Articles are JSON files at `site/content/guides-generated/<slug>.json`,
  matching the same `Guide` schema the site already uses for inline guides.
- `site/app/lib/guides.ts` was extended with a `loadGeneratedGuides()` helper
  that merges those JSON files with the inline `guides` array. The merge
  prefers inline guides on slug collision so editorial overrides win.
- `site/scripts/build-smart.js` watches `site/content/guides-generated/` so
  the incremental build correctly invalidates when the engine adds an article.
- `sitemap.ts` and `app/guides/[slug]/page.tsx` already call `getAllGuides()`,
  so generated articles automatically appear in `/guides`, `/guides/[slug]`,
  and `sitemap.xml` — no further wiring required.

## Quick start

```bash
# 1. Install deps once
cd growth-engine
pip install -r requirements.txt
# ANTHROPIC_API_KEY is read from repo root .env

# 2. Build a 30-day content plan
python scripts/1_keyword_research.py

# 3. Write today's article (drops a JSON in site/content/guides-generated/)
python scripts/2_generate_article.py

# 4. Inspect — open the JSON, scan headings, edit if you want
ls ../site/content/guides-generated/

# 5. When ready, ship it
python scripts/5_publish.py --include-guides-ts --deploy
```

## Daily autopilot

```powershell
# One-line install (run from elevated PowerShell)
cd growth-engine\windows
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
```

Three times per day (7 AM, 12 PM, 6 PM) the orchestrator runs:

1. Refresh the content plan if it's older than 30 days.
2. Generate one new article and write it to `site/content/guides-generated/`.
3. Run AI visibility checks for tracked queries (Claude / GPT / Perplexity).
4. Find two new backlink prospects.
5. Commit to git. If `schedule.auto_deploy: true` in `config.yaml`,
   also run `npm run deploy:rsync`.
6. Post the new article to the Facebook Page feed via `6_facebook_post.py`.

## Deploying after a new article

The site uses an **incremental** smart-builder (`site/scripts/build-smart.js`)
that hashes a `watchedPaths` list and skips rebuilds when nothing's changed.
The engine's `site/content/guides-generated/` is in that list, so a new JSON
file there triggers a real Next.js rebuild.

Two ways to deploy:

```bash
# A) From the engine — commits the article + loader, then rsyncs
python scripts/5_publish.py --include-guides-ts --deploy

# B) From the site — explicit Next.js build then rsync
cd ../site
npm run deploy:rsync
```

If you ever suspect the smart-build is reusing a stale `out/`, force a clean
rebuild:

```bash
cd site
rm -rf .next out
npm run build
npm run deploy:rsync
```

## Costs

At default settings (1 article/day, 5 visibility queries, 2 backlink searches):

- Claude Sonnet 4.6 (article + planner + scorer): ~$0.30–$0.60/day
- GPT-4o-mini (visibility check, optional): ~$0.05/day
- Perplexity (visibility check, optional): ~$0.05/day
- **Total: ~$10–$20/month** vs $99/month for BabyLoveGrowth

## Why tool-use instead of plain JSON prompting

Earlier versions asked Claude to "reply with JSON only" and parsed the text
response. Claude reliably returned JSON, but **not always with the same
shape** — sometimes a list, sometimes `{"briefs": [...]}`, sometimes
`{"keywords": [...]}` with strings instead of objects. Every shape variation
was a silent break.

All three Claude callers (planner, article generator, backlink scorer) now
use Anthropic's `tool_choice` feature to force Claude to invoke a single
named tool with a strict JSONSchema. The API itself rejects any response that
violates the schema, so structure drift is impossible. See
`lib/claude_client.py::complete_with_tool()`.

## Safety and review gates

- Articles land in `site/content/guides-generated/` (separate from existing
  inline guides) — nothing existing breaks if a generated article is bad.
- Every script accepts `--dry-run` (or `GROWTH_ENGINE_DRY_RUN=1` env var)
  for testing without burning API credits.
- `5_publish.py` requires `--deploy` to actually run rsync — no auto-ship.
- Outreach emails are **drafted but never sent** — they sit in
  `data/backlinks.db` for manual review. Use
  `python scripts/3_backlink_finder.py --export` to dump them to CSV.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ANTHROPIC_API_KEY is not set` | Add it to `E:\GITHUB\hotproductsdot-v2\.env` |
| Planner: `Expected JSON list of briefs, got <dict>` | You're on an old version — the current scripts use forced tool-use. `git pull` and retry. |
| `[publish] Nothing new to commit` but article exists | First commit: `git add -f site/content/guides-generated/<slug>.json && git commit -m "first article"`. Subsequent runs work normally. |
| New article doesn't show on the deployed site | Smart-build cached. `cd site && rm -rf .next out && npm run build && npm run deploy:rsync` |
| `npm run deploy:rsync` errors with "Could not resolve hostname" | Set up the `hotproducts` SSH host alias in `~/.ssh/config` |
| `disk I/O error` from sqlite | Filesystem mount issue. The DBs live in `data/` — check write permissions. |

## Files this engine touches in the existing repo

This is the complete list of edits the engine makes outside its own directory:

1. `site/app/lib/guides.ts` — adds `loadGeneratedGuides()` merge logic.
2. `site/scripts/build-smart.js` — adds `site/content/guides-generated/` to
   `watchedPaths`.
3. `site/content/guides-generated/*.json` — new directory the engine writes to.

That's it. The original five inline guides, the products CSV, the
`/best/[category]` money pages, and your deploy pipeline are untouched.
