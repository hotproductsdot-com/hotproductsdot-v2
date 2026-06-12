# hotproductsdot-v2

Affiliate product site built with Next.js 16. Lists top 1000 products with images, prices, categories, and Amazon affiliate links.

---

## Project Structure

```
hotproductsdot-v2/
├── site/                        # Next.js 16 app (the website)
├── products/
│   ├── top-1000.csv             # Product database (name, price, category, ASIN)
│   └── products4review.csv      # Oxylabs CSV vs live diffs (created/updated by script)
├── growth-engine/               # AI SEO autopilot — see growth-engine/README.md
├── oxylabs-amazon-product.sh    # Batch Oxylabs check; backs up & updates top-1000.csv
├── fetch_daily_deals.py         # Daily Limited Time Sale pipeline (discover → verify → CSV swap)
├── run_daily_deals.sh           # Cron wrapper: runs fetch_daily_deals.py in a git worktree, commits + pushes
├── site/public/products/        # Downloaded product images (.jpg)
├── site/content/guides-generated/   # JSON guides written by growth-engine
├── perform_qualityassurance.sh  # Full QA pipeline
├── *.js                         # JS utility scripts (run from project root)
└── *.py                         # Python utility scripts (run from project root)
```

---

## Growth Engine (BabyLoveGrowth clone)

Self-hosted AI SEO autopilot at [`growth-engine/`](growth-engine/README.md).
Replaces a $99/month BabyLoveGrowth subscription with ~$10–$20/month in API costs.

- Daily Claude-written buying guides committed to the site
- AI visibility tracking across Claude / GPT / Perplexity
- Backlink prospect finder + outreach email drafter
- 30-day content planner driven by SERP gap analysis
- Windows Task Scheduler installer for full autopilot

```bash
cd growth-engine
pip install -r requirements.txt
python scripts/run_daily.py             # full pipeline
python scripts/2_generate_article.py    # just write one article
python scripts/5_publish.py --include-guides-ts --deploy   # ship it
```

See [`growth-engine/README.md`](growth-engine/README.md) for full details,
architecture, troubleshooting, and the daily-autopilot installer.

---

## Data quality (images, prices, links)

**Honest expectation:** “100% correct” against live Amazon at all times is not something any static site can guarantee without continuous automated checks and manual review. This repo uses a **defense-in-depth** approach:

| Area | How it stays accurate | You should still… |
|------|------------------------|-------------------|
| **Affiliate links** | `site/app/lib/affiliate.ts` enforces `AFFILIATE_TAG` on outbound Amazon URLs; product CTAs use `buildAffiliateUrl()` | Run `python fix_amazon_urls.py --audit` and fix rows missing `/dp/` ASINs; spot-check links after CSV edits |
| **Prices** | CSV is the source of truth; copy on pages says prices may change | Run `./oxylabs-amazon-product.sh --limit 20` (or without `--limit` for full refresh) before big launches; rerun after bulk catalog updates |
| **Images** | Local files under `site/public/products/` override Amazon CDN; **cache-busting** `?v=<file-mtime>` is appended on build so **replacing an image file and redeploying** yields a new URL (fixes “old image in every browser”) | After replacing a `.jpg`, run a full site build + deploy so `products.json` / HTML pick up the new query string |

**Stale images after deploy (browsers showing old art):**  
That happens when the **URL stays identical** and caches reuse the file. The site now adds **`?v=<mtime>`** to local `/products/*.jpg` and `/products/*.svg` URLs at prebuild time, so each image replacement changes the query string and forces a fresh fetch. If anything still looks wrong, hard-refresh once or clear site data for your domain.

---

## QA Pipeline

Run this before every deployment to lint, check images, and build. Price / rating / review validation is **not** part of QA (each Oxylabs API call has a cost) — run `./oxylabs-amazon-product.sh` manually before launches.

```bash
./perform_qualityassurance.sh
```

**Steps:**

| Step | Check | On Failure |
|------|-------|------------|
| 1 | ESLint — static code analysis | Hard stop |
| 2 | Price validation | Skipped — run `./oxylabs-amazon-product.sh` manually |
| 3 | Image check | Hard stop if 10+ missing |
| 4 | Production build | Hard stop |

---

## Site Commands

Run from the `site/` directory (`cd site`):

| Command | Description |
|---------|-------------|
| `npm run dev` | Start local development server with hot reload at http://localhost:3000 |
| `npm run build` | Compile and bundle via stable webpack build; skips rebuild if no inputs changed |
| `npm run build:fast` | Compile and bundle via Turbopack for faster builds |
| `npm run start` | Serve the production build locally (requires `build` first) |
| `npm run lint` | Run ESLint to catch code errors and style issues |

For build worker tuning, set `BUILD_CPUS` before running `npm run build` (defaults to all CPU cores minus one).
Set `FORCE_BUILD=1` to force a full rebuild even if inputs are unchanged.

---

## Utility Scripts

Run from the **project root** (`node <script>`):

