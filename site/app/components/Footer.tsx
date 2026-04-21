import Link from "next/link";

// Top category guides — the internal links that push PageRank into our /best/
// money pages. Kept small to avoid nav bloat; these are the highest-intent
// commercial categories. Order matters (first six get more weight).
const TOP_GUIDES: { slug: string; label: string }[] = [
  { slug: "laptops", label: "Best Laptops" },
  { slug: "headphones", label: "Best Headphones" },
  { slug: "smart-home", label: "Best Smart Home" },
  { slug: "kitchen", label: "Best Kitchen" },
  { slug: "fitness", label: "Best Fitness" },
  { slug: "photography", label: "Best Photography" },
  { slug: "monitors", label: "Best Monitors" },
  { slug: "robot-vacuums", label: "Best Robot Vacuums" },
];

export default function Footer() {
  return (
    <footer className="border-t border-zinc-800 mt-20 py-10 text-sm text-zinc-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 space-y-4">
        <div className="flex flex-wrap gap-8 justify-between items-start">
          <div>
            <div className="text-white font-semibold mb-1">
              Hot<span className="text-orange-500">Products</span>
            </div>
            <p className="max-w-sm text-xs leading-relaxed">
              Curated Amazon product recommendations. We research so you don&apos;t have to.
            </p>
          </div>
          <nav className="flex gap-12 text-xs flex-wrap">
            <div className="flex flex-col gap-2">
              <span className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">Browse</span>
              <Link href="/" className="hover:text-white transition-colors">Home</Link>
              <Link href="/products" className="hover:text-white transition-colors">All Products</Link>
              <Link href="/guides" className="hover:text-white transition-colors">Buying Guides</Link>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">Top Guides</span>
              {TOP_GUIDES.map((g) => (
                <Link
                  key={g.slug}
                  href={`/best/${g.slug}`}
                  className="hover:text-white transition-colors"
                >
                  {g.label}
                </Link>
              ))}
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">Legal</span>
              <Link href="/disclaimer" className="hover:text-white transition-colors">Affiliate Disclaimer</Link>
              <Link href="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">Follow Us</span>
              <a
                href="https://www.tiktok.com/@hotproductsdot.of"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-white transition-colors flex items-center gap-1.5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.32 6.32 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.33-6.34V8.69a8.18 8.18 0 0 0 4.78 1.52V6.75a4.85 4.85 0 0 1-1.01-.06z"/>
                </svg>
                TikTok
              </a>
              <a
                href="https://www.instagram.com/hotproductsdot.official"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-white transition-colors flex items-center gap-1.5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/>
                </svg>
                Instagram
              </a>
            </div>
          </nav>
        </div>
        <p className="text-xs border-t border-zinc-800 pt-4">
          <strong className="text-zinc-400">Affiliate Disclosure:</strong> As an Amazon Associate we earn from qualifying purchases at no extra cost to you. Prices and availability are subject to change.{" "}
          <Link href="/disclaimer" className="underline hover:text-zinc-300 transition-colors">Full disclaimer →</Link>
        </p>
      </div>
    </footer>
  );
}
