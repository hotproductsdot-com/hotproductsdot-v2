---
name: hotproducts-growth
description: "Operate the hotproductsdot growth-engine: SEO articles, deals, Facebook posts, AI visibility."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [growth-engine, seo, affiliate, hotproductsdot]
    related_skills: [pantheon]
---

# HotProducts Growth Engine

Autonomous SEO/content pipeline for hotproductsdot.com.

## Layout

```
growth-engine/
├── config.yaml          # Site facts, categories, models
├── scripts/run_daily.py # Main orchestrator (runs all steps)
├── scripts/1_keyword_research.py
├── scripts/2_generate_article.py
├── scripts/3_backlink_finder.py
├── scripts/4_ai_visibility.py
├── scripts/5_publish.py
├── scripts/6_facebook_post.py
├── scripts/7_deal_finder.py
└── web_ui.py            # Deal poster UI (port 5050)
```

## Common commands (from repo root, WSL)

```bash
cd /mnt/e/GITHUB/hotproductsdot-v2/growth-engine
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate

# Full daily run (dry-run safe)
python scripts/run_daily.py --dry-run

# Individual steps
python scripts/2_generate_article.py
python scripts/7_deal_finder.py
python web_ui.py  # http://localhost:5050
```

## Schedule

3× daily via Windows Task Scheduler or GitHub Actions:
- 7 AM, 12 PM, 6 PM (see growth-engine/windows/install_task.ps1)

## Mercury autopilot checks

When running as Mercury persona, report:
1. Last run timestamp from `growth-engine/data/published.json`
2. Content plan queue depth from `growth-engine/data/content_plan.json`
3. Deal count from `growth-engine/data/deals.json`
4. Any errors in recent logs

## Safety

- Always use `--dry-run` when testing publish/deploy steps
- `auto_deploy: false` in config.yaml — never rsync without explicit user OK
- API keys live in repo-root `.env` (never commit)
