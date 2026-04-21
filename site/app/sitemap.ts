export const dynamic = "force-static";

import { MetadataRoute } from "next";
import { getAllProducts, getAllCategories } from "./lib/products";
import { getAllGuides } from "./lib/guides";
import { SITE_URL } from "./lib/constants";

export default function sitemap(): MetadataRoute.Sitemap {
  const products = getAllProducts();
  const categories = getAllCategories();
  const guides = getAllGuides();
  const now = new Date();

  const productUrls: MetadataRoute.Sitemap = products.map((p) => ({
    url: `${SITE_URL}/products/${p.slug}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  const categoryUrls: MetadataRoute.Sitemap = categories.map((c) => ({
    url: `${SITE_URL}/category/${c.slug}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  // /best/[category] — primary commercial money pages. Higher priority than
  // category hubs because these are the pages we want ranking for
  // "Best [category] 2026"-type queries.
  const bestUrls: MetadataRoute.Sitemap = categories.map((c) => ({
    url: `${SITE_URL}/best/${c.slug}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.9,
  }));

  // Individual guide detail pages (/guides/[slug]).
  const guideUrls: MetadataRoute.Sitemap = guides.map((g) => ({
    url: `${SITE_URL}/guides/${g.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  // Use a stable build date so crawlers don't see lastModified change on every deploy.
  // Set BUILD_DATE=YYYY-MM-DD in CI to pin it; falls back to today on local builds.
  const buildDate = process.env.BUILD_DATE ? new Date(process.env.BUILD_DATE) : now;

  return [
    { url: SITE_URL, lastModified: buildDate, changeFrequency: "daily", priority: 1.0 },
    { url: `${SITE_URL}/products`, lastModified: buildDate, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/guides`, lastModified: buildDate, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE_URL}/disclaimer`, lastModified: buildDate, changeFrequency: "monthly", priority: 0.3 },
    { url: `${SITE_URL}/privacy`, lastModified: buildDate, changeFrequency: "monthly", priority: 0.3 },
    ...bestUrls,
    ...categoryUrls,
    ...guideUrls,
    ...productUrls,
  ];
}
