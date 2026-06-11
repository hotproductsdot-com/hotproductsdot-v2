import Papa from "papaparse";
import fs from "fs";
import path from "path";

import { SITE_URL } from "./constants";

export interface Product {
  name: string;
  slug: string;
  category: string;
  categorySlug: string;
  priceRange: string;
  priceMin: number;
  priceMax: number;
  reviewCount: number;
  rating: number;
  bsr: string;
  bsrRank: number;
  affiliatePotential: number;
  amazonUrl: string;
  imageUrl: string;
  badge: "hot" | "top-rated" | "best-seller" | null;
  refreshedDate?: string;
  refreshedTs?: number;
  iLoved?: boolean;
  /** Limited-time deal fields — set by fetch_daily_deals.py on the daily sale batch. */
  limitedDeal?: boolean;
  dealDateTs?: number;
  listPrice?: number;
  discountPct?: number;
  boughtPastMonth?: number;
}

/** Parse "M/D/YYYY" or "YYYY-MM-DD" → epoch ms; 0 if unparseable. */
function parseRefreshedDate(raw: string): number {
  const s = (raw || "").trim();
  if (!s) return 0;
  const iso = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (iso) {
    const [, y, m, d] = iso;
    const t = Date.UTC(+y, +m - 1, +d);
    return Number.isFinite(t) ? t : 0;
  }
  const us = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (us) {
    const [, m, d, y] = us;
    const t = Date.UTC(+y, +m - 1, +d);
    return Number.isFinite(t) ? t : 0;
  }
  return 0;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function parsePrice(raw: string): { display: string; min: number; max: number } {
  const cleaned = (raw || "").replace(/[$,]/g, "").trim();
  if (!cleaned || !/\d/.test(cleaned)) return { display: "Check Price", min: 0, max: 0 };

  const rangeMatch = cleaned.match(/(\d+)\s*-\s*(\d+)/);
  if (rangeMatch) {
    const low = parseInt(rangeMatch[1], 10);
    const high = parseInt(rangeMatch[2], 10);
    if (low === 0 && high === 0) return { display: "Check Price", min: 0, max: 0 };
    return { display: `$${low.toLocaleString()}–$${high.toLocaleString()}`, min: low, max: high };
  }

  const single = cleaned.match(/(\d+)/);
  if (single) {
    const price = parseInt(single[1], 10);
    if (price === 0) return { display: "Check Price", min: 0, max: 0 };
    return { display: `$${price.toLocaleString()}`, min: price, max: price };
  }

  return { display: "Check Price", min: 0, max: 0 };
}

function parseBsrRank(bsr: string): number {
  const match = bsr.replace(/,/g, "").match(/#?(\d+)/);
  return match ? parseInt(match[1], 10) : 9999;
}

function extractAsin(url: string): string {
  const match = url.match(/\/dp\/([A-Z0-9]{10})/);
  return match ? match[1] : "";
}

function asinToImageUrl(asin: string): string {
  if (!asin) return "";
  return `https://m.media-amazon.com/images/P/${asin}.01._SCLZZZZZZZ_SX500_.jpg`;
}

let _imageFiles: Set<string> | null = null;

function getLocalImageFiles(): Set<string> {
  if (_imageFiles) return _imageFiles;
  const dir = path.join(process.cwd(), "public", "products");
  try {
    _imageFiles = new Set(fs.readdirSync(dir));
  } catch {
    _imageFiles = new Set();
  }
  return _imageFiles;
}

/** File mtime (ms) so replaced images get a new URL and browsers skip stale cache. */
function localImageCacheToken(slug: string, ext: string): string {
  const fp = path.join(process.cwd(), "public", "products", `${slug}.${ext}`);
  try {
    return String(Math.floor(fs.statSync(fp).mtimeMs));
  } catch {
    return "0";
  }
}

function getImageUrl(slug: string, asin: string): string {
  const files = getLocalImageFiles();
  if (files.has(`${slug}.jpg`)) {
    const v = localImageCacheToken(slug, "jpg");
    return `/products/${slug}.jpg?v=${v}`;
  }
  if (files.has(`${slug}.svg`)) {
    const v = localImageCacheToken(slug, "svg");
    return `/products/${slug}.svg?v=${v}`;
  }
  return asinToImageUrl(asin);
}

/** Absolute URL for Open Graph / Twitter (relative paths become site root). */
export function toAbsoluteImageUrl(imageUrl: string): string {
  if (!imageUrl) return "";
  if (imageUrl.startsWith("http")) return imageUrl;
  const p = imageUrl.startsWith("/") ? imageUrl : `/${imageUrl}`;
  return `${SITE_URL}${p}`;
}

function normalizeCategory(raw: string): string {
  const trimmed = (raw || "").trim();
  const map: Record<string, string> = {
    tv: "Smart Home",
    robotics: "Smart Home",
    "tv device": "Streaming",
    "?": "Electronics",
    "": "Electronics",
    " fitness": "Fitness",
    "fitness ": "Fitness",
    computers: "Laptops",
    computer: "Laptops",
    "desktop computers": "Laptops",
    "desktop computer": "Laptops",
    "pcs & laptops": "Laptops",
  };
  const lower = trimmed.toLowerCase();
  return map[lower] ?? (trimmed || "Electronics");
}

function assignBadge(affiliatePotential: number, bsrRank: number, rating: number): Product["badge"] {
  if (affiliatePotential >= 9) return "hot";
  if (bsrRank <= 3) return "best-seller";
  if (rating >= 4.7) return "top-rated";
  return null;
}

let _cache: Product[] | null = null;

export function getAllProducts(): Product[] {
  if (_cache) return _cache;

  // Use pre-built JSON if available (generated by prebuild script — much faster)
  const jsonPath = path.join(process.cwd(), "products.json");
  if (fs.existsSync(jsonPath)) {
    _cache = JSON.parse(fs.readFileSync(jsonPath, "utf-8")) as Product[];
    return _cache;
  }

  const csvPath = path.join(process.cwd(), "..", "products", "top-1000.csv");
  const csvContent = fs.readFileSync(csvPath, "utf-8");

  const result = Papa.parse(csvContent, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h: string) => h.trim(),
  });

  const seen = new Set<string>();
  const products: Product[] = [];

  for (const row of result.data as Record<string, string>[]) {
    const name = (row["Product Name"] || "").trim();
    if (!name) continue;

    const slug = slugify(name);
    if (seen.has(slug)) continue;
    seen.add(slug);

    const category = normalizeCategory(row["Category"]);
    const price = parsePrice(row["Price Range"]);
    const reviewCount = parseInt(String(row["Review Count"] || "0").replace(/[^0-9]/g, ""), 10) || 0;
    const rating = (() => {
      const n = parseFloat(String(row["Rating"]));
      return isNaN(n) || n < 1 || n > 5 ? 4.5 : n;
    })();
    const bsr = (row["BSR"] || "").trim();
    const bsrRank = parseBsrRank(bsr);
    const affiliatePotential = parseInt(row["Affiliate Potential"] || "7", 10) || 7;

    // Use actual Amazon URL from CSV — fall back to search only if missing
    const rawUrl = (row["Amazon URL"] || "").trim();
    const amazonUrl = rawUrl.startsWith("http")
      ? rawUrl
      : `https://www.amazon.com/s?k=${encodeURIComponent(name)}&tag=hotproduct033-20`;

    const asin = extractAsin(amazonUrl);
    const refreshedRaw = (row["Refreshed Date"] || "").trim();
    const refreshedTs = parseRefreshedDate(refreshedRaw);
    const actionNeeded = (row["Action Needed"] || "").trim().toLowerCase();
    const iLoved = actionNeeded.includes("loved");

    // Limited-time deal columns (fetch_daily_deals.py); empty on permanent rows.
    const discountPct = parseInt(row["Discount %"] || "0", 10) || 0;
    const limitedDeal =
      ((row["Temporary"] || "").trim() === "daily-deal" ||
        (row["Deal Date"] || "").trim() !== "") &&
      discountPct > 0;
    const dealDateTs = parseRefreshedDate((row["Deal Date"] || "").trim());
    const listPrice = parseFloat(row["List Price"] || "") || 0;
    const boughtPastMonth = parseInt(row["Bought Past Month"] || "0", 10) || 0;

    products.push({
      name,
      slug,
      category,
      categorySlug: slugify(category),
      priceRange: price.display,
      priceMin: price.min,
      priceMax: price.max,
      reviewCount,
      rating,
      bsr,
      bsrRank,
      affiliatePotential,
      amazonUrl,
      imageUrl: getImageUrl(slug, asin),
      badge: assignBadge(affiliatePotential, bsrRank, rating),
      refreshedDate: refreshedTs > 0 ? refreshedRaw : undefined,
      refreshedTs: refreshedTs > 0 ? refreshedTs : undefined,
      iLoved: iLoved || undefined,
      limitedDeal: limitedDeal || undefined,
      dealDateTs: dealDateTs > 0 ? dealDateTs : undefined,
      listPrice: listPrice > 0 ? listPrice : undefined,
      discountPct: discountPct > 0 ? discountPct : undefined,
      boughtPastMonth: boughtPastMonth > 0 ? boughtPastMonth : undefined,
    });
  }

  _cache = products;
  return products;
}

