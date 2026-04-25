# Pinterest Playbook — hotproductsdot.com

**Account:** @affiliate1009 · Profile: "Hot Products" · Domain: hotproductsdot.com
**Goal:** Drive Pinterest traffic to Amazon affiliate links (tag: `hotproducts033-20`)
**Last updated:** 2026-04-24

---

## ⚠️ Read this first — affiliate-link safety on Pinterest

You chose to pin directly to Amazon affiliate URLs. Pinterest *does* allow affiliate links, but their spam filters bite hard if you do it wrong. Three rules:

1. **Disclose every pin.** FTC requires it, and Pinterest's policy mandates `#ad` or `#affiliate` somewhere in the description. Bake this into every template — see Pin Description SEO below.
2. **Never spam the same pin/link.** Pinterest treats >5 saves of the same URL/day as spam. Vary the pin image AND vary the destination URL (use UTM tags — see UTM section).
3. **Use a 70/30 mix even if you "pin direct."** ~70% of pins to your own site (`/best/<category>` and `/products/<slug>` pages) and ~30% direct Amazon. Reasons: (a) the site pages already enforce your affiliate tag via `buildAffiliateUrl()`, (b) you control the destination if Pinterest changes policy, (c) your site pages are SEO-indexed so pins compound. Direct-Amazon pins are fine for hot/seasonal items where speed matters.

If you ever get a "your account has been flagged" notice — stop pinning immediately, audit the last 50 pins for repetition, and rotate to site-page pins for 30 days.

---

## Step 1 — Profile setup (one-time, ~20 min)

### 1a. Display name (the field that ranks in Pinterest search)

Pinterest's search engine treats your display name as keywords. Don't waste it on "Hot Products."

**Change to:** `Hot Products | Best Amazon Finds & Gift Ideas`

(80 char max — yours uses 49.)

### 1b. Bio (160 char)

```
Daily roundups of the best Amazon products in kitchen, tech, beauty, fitness & home. New picks every day → hotproductsdot.com #affiliate
```

The trailing `#affiliate` is your account-level disclosure — keeps you compliant if a pin description gets cropped.

### 1c. Claim your domain (REQUIRED)

You're already showing "claim hotproductsdot.com" in the header. Finish it:

1. Settings → **Claimed accounts** → **Websites** → **Claim**
2. Use the **HTML tag** method (easier than DNS for Next.js)
3. Add the meta tag to `site/app/layout.tsx`:
   ```tsx
   export const metadata = {
     other: { 'p:domain_verify': 'YOUR_VERIFICATION_CODE' }
   }
   ```
4. Deploy, then click **Verify** in Pinterest

Why it matters: claimed domains get analytics (which pins drive clicks), Rich Pins eligibility, and a verified checkmark next to your name.

### 1d. Enable Rich Pins (after claim)

Rich Pins pull metadata directly from your pages — title, price, availability appear ON the pin. Free and a 2-3× CTR boost.

1. Add Open Graph + product schema to your product detail pages (you likely already have OG tags from Next.js metadata)
2. Validate at `https://developers.pinterest.com/tools/url-debugger/` with one product URL
3. Once a single URL validates, ALL your product pages auto-qualify

Required OG tags for product Rich Pins:
```html
<meta property="og:title" content="..." />
<meta property="og:description" content="..." />
<meta property="og:image" content="..." />
<meta property="og:url" content="..." />
<meta property="product:price:amount" content="29.99" />
<meta property="product:price:currency" content="USD" />
<meta property="og:type" content="product" />
```

### 1e. Convert to Business + connect analytics

You have a Business account already (good). Two more clicks:

