const fs = require('fs');
const path = require('path');

const ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

const toFix = [
  { slug: 'leica-m11-camera', search: 'Leica M11 Monochrom Digital Rangefinder Camera Black' },
];

async function searchAndDownload(product) {
  const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(product.search)}`;
  const res = await fetch(searchUrl, {
    headers: { 'User-Agent': ua, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-US,en;q=0.9' },
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`Search HTTP ${res.status}`);
  const html = await res.text();
  const imgMatch = html.match(/class="s-image"[^>]*src="(https:\/\/m\.media-amazon\.com\/images\/I\/[^"]+)"/);
  if (!imgMatch) throw new Error('No image found');
  let imageUrl = imgMatch[1];
  imageUrl = imageUrl.replace(/_AC_UL\d+_SR\d+,\d+_/, '_AC_SL1500_');
  imageUrl = imageUrl.replace(/_AC_UY\d+_/, '_AC_SL1500_');
  imageUrl = imageUrl.replace(/_AC_UL\d+_/, '_AC_SL1500_');
  return imageUrl;
}

async function main() {
  for (const p of toFix) {
    try {
      console.log(`[FIX] ${p.slug}...`);
      const imageUrl = await searchAndDownload(p);
      const jpgPath = path.join('./site/public/products', p.slug + '.jpg');
      const res = await fetch(imageUrl, { headers: { 'User-Agent': ua, 'Accept': 'image/*' } });
      if (!res.ok) throw new Error(`Download failed: ${res.status}`);
      const buffer = Buffer.from(await res.arrayBuffer());
      fs.writeFileSync(jpgPath, buffer);
      console.log(`  ✓ Replaced (${(buffer.length / 1024).toFixed(0)} KB)`);
    } catch (err) {
      console.log(`  ✗ FAILED: ${err.message}`);
    }
  }
}
main().catch(console.error);
