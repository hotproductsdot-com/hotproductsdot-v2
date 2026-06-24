import type { Metadata } from "next";
import Link from "next/link";
import { getAllGuides } from "../lib/guides";
import { getCategoryIcon } from "../components/CategoryIcon";
import { SITE_URL } from "../lib/constants";

const canonical = `${SITE_URL}/guides`;

export const metadata: Metadata = {
  title: "Buying Guides — Expert Amazon Product Advice",
  description:
    "In-depth buying guides to help you choose the best products. Expert advice on laptops, smart home, photography, kitchen gear, and more.",
  alternates: { canonical },
  openGraph: {
    title: "Buying Guides — Expert Amazon Product Advice",
    description: "In-depth buying guides for laptops, smart home, photography, kitchen gear, and more.",
    url: canonical,
  },
};

export default function GuidesPage() {
  const guides = getAllGuides();

  const categories = Array.from(new Set(guides.map((g) => g.category))).sort();

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-14">
      {/* Header — Phase 2 upgrade */}
      <div className="mb-12">
        <h1 className="text-4xl font-bold text-white mb-3">Expert Buying Guides</h1>
        <p className="text-zinc-400 text-lg max-w-2xl mb-6">
          Cut through the noise. Our buying guides explain what actually matters — backed by real product data and Amazon reviews.
        </p>
        <div className="inline-flex gap-2 flex-wrap">
          <span className="text-xs text-zinc-500 font-medium">Popular categories:</span>
          {categories.slice(0, 5).map((cat) => (
            <a
              key={cat}
              href={`#${cat.toLowerCase().replace(/\s+/g, "-")}`}
              className="text-xs px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-full text-zinc-300 hover:border-orange-500/40 hover:text-orange-400 transition-all"
            >
              {cat}
            </a>
          ))}
        </div>
      </div>

      {/* Guide cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {guides.map((guide) => (
          <Link
            key={guide.slug}
            href={`/guides/${guide.slug}`}
            className="group flex flex-col bg-gradient-to-br from-zinc-900 to-zinc-950 border border-zinc-800 rounded-xl p-6 hover:border-orange-500/50 hover:shadow-xl hover:shadow-orange-500/10 transition-all"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-orange-500/10 rounded-lg flex items-center justify-center text-2xl shrink-0 group-hover:bg-orange-500/20 transition-colors">
                {getCategoryIcon(guide.categorySlug)}
              </div>
              <span className="text-xs font-semibold text-orange-400 uppercase tracking-wider">
                {guide.category}
              </span>
            </div>
            <h2 className="text-base font-bold text-white leading-snug mb-3 group-hover:text-orange-400 transition-colors line-clamp-2">
              {guide.title}
            </h2>
            <p className="text-zinc-400 text-sm leading-relaxed flex-1 mb-4">{guide.description}</p>
            <div className="inline-flex items-center gap-2 text-sm font-semibold text-orange-500 group-hover:text-orange-400 transition-colors">
              Start reading
              <span className="group-hover:translate-x-1 transition-transform">→</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
