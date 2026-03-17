import Link from "next/link";

export default function Header() {
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <Link href="/" className="text-lg font-bold text-white tracking-tight">
          Hot<span className="text-orange-500">Products</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm text-zinc-400">
          <Link href="/products" className="hover:text-white transition-colors">All Products</Link>
          <Link href="/category/photography" className="hover:text-white transition-colors hidden sm:block">Photography</Link>
          <Link href="/category/smart-home" className="hover:text-white transition-colors hidden sm:block">Smart Home</Link>
          <Link href="/category/laptops" className="hover:text-white transition-colors hidden md:block">Laptops</Link>
          <a
            href="https://www.amazon.com?tag=hotproducts-20"
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
          >
            Shop Amazon
          </a>
        </nav>
      </div>
    </header>
  );
}
