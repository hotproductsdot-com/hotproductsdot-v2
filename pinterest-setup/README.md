# Pinterest Setup — hotproductsdot.com

Complete Pinterest playbook for driving Amazon affiliate traffic. Open files in this order:

| # | File | What it is | Time to use |
|---|------|-----------|-------------|
| 1 | **PINTEREST_PLAYBOOK.md** | Master strategy: profile setup, claim domain, Rich Pins, posting cadence, FTC disclosure, affiliate-link safety | 30 min read, 90 min execute |
| 2 | **BOARDS.csv** | 40 SEO-named boards with descriptions, mapped to your `/best/<category>` silos. Launch 5 in Week 1, expand 5/week | Open in Excel/Sheets, copy descriptions when creating boards |
| 3 | **PIN_DESCRIPTIONS.md** | Title formulas, 5-part description framework, keyword bank per niche, hashtag strategy, what the 2026 algorithm rewards | Reference when writing every pin |
| 4 | **CONTENT_CALENDAR.md** | 30-day starter schedule (~150 pins) — Day 1 of week 1 through optimization in week 4 | Drop into Pinterest's built-in scheduler each Sunday |
| 5 | **pin-templates.html** | 4 visual pin designs (Kitchen / Beauty / Tech / Fitness) — preview in browser, recreate in Canva at 1000×1500 | Open in any browser |
| 6 | **pinterest_poster_stub.py** | API integration scaffold mirroring `instagram/poster.py` shape — wire up after Pinterest API approval (3-5 days) | Read once you apply for API access |

## TL;DR — the first hour

1. Update display name to **"Hot Products | Best Amazon Finds & Gift Ideas"** (Pinterest weighs this in search).
2. Finish claiming `hotproductsdot.com` (you started this — see Step 1c in playbook).
3. Validate ONE product URL at `developers.pinterest.com/tools/url-debugger/` → unlocks Rich Pins for the whole site.
4. Create the 5 starter boards from `BOARDS.csv` (rows 1-5). Don't create more on Day 1.
5. Schedule your first 7 days of pins from `CONTENT_CALENDAR.md`.

## ⚠️ Important — affiliate link safety

You chose to pin direct Amazon affiliate links. That works, but Pinterest's spam filters will throttle (or ban) accounts that abuse it. The playbook covers the 3 rules in detail:

- Always disclose (`#affiliate` per pin + bio-level disclosure)
- Never repeat the same URL > 5×/day
- Even when "pinning direct," send 70% of pins to your own `/best/<category>` and `/products/<slug>` pages — they already enforce your `tag=hotproduct033-20` via `buildAffiliateUrl()` in `site/app/lib/affiliate.ts`, AND you keep the retargeting pixel + control if Pinterest changes policy.

## Integration with your existing stack

| What you have | How Pinterest plugs in |
|---------------|-------------------------|
| `post_daily.py` (Instagram + TikTok) | Add Pinterest poster (see `pinterest_poster_stub.py`) once API approved |
| `marketing/content_calendar.json` | Add a `pinterest` channel array; same shape as Instagram entries |
| `scripts/banner_compose.py` | Use to generate 1000×1500 pin variations (use `pin-templates.html` for layout reference) |
| `site/public/products/` | Pin images can pull straight from here once Rich Pins is live |
| `site/app/lib/affiliate.ts` | Already enforces affiliate tag — site-pin destinations are pre-tagged for free |

## Weekly rhythm

- **Sunday (90 min):** batch-schedule the next 7 days. Open Pinterest scheduler, paste descriptions from `PIN_DESCRIPTIONS.md` templates.
- **Wednesday (30 min):** review `Pinterest Analytics` → identify top performer → make 3 variations → schedule for weekend.
- **Monthly:** add 5 new boards from `BOARDS.csv` until all 40 are live (8 weeks).

## Success metrics

| Week | Target monthly views | Target outbound clicks |
|------|----------------------|------------------------|
| 1 | < 1,000 | < 10 |
| 4 | 5,000-10,000 | 50+ |
| 8 | 25,000-50,000 | 250+ |
| 12 | 100,000+ | 1,000+ |

Cross-reference with Amazon Associates → look for `ascsubtag=pin-*` rows to attribute revenue.
