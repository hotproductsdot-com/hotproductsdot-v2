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

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-14">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-3xl font-bold text-white mb-3">Buying Guides</h1>
        <p className="text-zinc-400 text-lg max-w-2xl">
          Cut through the noise. Our guides explain what actually matters before you buy.
        </p>
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
            <div className="mt-4 text-xs font-semibold text-orange-500 group-hover:text-orange-400 transition-colors">
              Read guide →
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
