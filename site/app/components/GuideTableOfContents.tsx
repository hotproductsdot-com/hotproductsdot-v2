interface Section {
  heading: string;
  id: string;
}

interface TOCProps {
  sections: Section[];
}

export default function GuideTableOfContents({ sections }: TOCProps) {
  if (sections.length < 3) return null;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-10 sticky top-20 max-h-96 overflow-y-auto">
      <h3 className="text-sm font-bold text-white mb-4 uppercase tracking-widest">In This Guide</h3>
      <nav className="space-y-2">
        {sections.map((section) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="block text-xs text-zinc-400 hover:text-orange-400 transition-colors truncate"
          >
            {section.heading}
          </a>
        ))}
      </nav>
    </div>
  );
}