- Settings → **Analytics & reporting** → connect **Pinterest tag** to your site (give it to your dev or drop the script into `site/app/layout.tsx`). Lets you retarget pin viewers later.
- Settings → **Business** → **Lead ads** → leave OFF for now (you're affiliate, not lead-gen)

### 1f. Profile cover image

Pinterest now supports a header. Use a 1600×900 collage of your top 6 products with text overlay: "Daily Amazon Deals · Updated Daily." Generate via your existing `scripts/banner_compose.py`.

---

## Step 2 — Board structure

Mirror your site's silo architecture. Each board = one `/best/<category>` page on your site.

**See `BOARDS.csv` for the full importable list (40 boards).** Key principles:

- Board name = exact-match keyword phrase ("Best Kitchen Gadgets 2026", not "My Kitchen Stuff")
- Board description = 200-500 words, keyword-rich, includes 3-5 long-tail variants
- Board cover = a vertical pin (1000×1500) showing 3 hero products
- Don't create more than 5 boards on Day 1 — Pinterest's anti-spam treats sudden mass-board creation as suspicious. Add 5/week for 8 weeks.

### Recommended Day 1 boards (start here):

1. **Best Kitchen Gadgets 2026** (78 products in your DB)
2. **Luxury Beauty Finds Under $50** (77 products)
3. **Smart Home Must-Haves** (43 products)
4. **Best Gaming Setups & Accessories** (46 + 29 + 23 products)
5. **Daily Amazon Deals** (catch-all — pin everything here too)

### Week 2-8 expansion (5 boards/week):

See `BOARDS.csv` — covers Fitness, Photography, Laptops, Smart Home, Pet Supplies, Travel Accessories, Outdoor, Furniture, Power Tools, Gardening, etc.

---

## Step 3 — Posting strategy

### Cadence

Pinterest's 2025/2026 algorithm rewards **consistency over volume**. The new sweet spot:

| Tier | Daily pins | Notes |
|------|-----------|-------|
| Starter (weeks 1-4) | 5-7 fresh pins/day | Builds trust signals |
| Growth (weeks 5-12) | 10-15/day | Once monthly views >10k |
| Mature (3+ months) | 15-25/day | Mix new + repins |

**"Fresh pin" = new image + new title even if same URL.** Pinterest dramatically favors fresh pins over repins of the same image.

### Best times to post (US audience)

Use Pinterest's built-in scheduler (you chose this). Pin times that test best:

- **Weekdays:** 8-11 PM ET (evening browse)
- **Weekends:** 8-11 AM ET (morning planning)
- **Saturday 8-10 PM ET:** highest CTR slot for shopping pins

Pinterest's free scheduler lets you queue up to 100 pins ~2 weeks ahead. Workflow:
1. **Sunday batch session (90 min):** schedule the entire week
2. **Wednesday top-up (30 min):** add fresh pins for the weekend

### What to pin

| % | Type | Example |
|---|------|---------|
| 40% | Single product hero pins | One product, big image, price callout, "Shop on Amazon" CTA |
| 30% | "Best of" listicle pins | "5 Best Air Fryers Under $100" → pins to `/best/kitchen` |
| 20% | Lifestyle / use-case pins | Product in real setting ("Cozy reading nook with this lamp") |
| 10% | Deal alerts / seasonal | "Prime Day Picks" "Mother's Day Gifts Under $30" |

---

## Step 4 — UTM tagging (so you can prove Pinterest works)

Add UTM params to every pin destination. Pinterest dashboard tells you saves/impressions; UTMs tell you revenue.

**Format for SITE pins (recommended):**
```
https://hotproductsdot.com/best/kitchen?utm_source=pinterest&utm_medium=social&utm_campaign=kitchen-best-2026&utm_content=pin-air-fryer-roundup
```

**Format for DIRECT Amazon pins (if you must):**
```
https://www.amazon.com/dp/B0XXXXX?tag=hotproducts033-20&ascsubtag=pin-<board>-<date>
```

`ascsubtag` is Amazon's affiliate sub-tag — you'll see it in your Amazon Associates report and can attribute every sale back to the specific pin.

---

## Step 5 — Disclosure (FTC + Pinterest policy)

Every pin description needs ONE of these phrases (rotate so you don't look bot-like):

- `#ad`
- `#affiliate`
- `#affiliatelink`
- `As an Amazon Associate I earn from qualifying purchases.`
- `Paid link.`

Place at the END of the description. Pinterest's algorithm doesn't penalize disclosure tags; the FTC fines you if you skip them.

---

## Step 6 — Integrate with your existing pipeline

You already have `post_daily.py`, `marketing/content_calendar.json`, and Instagram/TikTok automation. Pinterest can plug in:

- **Pinterest API:** apply for developer access at `developers.pinterest.com` (~3-5 day approval). Free.
- Once approved, you can `POST /v5/pins` programmatically. Same pattern as your `instagram/poster.py`.
- **Until API approval:** use the built-in scheduler manually (Sunday batch).

I've sketched a `pinterest_poster.py` skeleton in this folder (`pinterest_poster_stub.py`) that mirrors your Instagram poster shape — wire it up when you have an API token.

---

## Quick-start checklist (first 7 days)

- [ ] Day 1: Update display name + bio + claim domain (Step 1)
- [ ] Day 1: Create the 5 starter boards (Step 2)
- [ ] Day 2: Validate one product URL in Pinterest's URL debugger → unlocks Rich Pins for whole site
- [ ] Day 3: Generate 30 pin images using your `scripts/banner_compose.py` (5/board)
- [ ] Day 3: Schedule first 7 days through Pinterest's built-in scheduler
- [ ] Day 4: Add Pinterest tag to site for retargeting
- [ ] Day 5: Apply for Pinterest API developer access
- [ ] Day 7: Check Pinterest Analytics — if any pin has >100 impressions, make 3 variations of it

---

## Files in this folder

- **PINTEREST_PLAYBOOK.md** — this file (master strategy)
- **BOARDS.csv** — 40 boards with names, descriptions, keywords
- **PIN_DESCRIPTIONS.md** — title/description templates + keyword bank
- **CONTENT_CALENDAR.md** — 30-day starter calendar
- **pin-templates.html** — 4 visual pin design templates (preview + copy specs)
- **pinterest_poster_stub.py** — API integration scaffold
