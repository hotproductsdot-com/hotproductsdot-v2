import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllCategories, getProductsByCategory, type Product } from "../../lib/products";
import { SITE_URL } from "../../lib/constants";
import { getCategoryIcon } from "../../components/CategoryIcon";
import TrackedAffiliateLink from "../../components/TrackedAffiliateLink";

interface Props { params: Promise<{ slug: string }> }

// Per-product review copy. Replaces the old duplicated template string with
// a blurb differentiated by each product's actual stats (rating, reviews,
// BSR rank, price tier, badge). Keeps the page from looking templated to
// Google's Helpful Content system.
function getProductBlurb(p: Product, catName: string): string {
  const cat = catName.toLowerCase();
  const parts: string[] = [];

  if (p.rating >= 4.7) {
    parts.push(
      `With a ${p.rating}-star average across ${p.reviewCount.toLocaleString()} verified buyers, this is one of the most consistently-reviewed ${cat} options on Amazon.`
    );
  } else if (p.rating >= 4.5) {
    parts.push(
      `Rated ${p.rating} stars by ${p.reviewCount.toLocaleString()} reviewers — strong enough to stand out in a crowded ${cat} field.`
    );
  } else {
    parts.push(
      `Backed by ${p.reviewCount.toLocaleString()} Amazon reviews averaging ${p.rating} stars.`
    );
  }

  if (p.bsrRank > 0 && p.bsrRank <= 10) {
    parts.push(`Currently sits at #${p.bsrRank} on Amazon's bestseller list in its subcategory.`);
  } else if (p.bsrRank > 0 && p.bsrRank <= 100) {
    parts.push(`Ranks inside Amazon's top 100 bestsellers in its subcategory (${p.bsr}).`);
  }

  if (p.priceMin > 0 && p.priceMin < 50) {
    parts.push(`At ${p.priceRange}, it's also one of the more accessible picks here — a fair place to start if you're new to ${cat}.`);
  } else if (p.priceMin >= 50 && p.priceMin < 200) {
    parts.push(`Priced at ${p.priceRange}, it lands squarely in the mainstream ${cat} tier — more capable than entry-level options without jumping to premium pricing.`);
  } else if (p.priceMin >= 200) {
    parts.push(`At ${p.priceRange} it's a premium pick, justified if you want the best build quality and features in ${cat}.`);
  }

  if (p.badge === "hot") {
    parts.push(`It's one of the fastest-moving items in our ${cat} tracking this week.`);
  } else if (p.badge === "best-seller") {
    parts.push(`A long-standing Amazon Best Seller — proven track record, not a flash-in-the-pan.`);
  } else if (p.badge === "top-rated") {
    parts.push(`Top-rated across thousands of reviews — the kind of ${cat} pick you don't need to second-guess.`);
  }

  return parts.join(" ");
}

export function generateStaticParams() {
  return getAllCategories().map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const cats = getAllCategories();
  const cat = cats.find((c) => c.slug === slug);
  if (\!cat) return { title: "Category Not Found" };
  const canonical = `${SITE_URL}/best/${slug}`;
  const title = `Best ${cat.name} for 2026 — Expert Picks & Reviews`;
  const description = `Top-rated ${cat.name} on Amazon. We reviewed the bestsellers so you don't have to. Unbiased, verified reviews with real prices.`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, url: canonical },
  };
}

