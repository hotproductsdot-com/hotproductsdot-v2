/**
 * validate-prices-parallel.js
 *
 * Runs N parallel workers, each checking a slice of the CSV.
 * Each worker writes a JSON patch file. A final merge applies all patches.
 *
 * Usage:  node validate-prices-parallel.js [--workers=4] [--dry-run]
 */

const { fork } = require('child_process');
const Papa = require('./site/node_modules/papaparse');
const fs = require('fs');
const path = require('path');

const CSV_PATH = './products/top-1000.csv';
const PATCHES_DIR = './products/.price-patches';

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');
const workersArg = args.find(a => a.startsWith('--workers='));
const NUM_WORKERS = workersArg ? parseInt(workersArg.split('=')[1]) : 4;

// ── Worker mode ──────────────────────────────────────────────────────────────
// When spawned as a child: node validate-prices-parallel.js --worker --start=0 --end=250 --id=0
if (args.includes('--worker')) {
  runWorker();
} else {
  runOrchestrator();
}

// ── Orchestrator ─────────────────────────────────────────────────────────────
async function runOrchestrator() {
  const csvContent = fs.readFileSync(CSV_PATH, 'utf-8');
  const parsed = Papa.parse(csvContent, { header: true, skipEmptyLines: true });
  const total = parsed.data.length;
  const chunkSize = Math.ceil(total / NUM_WORKERS);

  // Clean up old patches
  if (fs.existsSync(PATCHES_DIR)) fs.rmSync(PATCHES_DIR, { recursive: true });
  fs.mkdirSync(PATCHES_DIR, { recursive: true });

  console.log(`Products: ${total} | Workers: ${NUM_WORKERS} | Chunk: ~${chunkSize}`);
  console.log(`Mode: ${DRY_RUN ? 'DRY RUN' : 'WRITE'}`);
  console.log('─'.repeat(60));

  const workers = [];
  for (let i = 0; i < NUM_WORKERS; i++) {
    const start = i * chunkSize;
    const end = Math.min(start + chunkSize, total);
    workers.push(spawnWorker(i, start, end, DRY_RUN));
  }

  await Promise.all(workers);

  console.log('\n' + '─'.repeat(60));
  console.log('All workers done. Merging patches...');

  // Merge patches into CSV
  const patches = {};
  for (let i = 0; i < NUM_WORKERS; i++) {
    const patchFile = path.join(PATCHES_DIR, `worker-${i}.json`);
    if (fs.existsSync(patchFile)) {
      const p = JSON.parse(fs.readFileSync(patchFile, 'utf-8'));
      Object.assign(patches, p);
    }
  }

  const updateCount = Object.keys(patches).length;
  console.log(`Total price updates: ${updateCount}`);

  if (DRY_RUN || updateCount === 0) {
    if (DRY_RUN) console.log('(dry run — not saving)');
    else console.log('(no changes needed)');
    return;
  }

  // Apply patches (keyed by product name)
  const rows = parsed.data;
  for (const row of rows) {
    const name = (row['Product Name'] || '').trim();
    if (patches[name]) {
      row['Price Range'] = patches[name];
    }
  }

  const out = Papa.unparse(rows, { header: true });
  fs.writeFileSync(CSV_PATH + '.tmp', out, 'utf-8');
  fs.renameSync(CSV_PATH + '.tmp', CSV_PATH);
  console.log(`✓ Saved ${CSV_PATH}`);

  // Cleanup
  fs.rmSync(PATCHES_DIR, { recursive: true });
}

