# Integration Plan: Slickdeals + Woot + DailySteals → hotproductsdot.com

## Goal

Pull the highest-converting, most-engaging mechanics from three deal sites into the existing silo architecture (homepage → /best → /category → /products) **without** breaking the affiliate-site model. We're not running inventory, so anything that depends on real stock (Woot's "27 left") gets adapted into proxy signals (popularity score, recency, savings tier).

## What each site does best

### Slickdeals — community-validated deal credibility
The win is *trust by aggregation*. You don't browse Slickdeals to find a product, you browse it to find deals other shoppers already vetted. Concrete mechanics worth stealing:

- **Heat / temperature score** on every deal — single number that conveys "this is good"
- **Frontpage badge** — editorial curation layered on top of community signal
- **Price history** — a small graph that answers "is this actually a low price?" before the click
- **Deal alerts by keyword/category** — email/push when a matching deal goes live
- **Filters that match deal-shopper intent** — by % off, store, category, freshness, popularity
- **Comments / Q&A under each deal** — social proof and crowdsourced caveats
- **Expired vs. live treatment** — expired deals are dimmed but not deleted (SEO and history)

### Woot — urgency and personality
Woot turns shopping into entertainment. The page itself is the campaign. Concrete mechanics:

- **One hero deal per day** with countdown to midnight
- **"% sold" inventory bar** as a fear-of-missing-out trigger
- **Distinct, irreverent voice** in product copy — the deck reads like a friend texting you, not a spec sheet
- **Single-product landing page** with no distractions above the CTA
- **"Sold out" / "Sellout" treatments** that still rank well and capture reorder intent
- **Wacky surprise category** (Bag of Crap) as a recurring traffic event

### DailySteals — clean discount-first card layout
Less unique mechanics, but a very disciplined card UI:

- **Giant % off badge** in the corner — the discount is the headline
- **Original price struck-through next to sale price** — math done for the shopper
- **"Today's Deal" hero** with countdown — same urgency play as Woot, simpler execution
- **Category filter chips** above a tight grid
- **Email capture for the daily deal** — primary list-building move
- **Sold-out treatment** that keeps the card visible (SEO retention)

---

## What we adopt, adapt, or skip

| Feature | Source | Decision | Adaptation for an affiliate site |
|---|---|---|---|
| Heat / popularity score | Slickdeals | **Adopt** | Compute algorithmically (no user voting yet) — see "Heat Score" below |
| Frontpage editorial badge | Slickdeals | **Adopt** | Manual flag in `top-1000.csv` (`featured` column) |
| Price history chart | Slickdeals | **Adopt** | We already have Oxylabs price snapshots — log to a `price_history.csv` and render a sparkline |
| Deal alerts by category | Slickdeals | **Adopt** | Newsletter signup with category preference; delivers digest, not real-time |
| Filters (discount, price, recency) | Slickdeals | **Adopt** | Client-side filter bar on `/category/[slug]` and a new `/deals` page |
| Comments / community | Slickdeals | **Skip for now** | Moderation cost is too high for affiliate-site margins. Revisit at scale |
| Daily Deal of the Day | Woot | **Adopt** | New `/today` route + homepage hero. Pick algorithmically from highest-heat product daily |
| Countdown timer | Woot | **Adopt** | Counts to midnight UTC; resets daily. Pure UI, no inventory tied to it |
| Inventory bar ("% sold") | Woot | **Adapt** | Reframe as "Popularity" bar driven by heat score, not stock |
| Irreverent copy voice | Woot | **Adopt selectively** | New optional `quip` field per product; falls back to standard description if empty |
| Single-product focused page | Woot | **Already have** | `/products/[slug]` already does this. Polish CTA placement to match Woot density |
| Sold-out treatment | Woot/DailySteals | **Adapt** | Use for products where Oxylabs reports "unavailable" — dim the card, swap CTA to "Notify when back" (email capture) |
| Big % off badge | DailySteals | **Adopt** | Compute `(list - sale) / list` from Oxylabs `Price Range`; render only when ≥15% |
| Strikethrough original price | DailySteals | **Adopt** | Card and product page |
| Email capture for daily deal | DailySteals | **Adopt** | Same form as Slickdeals-style alerts; one list, multiple preferences |
| Wacky surprise drop | Woot ("Bag of Crap") | **Skip** | Doesn't fit Amazon affiliate model — we can't ship a mystery box |

