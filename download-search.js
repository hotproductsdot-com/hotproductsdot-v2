/**
 * Download product images using Amazon search (by product name, not ASIN).
 * More resilient than ASIN lookup — works even with stale ASINs.
 */

const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');
const path = require('path');

const csv = fs.readFileSync('./products/top-1000.csv', 'utf-8');
const result = Papa.parse(csv, { header: true, skipEmptyLines: true });

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

const userAgents = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
];

async function searchAmazon(productName) {
  const ua = userAgents[Math.floor(Math.random() * userAgents.length)];
  const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(productName)}`;

  const res = await fetch(searchUrl, {
    headers: {
      'User-Agent': ua,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Cache-Control': 'no-cache',
      'Referer': 'https://www.amazon.com/',
    },
    redirect: 'follow',
  });

  if (!res.ok) throw new Error(`Search HTTP ${res.status}`);
  const html = await res.text();

  if (html.includes('captcha') || html.includes('robot check') || html.includes('Enter the characters')) {
    throw new Error('CAPTCHA detected');
  }

  // Try to extract the first product image from search results
  const patterns = [
    /class="s-image"[^>]*src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/,
    /src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+_AC_UL\d+[^"]*)"[^>]*class="s-image"/,
    /"thumbnail"\s*:\s*"(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/,
    /src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+_AC_[^"]+)"/,
  ];

  let imageUrl = null;
  for (const pattern of patterns) {
    const m = html.match(pattern);
    if (m) {
      imageUrl = m[1];
      break;
    }
  }

  if (!imageUrl) throw new Error('No image found in search results');

  // Upgrade thumbnail to larger size
  imageUrl = imageUrl
    .replace(/_AC_UL\d+_SR\d+,\d+_/, '_AC_SL1500_')
    .replace(/_AC_UY\d+_/, '_AC_SL1500_')
    .replace(/_AC_UL\d+_/, '_AC_SL1500_')
    .replace(/_SX\d+_/, '_SX1500_')
    .replace(/_SY\d+_/, '_SY1500_');

  return imageUrl;
}

async function downloadImage(imageUrl, outputPath) {
  const ua = userAgents[Math.floor(Math.random() * userAgents.length)];
  const res = await fetch(imageUrl, {
    headers: { 'User-Agent': ua, 'Accept': 'image/*,*/*' },
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const buffer = Buffer.from(await res.arrayBuffer());
  if (buffer.length < 1000) throw new Error(`Image too small (${buffer.length} bytes) — likely error page`);
  fs.writeFileSync(outputPath, buffer);
  return buffer.length;
}

async function main() {
  const outDir = './site/public/products';
  const seen = new Set();
  const allProducts = [];

  for (const row of result.data) {
    const name = (row['Product Name'] || '').trim();
    if (!name) continue;
    const slug = slugify(name);
    if (seen.has(slug)) continue;
    seen.add(slug);
    const jpgPath = path.join(outDir, slug + '.jpg');
    const svgPath = path.join(outDir, slug + '.svg');
    const hasImage = fs.existsSync(jpgPath);
    allProducts.push({ name, slug, jpgPath, svgPath, hasImage });
  }

  const toDownload = allProducts.filter(p => !p.hasImage);
  console.log(`Total products: ${allProducts.length}`);
  console.log(`Have images: ${allProducts.filter(p => p.hasImage).length}`);
  console.log(`Missing: ${toDownload.length}`);
  console.log('---');

  let downloaded = 0;
  let failed = 0;
  let captchaCount = 0;

  for (let i = 0; i < toDownload.length; i++) {
    const p = toDownload[i];

    if (captchaCount >= 3) {
      console.log(`[ABORT] Too many CAPTCHAs — stopping at ${i}/${toDownload.length}`);
      console.log('Wait a few minutes and re-run to continue.');
      break;
    }

    try {
      console.log(`[${i + 1}/${toDownload.length}] ${p.name}`);
      const imageUrl = await searchAmazon(p.name);
      const size = await downloadImage(imageUrl, p.jpgPath);
      console.log(`  ✓ ${p.slug}.jpg (${(size / 1024).toFixed(0)} KB)`);
      downloaded++;
      captchaCount = 0; // reset on success

      // Remove SVG placeholder if exists
      if (fs.existsSync(p.svgPath)) fs.unlinkSync(p.svgPath);

      // Random delay 3-6s to avoid rate limiting
      await sleep(3000 + Math.random() * 3000);
    } catch (err) {
      console.log(`  ✗ ${err.message}`);
      failed++;
      if (err.message.includes('CAPTCHA')) {
        captchaCount++;
        // Back off longer on CAPTCHA
        await sleep(15000 + Math.random() * 10000);
      } else {
        await sleep(2000);
      }
    }
  }

  console.log('---');
  console.log(`Done. Downloaded: ${downloaded}, Failed: ${failed}`);
  console.log('Re-run to pick up from where it stopped.');
}

main().catch(console.error);
