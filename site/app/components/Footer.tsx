import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-zinc-800 mt-20 py-10 text-sm text-zinc-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 space-y-4">
        <div className="flex flex-wrap gap-6 justify-between items-start">
          <div>
            <div className="text-white font-semibold mb-1">
              Hot<span className="text-orange-500">Products</span>
            </div>
            <p className="max-w-sm text-xs leading-relaxed">
              Curated Amazon product recommendations. We research so you don&apos;t have to.
            </p>
          </div>
          <nav className="flex flex-col gap-2 text-xs">
            <Link href="/" className="hover:text-white transition-colors">Home</Link>
            <Link href="/products" className="hover:text-white transition-colors">All Products</Link>
          </nav>
        </div>
        <p className="text-xs border-t border-zinc-800 pt-4">
          <strong className="text-zinc-400">Affiliate Disclosure:</strong> As an Amazon Associate we earn from qualifying purchases at no extra cost to you. Prices and availability are subject to change.
        </p>
      </div>
    </footer>
  );
}
