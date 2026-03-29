import type { Product } from "../lib/products";

const config = {
  hot: { label: "🔥 Hot Pick", className: "bg-orange-500 text-white" },
  "top-rated": { label: "⭐ Top Rated", className: "bg-amber-500 text-white" },
  "best-seller": { label: "# Best Seller", className: "bg-emerald-600 text-white" },
};

export default function Badge({ badge }: { badge: Product["badge"] }) {
  if (!badge) return null;
  const { label, className } = config[badge];
  return (
    <span className={`absolute top-2.5 left-2.5 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide ${className}`}>
      {label}
    </span>
  );
}
