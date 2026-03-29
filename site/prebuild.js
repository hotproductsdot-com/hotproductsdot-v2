// Prebuild: parse CSV + resolve image URLs once, write products.json.
// Workers read this JSON directly — skips CSV parsing and ~10k existsSync calls.
const Papa = require('./node_modules/papaparse');
const fs = require('fs');
const path = require('path');

const csvPath = path.join(__dirname, '..', 'products', 'top-1000.csv');
const imgDir = path.join(__dirname, 'public', 'products');
const outPath = path.join(__dirname, 'products.json');

function slugify(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function parsePrice(raw) {
  const cleaned = (raw || '').replace(/[$,]/g, '').trim();
  if (!cleaned || !/\d/.test(cleaned)) return { display: 'Check Price', min: 0, max: 0 };
  const rangeMatch = cleaned.match(/(\d+)\s*-\s*(\d+)/);
  if (rangeMatch) {
    const low = parseInt(rangeMatch[1], 10);
    const high = parseInt(rangeMatch[2], 10);
    if (low === 0 && high === 0) return { display: 'Check Price', min: 0, max: 0 };
    return { display: `$${low.toLocaleString()}–$${high.toLocaleString()}`, min: low, max: high };
  }
  const single = cleaned.match(/(\d+)/);
  if (single) {
    const price = parseInt(single[1], 10);
    if (price === 0) return { display: 'Check Price', min: 0, max: 0 };
    return { display: `$${price.toLocaleString()}`, min: price, max: price };
  }
  return { display: 'Check Price', min: 0, max: 0 };
}

function parseBsrRank(bsr) {
  const match = bsr.replace(/,/g, '').match(/#?(\d+)/);
  return match ? parseInt(match[1], 10) : 9999;
}

function extractAsin(url) {
  const match = url.match(/\/dp\/([A-Z0-9]{10})/);
  return match ? match[1] : '';
}

function asinToImageUrl(asin) {
  if (!asin) return '';
  return `https://m.media-amazon.com/images/P/${asin}.01._SCLZZZZZZZ_SX500_.jpg`;
}

function normalizeCategory(raw) {
  const trimmed = (raw || '').trim();
  const map = {
    tv: 'Smart Home', robotics: 'Smart Home', 'tv device': 'Streaming',
    '?': 'Electronics', '': 'Electronics', ' fitness': 'Fitness',
    'fitness ': 'Fitness', computers: 'Laptops', computer: 'Laptops',
    'desktop computers': 'Laptops', 'desktop computer': 'Laptops',
    'pcs & laptops': 'Laptops',
  };
  const lower = trimmed.toLowerCase();
  return map[lower] ?? (trimmed || 'Electronics');
}

function assignBadge(affiliatePotential, bsrRank, rating) {
  if (affiliatePotential >= 9) return 'hot';
  if (bsrRank <= 3) return 'best-seller';
  if (rating >= 4.7) return 'top-rated';
  return null;
}

// Read image directory once
const imageFiles = new Set(fs.existsSync(imgDir) ? fs.readdirSync(imgDir) : []);

function getImageUrl(slug, asin) {
  if (imageFiles.has(`${slug}.jpg`)) return `/products/${slug}.jpg`;
  if (imageFiles.has(`${slug}.svg`)) return `/products/${slug}.svg`;
  return asinToImageUrl(asin);
}

const csvContent = fs.readFileSync(csvPath, 'utf-8');
const result = Papa.parse(csvContent, { header: true, skipEmptyLines: true, transformHeader: h => h.trim() });

const seen = new Set();
const products = [];

for (const row of result.data) {
  const name = (row['Product Name'] || '').trim();
  if (!name) continue;
  const slug = slugify(name);
  if (seen.has(slug)) continue;
  seen.add(slug);

  const category = normalizeCategory(row['Category']);
  const price = parsePrice(row['Price Range']);
  const reviewCount = parseInt(String(row['Review Count'] || '0').replace(/[^0-9]/g, ''), 10) || 0;
  const ratingRaw = parseFloat(String(row['Rating']));
  const rating = isNaN(ratingRaw) || ratingRaw < 1 || ratingRaw > 5 ? 4.5 : ratingRaw;
  const bsr = (row['BSR'] || '').trim();
  const bsrRank = parseBsrRank(bsr);
  const affiliatePotential = parseInt(row['Affiliate Potential'] || '7', 10) || 7;
  const rawUrl = (row['Amazon URL'] || '').trim();
  const amazonUrl = rawUrl.startsWith('http')
    ? rawUrl
    : `https://www.amazon.com/s?k=${encodeURIComponent(name)}&tag=hotproduct033-20`;
  const asin = extractAsin(amazonUrl);

  products.push({
    name, slug, category, categorySlug: slugify(category),
    priceRange: price.display, priceMin: price.min, priceMax: price.max,
    reviewCount, rating, bsr, bsrRank, affiliatePotential, amazonUrl,
    imageUrl: getImageUrl(slug, asin),
    badge: assignBadge(affiliatePotential, bsrRank, rating),
  });
}

fs.writeFileSync(outPath, JSON.stringify(products));
console.log(`prebuild: wrote ${products.length} products to products.json`);
