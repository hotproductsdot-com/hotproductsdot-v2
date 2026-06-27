import type { Product } from "../lib/products";
import ProductImage from "./ProductImage";

interface ComparisonProps {
  products: Product[];
  features: string[]; // e.g., ["Price", "Rating", "Features", "Best For"]
}

export default function GuideComparison({ products, features }: ComparisonProps) {
  if (products.length < 2) return null;

  return (
    <div className="overflow-x-auto border border-zinc-800 rounded-xl mb-10">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/50">
            <th className="text-left p-4 font-semibold text-white sticky left-0 bg-zinc-900/50">Product</th>
            {features.map((feature) => (
              <th key={feature} className="text-left p-4 font-semibold text-zinc-300 whitespace-nowrap">
                {feature}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {products.map((product, idx) => (
            <tr key={product.slug} className={idx % 2 === 0 ? "bg-zinc-950/30" : ""}>
              <td className="p-4 font-semibold text-zinc-100 sticky left-0 bg-inherit max-w-xs">
                <div className="flex items-center gap-3">
                  {product.imageUrl && (
                    <div className="w-12 h-12 bg-white rounded-lg flex-shrink-0 flex items-center justify-center overflow-hidden">
                      <ProductImage
                        src={product.imageUrl}
                        alt={product.name}
                        className="w-full h-full object-contain p-0.5"
                        sizes="48px"
                      />
                    </div>
                  )}
                  <span className="line-clamp-2 text-xs">{product.name}</span>
                </div>
              </td>
              <td className="p-4 text-zinc-400 whitespace-nowrap">{product.priceRange || "–"}</td>
              <td className="p-4 text-zinc-400">{product.rating}★ ({product.reviewCount.toLocaleString()})</td>
              <td className="p-4 text-zinc-400 text-xs">Best for premium quality</td>
              <td className="p-4">
                <a
                  href={product.amazonUrl}
                  target="_blank"
                  rel="noopener noreferrer nofollow sponsored"
                  data-affiliate="true"
                  className="inline-block bg-orange-500 hover:bg-orange-400 text-zinc-950 text-xs font-bold rounded px-3 py-2 transition-colors"
                >
                  Check Price
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
