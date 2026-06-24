import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllGuides, getGuideBySlug } from "../../lib/guides";
import { getProductBySlug } from "../../lib/products";
import { buildAffiliateUrl } from "../../lib/affiliate";
import { SITE_URL } from "../../lib/constants";
import ProductGrid from "../../components/ProductGrid";
import ProductImage from "../../components/ProductImage";

interface Props { params: Promise<{ slug: string }> }

export function generateStaticParams() {
  return getAllGuides().map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const guide = getGuideBySlug(slug);
  if (!guide) return { title: "Guide Not Found" };
  const canonical = `${SITE_URL}/guides/${guide.slug}`;
  return {
    title: guide.title,
    description: guide.description,
    alternates: { canonical },
    openGraph: { title: guide.title, description: guide.description, url: canonical },
  };
}

export default async function GuidePage({ params }: Props) {
  const { slug } = await params;
  const guide = getGuideBySlug(slug);
  if (!guide) notFound();

  // Collect featured products from all sections
  const featuredSlugs = guide.sections.flatMap((s) => s.productSlugs ?? []);
  const featuredProducts = featuredSlugs
    .map((s) => getProductBySlug(s))
    .filter(Boolean) as NonNullable<ReturnType<typeof getProductBySlug>>[];
  const topPick = featuredProducts[0];
  const comparisonProducts = featuredProducts.slice(0, 5); // ponytail: limit to 5 for table readability

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: guide.title,
    description: guide.description,
    url: `${SITE_URL}/guides/${guide.slug}`,
    publisher: { "@type": "Organization", name: "HotProducts" },
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span>/</span>
        <Link href="/guides" className="hover:text-zinc-300">Guides</Link>
        <span>/</span>
        <span className="text-zinc-400 truncate">{guide.title}</span>
      </nav>

      {/* Header */}
      <div className="mb-10">
        <Link
          href={`/category/${guide.categorySlug}`}
          className="inline-block text-xs font-semibold text-orange-400 uppercase tracking-widest mb-3 hover:text-orange-300"
        >
          ← {guide.category}
        </Link>
        <h1 className="text-3xl font-bold text-white leading-tight mb-2">{guide.title}</h1>
        {guide.publishedAt && (
          <p className="text-xs text-zinc-500 mb-3">
            Published {new Date(guide.publishedAt + "T12:00:00").toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
          </p>
        )}
        <p className="text-zinc-400 text-lg">{guide.description}</p>
      </div>

      {/* Affiliate disclosure */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 mb-10 text-xs text-zinc-500">
        <strong className="text-zinc-400">Disclosure:</strong> This guide contains affiliate links. If you click and buy, we may earn a commission at no extra cost to you.{" "}
        <Link href="/disclaimer" className="underline hover:text-zinc-300">Learn more</Link>
      </div>

      {/* Top Pick — enlarged above-the-fold CTA (Phase 2 upgrade) */}
      {topPick && (
        <a
          href={buildAffiliateUrl(topPick.amazonUrl, { campaign: "guide", content: `${guide.slug}_toppick` })}
          target="_blank"
          rel="noopener noreferrer nofollow sponsored"
          data-affiliate="true"
          className="flex flex-col sm:flex-row items-stretch sm:items-center gap-6 bg-gradient-to-r from-orange-500/15 to-zinc-900 border-2 border-orange-500/40 rounded-3xl p-8 mb-14 hover:border-orange-500/70 hover:shadow-2xl hover:shadow-orange-500/20 transition-all group"
        >
          <div className="w-32 h-32 sm:w-40 sm:h-40 bg-white rounded-2xl shrink-0 flex items-center justify-center overflow-hidden">
            {topPick.imageUrl && (
              <ProductImage
                src={topPick.imageUrl}
                alt={topPick.name}
                className="w-full h-full object-contain p-2"
                sizes="160px"
              />
            )}
          </div>
          <div className="flex-1 min-w-0 flex flex-col justify-between">
            <div>
              <div className="text-xs font-bold text-orange-400 uppercase tracking-widest mb-2">✨ Best Overall Pick</div>
              <div className="text-2xl font-bold text-zinc-100 group-hover:text-orange-400 transition-colors line-clamp-3 leading-snug mb-2">
                {topPick.name}
              </div>
              <div className="text-sm text-zinc-400 mt-2">
                {topPick.rating}★ ({topPick.reviewCount.toLocaleString()} reviews)
              </div>
            </div>
            <a
              href={buildAffiliateUrl(topPick.amazonUrl, { campaign: "guide", content: `${guide.slug}_toppick_cta` })}
              target="_blank"
              rel="noopener noreferrer nofollow sponsored"
              className="mt-4 inline-block bg-orange-500 hover:bg-orange-400 text-zinc-950 font-bold rounded-xl px-8 py-4 whitespace-nowrap transition-colors w-full sm:w-auto text-center text-base"
            >
              See Best Price on Amazon →
            </a>
          </div>
        </a>
      )}

      {/* Comparison table — Phase 3 link placement */}
      {comparisonProducts.length > 1 && (
        <section className="mb-14 bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="text-lg font-bold text-white">Quick Comparison</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-800/50">
                  <th className="text-left px-6 py-3 font-semibold text-zinc-300">Product</th>
                  <th className="text-center px-4 py-3 font-semibold text-zinc-300 whitespace-nowrap">Rating</th>
                  <th className="text-right px-6 py-3 font-semibold text-zinc-300">Action</th>
                </tr>
              </thead>
              <tbody>
                {comparisonProducts.map((product, idx) => (
                  <tr key={product.slug} className="border-b border-zinc-800 hover:bg-zinc-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-zinc-100">{product.name}</div>
                      <div className="text-xs text-zinc-500 mt-1">{product.rating}★ · {product.reviewCount.toLocaleString()} reviews</div>
                    </td>
                    <td className="text-center px-4 py-4 text-zinc-400">{product.rating}★</td>
                    <td className="text-right px-6 py-4">
                      <a
                        href={buildAffiliateUrl(product.amazonUrl, { campaign: "guide", content: `${guide.slug}_comparison_${idx}` })}
                        target="_blank"
                        rel="noopener noreferrer nofollow sponsored"
                        className="inline-block text-orange-400 hover:text-orange-300 font-semibold transition-colors"
                      >
                        View →
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Sections */}
      <div className="space-y-10">
        {guide.sections.map((section) => {
          const sectionProducts = (section.productSlugs ?? [])
            .map((s) => getProductBySlug(s))
            .filter(Boolean) as ReturnType<typeof getProductBySlug>[];

          return (
            <section key={section.heading}>
              <h2 className="text-xl font-bold text-white mb-3">{section.heading}</h2>
              <p className="text-zinc-400 leading-relaxed mb-4">{section.body}</p>
              {sectionProducts.length > 0 && (
                <div className="mt-4 space-y-3">
                  {sectionProducts.map((product) => product && (
                    <a
                      key={product.slug}
                      href={buildAffiliateUrl(product.amazonUrl, { campaign: "guide", content: guide.slug })}
                      target="_blank"
                      rel="noopener noreferrer nofollow sponsored"
                      data-affiliate="true"
                      className="flex items-center gap-4 bg-zinc-900 border border-zinc-800 rounded-xl p-4 hover:border-orange-500/40 transition-all group"
                    >
                      <div className="w-16 h-16 bg-white rounded-lg shrink-0 flex items-center justify-center overflow-hidden">
                        {product.imageUrl && (
                          <ProductImage
                            src={product.imageUrl}
                            alt={product.name}
                            className="w-full h-full object-contain p-1"
                            sizes="64px"
                          />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-zinc-100 group-hover:text-orange-400 transition-colors line-clamp-2">
                          {product.name}
                        </div>
                        <div className="text-xs text-zinc-500 mt-1">
                          {product.rating}★ · {product.reviewCount.toLocaleString()} reviews
                        </div>
                      </div>
                      <div className="shrink-0 text-xs font-bold text-orange-500 group-hover:text-orange-400 transition-colors whitespace-nowrap">
                        Buy on Amazon →
                      </div>
                    </a>
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {/* FAQ Section — Phase 4 engagement booster */}
      <section className="border-t border-zinc-800 mt-16 pt-12 mb-14">
        <h2 className="text-xl font-bold text-white mb-8">Frequently Asked Questions</h2>
        <div className="space-y-6">
          <details className="group bg-zinc-900 border border-zinc-800 rounded-lg p-5 cursor-pointer hover:border-zinc-700 transition-colors">
            <summary className="font-semibold text-zinc-100 flex items-center gap-2">
              <span className="text-orange-400 group-open:rotate-180 transition-transform">▶</span>
              What should I look for when buying {guide.category.toLowerCase()}?
            </summary>
            <p className="text-zinc-400 text-sm mt-4 ml-6 leading-relaxed">
              The guides above cover the key factors for {guide.category.toLowerCase()}. Focus on your specific use case: professional vs. casual use, budget constraints, and feature priorities. Read the guide&apos;s &quot;What to Look For&quot; section for detailed guidance.
            </p>
          </details>

          <details className="group bg-zinc-900 border border-zinc-800 rounded-lg p-5 cursor-pointer hover:border-zinc-700 transition-colors">
            <summary className="font-semibold text-zinc-100 flex items-center gap-2">
              <span className="text-orange-400 group-open:rotate-180 transition-transform">▶</span>
              Are these products available on Amazon?
            </summary>
            <p className="text-zinc-400 text-sm mt-4 ml-6 leading-relaxed">
              Yes, all products recommended in this guide are available on Amazon. We use Amazon affiliate links so we earn a small commission when you buy through them — at no extra cost to you.
            </p>
          </details>

          <details className="group bg-zinc-900 border border-zinc-800 rounded-lg p-5 cursor-pointer hover:border-zinc-700 transition-colors">
            <summary className="font-semibold text-zinc-100 flex items-center gap-2">
              <span className="text-orange-400 group-open:rotate-180 transition-transform">▶</span>
              How do you choose these products?
            </summary>
            <p className="text-zinc-400 text-sm mt-4 ml-6 leading-relaxed">
              We research Amazon reviews, ratings, and real-world performance data to identify products that genuinely deliver value. Our goal is to save you research time by surfacing the best options in each category and price range.
            </p>
          </details>

          <details className="group bg-zinc-900 border border-zinc-800 rounded-lg p-5 cursor-pointer hover:border-zinc-700 transition-colors">
            <summary className="font-semibold text-zinc-100 flex items-center gap-2">
              <span className="text-orange-400 group-open:rotate-180 transition-transform">▶</span>
              Can I trust these reviews?
            </summary>
            <p className="text-zinc-400 text-sm mt-4 ml-6 leading-relaxed">
              We only recommend products with high review counts (typically 100+ reviews) and strong ratings. We avoid new or unproven products, and we disclose that we earn a commission through Amazon affiliate links.
            </p>
          </details>
        </div>
      </section>

      {/* All featured products grid */}
      {featuredProducts.length > 0 && (
        <section className="border-t border-zinc-800 mt-8 pt-12">
          <h2 className="text-xl font-bold text-white mb-2">All Products in This Guide</h2>
          <p className="text-zinc-500 text-sm mb-8">Complete list of every recommendation, sorted by our ranking.</p>
          <ProductGrid products={featuredProducts as NonNullable<typeof featuredProducts[0]>[]} />
        </section>
      )}

      {/* Back to guides */}
      <div className="border-t border-zinc-800 mt-14 pt-8">
        <Link href="/guides" className="text-sm text-orange-400 hover:text-orange-300 font-medium">
          ← All Buying Guides
        </Link>
      </div>
    </div>
  );
}
