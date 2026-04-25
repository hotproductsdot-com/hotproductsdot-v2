import type { Metadata } from "next";
import Link from "next/link";
import { getLatestProducts } from "../lib/products";
import ProductGrid from "../components/ProductGrid";
import { SITE_NAME, SITE_URL } from "../lib/constants";

const canonical = `${SITE_URL}/latest`;
const PAGE_SIZE = 24;

export const metadata: Metadata = {
  title: "Latest Picks — Recently Refreshed Amazon Products",
  description:
    "The newest products added and refreshed on HotProducts. See what's trending this week across electronics, smart home, fitness, kitchen and more.",
  alternates: { canonical },
  openGraph: {
    title: "Latest Picks — Recently Refreshed Amazon Products",
    description:
      "The newest products added and refreshed on HotProducts. Trending Amazon picks, updated weekly.",
    url: canonical,
    siteName: SITE_NAME,
    type: "website",
  },
};

function formatRefreshed(ts: number | undefined): string | null {
  if (!ts) return null;
  return new Date(ts).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default function LatestPage() {
  const latest = getLatestProducts(PAGE_SIZE);
  const newest = latest[0];
  const lastUpdated = formatRefreshed(newest?.refreshedTs);

  const itemListLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "Latest Picks",
    itemListOrder: "https://schema.org/ItemListOrderDescending",
    numberOfItems: latest.length,
    itemListElement: latest.map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `${SITE_URL}/products/${p.slug}`,
      name: p.name,
    })),
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListLd) }}
      />
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Latest Picks</h1>
        <p className="text-zinc-500 mt-2">
          The newest products we&apos;ve added and refreshed across every category.
          {lastUpdated ? ` Last refresh: ${lastUpdated}.` : null}
        </p>
      </div>
      <ProductGrid products={latest} />
      <div className="mt-12 text-center">
        <Link
          href="/products"
          className="inline-block bg-orange-500 hover:bg-orange-600 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors"
        >
          Browse all products
        </Link>
      </div>
    </div>
  );
}
