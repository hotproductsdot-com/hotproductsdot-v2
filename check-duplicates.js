/**
 * check-duplicates.js
 *
 * Detects duplicate products in top-1000.csv before/after adding new entries.
 * Run with:  node check-duplicates.js
 * Auto-fix:  node check-duplicates.js --fix
 *
 * Catches two kinds of duplicates:
 *   1. EXACT  — same slug (e.g. same name, different capitalisation/punctuation)
 *   2. FUZZY  — similar name sharing brand + core model words (e.g. "La Mer The
 *               Moisturizing Cream" vs "La Mer Moisturizing Cream 2oz")
 */

const Papa = require('./site/node_modules/papaparse');
const fs   = require('fs');

const CSV_PATH  = './products/top-1000.csv';
const FIX_MODE  = process.argv.includes('--fix');
const FUZZY_THRESHOLD = 0.85; // Jaccard similarity — tune if too noisy

// ─── helpers ──────────────────────────────────────────────────────────────────

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/** Tokenise a product name into a bag of meaningful words (drops stop-words). */
// Words that add no discriminating value between products.
// NOTE: model-differentiating words (max, mini, pro, plus, ultra, gen, series)
//       are intentionally NOT in this list — they distinguish product variants.
const STOP = new Set([
  'the','a','an','and','or','of','for','with','in','on','at','by','to',
  'new','updated','version','edition','pack','bundle',
]);

function tokenise(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    // Keep numeric tokens (model numbers like "5", "9", "4k") and words > 1 char
    .filter(w => w.length > 0 && !STOP.has(w) && (w.length > 1 || /^\d$/.test(w)));
}

/** Jaccard similarity between two token sets. */
function jaccard(a, b) {
  const sa = new Set(a);
  const sb = new Set(b);
  let inter = 0;
  for (const t of sa) if (sb.has(t)) inter++;
  const union = sa.size + sb.size - inter;
  return union === 0 ? 0 : inter / union;
}

// ─── load CSV ─────────────────────────────────────────────────────────────────

const csvContent = fs.readFileSync(CSV_PATH, 'utf-8');
const parsed     = Papa.parse(csvContent, {
  header: true,
  skipEmptyLines: true,
  transformHeader: h => h.trim(),
});

const rows = parsed.data.map((row, i) => ({
  lineNum: i + 2,          // +2: 1-based + header row
  name:    (row['Product Name'] || '').trim(),
  raw:     row,
})).filter(r => r.name);

// ─── 1. exact duplicates (same slug) ─────────────────────────────────────────

const slugMap = new Map(); // slug → first occurrence index
const exactGroups = [];    // [{slug, indices:[…]}]

rows.forEach((r, idx) => {
  const slug = slugify(r.name);
  r.slug = slug;
  if (slugMap.has(slug)) {
    const first = slugMap.get(slug);
    // find or extend existing group
    let group = exactGroups.find(g => g.slug === slug);
    if (!group) {
      group = { slug, indices: [first] };
      exactGroups.push(group);
    }
    group.indices.push(idx);
  } else {
    slugMap.set(slug, idx);
  }
});

// ─── 2. fuzzy duplicates (similar but not identical slugs) ───────────────────

const tokens    = rows.map(r => tokenise(r.name));
const fuzzyPairs = [];

for (let i = 0; i < rows.length; i++) {
  for (let j = i + 1; j < rows.length; j++) {
    if (rows[i].slug === rows[j].slug) continue; // already caught above
    const sim = jaccard(tokens[i], tokens[j]);
    if (sim >= FUZZY_THRESHOLD) {
      fuzzyPairs.push({ i, j, sim: Math.round(sim * 100) });
    }
  }
}

// ─── report ───────────────────────────────────────────────────────────────────

const totalExact = exactGroups.reduce((s, g) => s + g.indices.length - 1, 0);
const totalFuzzy = fuzzyPairs.length;

if (totalExact === 0 && totalFuzzy === 0) {
  console.log('✅  No duplicates found. CSV is clean.');
  process.exit(0);
}

console.log('─'.repeat(60));
console.log(`🔍  Duplicate report for ${CSV_PATH}`);
console.log('─'.repeat(60));

if (exactGroups.length > 0) {
  console.log(`\n⛔  EXACT duplicates (${totalExact} extra rows):\n`);
  for (const g of exactGroups) {
    console.log(`  Slug: ${g.slug}`);
    for (const idx of g.indices) {
      const r = rows[idx];
      console.log(`    line ${String(r.lineNum).padStart(4)}  "${r.name}"`);
    }
    console.log(`    → keeping line ${rows[g.indices[0]].lineNum}, removing ${g.indices.slice(1).length} duplicate(s)\n`);
  }
}

if (fuzzyPairs.length > 0) {
  console.log(`\n⚠️   FUZZY duplicates (${totalFuzzy} suspicious pairs):\n`);
  for (const p of fuzzyPairs) {
    const a = rows[p.i];
    const b = rows[p.j];
    console.log(`  ${p.sim}% similar`);
    console.log(`    line ${String(a.lineNum).padStart(4)}  "${a.name}"`);
    console.log(`    line ${String(b.lineNum).padStart(4)}  "${b.name}"`);
    console.log();
  }
  console.log('  ℹ️   Fuzzy duplicates require manual review — run without --fix to inspect.\n');
}

// ─── auto-fix exact duplicates ────────────────────────────────────────────────

if (FIX_MODE) {
  if (exactGroups.length === 0) {
    console.log('✅  No exact duplicates to remove.');
  } else {
    // Collect row indices to remove (keep first occurrence, drop the rest)
    const toRemove = new Set(
      exactGroups.flatMap(g => g.indices.slice(1))
    );

    const keptRows = rows.filter((_, idx) => !toRemove.has(idx));

    // Re-serialise preserving original field order
    const fields  = parsed.meta.fields;
    const header  = fields.join(',');
    const body    = keptRows.map(r =>
      fields.map(f => {
        const v = String(r.raw[f] ?? '');
        return v.includes(',') ? `"${v.replace(/"/g, '""')}"` : v;
      }).join(',')
    ).join('\n');

    fs.writeFileSync(CSV_PATH, header + '\n' + body + '\n', 'utf-8');
    console.log(`✅  Removed ${toRemove.size} exact duplicate row(s). CSV updated.`);
    console.log('   Run node autofix-images.js if needed after adding new products.\n');
  }
} else if (totalExact > 0) {
  console.log('  💡  Run with --fix to automatically remove exact duplicates:\n');
  console.log('      node check-duplicates.js --fix\n');
}

console.log('─'.repeat(60));
process.exit(totalExact > 0 || totalFuzzy > 0 ? 1 : 0);
