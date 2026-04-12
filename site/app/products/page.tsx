import type { Metadata } from "next";
import { getAllProducts, getAllCategories } from "../lib/products";
import { SITE_URL } from "../lib/constants";
import SearchFilter from "../components/SearchFilter";

const canonical = `${SITE_URL}/products`;

export const metadata: Metadata = {
  title: "All Products — Top-Rated Amazon Picks",
  description:
    "Browse hundreds of top-rated, best-selling Amazon products. Filter by category, sort by price or rating. Updated weekly.",
  alternates: { canonical },
  openGraph: {
    title: "All Products — Top-Rated Amazon Picks",
    description: "Browse top-rated Amazon products across every category. Updated weekly.",
    url: canonical,
  },
};

export default function ProductsPage() {
  const products = getAllProducts();
  const categories = getAllCategories();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">All Products</h1>
        <p className="text-zinc-500 mt-2">Browse, search, and filter {products.length} top-rated picks</p>
      </div>
      <SearchFilter products={products} categories={categories} />
    </div>
  );
}
