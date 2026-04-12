import Link from "next/link";
import type { Product } from "../lib/products";
import { buildAffiliateUrl } from "../lib/affiliate";
import RatingStars from "./RatingStars";
import Badge from "./Badge";
import ProductImage from "./ProductImage";
import TrackedAffiliateLink from "./TrackedAffiliateLink";

function formatCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function ProductCard({ product }: { product: Product }) {
  return (
    <article className="group flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:border-orange-500/40 hover:shadow-xl hover:shadow-orange-500/5">
      {/* Image area — `relative` here so the skeleton overlay anchors correctly */}
      <Link href={`/products/${product.slug}`} className="block">
        <div className="relative aspect-[4/3] bg-white flex items-center justify-center overflow-hidden">
          <ProductImage
            src={product.imageUrl}
            alt={product.name}
            className="w-full h-full object-contain p-4 group-hover:scale-105 transition-transform duration-300"
          />
        </div>
        <Badge badge={product.badge} />
      </Link>

      {/* Content */}
      <div className="flex flex-col flex-1 p-4 gap-3">
        <Link href={`/products/${product.slug}`}>
          <h3 className="text-sm font-semibold text-zinc-100 leading-snug line-clamp-2 group-hover:text-orange-400 transition-colors">
            {product.name}
          </h3>
        </Link>

        <div className="flex items-center gap-2">
          <RatingStars rating={product.rating} />
          <span className="text-[11px] text-zinc-500">{product.rating} ({formatCount(product.reviewCount)})</span>
        </div>

        <div className="mt-auto">
          <TrackedAffiliateLink
            href={buildAffiliateUrl(product.amazonUrl, { campaign: "product-card", content: product.slug })}
            slug={product.slug}
            name={product.name}
            category={product.category}
            campaign="product-card"
            priceMin={product.priceMin}
            className="w-full flex items-center justify-center gap-1 bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold px-3 py-2 rounded-lg transition-colors"
          >
            Buy on Amazon →
          </TrackedAffiliateLink>
        </div>
      </div>
    </article>
  );
}
