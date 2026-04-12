import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllCategories, getProductsByCategory } from "../../lib/products";
import { SITE_URL } from "../../lib/constants";
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
  const canonical = `${SITE_URL}/category/${slug}`;
  const title = `Best ${cat.name} Products — Top Amazon Picks`;
  const description = `Browse ${cat.count} top-rated ${cat.name} products. Best prices, verified reviews, direct Amazon links. Updated weekly.`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, url: canonical },
  };
}

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;
  const products = getProductsByCategory(slug);
  if (products.length === 0) notFound();

  const catName = products[0]!.category;

  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Products", item: `${SITE_URL}/products` },
      { "@type": "ListItem", position: 3, name: catName, item: `${SITE_URL}/category/${slug}` },
    ],
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
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
