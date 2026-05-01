import type { Metadata } from "next";
import Link from "next/link";
import {
  getAllProducts,
  getAllCategories,
  getFeaturedProducts,
  getInstagramPostedProducts,
  getSaleProducts,
} from "./lib/products";
import ProductGrid from "./components/ProductGrid";
import DealCard from "./components/DealCard";
import { getCategoryIcon } from "./components/CategoryIcon";
import { SITE_NAME, SITE_URL } from "./lib/constants";

export const metadata: Metadata = {
  title: "HotProducts — Top-Rated Amazon Picks Across 40+ Categories",
  description:
    "HotProducts curates the best-selling, top-rated products on Amazon. Expert roundups and buying guides across electronics, smart home, fitness, kitchen, photography, and more — updated weekly.",
  alternates: { canonical: SITE_URL },
  openGraph: {
    title: "HotProducts — Top-Rated Amazon Picks Across 40+ Categories",
    description:
      "Expert roundups and buying guides for the best-selling products on Amazon. Verified reviews and real prices across 40+ categories.",
    url: SITE_URL,
    siteName: SITE_NAME,
    type: "website",
  },
};

export default function HomePage() {
  const featured = getFeaturedProducts(8);
  const deals = getSaleProducts(6);
  const recentlyPosted = getInstagramPostedProducts(8);
  const categories = getAllCategories();
  const allProducts = getAllProducts();

  // Organization + WebSite schema help Google understand brand queries and
  // enable sitelinks search box. Useful for brand queries like "hotproducts".
  const organizationLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    logo: `${SITE_URL}/app-icon.png`,
    sameAs: [
      "https://www.instagram.com/hotproductsdot.official",
      "https://www.tiktok.com/@hotproductsdot.of",
    ],
  };

  const websiteLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    url: SITE_URL,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${SITE_URL}/products?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteLd) }} />
      {/* Hero */}
      <section className="bg-gradient-to-b from-zinc-900 to-zinc-950 border-b border-zinc-800">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-20 text-center">
          <div className="inline-block bg-orange-500/10 text-orange-400 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-widest mb-6 border border-orange-500/20">
            Amazon&apos;s Best Picks
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white leading-tight mb-5">
            Find the Best Products{" "}
            <span className="text-orange-500">Before Everyone Else Does</span>
          </h1>
          <p className="text-zinc-400 text-lg mb-8 max-w-xl mx-auto">
            {allProducts.length} top-rated, best-selling products across {categories.length} categories — all with verified reviews and real prices.
          </p>
          <div className="flex flex-wrap gap-3 justify-center">
            <Link
              href="/products"
              className="bg-orange-500 hover:bg-orange-600 text-white font-semibold px-6 py-3 rounded-xl transition-colors"
            >
              Browse All Products →
            </Link>
            <a
              href="https://www.amazon.com/bestsellers?tag=hotproduct033-20"
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="border border-zinc-700 hover:border-zinc-500 text-zinc-300 font-semibold px-6 py-3 rounded-xl transition-colors"
            >
              Amazon Best Sellers
            </a>
          </div>
        </div>
      </section>

      {/* Recently on Instagram — surfaces what IG visitors just saw in their feed */}
      {recentlyPosted.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-14 pb-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-orange-400 text-xs font-bold uppercase tracking-widest">
                  Just Posted
                </span>
              </div>
              <h2 className="text-2xl font-bold text-white">Recently on Instagram</h2>
              <p className="text-zinc-500 text-sm mt-1">
                The products we featured on{" "}
                <a
                  href="https://www.instagram.com/hotproductsdot.official"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-orange-400 hover:text-orange-300"
                >
                  @hotproductsdot.official
                </a>{" "}
                — newest first.
              </p>
            </div>
            <Link
              href="/latest"
              className="text-sm text-orange-400 hover:text-orange-300 font-medium whitespace-nowrap"
            >
              See all latest →
            </Link>
          </div>
          <ProductGrid products={recentlyPosted} />
        </section>
      )}

      {/* Hot Deals */}
      {deals.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
          <div className="flex items-center justify-between mb-8">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-block w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
                <span className="text-orange-400 text-xs font-bold uppercase tracking-widest">Live Deals</span>
              </div>
              <h2 className="text-2xl font-bold text-white">Today&apos;s Hot Deals</h2>
              <p className="text-zinc-500 text-sm mt-1">Top-performing picks with the best prices right now</p>
            </div>
            <a
              href="https://www.amazon.com/deals?tag=hotproduct033-20"
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="text-sm text-orange-400 hover:text-orange-300 font-medium whitespace-nowrap"
            >
              All Amazon Deals →
            </a>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {deals.map((product) => (
              <DealCard key={product.slug} product={product} />
            ))}
          </div>
        </section>
      )}

      {/* Featured */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-2xl font-bold text-white">Top Picks</h2>
            <p className="text-zinc-500 text-sm mt-1">A fresh slice of our highest-potential picks — updated regularly</p>
          </div>
          <Link href="/products" className="text-sm text-orange-400 hover:text-orange-300 font-medium">
            View all →
          </Link>
        </div>
        <div id="featured-rotation"><ProductGrid products={featured} /></div>
      </section>

      {/* Best Categories (Money Pages) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14 border-t border-zinc-800">
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-orange-500">★</span>
            <span className="text-orange-400 text-xs font-bold uppercase tracking-widest">Expert Roundups</span>
          </div>
          <h2 className="text-2xl font-bold text-white">Best [Category] Guides</h2>
          <p className="text-zinc-500 text-sm mt-1">Deep dives into our top picks with verified reviews</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {categories.slice(0, 6).map((cat) => (
            <Link
              key={`best-${cat.slug}`}
              href={`/best/${cat.slug}`}
              className="group block bg-zinc-900 border border-zinc-800 rounded-xl p-6 hover:border-orange-500/40 hover:shadow-lg hover:shadow-orange-500/5 transition-all"
            >
              <div className="flex items-start gap-3 mb-3">
                <span className="text-2xl">{getCategoryIcon(cat.slug)}</span>
                <div className="flex-1">
                  <h3 className="font-semibold text-white group-hover:text-orange-400 transition-colors">
                    Best {cat.name}
                  </h3>
                  <p className="text-xs text-zinc-500 mt-1">{cat.count} products reviewed</p>
                </div>
              </div>
              <p className="text-sm text-zinc-400 mb-4">Expert roundup with detailed reviews and comparisons.</p>
              <span className="text-orange-400 text-sm font-medium">Read guide →</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Browse by Category */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white">Browse All Categories</h2>
          <p className="text-zinc-500 text-sm mt-1">Find exactly what you&apos;re looking for</p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {categories.map((cat) => (
            <Link
              key={cat.slug}
              href={`/category/${cat.slug}`}
              className="group flex flex-col items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-xl p-5 text-center hover:border-orange-500/40 hover:shadow-lg hover:shadow-orange-500/5 transition-all"
            >
              <span className="text-3xl">{getCategoryIcon(cat.slug)}</span>
              <span className="text-sm font-semibold text-zinc-200 group-hover:text-orange-400 transition-colors leading-tight">
                {cat.name}
              </span>
              <span className="text-[11px] text-zinc-600">{cat.count} products</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Trust strip */}
      <section className="border-t border-zinc-800 py-10">
        <div className="max-w-4xl mx-auto px-4 grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
          {[
            { icon: "✓", title: "Verified Reviews", sub: "Real Amazon ratings" },
            { icon: "↗", title: "Direct Links", sub: "Goes straight to Amazon" },
            { icon: "$", title: "Best Prices", sub: "Updated regularly" },
            { icon: "★", title: `${allProducts.length} Products`, sub: `${categories.length} categories` },
          ].map((item) => (
            <div key={item.title} className="space-y-1">
              <div className="text-orange-500 font-bold text-lg">{item.icon}</div>
              <div className="text-sm font-semibold text-zinc-200">{item.title}</div>
              <div className="text-xs text-zinc-600">{item.sub}</div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