---

## The one new primitive: the Heat Score

A single 0–100 score per product, computed at build time from signals you already collect. Replaces the need for user voting on day one and powers the Daily Deal pick, the popularity bar, the default sort, and the homepage rotation.

Suggested inputs (tune weights after launch):

- **Discount depth** (40%) — `(list_price - current_price) / list_price`
- **Rating × review count** (25%) — Bayesian average so a 5.0 with 3 reviews doesn't beat a 4.6 with 8,000
- **Recency of price drop** (20%) — products whose price fell in the last 7 days score higher
- **Click data** (15%) — once you have it; until then, distribute weight to discount

Store as a `heat_score` column on `top-1000.csv`. Recompute in `prebuild.js` so it lands in `products.json` for static rendering.

---

## Implementation plan — phased

### Phase 1 — Card and page polish (1–2 days, no new infra)
The cheap, high-leverage UI work that makes the existing site *feel* like a deal site.

1. **Product card redesign** — add corner `% off` badge, strikethrough original price, optional "Hot" flame icon when `heat_score ≥ 80`
2. **Sold-out treatment** — dim card + "Currently unavailable" pill when Oxylabs returned no live price
3. **Compute `heat_score`** in `prebuild.js` and write to `products.json`
4. **Default sort** on `/category/[slug]` and `/products` switches from alphabetical to heat-descending
5. **Filter bar** on category pages: `% off`, `price range`, `rating`, `sort by` (heat / price / newest)

**Files touched:** `site/app/components/ProductCard.tsx` (or equivalent), `site/app/category/[slug]/page.tsx`, `site/app/products/page.tsx`, `prebuild.js`

### Phase 2 — Daily Deal route (2–3 days)
The Woot/DailySteals hero play. New page + homepage block.

1. **`/today` route** — single highest-heat product not featured in the last 30 days
2. **Daily deal selector** — script run by GitHub Actions cron at 00:01 UTC; writes the chosen ASIN to `today_deal.json`
3. **Countdown component** — JS countdown to next 00:00 UTC, then auto-refresh
4. **Popularity bar** (not inventory bar) — `heat_score / 100` filled, label reads "Popularity" not "Sold"
5. **Homepage hero swap** — current Hot Deals block keeps its row, but a single "Today's Deal" panel goes above it
6. **Yesterday's Deal archive** — `/today/[date]` for SEO long-tail and to avoid 404s on shared links after midnight

**Files touched:** new `site/app/today/page.tsx`, new `site/app/today/[date]/page.tsx`, new `site/app/components/Countdown.tsx`, new `site/app/components/PopularityBar.tsx`, `site/app/page.tsx`, new `scripts/pick_daily_deal.py`, `.github/workflows/daily-deal.yml`

### Phase 3 — Price history (3–5 days)
The Slickdeals trust play. Most engineering of any phase because it needs persistent data over time.

1. **Price history log** — extend `oxylabs-amazon-product.sh` to append every observation to `products/price_history.csv` (asin, date, price)
2. **Sparkline component** — small inline SVG chart, last 90 days; on product page only
3. **"Lowest price in 30 days" badge** — computed from history, shown when current price ≤ min(30d)
4. **History endpoint** — static JSON per ASIN at build time so the chart loads without an API call

**Files touched:** `oxylabs-amazon-product.sh`, new `scripts/build_price_history.py`, new `site/app/components/PriceSparkline.tsx`, `site/app/products/[slug]/page.tsx`, `prebuild.js`

### Phase 4 — Email alerts (3–5 days)
The list-building play that all three sites do. Standalone subsystem.

