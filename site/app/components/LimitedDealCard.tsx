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

function formatBought(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)}M+`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K+`;
  return `${n}+`;
}

/**
 * Card for the homepage "Limited Time Sale" section — today's verified
 * on-sale batch (fetch_daily_deals.py). Shows the discount %, strikethrough
 * list price, and the Amazon "bought in past month" velocity badge.
 */
export default function LimitedDealCard({ product }: { product: Product }) {
  const dealUrl = buildAffiliateUrl(product.amazonUrl, {
    campaign: "limited-time-sale",
    content: product.slug,
  });

  const listPriceLabel =
    product.listPrice && product.listPrice > 0
      ? `$${product.listPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      : null;

  return (
    <article className="group relative flex flex-col bg-zinc-900 border border-red-900/60 rounded-xl overflow-hidden transition-all duration-200 hover:-translate-y-1 hover:border-red-500/70 hover:shadow-xl hover:shadow-red-500/10">
      {/* Deal badges */}
      <div className="absolute top-2.5 left-2.5 z-10 flex flex-col gap-1">
        <span className="bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide">
          ⏰ {product.discountPct}% Off
        </span>
        {product.boughtPastMonth ? (
          <span className="bg-zinc-950/80 text-amber-400 text-[10px] font-bold px-2 py-0.5 rounded-full tracking-wide">
            {formatBought(product.boughtPastMonth)} bought this month
          </span>
        ) : null}
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
          <h3 className="text-sm font-semibold text-zinc-100 leading-snug line-clamp-2 group-hover:text-red-400 transition-colors">
            {product.name}
          </h3>
        </Link>

        {/* Price: sale price + strikethrough list price */}
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-extrabold text-red-400">{product.priceRange}</span>
          {listPriceLabel && (
            <span className="text-xs text-zinc-500 line-through">{listPriceLabel}</span>
          )}
        </div>

        {/* Rating + reviews */}
        <div className="flex items-center gap-2">
          <RatingStars rating={product.rating} />
          <span className="text-[11px] text-zinc-400 font-medium">{product.rating}</span>
          <span className="text-[11px] text-zinc-500">({formatCount(product.reviewCount)} reviews)</span>
        </div>

        <div className="flex flex-wrap gap-1.5 text-[10px] text-zinc-500">
          <span className="bg-zinc-800 px-2 py-0.5 rounded-full">{product.category}</span>
          <span className="bg-red-950/60 text-red-400 px-2 py-0.5 rounded-full">
            Limited time
          </span>
        </div>

        {/* CTA */}
        <div className="mt-auto pt-1">
          <TrackedAffiliateLink
            href={dealUrl}
            slug={product.slug}
            name={product.name}
            category={product.category}
            campaign="limited-time-sale"
            priceMin={product.priceMin}
            className="w-full flex items-center justify-center gap-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-bold px-3 py-2.5 rounded-lg transition-colors"
          >
            Grab the Deal →
          </TrackedAffiliateLink>
        </div>
      </div>
    </article>
  );
}
