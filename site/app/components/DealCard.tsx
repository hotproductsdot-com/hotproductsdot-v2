import Link from "next/link";
import type { Product } from "../lib/products";
import { buildAffiliateUrl } from "../lib/affiliate";
import RatingStars from "./RatingStars";
import ProductImage from "./ProductImage";
import TrackedAffiliateLink from "./TrackedAffiliateLink";

function formatCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function DealCard({ product }: { product: Product }) {
  const dealUrl = buildAffiliateUrl(product.amazonUrl, {
    campaign: "hot-deals",
    content: product.slug,
  });

  const bsrLabel = product.bsrRank <= 10 ? `#${product.bsrRank} Best Seller` : null;

  return (
    <article className="group relative flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:border-orange-500/60 hover:shadow-xl hover:shadow-orange-500/10">
      {/* Deal badge */}
      <div className="absolute top-2.5 left-2.5 z-10 flex flex-col gap-1">
        <span className="bg-orange-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
          🔥 Hot Deal
        </span>
        {bsrLabel && (
          <span className="bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
            {bsrLabel}
          </span>
        )}
      </div>

      {/* Image */}
      <Link href={`/products/${product.slug}`} className="block">
        <div className="relative aspect-[4/3] bg-white flex items-center justify-center overflow-hidden">
          <ProductImage
            src={product.imageUrl}
            alt={product.name}
            className="w-full h-full object-contain p-4 group-hover:scale-105 transition-transform duration-300"
          />
        </div>
      </Link>

      {/* Content */}
      <div className="flex flex-col flex-1 p-4 gap-2">
        <Link href={`/products/${product.slug}`}>
          <h3 className="text-sm font-semibold text-zinc-100 leading-snug line-clamp-2 group-hover:text-orange-400 transition-colors">
            {product.name}
          </h3>
        </Link>

        {/* Price */}
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-extrabold text-orange-400">{product.priceRange}</span>
          <span className="text-[11px] text-zinc-500">on Amazon</span>
        </div>

        {/* Rating + reviews */}
        <div className="flex items-center gap-2">
          <RatingStars rating={product.rating} />
          <span className="text-[11px] text-zinc-400 font-medium">{product.rating}</span>
          <span className="text-[11px] text-zinc-500">({formatCount(product.reviewCount)} reviews)</span>
        </div>

        {/* Extra details */}
        <div className="flex flex-wrap gap-1.5 text-[10px] text-zinc-500">
          <span className="bg-zinc-800 px-2 py-0.5 rounded-full">
            {product.category}
          </span>
          {product.bsrRank <= 50 && (
            <span className="bg-zinc-800 px-2 py-0.5 rounded-full text-zinc-400">
              BSR #{product.bsrRank}
            </span>
          )}
          {product.rating >= 4.7 && (
            <span className="bg-zinc-800 px-2 py-0.5 rounded-full text-amber-400">
              Top Rated
            </span>
          )}
        </div>

        {/* CTA */}
        <div className="mt-auto pt-1">
          <TrackedAffiliateLink
            href={dealUrl}
            slug={product.slug}
            name={product.name}
            category={product.category}
            campaign="hot-deals"
            priceMin={product.priceMin}
            className="w-full flex items-center justify-center gap-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold px-3 py-2.5 rounded-lg transition-colors"
          >
            See Deal on Amazon →
          </TrackedAffiliateLink>
        </div>
      </div>
    </article>
  );
}
