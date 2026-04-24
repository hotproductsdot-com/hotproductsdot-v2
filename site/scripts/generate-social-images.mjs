// Build-time generator: renders Instagram-ready 1080x1080 PNGs for each product.
//
// Usage:
//   node scripts/generate-social-images.mjs                    # all products
//   node scripts/generate-social-images.mjs apple-ipad-pro-13-inch-m4   # one slug
//
// Output: site/public/social/<slug>.png
//
// Replaces the Python banner_compose.py pipeline. React-free — uses raw
// Satori VDOM objects to keep the script tiny and dependency-minimal.

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PRODUCTS_JSON = path.join(ROOT, 'products.json');
const PRODUCTS_IMG_DIR = path.join(ROOT, 'public', 'products');
const OUT_DIR = path.join(ROOT, 'public', 'social');
const FONT_DIR = path.join(ROOT, 'node_modules', '@fontsource', 'inter', 'files');

const SIZE = 1080;
const ORANGE = '#FF6B00';
const BG = '#0f0f0f';
const TEXT_DIM = '#9ca3af';

const FONT_SOURCES = [
  { weight: 400, file: 'inter-latin-400-normal.woff' },
  { weight: 700, file: 'inter-latin-700-normal.woff' },
  { weight: 900, file: 'inter-latin-900-normal.woff' },
];

async function loadFonts() {
  return Promise.all(FONT_SOURCES.map(async ({ weight, file }) => {
    const data = await fs.readFile(path.join(FONT_DIR, file));
    return { name: 'Inter', data, weight, style: 'normal' };
  }));
}

async function readProductImage(slug) {
  const p = path.join(PRODUCTS_IMG_DIR, `${slug}.jpg`);
  try {
    const buf = await fs.readFile(p);
    return `data:image/jpeg;base64,${buf.toString('base64')}`;
  } catch {
    return null;
  }
}

function pickBadge({ reviewCount, bsrRank, rating }) {
  if (reviewCount >= 10000) return 'VIRAL';
  if (bsrRank === 1) return 'AMAZON #1';
  if (rating >= 4.7) return "EDITOR'S PICK";
  return 'TRENDING';
}

// Raw Satori VDOM node: { type, props: { style, children } }
const el = (type, style, children) => ({ type, props: { style, children } });

// SVG star path (viewBox 0 0 24 24, pointing up).
const STAR_PATH = 'M12 2l2.9 6.9 7.5.6-5.7 4.9 1.8 7.3L12 17.8 5.5 21.7l1.8-7.3L1.6 9.5l7.5-.6L12 2z';

function star(filled) {
  return {
    type: 'svg',
    props: {
      width: 32, height: 32, viewBox: '0 0 24 24',
      style: { marginRight: 4 },
      children: [{
        type: 'path',
        props: { d: STAR_PATH, fill: filled ? '#FFB800' : '#4a4a4a' },
      }],
    },
  };
}

function starRow(rating) {
  const full = Math.round(rating);
  return Array.from({ length: 5 }, (_, i) => star(i < full));
}

function card(product, imgDataUri) {
  const badge = pickBadge(product);
  const reviewsLabel = `${product.rating.toFixed(1)}/5  ·  ${product.reviewCount.toLocaleString()} verified reviews`;

  return el('div', {
    width: SIZE, height: SIZE, display: 'flex', flexDirection: 'column',
    backgroundColor: BG, color: '#fff', fontFamily: 'Inter',
    padding: '56px 64px 48px',
  }, [
    // Badge
    el('div', { display: 'flex', justifyContent: 'center' }, [
      el('div', {
        backgroundColor: ORANGE, color: '#fff',
        fontSize: 22, fontWeight: 700, padding: '10px 26px',
        borderRadius: 999, letterSpacing: 1,
      }, badge),
    ]),

    // Title
    el('div', {
      display: 'flex', justifyContent: 'center', marginTop: 24,
    }, [
      el('div', {
        fontSize: 68, fontWeight: 900, textAlign: 'center',
        lineHeight: 1.1, maxWidth: 900,
      }, product.name),
    ]),

    // Rating line
    el('div', {
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      gap: 12, fontSize: 26, color: TEXT_DIM, marginTop: 18,
    }, [
      el('div', { display: 'flex', alignItems: 'center' }, starRow(product.rating)),
      el('span', {}, reviewsLabel),
    ]),

    // Price
    el('div', { display: 'flex', justifyContent: 'center', marginTop: 10 }, [
      el('div', {
        fontSize: 60, fontWeight: 900, color: ORANGE,
      }, product.priceRange),
    ]),

    // Product image
    el('div', {
      display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center',
      marginTop: 24, marginBottom: 24,
    }, imgDataUri ? [{
      type: 'img',
      props: { src: imgDataUri, width: 720, height: 560, style: { objectFit: 'contain' } },
    }] : []),

    // Bottom pills
    el('div', {
      display: 'flex', justifyContent: 'center', gap: 18,
    }, [
      el('div', {
        border: `2px solid ${ORANGE}`, borderRadius: 999,
        padding: '12px 28px', fontSize: 22, fontWeight: 700, color: '#fff',
      }, 'hotproductsdot.com'),
      el('div', {
        border: `2px solid ${ORANGE}`, borderRadius: 999,
        padding: '12px 28px', fontSize: 22, fontWeight: 700, color: '#fff',
      }, product.category),
    ]),
  ]);
}

async function renderOne(product, fonts) {
  const imgDataUri = await readProductImage(product.slug);
  const tree = card(product, imgDataUri);
  const svg = await satori(tree, { width: SIZE, height: SIZE, fonts });
  const resvg = new Resvg(svg, { background: BG, fitTo: { mode: 'width', value: SIZE } });
  const png = resvg.render().asPng();
  const out = path.join(OUT_DIR, `${product.slug}.png`);
  await fs.writeFile(out, png);
  return out;
}

async function main() {
  const filter = process.argv[2];
  const products = JSON.parse(await fs.readFile(PRODUCTS_JSON, 'utf8'));
  const picks = filter ? products.filter(p => p.slug === filter) : products;
  if (!picks.length) {
    console.error(`No products matched${filter ? ` slug=${filter}` : ''}`);
    process.exit(1);
  }

  await fs.mkdir(OUT_DIR, { recursive: true });
  console.log('Loading fonts…');
  const fonts = await loadFonts();
  console.log(`Rendering ${picks.length} card${picks.length === 1 ? '' : 's'}…`);

  for (const product of picks) {
    const out = await renderOne(product, fonts);
    console.log(`  ✓ ${product.slug} → ${path.relative(ROOT, out)}`);
  }
}

main().catch(err => { console.error(err); process.exit(1); });
