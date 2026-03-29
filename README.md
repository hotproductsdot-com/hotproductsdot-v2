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
└── *.js                         # Utility scripts (run from project root)
```

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
| `npm run build` | Compile and bundle the site for production (outputs to `site/.next/`) |
| `npm run start` | Serve the production build locally (requires `build` first) |
| `npm run lint` | Run ESLint to catch code errors and style issues |

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
