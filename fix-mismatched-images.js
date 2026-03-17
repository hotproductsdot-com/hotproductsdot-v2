const fs = require('fs');
const path = require('path');

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

// Products whose ASIN doesn't match (shared ASIN with different product, or wrong ASIN entirely)
const toFix = [
  // ASIN B0DYG9DKX8 is actually LG 45" OLED, not SANSUI
  { slug: 'sansui-27-inch-240hz-monitor', search: 'SANSUI 27 inch 240Hz gaming monitor 1440p' },
  // ASIN B0CZ1RTYQY is Dell UltraSharp 32, not AOC
  { slug: 'aoc-27-monitor', search: 'AOC 27 inch monitor' },
  // ASIN B09QF1H3VF is Dell XPS 17, not Leica M11
  { slug: 'leica-m11-camera', search: 'Leica M11 camera' },
  // ASIN B07Y47P31Y is Zhiyun Crane 4S, not WEEBill 3
  { slug: 'zhiyun-weebill-3', search: 'Zhiyun WEEBill 3 gimbal stabilizer' },
  // ASIN B0CXKXNNPX is Surface Pro 11, not Surface Laptop 5
  { slug: 'microsoft-surface-laptop-5', search: 'Microsoft Surface Laptop 5' },
  // ASIN B09N3G9T16 is LG 38", reused for LG 34" UltraWide
  { slug: 'lg-ultrawide-gaming-monitor-34', search: 'LG 34 inch UltraWide gaming monitor' },
  // ASIN B0CNS894RH shared — verify both are correct
  { slug: 'theragun-pro-2', search: 'Theragun Pro Plus massage gun' },
  // ASIN B0DFW9D66S shared
  { slug: 'autonomous-desk-pro', search: 'Autonomous SmartDesk Pro standing desk' },
  // ASIN B0D5BBYRJM shared — Nest Thermostat variants
  { slug: 'nest-thermostat-thermo', search: 'Google Nest Learning Thermostat 4th gen' },
  // ASIN B0DYJY27NS is a burner knob replacement part, not the actual stovetop
  { slug: 'thermador-pro-stovetop', search: 'Thermador Pro Grand range stovetop 36 inch' },
  // ASIN B09QF1H3VF is actually Leica M11, not Dell XPS 17
  { slug: 'dell-xps-17-laptop', search: 'Dell XPS 17 laptop 2024' },
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
    headers: { 'User-Agent': ua, 'Accept': 'image/*' },
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
