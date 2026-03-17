import Papa from "papaparse";
import fs from "fs";
import path from "path";

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

function getImageUrl(slug: string, asin: string): string {
  // Check for local images: jpg first, then svg placeholder
  const jpgPath = path.join(process.cwd(), "public", "products", `${slug}.jpg`);
  if (fs.existsSync(jpgPath)) {
    return `/products/${slug}.jpg`;
  }
  const svgPath = path.join(process.cwd(), "public", "products", `${slug}.svg`);
  if (fs.existsSync(svgPath)) {
    return `/products/${slug}.svg`;
  }
  return asinToImageUrl(asin);
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
      : `https://www.amazon.com/s?k=${encodeURIComponent(name)}&tag=hotproducts-20`;

    const asin = extractAsin(amazonUrl);

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

export function getFeaturedProducts(count = 12): Product[] {
  return getAllProducts()
    .sort((a, b) => b.affiliatePotential - a.affiliatePotential || b.rating - a.rating)
    .slice(0, count);
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
