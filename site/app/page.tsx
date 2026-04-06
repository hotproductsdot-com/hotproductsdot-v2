import Link from "next/link";
import { getAllProducts, getAllCategories, getFeaturedProducts } from "./lib/products";
import ProductGrid from "./components/ProductGrid";
import { getCategoryIcon } from "./components/CategoryIcon";

export default function HomePage() {
  const featured = getFeaturedProducts(8);
  const categories = getAllCategories();
  const allProducts = getAllProducts();

  return (
    <>
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

      {/* Categories */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14 border-t border-zinc-800">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white">Browse by Category</h2>
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
