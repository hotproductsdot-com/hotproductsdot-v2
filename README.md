# hotproductsdot-v2

Affiliate product site built with Next.js 16. Lists top 1000 products with images, prices, categories, and Amazon affiliate links.

---

## Project Structure

```
hotproductsdot-v2/
├── site/                        # Next.js 16 app (the website)
├── products/
│   └── top-1000.csv             # Product database (name, price, category, ASIN)
├── site/public/products/        # Downloaded product images (.jpg)
├── perform_qualityassurance.sh  # Full QA pipeline
├── *.js                         # JS utility scripts (run from project root)
└── *.py                         # Python utility scripts (run from project root)
```

---

## Data quality (images, prices, links)

**Honest expectation:** “100% correct” against live Amazon at all times is not something any static site can guarantee without continuous automated checks and manual review. This repo uses a **defense-in-depth** approach:

| Area | How it stays accurate | You should still… |
|------|------------------------|-------------------|
| **Affiliate links** | `site/app/lib/affiliate.ts` enforces `AFFILIATE_TAG` on outbound Amazon URLs; product CTAs use `buildAffiliateUrl()` | Run `python fix_amazon_urls.py --audit` and fix rows missing `/dp/` ASINs; spot-check links after CSV edits |
| **Prices** | CSV is the source of truth; copy on pages says prices may change | Run `node validate-prices-parallel.js --dry-run` (or apply) before big launches; rerun after bulk catalog updates |
| **Images** | Local files under `site/public/products/` override Amazon CDN; **cache-busting** `?v=<file-mtime>` is appended on build so **replacing an image file and redeploying** yields a new URL (fixes “old image in every browser”) | After replacing a `.jpg`, run a full site build + deploy so `products.json` / HTML pick up the new query string |

**Stale images after deploy (browsers showing old art):**  
That happens when the **URL stays identical** and caches reuse the file. The site now adds **`?v=<mtime>`** to local `/products/*.jpg` and `/products/*.svg` URLs at prebuild time, so each image replacement changes the query string and forces a fresh fetch. If anything still looks wrong, hard-refresh once or clear site data for your domain.

---

## QA Pipeline

Run this before every deployment to lint, validate prices, check images, and build.

```bash
./perform_qualityassurance.sh
```

**Steps:**

| Step | Check | On Failure |
|------|-------|------------|
| 1 | ESLint — static code analysis | Hard stop |
| 2 | Price validation (dry-run) | Warning only |
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

### Images

| Command | Description |
|---------|-------------|
| `node check-images.js` | Report how many product images are present vs missing |
| `node download-images.js` | Download all product images from Amazon |
| `node download-missing.js` | Download only images that are not yet saved locally |
| `node download-search.js` | Download images by searching when direct URL fails |
| `node fix-mismatched-images.js` | Detect and replace images that don't match their product |
| `node fix-single.js` | Fix the image for one specific product |
| `node generate-placeholders.js` | Generate grey placeholder images for any that are missing |

### Prices

| Command | Description |
|---------|-------------|
| `node validate-prices.js` | Check product prices against Amazon (sequential, slower) |
| `node validate-prices-parallel.js` | Check product prices in parallel across multiple workers (faster) |
| `node validate-prices-parallel.js --dry-run` | Report price mismatches without updating the CSV |
| `node validate-prices-parallel.js --workers=8` | Set number of parallel workers (default: 4) |

> **Note:** Price validation scrapes Amazon live. It is slow and may hit CAPTCHAs. Run overnight or with `--dry-run` for a quick status check.

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
| `python update_top_1000.py` | Validate and update entries in `top-1000.csv` |
| `python fix_amazon_urls.py --audit` | Count how many products are missing an ASIN (no `/dp/`) — no scraping |
| `python fix_amazon_urls.py` | Dry run — preview which search URLs would be resolved to direct `/dp/ASIN` links |
| `python fix_amazon_urls.py --apply` | Search Amazon for each product and replace search URLs with `/dp/ASIN` links |
| `python fix_amazon_urls.py --apply --limit 50` | Fix up to 50 products per run (recommended to avoid rate limits) |
| `python fix_amazon_urls.py --apply --workers 2` | Use 2 parallel workers (max 3 recommended) |
| `python fix_amazon_urls.py --threshold 0.5` | Require stronger word-overlap before accepting a match (default: 0.40) |

### Social Media

| Command | Description |
|---------|-------------|
| `python post_daily.py` | Post today's featured product to both Instagram and TikTok |
| `python post_daily.py --dry-run` | Preview posts without publishing |
| `python post_daily.py --platform instagram` | Post to Instagram only |
| `python post_daily.py --platform tiktok` | Post to TikTok only |

> **Note:** `post_daily.py` requires `IG_USER_ID`, `IG_ACCESS_TOKEN`, and `TIKTOK_ACCESS_TOKEN` environment variables (set as GitHub Actions secrets for CI use).

### Internal / Library Scripts

| Script | Description |
|--------|-------------|
| `tiktok_api.py` | TikTok Content Posting API v2 client — imported by `post_daily.py` |
| `fetch_amazon_products.py` | Minimal Amazon bestseller fetcher (prototype/utility) |

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

### Fix bad prices
```bash
node validate-prices-parallel.js --dry-run    # see mismatches
node validate-prices-parallel.js --workers=4  # apply fixes to CSV
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
