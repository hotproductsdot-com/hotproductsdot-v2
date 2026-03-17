const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');

const csv = fs.readFileSync('./products/top-1000.csv', 'utf-8');
const result = Papa.parse(csv, { header: true, skipEmptyLines: true });

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

const seen = new Set();
const products = [];

for (const row of result.data) {
  const name = (row['Product Name'] || '').trim();
  if (!name) continue;
  const slug = slugify(name);
  if (seen.has(slug)) continue;
  seen.add(slug);
  const hasLocal = fs.existsSync('./site/public/products/' + slug + '.jpg');
  const category = (row['Category'] || '').trim();
  products.push({ name, slug, category, hasLocal });
}

const missing = products.filter(p => !p.hasLocal);
console.log('Total unique products:', products.length);
console.log('Have local images:', products.filter(p => p.hasLocal).length);
console.log('Missing images:', missing.length);
console.log('---');
missing.forEach(p => console.log(p.slug + ' | ' + p.category + ' | ' + p.name));
