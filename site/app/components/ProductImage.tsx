"use client";
import { useState } from "react";

interface ProductImageProps {
  src: string;
  alt: string;
  className?: string;
  /** Tells the browser the image's rendered width across breakpoints. Defaults to a card-sized hint. */
  sizes?: string;
  /** Set true on the LCP image — eager + fetchpriority=high. */
  priority?: boolean;
}

const DEFAULT_SIZES = "(max-width: 640px) 45vw, 240px";
const OPT_DIR = "/products/_opt";
const WEBP_WIDTHS = [240, 480, 800] as const;
const JPG_FALLBACK_WIDTH = 480;

interface Variants {
  webpSrcSet: string;
  jpgFallback: string;
}

function deriveVariants(src: string): Variants | null {
  const match = src.match(/^\/products\/([^/]+)\.jpg(\?.*)?$/);
  if (!match) return null;
  const [, slug, query = ""] = match;
  const webpSrcSet = WEBP_WIDTHS.map(
    (w) => `${OPT_DIR}/${slug}-${w}.webp${query} ${w}w`,
  ).join(", ");
  return {
    webpSrcSet,
    jpgFallback: `${OPT_DIR}/${slug}-${JPG_FALLBACK_WIDTH}.jpg${query}`,
  };
}

export default function ProductImage({
  src,
  alt,
  className,
  sizes = DEFAULT_SIZES,
  priority = false,
}: ProductImageProps) {
  const [failed, setFailed] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);

  if (failed || !src) return null;

  const loading = priority ? "eager" : "lazy";
  const fetchPriority = priority ? "high" : "auto";
  const variants = deriveVariants(src);

  if (!variants) {
    return (
      <img
        src={src}
        alt={alt}
        className={className}
        loading={loading}
        decoding="async"
        fetchPriority={fetchPriority}
        onError={() => setFailed(true)}
      />
    );
  }

  const imgSrc = usingFallback ? src : variants.jpgFallback;

  return (
    <picture style={{ display: "contents" }}>
      {!usingFallback && (
        <source type="image/webp" srcSet={variants.webpSrcSet} sizes={sizes} />
      )}
      <img
        src={imgSrc}
        alt={alt}
        width={480}
        height={480}
        className={className}
        loading={loading}
        decoding="async"
        fetchPriority={fetchPriority}
        onError={() => {
          if (!usingFallback) {
            setUsingFallback(true);
          } else {
            setFailed(true);
          }
        }}
      />
    </picture>
  );
}
