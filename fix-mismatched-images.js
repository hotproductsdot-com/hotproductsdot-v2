const fs = require('fs');
const path = require('path');

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// Products whose image doesn't match — add { slug, search } entries here
const toFix = [
  { slug: 'herman-miller-aeron-chair', search: 'Herman Miller Aeron Chair ergonomic office' },
];

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
];

function randomUA() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

async function fetchWithRetry(url, options, maxRetries = 4) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    if (attempt > 0) {
      const delay = (2 ** attempt) * 2000 + Math.random() * 2000;
      console.log(`  → Retry ${attempt}/${maxRetries - 1} after ${(delay / 1000).toFixed(1)}s...`);
      await sleep(delay);
    }
    const res = await fetch(url, { ...options, headers: { ...options.headers, 'User-Agent': randomUA() } });
    if (res.status === 503 || res.status === 429) continue;
    return res;
  }
  throw new Error(`Search failed after ${maxRetries} attempts (rate limited)`);
}

async function searchAndDownload(product) {
  const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(product.search)}`;

  const res = await fetchWithRetry(searchUrl, {
    headers: {
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'gzip, deflate, br',
      'Cache-Control': 'no-cache',
    },
    redirect: 'follow',
  });

  if (!res.ok) throw new Error(`Search HTTP ${res.status}`);
  const html = await res.text();

  const imgMatch = html.match(/class="s-image"[^>]*src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/);
  if (!imgMatch) {
    const altMatch = html.match(/src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+_AC_[^"]+)"/);
    if (!altMatch) throw new Error('No image found in search results');
    return altMatch[1];
  }

  let imageUrl = imgMatch[1];
  imageUrl = imageUrl.replace(/_AC_UL\d+_SR\d+,\d+_/, '_AC_SL1500_');
  imageUrl = imageUrl.replace(/_AC_UY\d+_/, '_AC_SL1500_');
  imageUrl = imageUrl.replace(/_AC_UL\d+_/, '_AC_SL1500_');
  return imageUrl;
}

async function downloadImage(imageUrl, outputPath) {
  const res = await fetch(imageUrl, {
    headers: { 'User-Agent': randomUA(), 'Accept': 'image/*' },
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const buffer = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outputPath, buffer);
  return buffer.length;
}

async function main() {
  const outDir = './site/public/products';
  let fixed = 0;

  for (const p of toFix) {
    try {
      console.log(`[FIX] ${p.slug}...`);
      const imageUrl = await searchAndDownload(p);
      const jpgPath = path.join(outDir, p.slug + '.jpg');
      const size = await downloadImage(imageUrl, jpgPath);
      console.log(`  ✓ Replaced ${p.slug}.jpg (${(size / 1024).toFixed(0)} KB)`);
      fixed++;
      await sleep(3000 + Math.random() * 2000);
    } catch (err) {
      console.log(`  ✗ FAILED: ${err.message}`);
    }
  }

  console.log(`\nDone. Fixed ${fixed}/${toFix.length} images`);
}

main().catch(console.error);
