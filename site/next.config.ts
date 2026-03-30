import type { NextConfig } from "next";
import os from "os";

const isDev = process.env.NODE_ENV === "development";
const cpuCount = typeof os.availableParallelism === "function" ? os.availableParallelism() : os.cpus().length;
const buildCpus = Math.max(1, Number(process.env.BUILD_CPUS || cpuCount - 1));

const nextConfig: NextConfig = {
  // Static export only for production builds — dev server needs normal mode to serve all routes
  ...(isDev ? {} : { output: "export", trailingSlash: true, images: { unoptimized: true } }),
  turbopack: {
    root: __dirname,
  },
  experimental: {
    cpus: buildCpus,
  },
};

export default nextConfig;
