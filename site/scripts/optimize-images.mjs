#!/usr/bin/env node
// Generate responsive WebP + JPG fallback variants for every product image.
// Output: site/public/products/_opt/<slug>-{240,480,800}.webp + <slug>-480.jpg
// Idempotent: skips files whose derivatives are newer than the source.
// To force a full rebuild after changing quality/widths: rm -rf site/public/products/_opt
import sharp from "sharp";
import { readdir, mkdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, basename } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(__dirname, "..", "public", "products");
const OUT_DIR = join(SRC_DIR, "_opt");

const WEBP_WIDTHS = [240, 480, 800];
const WEBP_QUALITY = 80;
const JPG_FALLBACK_WIDTH = 480;
const JPG_QUALITY = 82;
const CONCURRENCY = 8;

function targetsFor(slug) {
  const out = WEBP_WIDTHS.map((w) => ({
    path: join(OUT_DIR, `${slug}-${w}.webp`),
    width: w,
    format: "webp",
  }));
  out.push({
    path: join(OUT_DIR, `${slug}-${JPG_FALLBACK_WIDTH}.jpg`),
    width: JPG_FALLBACK_WIDTH,
    format: "jpg",
  });
  return out;
}

async function isFresh(targetPath, srcMtimeMs) {
  try {
    const s = await stat(targetPath);
    return s.mtimeMs >= srcMtimeMs;
  } catch {
    return false;
  }
}

async function buildOne(srcPath, target) {
  let pipeline = sharp(srcPath).resize({
    width: target.width,
    withoutEnlargement: true,
  });
  pipeline =
    target.format === "webp"
      ? pipeline.webp({ quality: WEBP_QUALITY, effort: 4 })
      : pipeline.jpeg({ quality: JPG_QUALITY, mozjpeg: true });
  await pipeline.toFile(target.path);
}

async function processFile(file, counters) {
  const slug = basename(file, ".jpg");
  const srcPath = join(SRC_DIR, file);
  const srcStat = await stat(srcPath);
  const targets = targetsFor(slug);

  const freshness = await Promise.all(
    targets.map((t) => isFresh(t.path, srcStat.mtimeMs)),
  );
  if (freshness.every(Boolean)) {
    counters.skipped += 1;
    return;
  }

  await Promise.all(targets.map((t) => buildOne(srcPath, t)));
  counters.generated += 1;
  counters.srcBytes += srcStat.size;
  for (const t of targets) {
    try {
      const s = await stat(t.path);
      counters.outBytes += s.size;
    } catch {
      // ignore — buildOne would have thrown if it truly failed
    }
  }
}

async function pool(items, limit, worker) {
  let cursor = 0;
  const runners = Array.from({ length: limit }, async () => {
    while (cursor < items.length) {
      const idx = cursor;
      cursor += 1;
      try {
        await worker(items[idx]);
      } catch (err) {
        console.error(`[optimize-images] failed on ${items[idx]}:`, err.message);
      }
    }
  });
  await Promise.all(runners);
}

async function main() {
  if (!existsSync(SRC_DIR)) {
    console.log(`[optimize-images] no source dir at ${SRC_DIR}, skipping`);
    return;
  }
  await mkdir(OUT_DIR, { recursive: true });

  const entries = await readdir(SRC_DIR);
  const files = entries.filter((f) => f.toLowerCase().endsWith(".jpg"));
  if (files.length === 0) {
    console.log("[optimize-images] no JPG sources found, skipping");
    return;
  }

  const counters = { generated: 0, skipped: 0, srcBytes: 0, outBytes: 0 };
  const start = Date.now();
  await pool(files, CONCURRENCY, (f) => processFile(f, counters));
  const elapsed = ((Date.now() - start) / 1000).toFixed(1);

  console.log(
    `[optimize-images] ${counters.generated} regenerated, ${counters.skipped} unchanged, ${files.length} total in ${elapsed}s`,
  );
  if (counters.generated > 0) {
    const srcMb = (counters.srcBytes / 1e6).toFixed(1);
    const outMb = (counters.outBytes / 1e6).toFixed(1);
    console.log(
      `[optimize-images] processed ${srcMb} MB sources → ${outMb} MB derivatives`,
    );
  }
}

main().catch((err) => {
  console.error("[optimize-images] fatal:", err);
  process.exit(1);
});
