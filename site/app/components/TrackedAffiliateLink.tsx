"use client";

import { trackClick } from "../lib/analytics";

interface TrackedAffiliateLinkProps {
  href: string;
  slug: string;
  name: string;
  category: string;
  campaign: string;
  priceMin: number;
  className?: string;
  children: React.ReactNode;
}

export default function TrackedAffiliateLink({
  href,
  slug,
  name,
  category,
  campaign,
  priceMin,
  className,
  children,
}: TrackedAffiliateLinkProps) {
  function handleClick() {
    trackClick({ slug, name, category, campaign, priceMin });
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer nofollow sponsored"
      data-affiliate="true"
      className={className}
      onClick={handleClick}
    >
      {children}
    </a>
  );
}
