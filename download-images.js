const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');
const path = require('path');

const csv = fs.readFileSync('./products/top-1000.csv', 'utf-8');
const result = Papa.parse(csv, { header: true, skipEmptyLines: true });

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function extractAsin(url) {
  const m = url.match(/\/dp\/([A-Z0-9]{10})/);
  return m ? m[1] : null;
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

async function fetchAmazonImage(asin) {
  const ua = userAgents[Math.floor(Math.random() * userAgents.length)];
  const url = `https://www.amazon.com/dp/${asin}`;

  const res = await fetch(url, {
    headers: {
      'User-Agent': ua,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Cache-Control': 'no-cache',
    },
    redirect: 'follow',
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${asin}`);
  }

  const html = await res.text();

  // Try multiple extraction methods
  let imageUrl = null;

  // Method 1: hiRes from colorImages JS data
  const hiResMatch = html.match(/"hiRes"\s*:\s*"(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/);
  if (hiResMatch) {
    imageUrl = hiResMatch[1];
  }

  // Method 2: landingImage src
  if (!imageUrl) {
    const landingMatch = html.match(/id="landingImage"[^>]*src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/);
    if (landingMatch) {
      imageUrl = landingMatch[1];
    }
  }

  // Method 3: og:image meta tag
  if (!imageUrl) {
    const ogMatch = html.match(/property="og:image"\s+content="(https:\/\/[^"]+)"/);
    if (!ogMatch) {
      const ogMatch2 = html.match(/content="(https:\/\/[^"]+)"\s+property="og:image"/);
      if (ogMatch2) imageUrl = ogMatch2[1];
    } else {
      imageUrl = ogMatch[1];
    }
  }

  // Method 4: any large product image
  if (!imageUrl) {
    const imgMatch = html.match(/"large"\s*:\s*"(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/);
    if (imgMatch) imageUrl = imgMatch[1];
  }

  if (!imageUrl) {
    // Check if we got a CAPTCHA page
    if (html.includes('captcha') || html.includes('robot')) {
      throw new Error(`CAPTCHA/bot detection for ${asin}`);
    }
    throw new Error(`No image found in page for ${asin}`);
  }

  return imageUrl;
}

async function downloadImage(imageUrl, outputPath) {
  const res = await fetch(imageUrl, {
    headers: {
      'User-Agent': userAgents[0],
      'Accept': 'image/*',
    },
  });

  if (!res.ok) throw new Error(`Failed to download image: ${res.status}`);

  const buffer = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outputPath, buffer);
  return buffer.length;
}

async function main() {
  const outDir = './site/public/products';
  const seen = new Set();
  const products = [];

  // Build deduplicated product list
  for (const row of result.data) {
    const name = (row['Product Name'] || '').trim();
    if (!name) continue;
    const slug = slugify(name);
    if (seen.has(slug)) continue;
    seen.add(slug);

    const asin = extractAsin(row['Amazon URL'] || '');
    const jpgPath = path.join(outDir, slug + '.jpg');
    const hasImage = fs.existsSync(jpgPath);
    products.push({ name, slug, asin, jpgPath, hasImage });
  }

  const toDownload = products.filter(p => !p.hasImage && p.asin);
  console.log(`Total products: ${products.length}`);
  console.log(`Already have images: ${products.filter(p => p.hasImage).length}`);
  console.log(`To download: ${toDownload.length}`);
  console.log('---');

  // Track ASINs we've already fetched (some products share ASINs)
  const asinImageCache = {};
  let downloaded = 0;
  let failed = 0;
  let captchaHit = false;

  for (let i = 0; i < toDownload.length; i++) {
    const p = toDownload[i];

    if (captchaHit) {
      console.log(`[SKIP] ${p.slug} — stopped due to CAPTCHA`);
      failed++;
      continue;
    }

    try {
      let imageUrl;

      if (asinImageCache[p.asin]) {
        imageUrl = asinImageCache[p.asin];
        console.log(`[CACHE] ${p.slug} (${p.asin})`);
      } else {
        console.log(`[${i + 1}/${toDownload.length}] Fetching ${p.slug} (${p.asin})...`);
        imageUrl = await fetchAmazonImage(p.asin);
        asinImageCache[p.asin] = imageUrl;

        // Random delay between requests (2-5 seconds)
        const delay = 2000 + Math.random() * 3000;
        await sleep(delay);
      }

      const size = await downloadImage(imageUrl, p.jpgPath);
      console.log(`  ✓ Saved ${p.slug}.jpg (${(size / 1024).toFixed(0)} KB)`);
      downloaded++;

      // Remove SVG placeholder if it exists
      const svgPath = path.join(outDir, p.slug + '.svg');
      if (fs.existsSync(svgPath)) {
        fs.unlinkSync(svgPath);
      }
    } catch (err) {
      console.log(`  ✗ FAILED: ${err.message}`);
      if (err.message.includes('CAPTCHA')) {
        captchaHit = true;
      }
      failed++;
    }
  }

  console.log('---');
  console.log(`Done. Downloaded: ${downloaded}, Failed: ${failed}`);
}

main().catch(console.error);
