import type { Metadata } from "next";
import "./globals.css";
import Header from "./components/Header";
import Footer from "./components/Footer";

export const metadata: Metadata = {
  title: { default: "HotProducts — Top Amazon Picks", template: "%s | HotProducts" },
  description: "Discover the best-selling, top-rated products on Amazon. Curated picks with real reviews and the best prices.",
  metadataBase: new URL("https://hotproducts.dot"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