export default async function BestCategoryPage({ params }: Props) {
  const { slug } = await params;
  const products = getProductsByCategory(slug);
  if (products.length === 0) notFound();

  const catName = products[0]\!.category;
  const topProducts = products.slice(0, 5);
  const topPick = topProducts[0]\!;
  const canonical = `${SITE_URL}/best/${slug}`;

  // BreadcrumbList schema — mirrors the on-page breadcrumb navigation.
  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: `Best ${catName}`, item: canonical },
    ],
  };

  // ItemList schema — rich-result eligible. Each listed product becomes a
  // Product entry with AggregateRating + Offer so the full roundup is
  // machine-readable.
  const itemListLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `Best ${catName} for 2026`,
    url: canonical,
    numberOfItems: topProducts.length,
    itemListElement: topProducts.map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      item: {
        "@type": "Product",
        name: p.name,
        url: `${SITE_URL}/products/${p.slug}`,
        image: p.imageUrl || undefined,
        aggregateRating: {
          "@type": "AggregateRating",
          ratingValue: p.rating,
          reviewCount: p.reviewCount,
        },
        offers: {
          "@type": "Offer",
          priceCurrency: "USD",
          ...(p.priceMin > 0 ? { price: p.priceMin } : {}),
          availability: "https://schema.org/InStock",
          url: p.amazonUrl,
          seller: { "@type": "Organization", name: "Amazon" },
        },
      },
    })),
  };

  // FAQPage schema — mirrors the on-page FAQ. Eligible for FAQ rich snippets.
  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "What makes these products stand out?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "We prioritize bestsellers with 4.5+ ratings, strong sales velocity, and high affiliate potential. All products are verified on Amazon with real customer reviews.",
        },
      },
      {
        "@type": "Question",
        name: `How often is this ${catName.toLowerCase()} guide updated?`,
        acceptedAnswer: {
          "@type": "Answer",
          text: "Quarterly. We refresh prices, check for new bestsellers, and update availability. Check back seasonally for our latest picks.",
        },
      },
      {
        "@type": "Question",
        name: "Are these affiliate links?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Yes. We earn a small commission when you purchase through our links at no extra cost to you. This helps us maintain the site and keep these guides free.",
        },
      },
    ],
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }} />

      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span>/</span>
        <span className="text-zinc-400">Best {catName}</span>
      </nav>

      {/* FTC Disclosure — CRITICAL */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-8 text-sm text-blue-200">
        <strong>📢 Disclosure:</strong> This post contains affiliate links. If you click and buy, I may earn a commission at no extra cost to you.
      </div>

      {/* Hero Hook */}
      <div className="mb-12">
        <div className="inline-block bg-orange-500/10 text-orange-400 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-widest mb-4 border border-orange-500/20">
          {catName} Guide
        </div>
        <h1 className="text-4xl font-bold text-white mb-4">
          Best {catName} for 2026
        </h1>
        <p className="text-lg text-zinc-400 mb-6">
          We reviewed the top {topProducts.length} bestsellers on Amazon. Here's our unbiased breakdown to help you choose.
        </p>

        {/* Quick Facts */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-orange-500">{products.length}</div>
            <div className="text-xs text-zinc-500 mt-1">Products Reviewed</div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-orange-500">4.7★</div>
            <div className="text-xs text-zinc-500 mt-1">Avg Rating</div>
          </div>
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <div className="text-2xl font-bold text-orange-500">Updated</div>
            <div className="text-xs text-zinc-500 mt-1">Quarterly</div>
          </div>
        </div>
      </div>

      {/* Top Pick — Above the Fold CTA */}
      <div className="bg-gradient-to-br from-orange-500/10 to-orange-600/5 border border-orange-500/30 rounded-xl p-8 mb-12">
        <div className="flex gap-6">
          <div className="flex-shrink-0 w-32 h-32 bg-zinc-800 rounded-lg overflow-hidden">
            {topPick.imageUrl && (
              <img
                src={topPick.imageUrl}
                alt={topPick.name}
                className="w-full h-full object-cover"
              />
            )}
          </div>
          <div className="flex-1">
            <div className="text-orange-400 text-sm font-bold uppercase mb-2">🏆 Top Pick</div>
            <h2 className="text-2xl font-bold text-white mb-2">{topPick.name}</h2>
            <p className="text-zinc-400 mb-4">
              Best overall {catName.toLowerCase()}. Excellent build quality, top reviews on Amazon, and the best value in this category.
            </p>
            <div className="flex items-center gap-4 mb-4">
              <div className="flex items-center gap-1">
                <span className="text-yellow-400">★★★★★</span>
                <span className="text-zinc-400 text-sm">({topPick.reviewCount.toLocaleString()} reviews)</span>
              </div>
              <div className="text-zinc-400 text-sm">{topPick.priceRange}</div>
            </div>
            <TrackedAffiliateLink
              href={topPick.amazonUrl}
              className="bg-orange-500 hover:bg-orange-600 text-white font-semibold px-6 py-3 rounded-lg inline-block transition-colors"
              campaign="best-category-top-pick"
              slug={topPick.slug}
              name={topPick.name}
              category={topPick.category}
              priceMin={topPick.priceMin}
            >
              Check Price on Amazon →
            </TrackedAffiliateLink>
          </div>
        </div>
      </div>

      {/* Detailed Reviews */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-white mb-6">Full Reviews</h2>
        <div className="space-y-6">
          {topProducts.map((product) => (
            <div key={product.slug} className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
              <div className="flex gap-6 mb-4">
                <div className="flex-shrink-0 w-24 h-24 bg-zinc-800 rounded-lg overflow-hidden">
                  {product.imageUrl && (
                    <img
                      src={product.imageUrl}
                      alt={product.name}
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-white mb-1">{product.name}</h3>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-yellow-400">★★★★★</span>
                    <span className="text-zinc-500 text-sm">({product.reviewCount.toLocaleString()} reviews)</span>
                  </div>
                  <div className="text-orange-400 font-semibold">{product.priceRange}</div>
                </div>
              </div>
              <p className="text-zinc-400 mb-4">
                {product.badge && (
                  <span className="inline-block bg-zinc-800 text-zinc-200 text-xs font-bold px-2 py-1 rounded mr-2 capitalize">
                    {product.badge === "hot" ? "🔥 Hot Pick" : product.badge === "best-seller" ? "🏅 Best Seller" : "⭐ Top Rated"}
                  </span>
                )}
                {getProductBlurb(product, catName)}
              </p>
              <TrackedAffiliateLink
                href={product.amazonUrl}
                className="text-orange-400 hover:text-orange-300 font-medium text-sm"
                campaign="best-category-review"
                slug={product.slug}
                name={product.name}
                category={product.category}
                priceMin={product.priceMin}
              >
                View on Amazon →
              </TrackedAffiliateLink>
            </div>
          ))}
        </div>
      </div>

      {/* Comparison Table */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-white mb-6">Quick Comparison</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left py-3 px-4 font-semibold text-white">Product</th>
                <th className="text-left py-3 px-4 font-semibold text-white">Price</th>
                <th className="text-left py-3 px-4 font-semibold text-white">Rating</th>
                <th className="text-left py-3 px-4 font-semibold text-white">Reviews</th>
              </tr>
            </thead>
            <tbody>
              {topProducts.map((product) => (
                <tr key={product.slug} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                  <td className="py-3 px-4 text-zinc-300">{product.name}</td>
                  <td className="py-3 px-4 text-orange-400 font-semibold">{product.priceRange}</td>
                  <td className="py-3 px-4 text-yellow-400">★ {product.rating}</td>
                  <td className="py-3 px-4 text-zinc-400">{product.reviewCount.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* FAQ */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-white mb-6">FAQ</h2>
        <div className="space-y-4">
          <details className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold text-white hover:text-orange-400">What makes these products stand out?</summary>
            <p className="text-zinc-400 mt-3">
              We prioritize bestsellers with 4.5+ ratings, strong sales velocity, and high affiliate potential. All products are verified on Amazon with real customer reviews.
            </p>
          </details>
          <details className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold text-white hover:text-orange-400">How often is this guide updated?</summary>
            <p className="text-zinc-400 mt-3">
              Quarterly. We refresh prices, check for new bestsellers, and update availability. Check back seasonally for our latest picks.
            </p>
          </details>
          <details className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold text-white hover:text-orange-400">Are these affiliate links?</summary>
            <p className="text-zinc-400 mt-3">
              Yes. We earn a small commission when you purchase through our links at no extra cost to you. This helps us maintain the site and keep these guides free.
            </p>
          </details>
        </div>
      </div>

      {/* CTA */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 text-center mb-12">
        <h2 className="text-2xl font-bold text-white mb-3">Ready to upgrade?</h2>
        <p className="text-zinc-400 mb-6">Browse all {catName.toLowerCase()} on Amazon with verified reviews and pricing.</p>
        <TrackedAffiliateLink
          href={`https://www.amazon.com/s?k=${encodeURIComponent(catName)}&tag=hotproduct033-20`}
          className="bg-orange-500 hover:bg-orange-600 text-white font-semibold px-8 py-3 rounded-lg inline-block transition-colors"
          campaign="best-category-bottom-cta"
          slug={slug}
          name={`Browse ${catName}`}
          category={catName}
          priceMin={0}
        >
          Browse {catName} on Amazon →
        </TrackedAffiliateLink>
      </div>

      {/* Internal links to category hub */}
      <div className="border-t border-zinc-800 pt-8">
        <p className="text-zinc-500 text-sm mb-4">
          Want to browse more {catName.toLowerCase()} products?
        </p>
        <Link
          href={`/category/${slug}`}
          className="inline-block bg-zinc-800 hover:bg-zinc-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
        >
          View all {catName} →
        </Link>
      </div>
    </div>
  );
}
