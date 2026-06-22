export const dynamic = "force-static";

import { MetadataRoute } from "next";
import { SITE_URL } from "./lib/constants";

// Generated from SITE_URL so the sitemap reference can't drift from the
// canonical domain on a redeploy (replaces the old static public/robots.txt).
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
