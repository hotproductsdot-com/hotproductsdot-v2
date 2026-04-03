import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllProducts, getProductBySlug, getProductsByCategory } from "../../lib/products";
import { SITE_URL } from "../../lib/constants";
import { buildAffiliateUrl } from "../../lib/affiliate";
import RatingStars from "../../components/RatingStars";
import ProductGrid from "../../components/ProductGrid";
import Badge from "../../components/Badge";
import ProductImage from "../../components/ProductImage";

interface Props { params: Promise<{ slug: string }> }

export function generateStaticParams() {
  return getAllProducts().map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const p = getProductBySlug(slug);
  if (!p) return { title: "Product Not Found" };
  const canonical = `${SITE_URL}/products/${p.slug}`;
  return {
    title: p.name,
    description: `${p.name} — ${p.rating} stars, ${p.reviewCount.toLocaleString()} reviews. Highly rated ${p.category} product. Check the latest price on Amazon.`,
    alternates: { canonical },
    openGraph: {
      title: p.name,
      description: `${p.rating}★ · ${p.reviewCount.toLocaleString()} reviews · ${p.category}`,
      url: canonical,
      images: p.imageUrl ? [{ url: p.imageUrl }] : [],
    },
    twitter: { card: "summary_large_image" },
  };
}

function getWhyBuy(p: ReturnType<typeof getProductBySlug>): string[] {
  if (!p) return [];
  const points: string[] = [];
  if (p.rating >= 4.7) points.push(`Exceptional ${p.rating}-star rating from ${p.reviewCount.toLocaleString()} verified buyers`);
  else points.push(`Strong ${p.rating}-star average across ${p.reviewCount.toLocaleString()} reviews`);
  if (p.bsrRank <= 5) points.push(`Amazon Best Seller rank ${p.bsr} in its category`);
  if (p.affiliatePotential >= 9) points.push("One of our highest-confidence recommendations");
  if (p.priceMin > 0 && p.priceMin < 100) points.push(`Excellent value at ${p.priceRange}`);
  else if (p.priceMin >= 100) points.push(`Premium ${p.category.toLowerCase()} with price starting at ${p.priceRange}`);
  points.push("Ships with Amazon Prime — fast, free delivery");
  return points.slice(0, 4);
}

export default async function ProductDetailPage({ params }: Props) {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) notFound();

  const related = getProductsByCategory(product.categorySlug)
    .filter((p) => p.slug !== product.slug)
    .slice(0, 4);

  const whyBuy = getWhyBuy(product);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    category: product.category,
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: product.rating,
      reviewCount: product.reviewCount,
    },
    offers: {
      "@type": "Offer",
      priceCurrency: "USD",
      price: product.priceMin || undefined,
      availability: "https://schema.org/InStock",
      url: product.amazonUrl,
      seller: { "@type": "Organization", name: "Amazon" },
    },
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span aria-hidden="true">/</span>
        <Link href="/products" className="hover:text-zinc-300">Products</Link>
        <span aria-hidden="true">/</span>
        <Link href={`/category/${product.categorySlug}`} className="hover:text-zinc-300">{product.category}</Link>
        <span aria-hidden="true">/</span>
        <span className="text-zinc-400 truncate max-w-[200px]">{product.name}</span>
      </nav>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-16">
        {/* Image */}
        <div className="relative aspect-square bg-white rounded-2xl border border-zinc-200 flex items-center justify-center overflow-hidden">
          <ProductImage
            src={product.imageUrl}
            alt={product.name}
            className="w-full h-full object-contain p-8"
          />
          {product.badge && (
            <div className="absolute top-4 left-4">
              <Badge badge={product.badge} />
            </div>
          )}
        </div>

        {/* Details */}
        <div className="flex flex-col">
          <Link href={`/category/${product.categorySlug}`} className="inline-block self-start text-xs font-semibold text-orange-400 uppercase tracking-widest mb-3 hover:text-orange-300">
            ← {product.category}
          </Link>

          <h1 className="text-3xl font-bold text-white leading-tight mb-4">{product.name}</h1>

          <div className="flex items-center gap-3 mb-5">
            <RatingStars rating={product.rating} size="lg" />
            <span className="text-zinc-300 font-semibold">{product.rating}</span>
            <span className="text-zinc-500 text-sm">{product.reviewCount.toLocaleString()} reviews</span>
          </div>

          <div className="text-4xl font-extrabold text-white mb-6">{product.priceRange}</div>

          {/* Why buy */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
            <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Why We Recommend It</h3>
            <ul className="space-y-2">
              {whyBuy.map((point) => (
                <li key={point} className="flex items-start gap-2 text-sm text-zinc-300">
                  <span className="text-orange-500 mt-0.5 shrink-0">✓</span>
                  {point}
                </li>
              ))}
            </ul>
          </div>

          {/* Specs */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
            <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-3">Product Details</h3>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-zinc-600 text-xs">Category</dt><dd className="text-zinc-200">{product.category}</dd></div>
              <div><dt className="text-zinc-600 text-xs">Price Range</dt><dd className="text-zinc-200">{product.priceRange}</dd></div>
              <div><dt className="text-zinc-600 text-xs">Rating</dt><dd className="text-zinc-200">{product.rating} / 5.0</dd></div>
              <div><dt className="text-zinc-600 text-xs">Reviews</dt><dd className="text-zinc-200">{product.reviewCount.toLocaleString()}</dd></div>
              {product.bsr && <div className="col-span-2"><dt className="text-zinc-600 text-xs">Best Seller Rank</dt><dd className="text-zinc-200">{product.bsr}</dd></div>}
            </dl>
          </div>

          {/* CTA */}
          <a
            href={buildAffiliateUrl(product.amazonUrl, { campaign: "product-page", content: product.slug })}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="flex items-center justify-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold px-8 py-4 rounded-xl transition-colors text-lg mb-3"
          >
            Buy on Amazon
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
          <p className="text-[11px] text-zinc-600 text-center">
            As an Amazon Associate we earn from qualifying purchases. Price subject to change.
          </p>
        </div>
      </div>

      {/* Related */}
      {related.length > 0 && (
        <section className="border-t border-zinc-800 pt-12">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-xl font-bold text-white">More in {product.category}</h2>
            <Link href={`/category/${product.categorySlug}`} className="text-sm text-orange-400 hover:text-orange-300">
              See all →
            </Link>
          </div>
          <ProductGrid products={related} />
        </section>
      )}
    </div>
  );
}
