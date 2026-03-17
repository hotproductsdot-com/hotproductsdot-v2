import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllCategories, getProductsByCategory } from "../../lib/products";
import ProductGrid from "../../components/ProductGrid";
import { getCategoryIcon } from "../../components/CategoryIcon";

interface Props { params: Promise<{ slug: string }> }

export function generateStaticParams() {
  return getAllCategories().map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const cats = getAllCategories();
  const cat = cats.find((c) => c.slug === slug);
  if (!cat) return { title: "Category Not Found" };
  return {
    title: `${cat.name} — Top Picks`,
    description: `Browse ${cat.count} top-rated ${cat.name} products. Best prices, verified reviews, direct Amazon links.`,
  };
}

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;
  const products = getProductsByCategory(slug);
  if (products.length === 0) notFound();

  const catName = products[0].category;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span>/</span>
        <Link href="/products" className="hover:text-zinc-300">Products</Link>
        <span>/</span>
        <span className="text-zinc-400">{catName}</span>
      </nav>

      {/* Header */}
      <div className="flex items-center gap-4 mb-10">
        <div className="w-14 h-14 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center justify-center text-3xl">
          {getCategoryIcon(slug)}
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">{catName}</h1>
          <p className="text-zinc-500 text-sm mt-1">{products.length} products</p>
        </div>
      </div>

      <ProductGrid products={products} />
    </div>
  );
}
