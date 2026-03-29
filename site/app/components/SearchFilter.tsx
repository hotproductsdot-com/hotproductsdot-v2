"use client";
import { useState, useMemo } from "react";
import type { Product } from "../lib/products";
import ProductGrid from "./ProductGrid";

interface Props {
  products: Product[];
  categories: { name: string; slug: string }[];
  initialCategory?: string;
}

export default function SearchFilter({ products, categories, initialCategory = "" }: Props) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(initialCategory);
  const [sort, setSort] = useState<"featured" | "rating" | "reviews" | "price-low" | "price-high">("featured");

  const filtered = useMemo(() => {
    let result = products;
    if (category) result = result.filter((p) => p.categorySlug === category);
    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter((p) => p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) => {
      if (sort === "rating") return b.rating - a.rating;
      if (sort === "reviews") return b.reviewCount - a.reviewCount;
      if (sort === "price-low") return a.priceMin - b.priceMin;
      if (sort === "price-high") return b.priceMax - a.priceMax;
      return b.affiliatePotential - a.affiliatePotential || b.rating - a.rating;
    });
  }, [products, category, query, sort]);

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3 mb-8">
        <input
          type="search"
          placeholder="Search products..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 bg-zinc-900 border border-zinc-700 text-zinc-100 placeholder-zinc-500 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-orange-500"
        />
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 text-zinc-100 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-orange-500"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
          className="bg-zinc-900 border border-zinc-700 text-zinc-100 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-orange-500"
        >
          <option value="featured">Featured</option>
          <option value="rating">Top Rated</option>
          <option value="reviews">Most Reviews</option>
          <option value="price-low">Price: Low to High</option>
          <option value="price-high">Price: High to Low</option>
        </select>
      </div>

      <div className="mb-4 text-sm text-zinc-500">{filtered.length} products</div>

      <ProductGrid products={filtered} />
    </div>
  );
}
