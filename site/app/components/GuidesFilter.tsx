'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { Guide } from '../lib/guides';
import { getCategoryIcon } from './CategoryIcon';

interface GuidesFilterProps {
  guides: Guide[];
  categories: string[];
}

export default function GuidesFilter({ guides, categories }: GuidesFilterProps) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const byCategory = guides.reduce((acc, g) => {
    if (!acc[g.category]) acc[g.category] = [];
    acc[g.category].push(g);
    return acc;
  }, {} as Record<string, typeof guides>);

  const filteredGuides = selectedCategory ? byCategory[selectedCategory] || [] : guides;

  return (
    <>
      {/* Category filter */}
      <div className="mb-8 overflow-x-auto pb-2">
        <div className="flex gap-2">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-4 py-2 text-xs font-bold rounded-full whitespace-nowrap transition-colors ${
              selectedCategory === null
                ? 'bg-orange-500 text-zinc-950 hover:bg-orange-400'
                : 'bg-zinc-900 border border-zinc-800 text-zinc-300 hover:border-orange-500/40'
            }`}
          >
            All ({guides.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 text-xs font-semibold rounded-full whitespace-nowrap transition-colors ${
                selectedCategory === cat
                  ? 'bg-orange-500 text-zinc-950 hover:bg-orange-400'
                  : 'bg-zinc-900 border border-zinc-800 text-zinc-300 hover:border-orange-500/40'
              }`}
            >
              {cat} ({byCategory[cat]?.length || 0})
            </button>
          ))}
        </div>
      </div>

      {/* Guide cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {filteredGuides.map((guide) => (
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
    </>
  );
}
