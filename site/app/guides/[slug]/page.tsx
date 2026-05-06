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
    .filter(Boolean) as ReturnType<typeof getProductBySlug>[];

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
        <h1 className="text-3xl font-bold text-white leading-tight mb-3">{guide.title}</h1>
        <p className="text-zinc-400 text-lg">{guide.description}</p>
      </div>

      {/* Affiliate disclosure */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 mb-10 text-xs text-zinc-500">
        <strong className="text-zinc-400">Disclosure:</strong> This guide contains affiliate links. If you click and buy, we may earn a commission at no extra cost to you.{" "}
        <Link href="/disclaimer" className="underline hover:text-zinc-300">Learn more</Link>
      </div>

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

      {/* All featured products grid */}
      {featuredProducts.length > 0 && (
        <section className="border-t border-zinc-800 mt-14 pt-12">
          <h2 className="text-xl font-bold text-white mb-2">Products in This Guide</h2>
          <p className="text-zinc-500 text-sm mb-8">All recommended products, side by side.</p>
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
