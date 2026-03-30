const { execSync } = require("node:child_process");

function hasLightningCssBinary() {
  try {
    require("lightningcss");
    return true;
  } catch {
    return false;
  }
}

function getPlatformBinaryPackage() {
  if (process.platform === "win32" && process.arch === "x64") return "lightningcss-win32-x64-msvc";
  if (process.platform === "linux" && process.arch === "x64") return "lightningcss-linux-x64-gnu";
  if (process.platform === "darwin" && process.arch === "x64") return "lightningcss-darwin-x64";
  if (process.platform === "darwin" && process.arch === "arm64") return "lightningcss-darwin-arm64";
  return null;
}

function runFix(command) {
  execSync(command, {
    stdio: "inherit",
    env: process.env,
  });
}

if (hasLightningCssBinary()) {
  process.exit(0);
}

console.warn("Missing platform-specific lightningcss binary. Repairing dependencies for this OS...");

try {
  runFix("npm rebuild lightningcss @tailwindcss/node");
} catch {
  // Reinstall only if rebuild cannot recover the optional native binary.
  runFix("npm install");
}

if (!hasLightningCssBinary()) {
  const binaryPackage = getPlatformBinaryPackage();
  if (binaryPackage) {
    runFix(`npm install --no-save ${binaryPackage}`);
  }
}

if (!hasLightningCssBinary()) {
  console.error("Unable to load lightningcss native binary after repair.");
  process.exit(1);
}

console.log("lightningcss native binary is available.");
