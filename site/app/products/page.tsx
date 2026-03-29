import type { Metadata } from "next";
import { getAllProducts, getAllCategories } from "../lib/products";
import SearchFilter from "../components/SearchFilter";

export const metadata: Metadata = {
  title: "All Products",
  description: "Browse all top-rated Amazon products. Filter by category, sort by price or rating.",
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
