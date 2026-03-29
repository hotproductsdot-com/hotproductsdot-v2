import { AFFILIATE_TAG } from "./constants";

interface UtmParams {
  campaign: string;
  content?: string;
  source?: string;
  medium?: string;
}

/**
 * Ensures an Amazon URL has the correct affiliate tag and optional UTM params.
 * UTM params allow tracking which page/position drove each click.
 */
export function buildAffiliateUrl(amazonUrl: string, utm?: UtmParams): string {
  if (!amazonUrl) return amazonUrl;
  try {
    const url = new URL(amazonUrl);
    url.searchParams.set("tag", AFFILIATE_TAG);
    if (utm) {
      url.searchParams.set("utm_source", utm.source ?? "hotproducts");
      url.searchParams.set("utm_medium", utm.medium ?? "website");
      url.searchParams.set("utm_campaign", utm.campaign);
      if (utm.content) url.searchParams.set("utm_content", utm.content);
    }
    return url.toString();
  } catch {
    return amazonUrl;
  }
}
