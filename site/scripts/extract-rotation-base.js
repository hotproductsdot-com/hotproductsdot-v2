#!/usr/bin/env node
// After a full Next.js build, extracts rotation-base.html from out/index.html.
// Replaces the featured product grid with <!--FEATURED_PLACEHOLDER--> so
// rotate-homepage.js can inject fresh products without a full rebuild.
//
// Usage: node scripts/extract-rotation-base.js

const fs = require("fs");
const path = require("path");

const htmlPath = path.join(__dirname, "..", "out", "index.html");
const basePath = path.join(__dirname, "..", "rotation-base.html");

const html = fs.readFileSync(htmlPath, "utf-8");

// Locate the wrapper div injected in page.tsx
const MARKER = 'id="featured-rotation">';
const markerIdx = html.indexOf(MARKER);
if (markerIdx === -1) {
  throw new Error(
    'Could not find id="featured-rotation" in out/index.html.\n' +
      "Make sure page.tsx has <div id=\"featured-rotation\">..."
  );
}

const contentStart = markerIdx + MARKER.length;

// Walk forward counting <div depth to find the matching </div>
let depth = 1;
let i = contentStart;
while (i < html.length && depth > 0) {
  if (html[i] === "<") {
    if (html.startsWith("</div>", i)) {
      depth--;
      if (depth === 0) break;
      i += 6;
      continue;
    }
    if (html.startsWith("<div", i) && (html[i + 4] === " " || html[i + 4] === ">")) {
      depth++;
    }
  }
  i++;
}

if (depth !== 0) {
  throw new Error("Could not find closing </div> for featured-rotation div.");
}

const result =
  html.slice(0, contentStart) +
  "<!--FEATURED_PLACEHOLDER-->" +
  html.slice(i);

fs.writeFileSync(basePath, result);
console.log(
  `extract-rotation-base: saved rotation-base.html (${result.length} bytes)`
);
