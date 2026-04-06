#!/usr/bin/env node
// Daily homepage rotation: injects fresh featured products into rotation-base.html
// and writes out/index.html — no Next.js build required.
//
// Prerequisites: products.json must exist (run `node prebuild.js` first).
// Usage: FEATURED_DAY=2026-04-07 node scripts/rotate-homepage.js

const fs = require("fs");
const path = require("path");

const siteDir = path.join(__dirname, "..");
const basePath = path.join(siteDir, "rotation-base.html");
const productsPath = path.join(siteDir, "products.json");
const outDir = path.join(siteDir, "out");
const outPath = path.join(outDir, "index.html");

// ── Featured selection (mirrors products.ts getFeaturedProducts) ──────────────

function featuredCalendarDay() {
  const fromEnv = (process.env.FEATURED_DAY || "").trim();
  return fromEnv || new Date().toISOString().slice(0, 10);
}

function hashString(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seededShuffle(items, seed) {
  const arr = [...items];
  const rnd = mulberry32(seed);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    const tmp = arr[i];
    arr[i] = arr[j];
    arr[j] = tmp;
  }
  return arr;
}

function getFeaturedProducts(all, count = 8) {
  const day = featuredCalendarDay();
  const poolSize = Math.min(Math.max(count * 15, 120), all.length);
  const pool = [...all]
    .sort((a, b) => b.affiliatePotential - a.affiliatePotential || b.rating - a.rating)
    .slice(0, poolSize);
  const seed = hashString(`featured|${day}|v1|${all.length}`);
  return seededShuffle(pool, seed).slice(0, count);
}

// ── HTML generators (mirrors component output) ────────────────────────────────

const STAR_PATH =
  "M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z";

function renderStars(rating) {
  let out =
    `<span class="flex items-center gap-0.5" aria-label="${rating} out of 5 stars">`;
  for (let i = 1; i <= 5; i++) {
    const filled = rating >= i;
    const half = !filled && rating >= i - 0.5;
    const color = filled || half ? "text-amber-400" : "text-zinc-700";
    out += `<svg class="w-3.5 h-3.5 ${color}" viewBox="0 0 20 20" fill="currentColor">`;
    if (half) {
      out +=
        `<defs><linearGradient id="h${i}">` +
        `<stop offset="50%" stop-color="currentColor"></stop>` +
        `<stop offset="50%" stop-color="#3f3f46"></stop>` +
        `</linearGradient></defs>` +
        `<path fill="url(#h${i})" d="${STAR_PATH}"></path>`;
    } else {
      out += `<path d="${STAR_PATH}"></path>`;
    }
    out += `</svg>`;
  }
  out += `</span>`;
  return out;
}

const BADGE_CONFIG = {
  hot: { label: "🔥 Hot Pick", cls: "bg-orange-500 text-white" },
  "top-rated": { label: "⭐ Top Rated", cls: "bg-amber-500 text-white" },
  "best-seller": { label: "# Best Seller", cls: "bg-emerald-600 text-white" },
};

function renderBadge(badge) {
  const b = BADGE_CONFIG[badge];
  if (!b) return "";
  return (
    `<span class="absolute top-2.5 left-2.5 text-[10px] font-bold px-2 py-0.5 ` +
    `rounded-full uppercase tracking-wide ${b.cls}">${b.label}</span>`
  );
}

function buildAffiliateUrl(amazonUrl, slug) {
  try {
    const url = new URL(amazonUrl);
    url.searchParams.set("tag", "hotproduct033-20");
    url.searchParams.set("utm_source", "hotproducts");
    url.searchParams.set("utm_medium", "website");
    url.searchParams.set("utm_campaign", "product-card");
    url.searchParams.set("utm_content", slug);
    return url.toString();
  } catch {
    return amazonUrl;
  }
}

function formatCount(n) {
  return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n);
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderCard(p) {
  const affiliateUrl = buildAffiliateUrl(p.amazonUrl, p.slug);
  // Mirrors ProductImage SSR output: loading skeleton + hidden img (status="loading")
  const imgStyle =
    "position:absolute;height:100%;width:100%;left:0;top:0;right:0;bottom:0;color:transparent;opacity:0";

  return (
    `<article class="group flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-xl hover:shadow-orange-500/5">` +
    `<a class="block" href="/products/${p.slug}">` +
    `<div class="relative aspect-[4/3] bg-white flex items-center justify-center overflow-hidden">` +
    `<div class="absolute inset-0 animate-pulse bg-zinc-100"></div>` +
    `<img alt="${esc(p.name)}" loading="lazy" decoding="async" data-nimg="fill"` +
    ` class="w-full h-full object-contain p-4 group-hover:scale-105 transition-transform duration-300"` +
    ` style="${imgStyle}" src="${esc(p.imageUrl)}"/>` +
    `</div>` +
    renderBadge(p.badge) +
    `</a>` +
    `<div class="flex flex-col flex-1 p-4 gap-3">` +
    `<a href="/products/${p.slug}">` +
    `<h3 class="text-sm font-semibold text-zinc-100 leading-snug line-clamp-2 group-hover:text-orange-400 transition-colors">${esc(p.name)}</h3>` +
    `</a>` +
    `<div class="flex items-center gap-2">` +
    renderStars(p.rating) +
    `<span class="text-[11px] text-zinc-500">${p.rating} (${formatCount(p.reviewCount)})</span>` +
    `</div>` +
    `<div class="mt-auto">` +
    `<a href="${esc(affiliateUrl)}" target="_blank" rel="noopener noreferrer nofollow sponsored" data-affiliate="true"` +
    ` class="w-full flex items-center justify-center gap-1 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold px-3 py-2 rounded-lg transition-colors">` +
    `Buy on Amazon \u2192</a>` +
    `</div>` +
    `</div>` +
    `</article>`
  );
}

function renderGrid(products) {
  return (
    `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">` +
    products.map(renderCard).join("") +
    `</div>`
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

if (!fs.existsSync(basePath)) {
  throw new Error(
    "rotation-base.html not found.\n" +
      "Run a full build first, then: node scripts/extract-rotation-base.js"
  );
}
if (!fs.existsSync(productsPath)) {
  throw new Error(
    "products.json not found.\n" +
      "Run: node prebuild.js"
  );
}

const base = fs.readFileSync(basePath, "utf-8");
const PLACEHOLDER = "<!--FEATURED_PLACEHOLDER-->";

if (!base.includes(PLACEHOLDER)) {
  throw new Error(
    "rotation-base.html does not contain <!--FEATURED_PLACEHOLDER-->.\n" +
      "Re-run extract-rotation-base.js after a full build."
  );
}

const all = JSON.parse(fs.readFileSync(productsPath, "utf-8"));
const day = featuredCalendarDay();
const featured = getFeaturedProducts(all, 8);
const newHtml = base.replace(PLACEHOLDER, renderGrid(featured));

if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(outPath, newHtml);

console.log(
  `rotate-homepage: wrote out/index.html — ${featured.length} products for ${day}`
);
