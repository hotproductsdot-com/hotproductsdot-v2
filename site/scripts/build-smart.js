const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { spawnSync } = require("node:child_process");

const mode = process.argv[2] === "turbopack" ? "turbopack" : "webpack";
const siteDir = path.resolve(__dirname, "..");
const rootDir = path.resolve(siteDir, "..");
const outDir = path.join(siteDir, "out");
const nextDir = path.join(siteDir, ".next");
const stateFile = path.join(nextDir, `build-inputs-${mode}.json`);

const watchedPaths = [
  path.join(siteDir, "app"),
  path.join(siteDir, "prebuild.js"),
  path.join(siteDir, "next.config.ts"),
  path.join(siteDir, "postcss.config.mjs"),
  path.join(siteDir, "package.json"),
  path.join(siteDir, "package-lock.json"),
  path.join(siteDir, "tsconfig.json"),
  path.join(rootDir, "products", "top-1000.csv"),
];

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: siteDir,
    stdio: "inherit",
    shell: process.platform === "win32",
    env: process.env,
  });
  return result.status ?? 1;
}

function exists(p) {
  try {
    fs.accessSync(p);
    return true;
  } catch {
    return false;
  }
}

function walkFiles(targetPath, files) {
  const stat = fs.statSync(targetPath);
  if (stat.isFile()) {
    files.push({ filePath: targetPath, size: stat.size, mtimeMs: stat.mtimeMs });
    return;
  }
  const entries = fs.readdirSync(targetPath, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === ".next" || entry.name === "out" || entry.name === "node_modules") continue;
    walkFiles(path.join(targetPath, entry.name), files);
  }
}

function computeInputHash() {
  const files = [];
  for (const p of watchedPaths) {
    if (exists(p)) walkFiles(p, files);
  }
  files.sort((a, b) => a.filePath.localeCompare(b.filePath));

  const hash = crypto.createHash("sha1");
  for (const file of files) {
    hash.update(path.relative(rootDir, file.filePath));
    hash.update("|");
    hash.update(String(file.size));
    hash.update("|");
    hash.update(String(Math.floor(file.mtimeMs)));
    hash.update("\n");
  }
  return hash.digest("hex");
}

function readState() {
  if (!exists(stateFile)) return null;
  try {
    return JSON.parse(fs.readFileSync(stateFile, "utf8"));
  } catch {
    return null;
  }
}

function writeState(inputHash) {
  if (!exists(nextDir)) fs.mkdirSync(nextDir, { recursive: true });
  fs.writeFileSync(stateFile, JSON.stringify({ inputHash, builtAt: new Date().toISOString() }, null, 2));
}

const inputHash = computeInputHash();
const previous = readState();
const shouldForce = process.env.FORCE_BUILD === "1";
const isNoOp = !shouldForce && previous?.inputHash === inputHash && exists(outDir);

if (isNoOp) {
  console.log(`No build inputs changed for ${mode}. Reusing existing out/.`);
  console.log("Set FORCE_BUILD=1 to force a full rebuild.");
  process.exit(0);
}

const prebuildStatus = run("node", ["prebuild.js"]);
if (prebuildStatus !== 0) process.exit(prebuildStatus);

const nextArgs = mode === "turbopack" ? ["build", "--turbopack"] : ["build", "--webpack"];
const buildStatus = run("next", nextArgs);
if (buildStatus !== 0) process.exit(buildStatus);

writeState(inputHash);
