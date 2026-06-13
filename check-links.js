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
const VALIDATE_TITLE = false; // use check-product-title-alignment.py instead
const TIMEOUT_MS = 15000;
const TITLE_STOPWORDS = new Set([
  'amazon', 'the', 'and', 'for', 'with', 'from', 'a', 'an', 'of', 'to',
  'smart', 'video', 'calling', 'touch', 'screen', 'display', 'device', 'new',
  'black', 'white',
]);

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

// --- Strip ALL query parameters before checking ---
// Critical: leaving `?tag=hotproduct033-20` in the URL causes Amazon's
// affiliate-tracking system to count every check as a "click" against our
// account. A weekly run of this script across 1,090 products easily generates
// 16,000+ phantom clicks per month, which:
//   1. Tanks the dashboard conversion rate (looks like 0.006% when it's actually fine)
//   2. May trigger Amazon's fraud-detection heuristics on the Associates account
//   3. Blocks PA-API qualification because the metrics look fraudulent
// Validation only needs to know whether /dp/<ASIN> resolves — the tag is
// irrelevant for that check, so we strip it.
function tagFreeUrl(rawUrl) {
  try {
    const u = new URL(rawUrl);
    // Keep host + path only; drop search + hash. Both `?tag=...` and any
    // other tracking params (`th=1`, `linkCode=...`, `ref=...`) are removed.
    return `${u.protocol}//${u.hostname}${u.pathname}`;
  } catch {
    return rawUrl;  // unparseable — let the caller's URL constructor fail
  }
}

function normalizeTokens(raw) {
  return new Set(
    String(raw || '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .split(/\s+/)
      .map((t) => t.trim())
      .filter((t) => t && !TITLE_STOPWORDS.has(t))
  );
}

function tokenCoverage(expected, observed) {
  if (expected.size === 0) return 1;
  let hit = 0;
  for (const token of expected) {
    if (observed.has(token)) hit++;
  }
  return hit / expected.size;
}

function extractAmazonTitle(html) {
  const fromProductTitle = html.match(/id="productTitle"[^>]*>([\s\S]*?)<\/span>/i);
  if (fromProductTitle) {
    return fromProductTitle[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  }
  const fromTitleTag = html.match(/<title>([\s\S]*?)<\/title>/i);
  if (fromTitleTag) {
    return fromTitleTag[1]
      .replace(/\s+-\s+Amazon\.com.*$/i, '')
      .replace(/^Amazon\.com\s*:\s*/i, '')
      .trim();
  }
  return '';
}

function requestUrl(url, method) {
  return new Promise((resolve) => {
    const cleanedUrl = tagFreeUrl(url);

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
        method,
        headers: HEADERS,
        timeout: TIMEOUT_MS,
      };

      const req = https.request(options, (res) => {
        const { statusCode } = res;
        let body = '';

        if (method === 'GET') {
          res.setEncoding('utf8');
          res.on('data', (chunk) => {
            body += chunk;
            if (body.length > 250000) {
              req.destroy();
            }
          });
        } else {
          res.resume();
        }

        if (statusCode >= 301 && statusCode <= 308 && res.headers.location) {
          const next = res.headers.location.startsWith('http')
            ? res.headers.location
            : `https://${parsed.hostname}${res.headers.location}`;
          return attempt(next, redirectCount + 1);
        }

        resolve({
          url,
          finalUrl: targetUrl !== url ? targetUrl : undefined,
          status: statusCode,
          body,
          path: parsed.pathname + parsed.search,
          broken: statusCode === 404 || statusCode >= 500,
          detail: statusCode === 404
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

    attempt(cleanedUrl, 0);
  });
}

// --- HTTP check with redirect following ---
async function checkUrl(row) {
  const { url, name } = row;
  const head = await requestUrl(url, 'HEAD');

  const finalPath = head.path || '';
  const redirectedToHome = head.finalUrl && (
    finalPath === '/' || finalPath.startsWith('/s?') || finalPath.startsWith('/s/?')
  );

  const result = {
    url,
    name,
    finalUrl: head.finalUrl,
    status: head.status,
    broken: head.broken || redirectedToHome,
    detail: redirectedToHome
      ? 'Redirected to homepage/search (product likely removed)'
      : head.detail,
  };

  if (VALIDATE_TITLE && !result.broken && /\/dp\/[A-Z0-9]{10}/.test(url)) {
    const page = await requestUrl(url, 'GET');
    const amazonTitle = extractAmazonTitle(page.body || '');
    const coverage = tokenCoverage(normalizeTokens(name), normalizeTokens(amazonTitle));
    result.amazonTitle = amazonTitle;
    result.titleCoverage = coverage;
    result.titleMismatch = coverage < 1;
    if (result.titleMismatch) {
      result.broken = true;
      result.detail = `Title mismatch (${Math.round(coverage * 100)}% coverage): "${amazonTitle}"`;
    }
  }

  return result;
}

// --- Concurrency pool ---
async function checkAll(items) {
  const results = [];
  const queue = [...items];
  let done = 0;
  const total = items.length;

  async function worker() {
    while (queue.length > 0) {
      const item = queue.shift();
      process.stdout.write(`\r[${++done}/${total}] Checking...`);
      const result = await checkUrl(item);
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

  const enriched = await checkAll(items);

  const broken = enriched.filter(r => r.broken);
  const mismatches = enriched.filter(r => r.titleMismatch);
  const timeouts = enriched.filter(r => r.status === 'timeout');
  const ok = enriched.filter(r => !r.broken && r.status !== 'timeout' && !r.titleMismatch);

  // --- Print summary ---
  console.log('\n=== LINK CHECK REPORT ===');
  console.log(`Total: ${enriched.length} | OK: ${ok.length} | Broken: ${broken.length} | Title mismatches: ${mismatches.length} | Timeouts: ${timeouts.length}`);
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

  if (mismatches.length > 0) {
    console.log('\n--- TITLE MISMATCHES ---');
    mismatches.forEach(r => {
      console.log(`[title] ${r.name}`);
      console.log(`  URL: ${r.url}`);
      console.log(`  Reason: ${r.detail}`);
      if (r.amazonTitle) console.log(`  Amazon title: ${r.amazonTitle}`);
    });
  }

  if (broken.length === 0 && mismatches.length === 0) {
    console.log('\nAll links look good!');
  } else if (broken.length === 0 && mismatches.length > 0) {
    console.log('\nLinks resolve, but one or more titles do not match the catalog row.');
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
    summary: { total: enriched.length, ok: ok.length, broken: broken.length, mismatches: mismatches.length, timeouts: timeouts.length },
    broken,
    mismatches,
    timeouts,
  };

  const outPath = OUTPUT_PATH || path.join(__dirname, 'link-report.json');
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
  console.log(`Full report saved to: ${outPath}`);

  // Exit with error code if broken links or title mismatches are found.
  process.exit((broken.length > 0 || mismatches.length > 0) ? 1 : 0);
}

main().catch(err => { console.error(err); process.exit(1); });