function spawnWorker(id, start, end, dryRun) {
  return new Promise((resolve, reject) => {
    const workerArgs = [
      '--worker',
      `--start=${start}`,
      `--end=${end}`,
      `--id=${id}`,
      ...(dryRun ? ['--dry-run'] : []),
    ];
    const child = fork(__filename, workerArgs, { silent: true });

    child.stdout.on('data', (data) => {
      process.stdout.write(data.toString());
    });
    child.stderr.on('data', (data) => {
      process.stderr.write(data.toString());
    });
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Worker ${id} exited with code ${code}`));
    });
  });
}

// ── Worker logic ──────────────────────────────────────────────────────────────
async function runWorker() {
  const startArg = args.find(a => a.startsWith('--start='));
  const endArg = args.find(a => a.startsWith('--end='));
  const idArg = args.find(a => a.startsWith('--id='));
  const start = parseInt(startArg.split('=')[1]);
  const end = parseInt(endArg.split('=')[1]);
  const id = parseInt(idArg.split('=')[1]);
  const dryRun = args.includes('--dry-run');

  const csvContent = fs.readFileSync(CSV_PATH, 'utf-8');
  const parsed = Papa.parse(csvContent, { header: true, skipEmptyLines: true });
  const rows = parsed.data.slice(start, end);

  const userAgents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  ];

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  function parseCurrentPrice(raw) {
    if (!raw) return null;
    const cleaned = (raw || '').replace(/[$,\s]/g, '');
    const range = cleaned.match(/^(\d+)-(\d+)$/);
    if (range) return (parseInt(range[1]) + parseInt(range[2])) / 2;
    const single = cleaned.match(/^(\d+)$/);
    if (single) return parseInt(single[1]);
    return null;
  }

  function formatPrice(min, max) {
    if (!min) return 'Check Price';
    if (!max || max === min) return `$${min.toLocaleString()}`;
    return `$${min.toLocaleString()}-${max.toLocaleString()}`;
  }

  async function fetchAmazonPrice(productName) {
    const ua = userAgents[Math.floor(Math.random() * userAgents.length)];
    const url = `https://www.amazon.com/s?k=${encodeURIComponent(productName)}`;

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

    const resultBlocks = html.split('data-component-type="s-search-result"');
    const prices = [];

    for (let i = 1; i <= Math.min(3, resultBlocks.length - 1); i++) {
      const block = resultBlocks[i];
      if (block.includes('"s-sponsored-label-info-icon"') || block.includes('AdHolder')) continue;

      const offscreenMatches = block.matchAll(/class="a-offscreen">(\$[\d,]+\.?\d*)</g);
      for (const m of offscreenMatches) {
        const val = parseFloat(m[1].replace(/[$,]/g, ''));
        if (val >= 1 && val < 100000) { prices.push(Math.round(val)); break; }
      }

      if (prices.length < i) {
        const wholeMatch = block.match(/class="a-price-whole">([\d,]+)/);
        if (wholeMatch) {
          const val = parseInt(wholeMatch[1].replace(/,/g, ''), 10);
          if (val >= 1 && val < 100000) prices.push(val);
        }
      }
    }

    if (prices.length === 0) return null;
    prices.sort((a, b) => a - b);
    return { min: prices[0], max: prices[prices.length - 1] > prices[0] * 1.5 ? prices[prices.length - 1] : prices[0] };
  }

  function isPriceMismatch(currentRaw, fetched) {
    const current = parseCurrentPrice(currentRaw);
    if (!current || current === 0) return true;
    if (!fetched) return false;
    const diff = Math.abs(current - fetched.min);
    const pct = diff / Math.max(current, fetched.min);
    return pct > 0.35 || diff > 300;
  }

  // Stagger workers so they don't all hit Amazon simultaneously
  await sleep(id * 2000);

  const patches = {};
  let captchaHits = 0;
  const prefix = `[W${id} ${start}-${end}]`;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const name = (row['Product Name'] || '').trim();
    const currentPrice = (row['Price Range'] || '').trim();
    const rowNum = start + i + 1;
    if (!name) continue;

    if (captchaHits >= 3) {
      console.log(`${prefix} ⛔ Too many CAPTCHAs — stopping at row ${rowNum}`);
      break;
    }

    try {
      const fetched = await fetchAmazonPrice(name);

      if (!fetched) {
        console.log(`${prefix} [${rowNum}] ${name} → no price`);
        await sleep(1500);
        continue;
      }

      const mismatch = isPriceMismatch(currentPrice, fetched);
      const newPrice = formatPrice(fetched.min, fetched.max);

      if (mismatch) {
        console.log(`${prefix} [${rowNum}] ⚠ ${name}  ${currentPrice || '(blank)'} → ${newPrice}`);
        patches[name] = newPrice;
      } else {
        console.log(`${prefix} [${rowNum}] ✓ ${name}  (${currentPrice})`);
      }

      captchaHits = 0;
      // Each worker uses a slightly different base delay to spread load
      await sleep(3500 + id * 500 + Math.random() * 2000);
    } catch (err) {
      if (err.message === 'CAPTCHA') {
        captchaHits++;
        console.log(`${prefix} [${rowNum}] ⛔ CAPTCHA — backing off`);
        await sleep(25000);
      } else {
        console.log(`${prefix} [${rowNum}] ✗ ${name} → ${err.message}`);
        await sleep(1000);
      }
    }
  }

  if (!dryRun) {
    const patchFile = path.join(PATCHES_DIR, `worker-${id}.json`);
    fs.writeFileSync(patchFile, JSON.stringify(patches, null, 2));
  }

  console.log(`${prefix} Done. Updates: ${Object.keys(patches).length}`);
}