> **Script overlap / redundancy reference:**
>
> | Group | Preferred | Superseded / Narrower |
> |-------|-----------|-----------------------|
> | Add products to catalog | `add_new_products.py`, `scrape_top_affiliates.py` | `generate_products.py` (hardcoded data only — one-time fill) |
> | Remove duplicates | `remove_duplicates.py` (model-aware, Python) | `check-duplicates.js` (quick JS check only) |
> | Price / rating / review validation | `oxylabs-amazon-product.sh` (Oxylabs API, structured) | _(HTML scrapers removed — see git history)_ |
> | Image download | `autofix-images.js` → `download-missing.js` → `download-search.js` | `download-images.js` (full re-download, rarely needed) |
> | Duplicate library | `products/check_duplicates.py` | (imported by all catalog scripts — not a standalone replacement) |

### Oxylabs Amazon product batch checker (`oxylabs-amazon-product.sh`)

Structured Amazon product data via [Oxylabs Web Scraper API](https://oxylabs.io/products/scraper-api/ecommerce/amazon) (paid / trial — not the same as Amazon PA API). Copy `.env.example` to `.env` and set `OXYLABS_USERNAME` and `OXYLABS_PASSWORD` from [dashboard.oxylabs.io](https://dashboard.oxylabs.io/).

**What it does:** Reads ASINs from `products/top-1000.csv` (five per batch), calls Oxylabs for each product, compares live data to the CSV, appends mismatches to `products/products4review.csv`, and writes **Price Range**, **Rating**, and **Review Count** updates back into `top-1000.csv`. Before any changes, it copies `top-1000.csv` to a dated backup (e.g. `products/top-1000.backup.2026-04-04.csv`; if that file already exists, a time suffix is added).

**Requirements:** `bash`, `curl`, and `python3` on your PATH.

**Usage:**

```bash
chmod +x oxylabs-amazon-product.sh
./oxylabs-amazon-product.sh [--limit N] [--geo GEO] [--offset N]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--limit N` | Process at most **N** products after `--offset` (default: all rows) |
| `--geo GEO` | Oxylabs `geo_location` (US ZIP code; default: **90210**) |
| `--offset N` | Skip the first **N** rows of the CSV before applying `--limit` (default: **0**) |

**Examples:**

```bash
./oxylabs-amazon-product.sh                          # full catalog
./oxylabs-amazon-product.sh --limit 50              # first 50 rows (after offset)
./oxylabs-amazon-product.sh --limit 10 --offset 20  # rows 21–30
./oxylabs-amazon-product.sh --geo 10001             # use New York ZIP for geo
```

**Equivalent single-product request** (what the script issues per ASIN):

```bash
curl 'https://realtime.oxylabs.io/v1/queries' \
  --user "USERNAME:PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
        "source": "amazon_product",
        "query": "B07FZ8S74R",
        "geo_location": "90210",
        "parse": true
      }'
```

### Images

| Command | Description |
|---------|-------------|
| `node check-images.js` | Report how many product images are present vs missing |
| `node autofix-images.js` | Download or re-download images for any product missing a local file; called automatically by Python catalog scripts after each batch |
| `node download-images.js` | Download **all** product images from Amazon (full re-download; prefer `autofix-images.js` for incremental runs) |
| `node download-missing.js` | Download only images that are not yet saved locally |
| `node download-search.js` | Download images by searching Amazon by product name — more resilient when ASINs are stale |
| `node fix-mismatched-images.js` | Detect and replace images that don't match their product |
| `node fix-single.js` | Fix the image for one specific product |
| `node generate-placeholders.js` | Generate grey placeholder images for any that are missing |

> **Image script ranking (most → least useful for day-to-day):**
> `autofix-images.js` → `download-missing.js` → `download-search.js` → `fix-mismatched-images.js` → `fix-single.js` → `download-images.js` (full re-download, rarely needed) → `generate-placeholders.js` (last resort)

### Prices / Ratings / Reviews

| Command | Description |
|---------|-------------|
| `python refresh_catalog_local.py` | **Recommended.** Pull live price / rating / review count / availability for every product via the **local scraper** (`amazon_local_api.py` — free, no API key) and merge into `products/top-1000.csv`. Same backup / diff / merge behavior as the Oxylabs script |
| `python refresh_catalog_local.py --limit 50` | Only process the first 50 products (quick sample) |
| `python refresh_catalog_local.py --offset 500 --limit 100` | Resume / process a slice |
| `python refresh_catalog_local.py --dry-run` | Preview changes without writing any file |
| `python amazon_local_api.py B0DW1X5YCQ --pretty` | Scrape one or more ASINs and print structured JSON (title, price, rating, reviews, availability, BSR) — local equivalent of the Oxylabs `amazon_product` source |
| `python refresh_prices.py` | Fetch live prices for all products via Scrapling (free, no API key required) and write changes back to `top-1000.csv` |
| `python refresh_prices.py --workers 4` | Concurrent fetch workers (default: 4) |
| `python refresh_prices.py --delay 3.0` | Per-worker request delay in seconds (default: 2.0) |
| `python refresh_prices.py --dry-run` | Preview price changes without writing to CSV |
| `./oxylabs-amazon-product.sh` | Pull live price / rating / review count for every product via the Oxylabs Amazon Product API and merge into `products/top-1000.csv` |
| `./oxylabs-amazon-product.sh --limit 50` | Only process the first 50 products (quick sample) |
| `./oxylabs-amazon-product.sh --offset 500 --limit 100` | Resume / process a slice |
| `./oxylabs-amazon-product.sh --geo 10001` | Query a specific geo zip (default `90210`) |
| `./oxylabs-amazon-product.sh --check-links` | Audit every Amazon link for dead (404) / removed / unavailable listings. Writes offenders to `products/broken-links.csv`; skips the price/rating/review merge |
| `./oxylabs-amazon-product.sh --check-links --limit 100` | Audit only the first 100 links |

> **`refresh_catalog_local.py` (local scraper):** the free replacement for the Oxylabs workflow. `amazon_local_api.py` fetches each product page with a ladder of engines (curl_cffi Chrome TLS impersonation → curl_cffi Safari → Scrapling), detects CAPTCHAs/soft-blocks and rotates engines with backoff, and parses price from the embedded buy-box JSON first (DOM selectors as fallback — note: Amazon's buy-box `.a-offscreen` span is often **empty** now, so selector-only scrapers miss prices). Every ASIN ends in a definitive verdict: data, `listing_removed`, or `unavailable`. Differences land in `products/products4review.csv`, dead listings in `products/broken-links.csv`, and a dated CSV backup is written before any merge — identical surfaces to the Oxylabs script. Exit code is non-zero if any product failed to reach a verdict. Unit tests: `venv/bin/python -m pytest tests/`.
>
> **`refresh_prices.py` vs Oxylabs:** `refresh_prices.py` scrapes Amazon directly via Scrapling (TLS fingerprint impersonation, no API cost). It only updates `Price Range` and `Refreshed Date` — not rating or review count. Use it for free daily price checks. Use Oxylabs when you need structured rating/review data or want to avoid any scraping risk.
>
> Console output shows every row: `ok` (unchanged, within 2%), `→` (updated), `BLOCKED` (CAPTCHA), `no price`, or `ERR`. Updated rows also write the previous value to `Old Price`.
>
> **Oxylabs:** requests the `amazon_product` realtime API with `parse=true`, so responses are structured JSON (no HTML scraping, no CAPTCHAs). Differences land in `products/products4review.csv`; a dated backup of the CSV is written before any merge.
> Requires `OXYLABS_USERNAME` / `OXYLABS_PASSWORD` in `.env` (each call has a per-request cost — hence this isn't run from automated QA).

### Links & Affiliate Tags

| Command | Description |
|---------|-------------|
| `node check-links.js` | Check all Amazon URLs in `top-1000.csv` for broken/404 links |
| `node check-links.js --concurrency 5` | Set parallel request concurrency (default: 5) |
| `node check-links.js --output report.json` | Write results to a JSON file |
| `node fix-affiliate-tags.js` | Scan all CSV files for Amazon URLs missing the affiliate tag and add it |
| `node fix-affiliate-tags.js --dry-run` | Preview affiliate tag fixes without writing |

### Duplicate Detection (JS)

| Command | Description |
|---------|-------------|
| `node check-duplicates.js` | Detect duplicate products in `top-1000.csv` |
| `node check-duplicates.js --fix` | Auto-remove detected duplicates |

> **Note:** For removing duplicates from the catalog, prefer `python remove_duplicates.py` (model-number-aware fuzzy matching). `check-duplicates.js` is a lighter JS alternative for quick checks.

---

## Python Scripts

Run from the **project root** (`python <script>`). Install dependencies first:

```bash
pip install -r requirements.txt
```

### Catalog Management

| Command | Description |
|---------|-------------|
| `python add_new_products.py` | Scrape Amazon search results and append new unique products to the CSV |
| `python add_new_products.py --runs 5` | Run 5 back-to-back batches (default: 1 run = 10 products) |
| `python add_new_products.py --batch-size 20` | Set products per run (default: 10) |
| `python add_new_products.py --category "Kitchen"` | Target a single category |
| `python add_new_products.py --dry-run` | Preview products that would be added without writing to CSV |
| `python add_new_products.py --skip-images` | Skip running `autofix-images.js` after adding products |
| `python add_product_by_asin.py B0FWKB7W3X` | Add one specific product to the catalog by its Amazon ASIN |
| `python add_product_by_asin.py B0FWKB7W3X --category "Health & Wellness"` | Add by ASIN with a specific category |
| `python add_product_by_asin.py B0FWKB7W3X --name "Custom Name" --dry-run` | Preview a single ASIN add with a name override |
| `python remove_duplicates.py` | Preview duplicate products (dry run, no changes) |
| `python remove_duplicates.py --apply` | Remove same make/model duplicates from the CSV |
| `python remove_duplicates.py --threshold 90` | Lower fuzzy-match threshold (default: 95) |
| `python remove_duplicates.py --show-skipped` | Also show pairs that are different models (correctly skipped) |
| `python generate_products.py` | Fill `top-1000.csv` up to 1,000 products with curated product data |
| `python scrape_top_affiliates.py` | Scrape Amazon bestsellers from high-commission categories and append to the CSV |
| `python scrape_top_affiliates.py --runs 5` | Run 5 back-to-back batches |
| `python scrape_top_affiliates.py --category "Kitchen"` | Target a single category |
| `python scrape_top_affiliates.py --dry-run` | Preview without writing |
| `python fix_amazon_urls.py --audit` | Count how many products are missing an ASIN (no `/dp/`) — no scraping |
| `python fix_amazon_urls.py` | Dry run — preview which search URLs would be resolved to direct `/dp/ASIN` links |
| `python fix_amazon_urls.py --apply` | Search Amazon for each product and replace search URLs with `/dp/ASIN` links |
| `python fix_amazon_urls.py --apply --limit 50` | Fix up to 50 products per run (recommended to avoid rate limits) |
| `python fix_amazon_urls.py --apply --workers 2` | Use 2 parallel workers (max 3 recommended) |
| `python fix_amazon_urls.py --threshold 0.5` | Require stronger word-overlap before accepting a match (default: 0.40) |

### Daily Deals

| Command | Description |
|---------|-------------|
| `python fetch_daily_deals.py --dry-run` | Discover + verify + rank today's deals; print results without writing any file |
| `python fetch_daily_deals.py` | Full run: discover, verify via Oxylabs, swap deal rows in `top-1000.csv`, download images |
| `python fetch_daily_deals.py --max-verify 30` | Limit Oxylabs calls to 30 (reduces API cost for a quick check) |
| `python fetch_daily_deals.py --min-discount 20` | Only keep deals with ≥ 20% off |
| `python fetch_daily_deals.py --deal-count 10` | Keep only the top 10 deals instead of 25 |
| `./run_daily_deals.sh` | Cron wrapper — runs `fetch_daily_deals.py` in a detached git worktree, commits + pushes to `main` |

### Social Media

| Command | Description |
|---------|-------------|
| `python post_daily.py` | Post today's featured product to Instagram |
| `python post_daily.py --dry-run` | Preview posts without publishing |
| `python post_daily.py --platform all` | Post to both Instagram and TikTok |
| `python post_daily.py --platform instagram` | Post to Instagram only |
| `python post_daily.py --platform tiktok` | Post to TikTok only |

> **Note:** `post_daily.py` requires `IG_USER_ID`, `IG_ACCESS_TOKEN`, and `TIKTOK_ACCESS_TOKEN` environment variables, set as GitHub Actions secrets for CI use.

#### `post_daily.py` — Complete Command-Line Reference

**Core Posting Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dry-run` | flag | off | Preview posts without sending to Instagram/TikTok |
| `--platform` | choice | instagram | Platform: `instagram`, `tiktok`, or `all` |

**Product Selection:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--force` | flag | off | Ignore post history; cycle via day-of-year rotation |
| `--category CATEGORY` | string | — | Only pick from products in this category (case-insensitive) |
| `--list-categories` | flag | off | Show all available product categories and exit |

**Image Generation:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--catalog-image-only` | flag | off | Skip AI generation; use the on-site product JPG |
| `--banner-only` | flag | off | Skip AI image variants (banner, studio_dark, etc.); compose and post the banner only |
| `--use-local-flux` | flag | off | Use local FLUX.1 [schnell] instead of Gemini (requires `pip install -r requirements-flux.txt`) |
| `--on-empty-ai-images` | choice | catalog | When AI generation fails: `catalog` (use site image) or `abort` (exit with error) |
| `--ignore-deals` | flag | off | Skip the limited-time deals pool; use the normal rotation even when a fresh daily-deal batch exists |

**Logging:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-v, --verbose` | flag | off | Enable debug logging to stderr (mutually exclusive with `-q`) |
| `-q, --quiet` | flag | off | Only warnings/errors to stderr (mutually exclusive with `-v`) |
| `--log-file PATH` | string | — | Append all logs to a file (UTF-8 encoded) |

**Common Examples:**

```bash
# Preview today's product
python post_daily.py --dry-run

# Post to Instagram (real)
python post_daily.py

# Post to both platforms
python post_daily.py --platform all

# List available categories
python post_daily.py --list-categories

# Post from Photography category only
python post_daily.py --category Photography

# Force a specific product (via day-of-year rotation)
python post_daily.py --force --dry-run

# Skip AI variants, just compose and post the banner
python post_daily.py --banner-only

# Use local FLUX instead of Gemini
python post_daily.py --use-local-flux --platform instagram

# Verbose logging with file output
python post_daily.py -v --log-file posts.log

# Fallback to site image if Gemini fails
python post_daily.py --on-empty-ai-images catalog
```

#### Image Generation Options for Social Posts

`post_daily.py` supports three image generation backends. Choose one based on your hardware and API access:

| Option | Pros | Cons | Setup | Environment Variable |
|--------|------|------|-------|----------------------|
| **Google Gemini** (Nano Banana) | Fast, cloud-based, no GPU needed, includes Claude prompt optimization | Requires Google AI Pro plan | `pip install -r requirements.txt` + API key | `GEMINI_API_KEY` |
| **Local FLUX.1 [schnell]** | Zero API costs, offline, full control | Requires GPU (GTX 1070+), slow (~2–4 min per 5 images) | `pip install -r requirements-flux.txt` | N/A (uses `--use-local-flux` flag) |
| **ModelsLab** (legacy) | Fast cloud generation | Paid API, being phased out | Manual setup | `MODELSLAB_KEY` |

**Google Gemini (recommended for most users):**
```bash
# Set your API key in .env
echo "GEMINI_API_KEY=your-key-here" >> .env

# Run with automatic image generation
python post_daily.py

# Preview without publishing
python post_daily.py --dry-run

# Fall back to catalog image if generation fails
python post_daily.py --on-empty-ai-images catalog

# Exit with error if generation produces no variants
python post_daily.py --on-empty-ai-images abort
```

**Local FLUX.1 [schnell]:**
```bash
# Install local dependencies (one-time)
pip install -r requirements-flux.txt

# Generate using local GPU
python post_daily.py --use-local-flux

# Note: Initial model download (~5.5GB), then ~2–4 min per product
```

**How image generation integrates with `post_daily.py`:**
- When an image source is set (Gemini, local FLUX), `post_daily.py` generates 5 styled variants
- User selects one interactively (or auto-picks first variant in CI)
- Chosen image is composed into the branded 1080×1080 banner (if `IMGBB_API_KEY` is set)
- Falls back to catalog product image if generation fails or is skipped

**Image styles (all backends):**
- `banner` — Premium affiliate marketing style (dark charcoal + orange accent)
- `studio_dark` — Professional studio lighting
- `lifestyle` — Real-world home setting
- `vibrant` — Bold, Gen-Z Instagram energy
- `detail` — Close-up macro photography

### AI-Powered Affiliate Content Tools

Generate scroll-stopping hooks, platform-specific CTAs, content calendars, and optimized bios using Claude AI. Set `ANTHROPIC_API_KEY` in `.env` to enable (falls back to templates if not set).

| Command | Description |
|---------|-------------|
| `python generate_content_calendar.py` | Generate a 7-day posting plan with products, hooks, CTAs, and platform assignments |
| `python generate_content_calendar.py --days 14` | Plan 14 days ahead (adjustable 1–30) |
| `python generate_content_calendar.py --output my_calendar.json` | Save to custom path |
| `streamlit run dashboard.py` | Launch interactive web dashboard with 4 tools (Hook Writer, CTA Builder, Content Calendar, Bio Optimizer) |

**How it integrates with `post_daily.py`:**
- When you run `post_daily.py` with `ANTHROPIC_API_KEY` set, each post automatically gets AI-generated hooks and platform-specific CTAs
- Instagram hooks: "This one's blowing up on Amazon 🔥" style
- TikTok hooks: adapted for platform engagement
- CTAs: Instagram "Link in bio → $X 🛒", TikTok "Comment LINK 👇"
- Falls back gracefully to templates if API is unavailable

**Example content calendar output** (`marketing-campaigns/content_calendar.json`):
```json
{
  "generated_at": "2026-04-14T12:00:00",
  "days": 7,
  "entries": [
    {
      "day": 1,
      "date": "2026-04-14",
      "platform": "instagram",
      "product": { "name": "Wireless Earbuds", "price": "$49.99", ... },
      "hook": "Everyone's grabbing this right now 👀",
      "cta": "Link in bio → $49.99 🛒",
      "hashtags": "#hotproducts #amazonfinds #musthave"
    }
  ]
}
```

**Dashboard tabs:**
1. **🎣 Hook Writer** — Generate 5 scroll-stopping opening lines for a product
2. **📢 CTA Builder** — Create Instagram or TikTok call-to-action text
3. **📅 Content Calendar** — Plan N days of posts; download as JSON
4. **✨ Bio Optimizer** — Generate optimized Instagram/TikTok bio text

### Instagram Module (`instagram/`)

The `instagram/` package is used internally by `post_daily.py` for Instagram posting and content generation.

| Module | Description |
|--------|-------------|
| `instagram/affiliate_tools.py` | AI-powered content tools: hooks, CTAs, content calendars, bio optimization (Claude Haiku via Anthropic API) |
| `instagram/scraper.py` | Scrapes product data for Instagram content |
| `instagram/caption.py` | Generates captions for Instagram posts |
| `instagram/poster.py` | Publishes posts via the Meta Graph API |
| `instagram/bot.py` | Orchestrates the full Instagram posting flow |

### Internal / Library Scripts

| Script | Description |
|--------|-------------|
| `tiktok_api.py` | TikTok Content Posting API v2 client — imported by `post_daily.py` |
| `products/check_duplicates.py` | Duplicate-guard library imported by `add_new_products.py`, `scrape_top_affiliates.py`, and `remove_duplicates.py`; also runnable standalone (`python products/check_duplicates.py`) |
| `products/verify_products.py` | Stub — placeholder for future product-file verification logic; not yet implemented |

### Tests

| Command | Description |
|---------|-------------|
| `python test_instagram_post.py` | Unit tests for the `post_instagram` function in `post_daily.py`; mocks the Meta Graph API two-step flow (media creation + publish) |
| `python -m pytest test_instagram_post.py -v` | Run with pytest for verbose output |

---

## Typical Workflows

### Daily development
```bash
cd site && npm run dev
```

### Before deploying
```bash
./perform_qualityassurance.sh
```

### Fix missing images
```bash
node check-images.js          # see what's missing
node download-missing.js      # attempt to download them
node generate-placeholders.js # generate placeholders for any that still fail
```

### Fix bad prices / ratings / review counts
```bash
./oxylabs-amazon-product.sh --limit 20   # quick sample (mismatches logged to products/products4review.csv, CSV updated)
./oxylabs-amazon-product.sh              # full catalog refresh
```

### Production build only
```bash
cd site && npm run build
```

---

## Deployment

The site deploys automatically to Hostinger via GitHub Actions when you push to `main`. The CI workflow builds the site and FTP-syncs only changed files.

**Build output (`site/out/`) is NOT tracked in git** — it's built fresh in CI each time.

### Push changes and deploy
```bash
git add -A
git commit -m "your message here"
git push origin main
```

### Push to a branch for review first
```bash
git checkout -b your-branch-name
git add -A
git commit -m "your message here"
git push -u origin HEAD
# Then merge on GitHub → auto-deploys on merge to main
```

### Force a full rebuild
Set `FORCE_BUILD=1` in the GitHub Actions workflow environment, or re-run the workflow from the Actions tab.

---

## Products I LOVE

A hand-curated section that appears at the top of the homepage (right after the hero) showcasing products you personally recommend. Unlike the algorithmic Top Picks rotation, this list is fully manual — you control it via the CSV.

### How to tag a product

In `products/top-1000.csv`, set the `Action Needed` column to `loved` for any product you want featured:

```
Product Name,...,Refreshed Date,Action Needed
TESSAN European Travel Plug Adapter USB C 3 Pack,...,5/10/2026,loved
```

After editing the CSV, regenerate the build cache:

```bash
cd site && node prebuild.js
```

The section only renders when at least one product is tagged. To remove a product from the section, clear or change its `Action Needed` value and re-run `prebuild.js`.

| Piece | Role |
|-------|------|
| `products/top-1000.csv` — `Action Needed` column | Source of truth — set to `loved` to include |
| `site/app/lib/products.ts` — `getILovedProducts()` | Filters the catalog for `iLoved === true` |
| `site/prebuild.js` | Parses `Action Needed` and writes `iLoved` into `products.json` |
| `site/app/page.tsx` — "Products I LOVE" section | Renders the grid, only shown when products exist |

---

## Limited Time Sale (Daily Deals)

A homepage section that shows today's top on-sale Amazon products — verified discounts, ranked by sales velocity. Refreshed every morning at 8 am Central by a cron job, and consumed by `post_daily.py` so the daily Instagram post also features a real deal.

### How it works

| Phase | What happens |
|-------|-------------|
| **1 — Discover** | `fetch_daily_deals.py` scrapes Amazon Best Sellers pages (free, reuses `find_bestsellers.py`) and collects candidates that pass a loose pre-filter (≥4.5 stars, ≥500 reviews, $15–$500, BSR ≤ 100) |
| **2 — Verify** | Each candidate ASIN is checked via the Oxylabs `amazon_product` API (paid, capped by `--max-verify`) to get the real current price, strikethrough list price, and the "N+ bought in past month" velocity badge |
| **3 — Rank** | `deal_score = sales_velocity × discount%`. Velocity = badge number if present, else `review_count / 10` as a cumulative-sales proxy |
| **4 — Swap** | `products/top-1000.csv` is atomically updated: yesterday's `Temporary=daily-deal` rows are dropped, deal columns on permanent rows are cleared, and today's top 25 are written (as new rows, or merged in-place when the ASIN already exists as a permanent product) |
| **5 — Images** | Product JPGs are downloaded to `site/public/products/` for any new slug (same job `autofix-images.js` does for manual adds — no Node dependency) |

### New CSV columns

These columns are appended to `top-1000.csv` by `fetch_daily_deals.py`. They are empty on permanent catalog rows.

| Column | Description |
|--------|-------------|
| `Temporary` | `daily-deal` on batch rows; `""` on permanent rows |
| `Deal Date` | ISO date the deal was verified (e.g. `2026-06-10`) |
| `List Price` | Strikethrough / was-price from Oxylabs |
| `Discount %` | Whole-percent markdown |
| `Bought Past Month` | Parsed "N+ bought in past month" badge number; 0 when absent |

### Cron setup

**Status: INSTALLED** (2026-06-11) in the `cyberace` user crontab on the WSL2 machine where the repo lives. Runs daily at 8 am Central:

```cron
# HotProducts Daily Deals — Limited Time Sale refresh (added 2026-06-11)
0 8 * * * /mnt/e/GITHUB/hotproductsdot-v2/run_daily_deals.sh >> /mnt/e/GITHUB/hotproductsdot-v2/logs/daily_deals.log 2>&1
```

To verify or manage the schedule:

```bash
crontab -l | grep run_daily_deals          # confirm the entry exists
service cron status                        # confirm the cron daemon is running (WSL2)
tail -50 logs/daily_deals.log              # check the latest run's output
```

> **WSL2 note:** cron only fires while the WSL2 instance is running. If the machine was asleep or WSL was shut down at 8 am, that day's run is skipped — run `./run_daily_deals.sh` manually to catch up. The 14:00 UTC `daily_post.yml` workflow then picks up whatever batch is on `main`.

`run_daily_deals.sh` runs `fetch_daily_deals.py` inside a **detached git worktree** (`/mnt/e/GITHUB/.hotproducts-deals-worktree`) so the developer checkout (which may be on a feature branch or have uncommitted changes) is never touched. After a successful run it commits the updated catalog + images and pushes to `main` with `[skip ci]` in the message. If no qualifying deals are found (exit code 2), yesterday's batch is kept live and nothing is pushed.

### Running manually

```bash
# Dry run: discover + verify + rank, print results, do not touch CSV
python fetch_daily_deals.py --dry-run -v

# Full run with custom options
python fetch_daily_deals.py --deal-count 25 --max-verify 60 --min-discount 10
```

| Option | Default | Description |
|--------|---------|-------------|
| `--deal-count N` | 25 | How many deals to keep in the catalog |
| `--max-verify N` | 60 | Oxylabs verification budget (paid calls) |
| `--min-discount PCT` | 10 | Minimum discount % to qualify |
| `--dry-run` | off | Print ranked deals without writing any file |
| `-v` | off | Verbose / debug logging |

### How `post_daily.py` uses deals

When a fresh deal batch exists in the catalog (`Temporary=daily-deal`, `Deal Date` within 2 days), `post_daily.py` automatically uses the **deal pool** instead of the normal rotation. Posts are ranked by `deal_score` so the top 5 deals are posted each day. The Instagram caption gains a `⏰ LIMITED-TIME DEAL: N% OFF (was $X)` line at the top. Pass `--ignore-deals` to skip the deal pool and fall back to the normal rotation.

### How the site renders deals

| Piece | Role |
|-------|------|
| `fetch_daily_deals.py` | Writes deal rows + 5 new CSV columns to `products/top-1000.csv` |
| `site/prebuild.js` | Parses deal columns into `products.json` at build time |
| `site/app/lib/products.ts` — `getLimitedTimeDeals()` | Filters for `limitedDeal=true`, staleness ≤ 2 days, sorted by velocity × discount |
| `site/app/lib/products.ts` — `getSaleProducts()` | Excludes `limitedDeal` rows so they don't double-appear in the Hot Deals section |
| `site/app/components/LimitedDealCard.tsx` | Red-accented card: discount badge, velocity badge, strikethrough price, "Grab the Deal →" CTA |
| `site/app/page.tsx` — "Limited Time Sale" section | Rendered above Hot Deals; hidden when the batch is stale or empty |

### Tests

```bash
python -m pytest tests/test_fetch_daily_deals.py -v   # 20 unit tests
```

Covers: badge parsing, discount math, deal scoring, catalog row swap (swap-out of yesterday's batch, merge-in-place for existing ASINs, legacy fieldname extension, stale column clearing), `post_daily.select_deal_pool` freshness window + ranking, and Instagram caption deal line.

---

## Homepage featured picks (daily rotation)

The homepage **Top Picks** grid is not a fixed “top 8 forever” list. It is built from a **quality pool** (roughly the strongest ~120 products by affiliate score and rating), then **shuffled with a deterministic seed** so the visible eight change **each UTC calendar day** when the site is rebuilt.

| Piece | Role |
|--------|------|
| `site/app/lib/products.ts` — `getFeaturedProducts()` | Picks the pool, shuffles with seed `featured \| {YYYY-MM-DD} \| …` |
| `site/scripts/build-smart.js` | Includes **`FEATURED_DAY`** (or today’s UTC date) in the build input hash so a new day is not treated as a no-op rebuild |
| `.github/workflows/deploy.yml` | Sets `FEATURED_DAY` to `date -u +%Y-%m-%d` and runs on **push to `main`**, **daily schedule** (`cron`, UTC), and **`workflow_dispatch`** |

**Operational notes:**

- **UTC day** — “Midnight” for rotation follows UTC, not your local timezone.
- **Static export** — Visitors see whatever was in the last deployed `out/`. A new mix appears after a successful build + deploy.
- **Daily deploy** — The scheduled workflow rebuilds and FTP-syncs so Top Picks can change without you pushing code. Ensure **Actions** are enabled for the repo and the schedule is not disabled for inactive repos (GitHub may pause cron on forks or idle repos).
- **Local preview** — `cd site && npm run build` uses today’s UTC date unless you override: `FEATURED_DAY=2026-04-10 npm run build` (PowerShell: `$env:FEATURED_DAY="2026-04-10"; npm run build`).

**One-time walkthrough (end-to-end):**

1. Commit and push your work to `main` **or** open **Actions → “Build & Deploy to Hostinger” → Run workflow** to deploy the current `main` without a new commit.
2. Wait for the job to finish (build → FTP upload).
3. Open the live site and confirm **Top Picks** matches a fresh slice of the catalog.
4. The next calendar **UTC** day, either push again or let the **scheduled** run publish a new build so Top Picks can change again.

---

## When `git push` is rejected (remote has new commits)

If you see `! [rejected] main -> main (fetch first)` or “the remote contains work that you do not have locally”, someone (or another machine, or GitHub) added commits on `main` that your clone does not have. **Integrate those commits, then push.**

**Recommended (linear history):**

```bash
git fetch origin
git pull --rebase origin main
# resolve any conflicts, then:
git push origin main
```

**Alternative (merge commit):**

```bash
git pull origin main
git push origin main
```

After a successful push, deployment runs automatically if Actions is set up for `main`.

---

## Daily Development Checklist

A three-phase workflow for fixing links, generating content, and shipping to production.

### 🌅 Morning (9:00–12:00)

**Goal:** Audit and validate the catalog

- [ ] **Pull latest:** `git fetch origin && git pull --rebase origin main`
- [ ] **Check link health:** `node check-links.js --concurrency 8 --output morning-links.json`
  - 🎯 **Progress:** All URLs return `status: 200` or are marked “known-broken”
- [ ] **Fix broken affiliate tags:** `node fix-affiliate-tags.js --dry-run` → review output
  - 🎯 **Progress:** No missing `/dp/ASIN` patterns in output
- [ ] **Apply fixes:** `node fix-affiliate-tags.js` (if dry-run showed issues)
- [ ] **Verify images:** `node check-images.js`
  - 🎯 **Progress:** <5% missing (all recent products have images)
- [ ] **Commit if needed:** `git add -A && git commit -m “chore: morning link audit and affiliate tag fixes”`

**When done:** You've validated that outbound links are live and formatted correctly.

---

### ☀️ Afternoon (12:00–17:00)

**Goal:** Generate content and refresh the social media queue

- [ ] **List available categories:** `python post_daily.py --list-categories`
- [ ] **Preview today's post:** `python post_daily.py --dry-run` (or `--dry-run --platform all`)
  - 🎯 **Progress:** Generated post preview shown; select best image variant
- [ ] **Generate content calendar:** `python generate_content_calendar.py --days 7 --output marketing-campaigns/calendar_refresh.json`
  - 🎯 **Progress:** 7-day plan with hooks, CTAs, and hashtags saved
- [ ] **Post to social (real):** `python post_daily.py --platform all` or `--platform instagram` / `--platform tiktok`
  - 🎯 **Progress:** New post published to selected platform(s); screenshot confirmation
- [ ] **Optional:** Refresh product catalog if adding new items
  - `python add_new_products.py --dry-run --batch-size 10` (preview)
  - `python add_new_products.py --batch-size 10` (apply, auto-fixes images)
- [ ] **Commit content updates:** `git add -A && git commit -m “feat: afternoon social media post + content calendar refresh”`

**When done:** Today's product is featured on social, and content plan is refreshed for the next 7 days.

---

### 🌆 Evening (17:00–21:00)

**Goal:** Quality assurance, bug fixes, and production deploy

- [ ] **Run full QA pipeline:**
  ```bash
  ./perform_qualityassurance.sh
  ```
  - 🎯 **Progress:** ESLint ✅, prices ✅, images ✅, build ✅
- [ ] **Spot-check price accuracy** (optional, if prices updated during day):
  - `./oxylabs-amazon-product.sh --limit 50` (live API sample; writes diffs to `products/products4review.csv` and updates CSV)
  - 🎯 **Progress:** <10% mismatch rate or none
- [ ] **Test locally before deploy:**
  ```bash
  cd site && npm run build
  npm run start  # visit http://localhost:3000 and spot-check Top Picks, product links
  ```
  - 🎯 **Progress:** Site loads, products render, affiliate links open correctly
- [ ] **Fix any issues found:**
  - Bad image? `node fix-single.js <product-id>`
  - Bad price/rating/reviews? `./oxylabs-amazon-product.sh --limit 20` (live API; updates CSV and logs diffs)
  - Broken link? `node fix-amazon-urls.py --apply --limit 10`
- [ ] **Final commit + push to main:**
  ```bash
  git add -A
  git commit -m “fix: evening QA pass and production fixes”
  git push origin main
  ```
  - 🎯 **Progress:** Pushed to `main`; GitHub Actions deploy starts automatically
- [ ] **Verify deployment:** Monitor GitHub Actions → wait for “Build & Deploy to Hostinger” to complete
  - 🎯 **Progress:** Deployment ✅; live site updated
- [ ] **Smoke test live site:** Open https://hotproductsdot.official (or your domain) in browser
  - 🎯 **Progress:** Homepage loads, Top Picks visible, click one affiliate link
- [ ] **Close day:** Log any blocking issues or next-day priorities in project notes

**When done:** Code is clean, site is tested, deployment is live, and you're ready for tomorrow.

---

## Quick Reference: Daily One-Liner Shortcuts

```bash
# Morning audit (one command)
node check-links.js && node check-images.js && node fix-affiliate-tags.js --dry-run

# Afternoon social (one command)
python post_daily.py --dry-run && python generate_content_calendar.py --days 7

# Evening QA + deploy (one command)
./perform_qualityassurance.sh && cd site && npm run build && git add -A && git commit -m “deploy” && git push

# Full catalog maintenance (run overnight)
python add_new_products.py --runs 3 && python remove_duplicates.py --apply && python fix_amazon_urls.py --apply --limit 50
```

---
