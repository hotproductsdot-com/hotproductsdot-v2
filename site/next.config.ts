import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  // Static export only for production builds — dev server needs normal mode to serve all routes
  ...(isDev ? {} : { output: "export", trailingSlash: true, images: { unoptimized: true } }),
  turbopack: {
    root: __dirname,
  },
  experimental: {
    cpus: 15,
  },
};

export default nextConfig;
