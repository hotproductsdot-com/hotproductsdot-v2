"use client";
import Image from "next/image";
import { useState } from "react";

interface ProductImageProps {
  src: string;
  alt: string;
  fallback?: React.ReactNode;
  className?: string;
}

export default function ProductImage({ src, alt, className }: ProductImageProps) {
  const [prevSrc, setPrevSrc] = useState(src);
  const [status, setStatus] = useState<"loading" | "ok" | "failed">("loading");

  if (prevSrc !== src) {
    setPrevSrc(src);
    setStatus("loading");
  }

  if (status === "failed" || !src) {
    return null;
  }

  return (
    <>
      {status === "loading" && (
        <div className="absolute inset-0 animate-pulse bg-zinc-100" />
      )}
      <Image
        fill
        src={src}
        alt={alt}
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
