// Single source of truth for affiliate configuration.
// NOTE: The scraper uses hotproduct033-20 (in scrape_top_affiliates.py).
// This tag is used for all site-generated links to stay consistent.
export const AFFILIATE_TAG = "hotproduct033-20";
export const SITE_NAME = "HotProducts";
export const SITE_URL = "https://hotproducts.online";
export const SITE_LOGO = `${SITE_URL}/app-icon.png`;
export const AFFILIATE_DISCLOSURE =
  "As an Amazon Associate I earn from qualifying purchases.";

// Canonical brand entity. Single definition reused as the homepage
// Organization and as author/publisher on content pages, so AI/search engines
// resolve every reference to ONE entity (split entities weaken E-E-A-T).
// Nested usages omit @context; the standalone homepage block adds it.
export const BRAND_ORG = {
  "@type": "Organization",
  name: SITE_NAME,
  url: SITE_URL,
  logo: SITE_LOGO,
  sameAs: [
    "https://www.instagram.com/hotproductsdot.official",
    "https://www.tiktok.com/@hotproductsdot.of",
  ],
} as const;
