#!/usr/bin/env node
/**
 * fix-affiliate-tags.js
 * Scans all CSV files for Amazon URLs missing the affiliate tag and fixes them.
 * Usage: node fix-affiliate-tags.js [--dry-run]
 */

const fs = require("fs");
const path = require("path");

const AFFILIATE_TAG = "hotproduct033-20";
const CSV_FILES = [
  "products/top-1000.csv",
  "top-1000.csv",
];
const DRY_RUN = process.argv.includes("--dry-run");

function fixUrl(url) {
  if (!url || !url.includes("amazon.com")) return { fixed: url, changed: false };
  try {
    const parsed = new URL(url);
    const existing = parsed.searchParams.get("tag");
    if (existing === AFFILIATE_TAG) return { fixed: url, changed: false };
    parsed.searchParams.set("tag", AFFILIATE_TAG);
    return { fixed: parsed.toString(), changed: true };
  } catch {
    return { fixed: url, changed: false };
  }
}

let totalFixed = 0;

for (const relPath of CSV_FILES) {
  const filePath = path.resolve(__dirname, relPath);
  if (!fs.existsSync(filePath)) {
    console.log(`SKIP  ${relPath} (not found)`);
    continue;
  }

  const content = fs.readFileSync(filePath, "utf8");
  const lines = content.split("\n");
  const header = lines[0];
  let fileFixed = 0;

  const updated = lines.map((line, i) => {
    if (i === 0) return line; // header
    if (!line.trim()) return line;

    // Replace all amazon URLs in the line
    const result = line.replace(
      /https?:\/\/[^\s,"]+amazon\.com[^\s,"]*/g,
      (match) => {
        const { fixed, changed } = fixUrl(match);
        if (changed) {
          fileFixed++;
          console.log(`  FIX  line ${i + 1}: ${match}`);
          console.log(`    => ${fixed}`);
        }
        return fixed;
      }
    );
    return result;
  });

  if (fileFixed > 0) {
    if (DRY_RUN) {
      console.log(`\n[DRY RUN] ${relPath}: would fix ${fileFixed} URL(s)`);
    } else {
      fs.writeFileSync(filePath, updated.join("\n"), "utf8");
      console.log(`\nWROTE  ${relPath}: fixed ${fileFixed} URL(s)`);
    }
    totalFixed += fileFixed;
  } else {
    console.log(`OK    ${relPath}: all URLs already have tag`);
  }
}

console.log(`\nDone. ${totalFixed} URL(s) ${DRY_RUN ? "need fixing" : "fixed"}.`);
if (DRY_RUN && totalFixed > 0) {
  console.log("Run without --dry-run to apply changes.");
}
