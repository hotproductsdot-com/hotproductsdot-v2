import type { Metadata } from "next";
import Link from "next/link";
import { getInstagramPostedProducts } from "../lib/products";
import ProductGrid from "../components/ProductGrid";
import { SITE_NAME, SITE_URL } from "../lib/constants";

const canonical = `${SITE_URL}/latest`;
const PAGE_SIZE = 50;

export const metadata: Metadata = {
  title: "Latest Picks — Recently Featured on Instagram",
  description:
    "Every product we've recently featured on @hotproductsdot.official, newest first. See what's trending across electronics, smart home, fitness, kitchen and more.",
  alternates: { canonical },
  openGraph: {
    title: "Latest Picks — Recently Featured on Instagram",
    description:
      "Every product we've recently featured on Instagram. Trending Amazon picks, updated as we post.",
    url: canonical,
    siteName: SITE_NAME,
    type: "website",
  },
};

function formatPostedDate(ts: number): string {
  return new Date(ts).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default function LatestPage() {
  const posts = getInstagramPostedProducts(PAGE_SIZE);
  const newest = posts[0];
  const lastPosted = newest ? formatPostedDate(newest.postedTs) : null;

  const itemListLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "Latest Instagram Picks",
    itemListOrder: "https://schema.org/ItemListOrderDescending",
    numberOfItems: posts.length,
    itemListElement: posts.map((p, i) => ({
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
          Every product we&apos;ve recently featured on{" "}
          <a
            href="https://www.instagram.com/hotproductsdot.official"
            target="_blank"
            rel="noopener noreferrer"
            className="text-orange-500 hover:text-orange-400 transition-colors"
          >
            @hotproductsdot.official
          </a>
          , newest first.
          {lastPosted ? ` Last post: ${lastPosted}.` : null}
        </p>
      </div>

      {posts.length === 0 ? (
        <div className="text-center py-16 text-zinc-500">
          No Instagram posts logged yet. Check back soon — new picks drop daily.
        </div>
      ) : (
        <ProductGrid products={posts} />
      )}

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
