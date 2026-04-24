# hotproductsdot.com — Silo Architecture

## Overview
Unified domain with category-based silos. Each category has:
1. **Money Page** (`/best/[category]`) — Expert roundup, detailed reviews, CTAs
2. **Category Hub** (`/category/[category]`) — Browse all products in category
3. **Individual Products** (`/products/[slug]`) — Single product detail page

## Site Map

```
/                             Homepage
├── /products                All products grid
├── /guides                  How-to content (future)
│
├── /best/[category]         ⭐ MONEY PAGES (Expert Roundups)
│   ├── /best/fitness
│   ├── /best/kitchen
│   ├── /best/photography
│   └── ... (one per category)
│
├── /category/[category]     Category hubs (product browsing)
│   ├── /category/fitness
│   ├── /category/kitchen
│   ├── /category/photography
│   └── ... (one per category)
│
└── /products/[slug]         Individual product pages
```

## Content Hierarchy

### Money Pages (`/best/[category]`)
**Purpose:** Drive affiliate clicks with expert roundups

**Structure:**
- FTC Disclosure (prominent)
- Hook: Problem statement + category overview
- Quick Facts (product count, avg rating, update frequency)
- Top Pick (above-fold CTA)
- Detailed Reviews (top 5 products with images + CTAs)
- Comparison Table (quick reference)
- FAQ (trust building)
- Bottom CTA (browse all on Amazon)
- Internal Link → Category Hub

**Link Strategy:**
- Rank for: "Best [category] 2026", "Best [category] for [use case]"
- Target: Commercial + informational hybrid
- CTA buttons: 5–7 affiliate links per page
- Internal: Links to category hub at bottom

**Update Schedule:** Quarterly

### Category Hubs (`/category/[category]`)
**Purpose:** Product discovery, category authority

**Structure:**
- Icon + category name
- Full product grid (all items in category)
- Breadcrumb nav
- No affiliate CTAs (browse-only)

**Link Strategy:**
- Internal: Linked from `/best/[category]` pages (silo authority)
- Linked from homepage category grid
- Supports discovery, not conversion

### Homepage (`/`)
**Sections in order:**
1. Hero (brand + value prop)
2. Hot Deals (6 highest-potential products)
3. Top Picks (featured rotation)
4. **Best Category Guides** (6 top categories → `/best/[slug]`)
5. Browse All Categories (all categories → `/category/[slug]`)
6. Trust strip (stats + benefits)

**Internal Linking Flow:**
- Homepage → Best Guides → Category Hub → Products
- Authority flows top-down

## Affiliate Link Placement

### Money Pages (`/best/[category]`)
- **Above fold:** Top pick CTA (highest conversion)
- **Per product:** 1 CTA per reviewed item
- **Comparison table:** Links to Amazon
- **Bottom CTA:** Browse all on Amazon
- **Target:** 5–7 links per page

### Category Hubs
- **No affiliate links** (discovery, not conversion)

### Homepage
- Header: "Shop Amazon" button (main nav CTA)
- Hot Deals: Small product cards linking to Amazon
- All category links are browse-only

## Internal Linking Strategy

**Silo Structure (Authority Flow):**
```
Homepage
  ↓
Best [Category] (Money Page)
  ↓
Category Hub (Browsing)
  ↓
Individual Products
```

**Cross-silo:** Minimal (stay focused per category)

**Link Equity:**
- Top-level silo pages (money pages) get most internal links
- Category hubs get links from money pages + homepage
- Product pages get links from hubs + money pages

## SEO Keywords

### Money Pages
- Primary: "Best [category] 2026"
- Secondary: "Best [category] for [use case]", "[category] reviews", "[category] comparison"
- Intent: Commercial (high-intent buyers)

### Category Hubs
- Primary: "[category] products", "Best [category]"
- Secondary: "[category] prices", "[category] deals"
- Intent: Informational/commercial (discovery phase)

### Homepage
- Brand: "hotproductsdot", "hot products"
- Generic: "Amazon products", "best deals Amazon"
- Intent: Brand awareness + discovery

## Technical Implementation

### File Structure
```
site/app/
├── best/
│   └── [slug]/
│       └── page.tsx          Money page template
├── category/
│   └── [slug]/
│       └── page.tsx          Category hub
├── products/
│   └── [slug]/
│       └── page.tsx          Product detail
├── page.tsx                   Homepage
└── lib/
    └── products.ts           Product data + category queries
```

### Dynamic Route Generation
- `generateStaticParams()` in both `best/` and `category/` uses `getAllCategories()`
- Pre-builds pages at deploy time (ISR-friendly)
- New products update via CSV without page rebuild

## Performance Metrics to Track

### Money Pages (`/best/[category]`)
- Clicks per page (CTR)
- Earnings per click (EPC)
- Conversion rate (visitors → clicks)
- Average session duration
- Bounce rate

### Category Hubs
- Time on page
- Pages per session
- Bounce rate (should be low — discovery page)

### Overall
- Organic traffic by page
- Top landing pages (Google Search Console)
- RPM (revenue per 1,000 sessions)

## Compliance Checklist

- [x] FTC Disclosure on every money page (above-fold)
- [x] Affiliate link disclosure language ("affiliate links" + no cost to user)
- [x] No email affiliate links
- [x] No link shorteners hiding Amazon
- [x] Images via local CDN (not PA API until 3+ sales)
- [x] Prices shown as "Check Price" (not exact)

## Future Enhancements

1. **Guides** (`/guides/[slug]`) — How-to content linking to money pages
2. **Comparisons** (`/vs/[a]-vs-[b]`) — Product comparison pages
3. **Seasonal Updates** — Holiday gift guides, seasonal roundups
4. **Email List** — Newsletter with affiliate links (secondary channel)
5. **Ad Network** — Mediavine/AdThrive once traffic hits thresholds
