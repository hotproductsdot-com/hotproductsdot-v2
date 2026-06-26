import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Affiliate Disclaimer",
  description:
    "HotProducts affiliate disclosure and disclaimer. We are an Amazon Associate and earn from qualifying purchases.",
  robots: { index: true, follow: true },
};

export default function DisclaimerPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-14">
      <nav className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span>/</span>
        <span className="text-zinc-400">Disclaimer</span>
      </nav>

      <h1 className="text-3xl font-bold text-white mb-2">Affiliate Disclaimer</h1>
      <p className="text-zinc-500 text-sm mb-10">Last updated: March 2026</p>

      <div className="prose prose-invert prose-zinc max-w-none space-y-8 text-zinc-300 text-sm leading-relaxed">

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Amazon Associates Disclosure</h2>
          <p>
            HotProducts (<strong className="text-zinc-200">hotproducts.online</strong>) is a participant in the{" "}
            <strong className="text-zinc-200">Amazon Services LLC Associates Program</strong>, an affiliate advertising
            program designed to provide a means for sites to earn advertising fees by advertising and linking to
            Amazon.com.
          </p>
          <p className="mt-3">
            <strong className="text-zinc-200">As an Amazon Associate I earn from qualifying purchases.</strong> This
            means that when you click on certain links on this site and make a purchase, we may receive a small
            commission — at no additional cost to you.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">How Affiliate Links Work</h2>
          <p>
            When you click a &ldquo;View Deal&rdquo; or &ldquo;Check Price on Amazon&rdquo; button on this site, you
            are redirected to Amazon.com. If you complete a qualifying purchase within the Amazon session cookie
            window, we earn a small referral fee. The price you pay is never affected by our commission.
          </p>
          <p className="mt-3">
            Our affiliate tag is embedded in the link URL (e.g., <code className="text-orange-400">tag=hotproduct033-20</code>).
            Amazon tracks purchases attributed to our tag and pays us a commission according to their{" "}
            <a href="https://affiliate-program.amazon.com/help/node/topic/GRXPHT8U84RAYDXZ" target="_blank" rel="noopener noreferrer nofollow" className="text-orange-400 hover:text-orange-300 underline">
              standard commission schedule
            </a>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Editorial Independence</h2>
          <p>
            Our product recommendations are based on publicly available data including Amazon bestseller rankings,
            customer ratings, and review counts. We are not paid by manufacturers or sellers to feature specific
            products. The affiliate commission structure may influence which categories we cover (we tend to focus
            on categories with higher commission rates), but individual product selections are based on objective
            performance data.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Pricing Disclaimer</h2>
          <p>
            We do not display specific prices on this site. Amazon prices change frequently, and displaying
            outdated prices would be misleading. Always check the current price on Amazon before making a
            purchase decision.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">FTC Compliance</h2>
          <p>
            This disclosure is provided in accordance with the{" "}
            <strong className="text-zinc-200">Federal Trade Commission&apos;s 16 CFR Part 255</strong>: Guides
            Concerning the Use of Endorsements and Testimonials in Advertising. We are committed to
            transparency about our affiliate relationships.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Contact</h2>
          <p>
            If you have questions about our affiliate relationships or this disclaimer, please review our{" "}
            <Link href="/privacy" className="text-orange-400 hover:text-orange-300 underline">Privacy Policy</Link> or
            contact us through the site.
          </p>
        </section>
      </div>
    </div>
  );
}
