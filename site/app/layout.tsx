import type { Metadata } from "next";
import "./globals.css";
import Header from "./components/Header";
import Footer from "./components/Footer";
import AffiliateDisclosure from "./components/AffiliateDisclosure";
import { SITE_NAME, SITE_URL } from "./lib/constants";

export const metadata: Metadata = {
  title: { default: `${SITE_NAME} — Top Amazon Picks`, template: `%s | ${SITE_NAME}` },
  description:
    "Discover the best-selling, top-rated products on Amazon. Curated picks with real reviews across electronics, smart home, laptops, photography, and more.",
  metadataBase: new URL(SITE_URL),
  robots: { index: true, follow: true },
  openGraph: {
    siteName: SITE_NAME,
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    site: "@hotproductsdot",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <Header />
        {/* FTC-required disclosure — must appear before any affiliate content */}
        <AffiliateDisclosure variant="banner" />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
