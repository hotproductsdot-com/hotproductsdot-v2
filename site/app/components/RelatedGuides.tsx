import Link from "next/link";
import type { Guide } from "../lib/guides";
import { getCategoryIcon } from "./CategoryIcon";

interface RelatedGuidesProps {
  currentSlug: string;
  category: string;
  allGuides: Guide[];
}

export default function RelatedGuides({ currentSlug, category, allGuides }: RelatedGuidesProps) {
  const related = allGuides
    .filter((g) => g.categorySlug === category.toLowerCase().replace(/\s+/g, "-") && g.slug !== currentSlug)
    .slice(0, 3);

  if (related.length === 0) return null;

  return (
    <section className="border-t border-zinc-800 mt-14 pt-12">
      <h2 className="text-xl font-bold text-white mb-6">Explore More in {category}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {related.map((guide) => (
          <Link
            key={guide.slug}
            href={`/guides/${guide.slug}`}
            className="group flex flex-col bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 hover:border-orange-500/40 transition-all"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 bg-zinc-800 rounded-lg flex items-center justify-center text-lg shrink-0">
                {getCategoryIcon(guide.categorySlug)}
              </div>
            </div>
            <h3 className="text-sm font-bold text-white leading-snug mb-2 group-hover:text-orange-400 transition-colors line-clamp-2">
              {guide.title}
            </h3>
            <p className="text-xs text-zinc-500 flex-1 line-clamp-2">{guide.description}</p>
            <div className="mt-3 text-xs font-semibold text-orange-500 group-hover:text-orange-400 transition-colors">
              Read →
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