export function getProductBySlug(slug: string): Product | undefined {
  return getAllProducts().find((p) => p.slug === slug);
}

export function getProductsByCategory(categorySlug: string): Product[] {
  return getAllProducts().filter((p) => p.categorySlug === categorySlug);
}

/** UTC calendar day for seeded featured rotation; override in CI with FEATURED_DAY=YYYY-MM-DD. */
function featuredCalendarDay(): string {
  const fromEnv = (process.env.FEATURED_DAY || "").trim();
  if (fromEnv) return fromEnv;
  return new Date().toISOString().slice(0, 10);
}

function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seededShuffle<T>(items: T[], seed: number): T[] {
  const arr = [...items];
  const rnd = mulberry32(seed);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    const tmp = arr[i]!;
    arr[i] = arr[j]!;
    arr[j] = tmp;
  }
  return arr;
}

/**
 * Homepage "Top Picks": deterministic mix that changes each UTC day.
 * Draws from the strongest products, then shuffles with a date seed so the grid is not static.
 */
export function getFeaturedProducts(count = 12): Product[] {
  const day = featuredCalendarDay();
  const all = getAllProducts();
  const poolSize = Math.min(Math.max(count * 15, 120), all.length);
  const pool = [...all]
    .sort((a, b) => b.affiliatePotential - a.affiliatePotential || b.rating - a.rating)
    .slice(0, poolSize);
  const seed = hashString(`featured|${day}|v1|${all.length}`);
  return seededShuffle(pool, seed).slice(0, count);
}