1. **Signup form** — embed on homepage, `/today`, and footer; collects email + category preferences
2. **Storage** — start with a hosted ESP (ConvertKit, Beehiiv, Buttondown) so we don't run our own list infra
3. **Daily digest** — cron-triggered job picks top 5 heat-scored products per category and sends per-preference
4. **Double opt-in** — required for CAN-SPAM/GDPR
5. **Unsubscribe + preference center** — handled by the ESP

**Decision needed:** which ESP? Recommend Beehiiv (free tier to 2,500 subs, decent deliverability, good API).

### Phase 5 — Voice and editorial flair (ongoing)
The Woot personality play. No engineering, all content.

1. **Add `quip` field** to `top-1000.csv` (optional, one sentence, irreverent)
2. **Render below the title** on product cards and pages when present
3. **Style guide** — three sentences max, never punching down, no fake urgency, no ALL CAPS
4. **Backfill priority** — top 100 by heat score first

---

## What this changes in your existing architecture

The silo structure stays intact. Two new top-level routes get added and the homepage gets reordered:

```
/                             Homepage
├── /today                    ⭐ NEW — Woot-style daily deal
├── /today/[date]             NEW — archive of past daily deals
├── /deals                    NEW — Slickdeals-style filtered feed (heat-sorted, filterable)
├── /products                 (unchanged)
├── /best/[category]          (unchanged — money pages still rank)
├── /category/[category]      (gains filter bar + heat sort)
└── /products/[slug]          (gains price sparkline + popularity bar + quip)
```

Updated homepage section order:

1. Hero (brand)
2. **Today's Deal** (new — single Woot-style hero)
3. **Email signup** (new — small inline bar)
4. Hot Deals (existing, now heat-sorted)
5. Top Picks
6. Best Category Guides (unchanged — these are the SEO money pages)
7. Browse All Categories
8. Trust strip

---

## Risks and trade-offs to flag before starting

- **FTC compliance** — countdown timers and "popularity" bars edge toward dark patterns if the underlying urgency is fake. The countdown to midnight is real (the deal does rotate); the popularity bar must be labeled clearly so it isn't read as inventory. Keep your existing FTC disclosure prominent on `/today`.
- **Amazon Operating Agreement** — affiliates can't display Amazon prices that may be stale. You already use "Check Price" copy on existing pages; the strikethrough discount badge needs the same hedge ("List $X / Recently $Y — check current price"). Don't show a precise current price next to a precise list price unless you've refreshed via Oxylabs that day.
- **Price history accuracy** — sparkline is only as good as the cadence of `oxylabs-amazon-product.sh`. Daily runs are ideal; weekly is the floor. Anything sparser and the chart misleads.
- **Heat score drift** — without click data, the formula leans heavily on discount, which means a $200 product with a 40% off list price will always outrank a perennial $25 best-seller. Plan to add click weighting (Phase 1.5) once you've got 4+ weeks of analytics.
- **Build time** — heat score and price history both run in `prebuild.js`. With 1,000 products this is fine; if the catalog grows past 5,000 you'll want to move computation to a separate cron and just read the result at build.
- **Daily deal staleness** — if the cron fails to pick a new deal, the page goes stale silently. Add a freshness check in `prebuild.js` that fails the build if `today_deal.json` is older than 25 hours.

---

## Suggested order if you only have a week

Day 1–2: Phase 1 (card polish + heat score + filters) — biggest visual lift, no new pages
Day 3–4: Phase 2 (daily deal route) — the marquee feature
Day 5: Phase 5 starter (write 25 quips for top products) — costs nothing, ships personality
Phase 3 (price history) and Phase 4 (email) wait for week 2.

---

## Open questions for you

1. Are you OK with adding a third-party email service (Beehiiv recommended), or do you want to build list infra in-repo?
2. Do you want the daily deal picked algorithmically only, or do you want a manual override flag in the CSV so you can pin a specific product?
3. How aggressive should the voice be? Woot-level snark, or one-step dialed back for SEO neutrality?
4. Should `/today` and `/deals` carry the existing affiliate CTA pattern ("Check Price on Amazon"), or do we want a tighter button treatment matched to Woot's single big orange button?
