import type { Metadata } from "next";
import Link from "next/link";
import { getAllGuides } from "../lib/guides";
import { getCategoryIcon } from "../components/CategoryIcon";
import { SITE_URL, BRAND_ORG } from "../lib/constants";

const canonical = `${SITE_URL}/guides`;

export const metadata: Metadata = {
  title: "Expert Buying Guides 2026 — Best Product Recommendations",
  description:
    "171+ expert buying guides covering everything from laptops to kitchen gadgets. Cut through product noise with honest reviews and real recommendations.",
  alternates: { canonical },
  openGraph: {
    title: "Expert Buying Guides 2026 — Best Product Recommendations",
    description: "171+ expert buying guides. Honest advice on what to buy and why it matters. Photography, smart home, laptops, kitchen, and more.",
    url: canonical,
  },
  keywords: [
    "buying guides",
    "best products 2026",
    "product recommendations",
    "buyer's guides",
    "what to buy",
    "product comparisons",
  ],
};

export default function GuidesPage() {
  const guides = getAllGuides();
  const categories = Array.from(new Set(guides.map((g) => g.category))).sort();
  const byCategory = Object.groupBy(guides, (g) => g.category);

  // ponytail: CollectionPage + FAQPage schema for richer SERP appearance
  const jsonLdCollection = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Buying Guides",
    description: "Expert buying guides for 2026",
    url: canonical,
    publisher: BRAND_ORG,
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: guides.length,
      itemListElement: guides.slice(0, 10).map((g, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: g.title,
        description: g.description,
        url: `${SITE_URL}/guides/${g.slug}`,
      })),
    },
  };

  const jsonLdFaq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "How do you pick the products to recommend?",
        acceptedAnswer: { "@type": "Answer", text: "We evaluate based on real-world performance, customer ratings, value for money, and expert consensus. No sponsorships or paid placements." },
      },
      {
        "@type": "Question",
        name: "Are your guides always up to date?",
        acceptedAnswer: { "@type": "Answer", text: "Yes. We refresh guides regularly with new products, updated prices, and changing market conditions." },
      },
      {
        "@type": "Question",
        name: "Can I trust the affiliate links?",
        acceptedAnswer: { "@type": "Answer", text: "Absolutely. We use affiliate links to support the site while providing honest recommendations. You pay the same price on Amazon." },
      },
    ],
  };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-14">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdCollection) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdFaq) }} />
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-3xl font-bold text-white mb-3">Buying Guides</h1>
        <p className="text-zinc-400 text-lg max-w-2xl">
          Cut through the noise. Our guides explain what actually matters before you buy.
        </p>
        <p className="text-xs text-zinc-500 mt-4">
          {guides.length} comprehensive guides covering {categories.length} categories
        </p>
      </div>

      {/* Category filter */}
      <div className="mb-8 overflow-x-auto pb-2">
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-orange-500 text-zinc-950 text-xs font-bold rounded-full whitespace-nowrap transition-colors hover:bg-orange-400">
            All ({guides.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              className="px-4 py-2 bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs font-semibold rounded-full whitespace-nowrap hover:border-orange-500/40 transition-colors"
            >
              {cat} ({byCategory[cat]?.length || 0})
            </button>
          ))}
        </div>
      </div>

      {/* Guide cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {guides.map((guide) => (
          <Link
            key={guide.slug}
            href={`/guides/${guide.slug}`}
            className="group flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl p-6 hover:border-orange-500/40 hover:shadow-xl hover:shadow-orange-500/5 transition-all"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-zinc-800 rounded-lg flex items-center justify-center text-xl shrink-0">
                {getCategoryIcon(guide.categorySlug)}
              </div>
              <span className="text-xs font-semibold text-orange-400 uppercase tracking-wider">
                {guide.category}
              </span>
            </div>
            <h2 className="text-lg font-bold text-white leading-snug mb-2 group-hover:text-orange-400 transition-colors">
              {guide.title}
            </h2>
            <p className="text-zinc-500 text-sm leading-relaxed flex-1">{guide.description}</p>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-zinc-500">
                {guide.sections.length} sections
              </span>
              <span className="text-xs font-semibold text-orange-500 group-hover:text-orange-400 transition-colors">
                Read guide →
              </span>
            </div>
          </Link>
        ))}
      </div>

      {/* FAQ for guides page */}
      <section className="mt-20 pt-12 border-t border-zinc-800">
        <h2 className="text-2xl font-bold text-white mb-8">Guide FAQs</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[
            { q: "How do you pick the products to recommend?", a: "We evaluate based on real-world performance, customer ratings, value for money, and expert consensus. No sponsorships or paid placements." },
            { q: "Are your guides always up to date?", a: "Yes. We refresh guides regularly with new products, updated prices, and changing market conditions." },
            { q: "Can I trust the affiliate links?", a: "Absolutely. We use affiliate links to support the site while providing honest recommendations. You pay the same price on Amazon." },
            { q: "Which categories have the most guides?", a: "Photography and Smart Home have the most coverage, but we're adding new categories constantly based on reader interest." },
          ].map((faq, i) => (
            <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
              <h3 className="text-sm font-bold text-white mb-3">{faq.q}</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">{faq.a}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