/**
 * "Hot Deals" section: highest affiliate-potential products with strong BSR.
 * Sorted by affiliate potential desc, then BSR rank asc (lower = better).
 */
export function getSaleProducts(count = 6): Product[] {
  return getAllProducts()
    // Exclude limited-time deals — they have their own homepage section.
    .filter((p) => p.affiliatePotential >= 8 && !p.limitedDeal)
    .sort((a, b) => b.affiliatePotential - a.affiliatePotential || a.bsrRank - b.bsrRank)
    .slice(0, count);
}

/** Deal batches older than this are stale (cron missed a run) — hide them. */
const LIMITED_DEAL_MAX_AGE_MS = 2 * 24 * 60 * 60 * 1000;

/**
 * "Limited Time Sale" section: today's on-sale batch from fetch_daily_deals.py,
 * ranked by sales velocity ("bought in past month" badge, review-count
 * fallback) × discount %. Empty when the batch is stale or absent.
 */
export function getLimitedTimeDeals(count = 25): Product[] {
  const now = Date.now();
  const velocity = (p: Product) =>
    (p.boughtPastMonth || Math.max(p.reviewCount, 1) / 10) * (p.discountPct ?? 0);
  return getAllProducts()
    .filter(
      (p) =>
        p.limitedDeal &&
        (p.discountPct ?? 0) > 0 &&
        (p.dealDateTs ?? 0) > 0 &&
        now - (p.dealDateTs ?? 0) <= LIMITED_DEAL_MAX_AGE_MS,
    )
    .sort((a, b) => velocity(b) - velocity(a))
    .slice(0, count);
}

export interface InstagramPostedProduct extends Product {
  postedAt: string;
  postedTs: number;
  mediaId: string;
}

/**
 * "Latest" feed: products that were successfully posted to Instagram,
 * newest post first. Reads marketing-campaigns/post_log.csv at build time
 * (page is statically generated, so file IO happens once per build).
 *
 * Dedupes by product slug, keeping the most recent post for each.
 * Skips entries whose product name no longer matches any row in the catalog.
 */
export function getInstagramPostedProducts(count = 50): InstagramPostedProduct[] {
  const all = getAllProducts();
  const bySlug = new Map(all.map((p) => [p.slug, p]));
  const byName = new Map(all.map((p) => [p.name, p]));

  const csvPath = path.join(process.cwd(), "..", "marketing-campaigns", "post_log.csv");
  let csvContent = "";
  try {
    csvContent = fs.readFileSync(csvPath, "utf-8");
  } catch {
    return [];
  }

  const result = Papa.parse(csvContent, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h: string) => h.trim(),
  });

  const newest = new Map<string, InstagramPostedProduct>();
  for (const row of result.data as Record<string, string>[]) {
    if ((row["Platform"] || "").trim() !== "instagram") continue;
    if ((row["Status"] || "").trim() !== "ok") continue;

    const productName = (row["Product"] || "").trim();
    if (!productName) continue;

    const product = byName.get(productName) ?? bySlug.get(slugify(productName));
    if (!product) continue;

    const postedAt = (row["Date"] || "").trim();
    const postedTs = parseRefreshedDate(postedAt);
    if (postedTs <= 0) continue;

    const existing = newest.get(product.slug);
    if (!existing || postedTs > existing.postedTs) {
      newest.set(product.slug, {
        ...product,
        postedAt,
        postedTs,
        mediaId: (row["Detail"] || "").trim(),
      });
    }
  }

  return Array.from(newest.values())
    .sort((a, b) => b.postedTs - a.postedTs)
    .slice(0, count);
}

export function getILovedProducts(): Product[] {
  return getAllProducts().filter((p) => p.iLoved === true);
}

export function getAllCategories() {
  const products = getAllProducts();
  const map = new Map<string, { name: string; slug: string; count: number }>();
  for (const p of products) {
    if (!map.has(p.categorySlug)) {
      map.set(p.categorySlug, { name: p.category, slug: p.categorySlug, count: 0 });
    }
    map.get(p.categorySlug)!.count++;
  }
  return Array.from(map.values()).sort((a, b) => b.count - a.count);
}
