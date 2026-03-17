"use client";
import { useState, useRef, useEffect } from "react";

interface ProductImageProps {
  src: string;
  alt: string;
  fallback: React.ReactNode;
  className?: string;
  loading?: "lazy" | "eager";
}

export default function ProductImage({ src, alt, fallback, className, loading }: ProductImageProps) {
  const [status, setStatus] = useState<"loading" | "ok" | "failed">("loading");
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    // Reset every time src changes so stale ok/failed state doesn't bleed through
    setStatus("loading");
    const img = imgRef.current;
    if (!img) return;

    // Handle hot-cache hits where the browser has already decoded the image
    // Only trust complete + non-zero naturalWidth to avoid mid-decode false negatives
    if (img.complete && img.naturalWidth > 0 && img.naturalHeight > 0) {
      setStatus("ok");
    }
    // All other cases (loading, error, tracking pixel) handled by onLoad / onError
  }, [src]);

  if (status === "failed" || !src) {
    return <>{fallback}</>;
  }

  return (
    <>
      {status === "loading" && (
        <div className="absolute inset-0 animate-pulse bg-zinc-100" />
      )}
      <img
        ref={imgRef}
        src={src}
        alt={alt}
        loading={loading}
        className={className}
        style={status === "loading" ? { opacity: 0 } : undefined}
        onError={() => setStatus("failed")}
        onLoad={(e) => {
          const img = e.currentTarget;
          if (img.naturalWidth <= 10 || img.naturalHeight <= 10) {
            setStatus("failed");
          } else {
            setStatus("ok");
          }
        }}
      />
    </>
  );
}
