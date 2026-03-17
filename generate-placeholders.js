const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');
const path = require('path');

const csv = fs.readFileSync('./products/top-1000.csv', 'utf-8');
const result = Papa.parse(csv, { header: true, skipEmptyLines: true });

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

const categoryColors = {
  'Laptops':            { bg: '#1e293b', accent: '#3b82f6', icon: '💻' },
  'Gaming Laptops':     { bg: '#1a1a2e', accent: '#8b5cf6', icon: '🎮' },
  'Gaming Desktops':    { bg: '#1a1a2e', accent: '#7c3aed', icon: '🖥️' },
  'Gaming Peripherals': { bg: '#1a1a2e', accent: '#a78bfa', icon: '🕹️' },
  'Gaming Headsets':    { bg: '#1a1a2e', accent: '#6d28d9', icon: '🎧' },
  'Headphones':         { bg: '#1c1917', accent: '#f97316', icon: '🎧' },
  'Audio':              { bg: '#1c1917', accent: '#ea580c', icon: '🎵' },
  'Speakers':           { bg: '#1c1917', accent: '#fb923c', icon: '🔊' },
  'Monitors':           { bg: '#0f172a', accent: '#06b6d4', icon: '🖥️' },
  'Smart Home':         { bg: '#0d1b2a', accent: '#22d3ee', icon: '🏠' },
  'Smart Displays':     { bg: '#0d1b2a', accent: '#0ea5e9', icon: '📺' },
  'Security':           { bg: '#1a0a0a', accent: '#ef4444', icon: '🔒' },
  'Photography':        { bg: '#1a1a1a', accent: '#f59e0b', icon: '📷' },
  'Drones':             { bg: '#0a1628', accent: '#14b8a6', icon: '🚁' },
  'Kitchen':            { bg: '#1a1209', accent: '#d97706', icon: '🍳' },
  'Home':               { bg: '#1a1209', accent: '#a3e635', icon: '🏡' },
  'Furniture':          { bg: '#1a1612', accent: '#78716c', icon: '🪑' },
  'Fitness':            { bg: '#0a1a0a', accent: '#22c55e', icon: '💪' },
  'Tablets':            { bg: '#1e293b', accent: '#60a5fa', icon: '📱' },
  'Computers':          { bg: '#1e293b', accent: '#818cf8', icon: '💻' },
  'Streaming':          { bg: '#1a0a2e', accent: '#c084fc', icon: '📺' },
  'Personal Care':      { bg: '#1a1a1a', accent: '#ec4899', icon: '✨' },
  'Electronics':        { bg: '#1a1a1a', accent: '#fbbf24', icon: '⚡' },
};

const defaultColor = { bg: '#1a1a1a', accent: '#f97316', icon: '📦' };

function wordWrap(text, maxChars) {
  const words = text.split(' ');
  const lines = [];
  let current = '';
  for (const word of words) {
    if (current && (current + ' ' + word).length > maxChars) {
      lines.push(current);
      current = word;
    } else {
      current = current ? current + ' ' + word : word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

function generateSVG(name, category) {
  const colors = categoryColors[category] || defaultColor;
  const lines = wordWrap(name, 22);
  const lineHeight = 28;
  const textStartY = 260 - (lines.length * lineHeight) / 2;

  const textLines = lines.map((line, i) =>
    `<text x="250" y="${textStartY + i * lineHeight}" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" font-size="22" font-weight="700" fill="white">${escapeXml(line)}</text>`
  ).join('\n    ');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:${colors.bg}" />
      <stop offset="100%" style="stop-color:${lighten(colors.bg, 15)}" />
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:${colors.accent};stop-opacity:0.3" />
      <stop offset="100%" style="stop-color:${colors.accent};stop-opacity:0.05" />
    </linearGradient>
  </defs>
  <rect width="500" height="500" fill="url(#bg)" rx="0"/>
  <rect x="0" y="0" width="500" height="500" fill="url(#accent)" />
  <circle cx="250" cy="140" r="60" fill="${colors.accent}" opacity="0.15"/>
  <text x="250" y="158" text-anchor="middle" font-size="52">${colors.icon}</text>
  ${textLines}
  <rect x="180" y="${textStartY + lines.length * lineHeight + 10}" width="140" height="3" rx="2" fill="${colors.accent}" opacity="0.4"/>
  <text x="250" y="${textStartY + lines.length * lineHeight + 38}" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" font-size="13" font-weight="500" fill="${colors.accent}" letter-spacing="2" text-transform="uppercase">${escapeXml(category.toUpperCase())}</text>
  <rect x="0" y="494" width="500" height="6" fill="${colors.accent}" opacity="0.6"/>
</svg>`;
}

function escapeXml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');
}

function lighten(hex, amount) {
  const r = Math.min(255, parseInt(hex.slice(1, 3), 16) + amount);
  const g = Math.min(255, parseInt(hex.slice(3, 5), 16) + amount);
  const b = Math.min(255, parseInt(hex.slice(5, 7), 16) + amount);
  return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
}

// Process
const seen = new Set();
let generated = 0;
const outDir = './site/public/products';

for (const row of result.data) {
  const name = (row['Product Name'] || '').trim();
  if (!name) continue;
  const slug = slugify(name);
  if (seen.has(slug)) continue;
  seen.add(slug);

  const jpgPath = path.join(outDir, slug + '.jpg');
  if (fs.existsSync(jpgPath)) continue; // already has a real image

  const svgPath = path.join(outDir, slug + '.svg');
  const category = (row['Category'] || 'Electronics').trim();
  const svg = generateSVG(name, category);
  fs.writeFileSync(svgPath, svg);
  generated++;
}

console.log(`Generated ${generated} SVG placeholder images`);
