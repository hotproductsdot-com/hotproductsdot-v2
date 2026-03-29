/**
 * validate-prices.js
 *
 * Fetches live Amazon prices for every product in top-1000.csv and updates
 * the "Price Range" column where the current value looks wrong.
 *
 * Run:  node validate-prices.js
 *   --dry-run    Print changes but don't save
 *   --limit=N    Stop after N products
 *   --skip=N     Skip first N products (for resuming)
 */

const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');

const CSV_PATH = './products/top-1000.csv';
const TMP_PATH = './products/top-1000.csv.tmp';

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');
const limitArg = args.find(a => a.startsWith('--limit='));
const skipArg = args.find(a => a.startsWith('--skip='));
const LIMIT = limitArg ? parseInt(limitArg.split('=')[1], 10) : Infinity;
const SKIP = skipArg ? parseInt(skipArg.split('=')[1], 10) : 0;

const userAgents = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
];

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function parseCurrentPrice(raw) {
  if (!raw) return null;
  const cleaned = (raw || '').replace(/[$,\s]/g, '');
  const range = cleaned.match(/^(\d+)-(\d+)$/);
  if (range) return (parseInt(range[1]) + parseInt(range[2])) / 2;
  const single = cleaned.match(/^(\d+)$/);
  if (single) return parseInt(single[1]);
  return null; // "Check Price" or non-numeric
}

function formatPrice(min, max) {
  if (!min) return 'Check Price';
  if (!max || max === min) return `$${min.toLocaleString()}`;
  return `$${min.toLocaleString()}-${max.toLocaleString()}`;
}

/**
 * Fetch the price of the FIRST main search result on Amazon.
 * Targets `.a-offscreen` within the first product result div.
 */
async function fetchAmazonPrice(productName) {
  const ua = userAgents[Math.floor(Math.random() * userAgents.length)];
  const url = `https://www.amazon.com/s?k=${encodeURIComponent(productName)}&ref=nb_sb_noss`;

  const res = await fetch(url, {
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

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const html = await res.text();

  if (html.includes('captcha') || html.includes('Enter the characters') || html.includes('robot check')) {
    throw new Error('CAPTCHA');
  }

  // Find prices from the first few real search results.
  // Amazon search results: each product is in a div with data-component-type="s-search-result"
  // The price is inside class="a-offscreen" which contains "$1,299.00"
  const resultBlocks = html.split('data-component-type="s-search-result"');

  // Skip block[0] (before first result), check first 3 results
  const prices = [];
  for (let i = 1; i <= Math.min(3, resultBlocks.length - 1); i++) {
    const block = resultBlocks[i];

    // Skip sponsored results
    if (block.includes('"s-sponsored-label-info-icon"') || block.includes('AdHolder')) continue;

    // Extract .a-offscreen prices (e.g. "$1,299.00" or "$29.99")
    const offscreenMatches = block.matchAll(/class="a-offscreen">(\$[\d,]+\.?\d*)</g);
    for (const m of offscreenMatches) {
      const val = parseFloat(m[1].replace(/[$,]/g, ''));
      if (val >= 1 && val < 100000) {
        prices.push(Math.round(val));
        break; // Only take first price per block
      }
    }

    // Fallback: a-price-whole
    if (prices.length === 0 || prices.length < i) {
      const wholeMatch = block.match(/class="a-price-whole">([\d,]+)/);
      if (wholeMatch) {
        const val = parseInt(wholeMatch[1].replace(/,/g, ''), 10);
        if (val >= 1 && val < 100000) prices.push(val);
      }
    }
  }

  if (prices.length === 0) return null;

  // Use lowest price as min, highest of first 3 as rough max
  prices.sort((a, b) => a - b);
  const min = prices[0];
  const max = prices[prices.length - 1];

  return { min, max: max > min * 1.5 ? max : min };
}

/**
 * Is the current price in the CSV significantly wrong vs. what Amazon shows?
 * Returns true if update is warranted.
 */
function isPriceMismatch(currentRaw, fetched) {
  const current = parseCurrentPrice(currentRaw);
  if (!current || current === 0) return true; // blank or "Check Price" → update
  if (!fetched) return false;

  const diff = Math.abs(current - fetched.min);
  const pct = diff / Math.max(current, fetched.min);
  return pct > 0.35 || diff > 300;
}

async function main() {
  const csvContent = fs.readFileSync(CSV_PATH, 'utf-8');
  const parsed = Papa.parse(csvContent, { header: true, skipEmptyLines: true });
  const rows = parsed.data;

  console.log(`Products: ${rows.length}`);
  console.log(`Mode: ${DRY_RUN ? 'DRY RUN' : 'WRITE'} | Skip: ${SKIP} | Limit: ${LIMIT === Infinity ? 'all' : LIMIT}`);
  console.log('---');

  let checked = 0;
  let updated = 0;
  let captchaHits = 0;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const name = (row['Product Name'] || '').trim();
    if (!name) continue;

    if (i < SKIP) continue;
    if (checked >= LIMIT) break;
    if (captchaHits >= 3) {
      console.log(`[ABORT] Too many CAPTCHAs — re-run with --skip=${i}`);
      break;
    }

    checked++;
    const currentPrice = (row['Price Range'] || '').trim();

    try {
      const fetched = await fetchAmazonPrice(name);

      if (!fetched) {
        console.log(`[${i + 1}] ${name} → no price found (kept: ${currentPrice || 'blank'})`);
        await sleep(1500);
        continue;
      }

      const mismatch = isPriceMismatch(currentPrice, fetched);
      const newPrice = formatPrice(fetched.min, fetched.max);

      if (mismatch) {
        console.log(`[${i + 1}] ⚠ ${name}`);
        console.log(`       was: ${currentPrice || '(blank)'}  →  now: ${newPrice}`);
        rows[i]['Price Range'] = newPrice;
        updated++;
      } else {
        console.log(`[${i + 1}] ✓ ${name}  (${currentPrice})`);
      }

      captchaHits = 0;
      await sleep(3000 + Math.random() * 2000);
    } catch (err) {
      if (err.message === 'CAPTCHA') {
        captchaHits++;
        console.log(`[${i + 1}] ⛔ CAPTCHA (${captchaHits}/3) — backing off 20s`);
        await sleep(20000);
      } else {
        console.log(`[${i + 1}] ✗ ${name} → ${err.message}`);
        await sleep(1000);
      }
    }
  }

  console.log('---');
  console.log(`Checked: ${checked} | Updated: ${updated}`);

  if (!DRY_RUN && updated > 0) {
    const out = Papa.unparse(rows, { header: true });
    fs.writeFileSync(TMP_PATH, out, 'utf-8');
    fs.renameSync(TMP_PATH, CSV_PATH);
    console.log(`✓ Saved ${CSV_PATH}`);
  } else if (DRY_RUN) {
    console.log('(dry run — no changes saved)');
  } else {
    console.log('(no changes needed)');
  }
}

main().catch(console.error);
