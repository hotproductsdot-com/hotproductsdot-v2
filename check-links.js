#!/usr/bin/env node
/**
 * check-links.js
 * Checks all Amazon URLs in top-1000.csv for broken/404 links.
 * Usage: node check-links.js [--csv products/top-1000.csv] [--concurrency 5] [--output report.json]
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// --- CLI args ---
const args = process.argv.slice(2);
const getArg = (flag, def) => {
  const i = args.indexOf(flag);
  return i !== -1 && args[i + 1] ? args[i + 1] : def;
};
const CSV_PATH = getArg('--csv', path.join(__dirname, 'products/top-1000.csv'));
const CONCURRENCY = parseInt(getArg('--concurrency', '5'), 10);
const OUTPUT_PATH = getArg('--output', '');
const TIMEOUT_MS = 15000;

// Realistic browser headers to avoid Amazon blocking
const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
  'Connection': 'keep-alive',
};

// --- Simple CSV parser (handles quoted fields) ---
function parseCsv(content) {
  const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const headers = splitCsvLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const values = splitCsvLine(line);
    const row = {};
    headers.forEach((h, idx) => { row[h.trim()] = (values[idx] || '').trim(); });
    rows.push(row);
  }
  return rows;
}

function splitCsvLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

// --- HTTP check with redirect following ---
function checkUrl(url) {
  return new Promise((resolve) => {
    const attempt = (targetUrl, redirectCount) => {
      if (redirectCount > 5) {
        return resolve({ url, status: 'error', detail: 'Too many redirects', broken: true });
      }

      let parsed;
      try {
        parsed = new URL(targetUrl);
      } catch {
        return resolve({ url, status: 'error', detail: 'Invalid URL', broken: true });
      }

      const options = {
        hostname: parsed.hostname,
        path: parsed.pathname + parsed.search,
        method: 'GET',
        headers: HEADERS,
        timeout: TIMEOUT_MS,
      };

      const req = https.request(options, (res) => {
        const { statusCode } = res;
        // Drain the response body so the socket closes cleanly
        res.resume();

        if (statusCode >= 301 && statusCode <= 308 && res.headers.location) {
          // Follow redirect
          const next = res.headers.location.startsWith('http')
            ? res.headers.location
            : `https://${parsed.hostname}${res.headers.location}`;
          return attempt(next, redirectCount + 1);
        }

        const broken = statusCode === 404 || statusCode >= 500;
        // Amazon redirects dead product pages to their homepage or search
        const finalPath = parsed.pathname + parsed.search;
        const redirectedToHome = redirectCount > 0 &&
          (finalPath === '/' || finalPath.startsWith('/s?') || finalPath.startsWith('/s/?'));

        resolve({
          url,
          finalUrl: targetUrl !== url ? targetUrl : undefined,
          status: statusCode,
          broken: broken || redirectedToHome,
          detail: redirectedToHome
            ? 'Redirected to homepage/search (product likely removed)'
            : statusCode === 404
              ? '404 Not Found'
              : statusCode >= 500
                ? `Server error ${statusCode}`
                : 'OK',
        });
      });

      req.on('timeout', () => {
        req.destroy();
        resolve({ url, status: 'timeout', detail: 'Request timed out', broken: false });
      });

      req.on('error', (err) => {
        resolve({ url, status: 'error', detail: err.message, broken: true });
      });

      req.end();
    };

    attempt(url, 0);
  });
}

// --- Concurrency pool ---
async function checkAll(urls) {
  const results = [];
  const queue = [...urls];
  let done = 0;
  const total = urls.length;

  async function worker() {
    while (queue.length > 0) {
      const url = queue.shift();
      process.stdout.write(`\r[${++done}/${total}] Checking...`);
      const result = await checkUrl(url);
      results.push(result);
      // Small delay between requests to avoid rate-limiting
      await new Promise(r => setTimeout(r, 300));
    }
  }

  const workers = Array.from({ length: CONCURRENCY }, () => worker());
  await Promise.all(workers);
  process.stdout.write('\n');
  return results;
}

// --- CSV serializer (preserves original column order) ---
function serializeCsv(headers, rows) {
  const escape = (val) => {
    if (val == null) return '';
    const str = String(val);
    return str.includes(',') || str.includes('"') || str.includes('\n')
      ? `"${str.replace(/"/g, '""')}"`
      : str;
  };
  const headerLine = headers.map(escape).join(',');
  const dataLines = rows.map(row => headers.map(h => escape(row[h] || '')).join(','));
  return [headerLine, ...dataLines].join('\n') + '\n';
}

// --- Main ---
async function main() {
  if (!fs.existsSync(CSV_PATH)) {
    console.error(`CSV not found: ${CSV_PATH}`);
    process.exit(1);
  }

  const rawContent = fs.readFileSync(CSV_PATH, 'utf8').replace(/^\uFEFF/, '');
  const rows = parseCsv(rawContent);

  const urlCol = 'Amazon URL';
  const nameCol = 'Product Name';

  // Preserve original header order from the first line
  const headers = splitCsvLine(rawContent.replace(/\r\n/g, '\n').split('\n')[0]);

  const items = rows
    .filter(r => r[urlCol] && r[urlCol].startsWith('http'))
    .map(r => ({ name: r[nameCol] || '(unknown)', url: r[urlCol] }));

  console.log(`Checking ${items.length} URLs from ${CSV_PATH} (concurrency: ${CONCURRENCY})...`);

  const results = await checkAll(items.map(i => i.url));

  // Merge product name back in
  const urlToName = Object.fromEntries(items.map(i => [i.url, i.name]));
  const enriched = results.map(r => ({ ...r, name: urlToName[r.url] || '' }));

  const broken = enriched.filter(r => r.broken);
  const timeouts = enriched.filter(r => r.status === 'timeout');
  const ok = enriched.filter(r => !r.broken && r.status !== 'timeout');

  // --- Print summary ---
  console.log('\n=== LINK CHECK REPORT ===');
  console.log(`Total: ${enriched.length} | OK: ${ok.length} | Broken: ${broken.length} | Timeouts: ${timeouts.length}`);
  console.log(`Date: ${new Date().toISOString()}`);

  if (broken.length > 0) {
    console.log('\n--- BROKEN LINKS ---');
    broken.forEach(r => {
      console.log(`[${r.status}] ${r.name}`);
      console.log(`  URL: ${r.url}`);
      console.log(`  Reason: ${r.detail}`);
      if (r.finalUrl) console.log(`  Redirected to: ${r.finalUrl}`);
    });
  }

  if (timeouts.length > 0) {
    console.log('\n--- TIMEOUTS (may be flaky, re-check manually) ---');
    timeouts.forEach(r => console.log(`  ${r.name} — ${r.url}`));
  }

  if (broken.length === 0) {
    console.log('\nAll links look good!');
  }

  // --- Remove broken items from CSV ---
  if (broken.length > 0) {
    const brokenUrls = new Set(broken.map(r => r.url));
    const cleanedRows = rows.filter(r => !brokenUrls.has(r[urlCol]));
    const removedCount = rows.length - cleanedRows.length;
    fs.writeFileSync(CSV_PATH, serializeCsv(headers, cleanedRows), 'utf8');
    console.log(`\nRemoved ${removedCount} dead-link product(s) from ${CSV_PATH}`);
  }

  // --- Write JSON report ---
  const report = {
    date: new Date().toISOString(),
    csvFile: CSV_PATH,
    summary: { total: enriched.length, ok: ok.length, broken: broken.length, timeouts: timeouts.length },
    broken,
    timeouts,
  };

  const outPath = OUTPUT_PATH || path.join(__dirname, 'link-report.json');
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
  console.log(`Full report saved to: ${outPath}`);

  // Exit with error code if broken links found (useful for CI)
  process.exit(broken.length > 0 ? 1 : 0);
}

main().catch(err => { console.error(err); process.exit(1); });
