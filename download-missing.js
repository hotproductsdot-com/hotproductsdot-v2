const fs = require('fs');
const path = require('path');

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

// These products had 404 ASINs — try searching Amazon for them
const missing = [
];

async function searchAndDownload(product) {
  const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(product.search)}`;

  const res = await fetch(searchUrl, {
    headers: {
      'User-Agent': ua,
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Language': 'en-US,en;q=0.9',
    },
    redirect: 'follow',
  });

  if (!res.ok) throw new Error(`Search HTTP ${res.status}`);
  const html = await res.text();

  // Extract first product image from search results
  // Look for product images in search results
  const imgMatch = html.match(/class="s-image"[^>]*src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/);
  if (!imgMatch) {
    // Try alternative pattern
    const altMatch = html.match(/src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+_AC_[^"]+)"/);
    if (!altMatch) throw new Error('No image found in search results');
    return altMatch[1];
  }

  // Upgrade the search result thumbnail to a larger image
  let imageUrl = imgMatch[1];
  // Replace sizing suffix for larger image
  imageUrl = imageUrl.replace(/_AC_UL\d+_SR\d+,\d+_/, '_AC_SL1500_');
  imageUrl = imageUrl.replace(/_AC_UY\d+_/, '_AC_SL1500_');
  imageUrl = imageUrl.replace(/_AC_UL\d+_/, '_AC_SL1500_');

  return imageUrl;
}

async function downloadImage(imageUrl, outputPath) {
  const res = await fetch(imageUrl, {
    headers: { 'User-Agent': ua, 'Accept': 'image/*' },
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const buffer = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outputPath, buffer);
  return buffer.length;
}

async function main() {
  const outDir = './site/public/products';
  let downloaded = 0;

  for (const p of missing) {
    const jpgPath = path.join(outDir, p.slug + '.jpg');
    if (fs.existsSync(jpgPath)) {
      console.log(`[SKIP] ${p.slug} already exists`);
      continue;
    }

    try {
      console.log(`[SEARCH] ${p.slug}...`);
      const imageUrl = await searchAndDownload(p);
      const size = await downloadImage(imageUrl, jpgPath);
      console.log(`  ✓ Saved ${p.slug}.jpg (${(size / 1024).toFixed(0)} KB)`);
      downloaded++;

      // Remove SVG placeholder if exists
      const svgPath = path.join(outDir, p.slug + '.svg');
      if (fs.existsSync(svgPath)) fs.unlinkSync(svgPath);

      await sleep(3000 + Math.random() * 2000);
    } catch (err) {
      console.log(`  ✗ FAILED: ${err.message}`);
    }
  }

  console.log(`\nDone. Downloaded ${downloaded}/${missing.length}`);
}

main().catch(console.error);
