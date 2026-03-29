const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');
const path = require('path');

const CSV_PATH = './products/top-1000.csv';
const OUT_DIR = './site/public/products';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function findMissing() {
  const csv = fs.readFileSync(CSV_PATH, 'utf-8');
  const result = Papa.parse(csv, { header: true, skipEmptyLines: true });
  const seen = new Set();
  const missing = [];

  for (const row of result.data) {
    const name = (row['Product Name'] || '').trim();
    if (!name) continue;
    const slug = slugify(name);
    if (seen.has(slug)) continue;
    seen.add(slug);
    if (!fs.existsSync(path.join(OUT_DIR, slug + '.jpg'))) {
      missing.push({ slug, name });
    }
  }

  return missing;
}

async function findImageUrl(name) {
  const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(name)}`;
  const res = await fetch(searchUrl, {
    headers: {
      'User-Agent': UA,
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Language': 'en-US,en;q=0.9',
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
    headers: { 'User-Agent': UA, 'Accept': 'image/*' },
  });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const buffer = Buffer.from(await res.arrayBuffer());
  fs.writeFileSync(outputPath, buffer);
  return buffer.length;
}

async function main() {
  const missing = findMissing();

  if (missing.length === 0) {
    console.log('✓ All product images present — nothing to do.');
    return;
  }

  console.log(`Found ${missing.length} missing image(s):\n`);
  missing.forEach(p => console.log(`  • ${p.slug}`));
  console.log('');

  let downloaded = 0;
  let failed = 0;

  for (const p of missing) {
    const jpgPath = path.join(OUT_DIR, p.slug + '.jpg');
    try {
      console.log(`[SEARCH] ${p.slug}...`);
      const imageUrl = await findImageUrl(p.name);
      const size = await downloadImage(imageUrl, jpgPath);
      console.log(`  ✓ Saved ${p.slug}.jpg (${(size / 1024).toFixed(0)} KB)`);
      downloaded++;

      const svgPath = path.join(OUT_DIR, p.slug + '.svg');
      if (fs.existsSync(svgPath)) fs.unlinkSync(svgPath);

      await sleep(3000 + Math.random() * 2000);
    } catch (err) {
      console.log(`  ✗ FAILED: ${err.message}`);
      failed++;
    }
  }

  console.log(`\nDone. Downloaded ${downloaded}/${missing.length}${failed > 0 ? `, ${failed} failed` : ''}.`);

  if (failed > 0) process.exit(1);
}

main().catch(err => { console.error(err); process.exit(1); });
