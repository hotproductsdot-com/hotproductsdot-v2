import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "HotProducts privacy policy — how we collect, use, and protect your information.",
  robots: { index: true, follow: true },
};

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-14">
      <nav className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span>/</span>
        <span className="text-zinc-400">Privacy Policy</span>
      </nav>

      <h1 className="text-3xl font-bold text-white mb-2">Privacy Policy</h1>
      <p className="text-zinc-500 text-sm mb-10">Last updated: March 2026</p>

      <div className="space-y-8 text-zinc-300 text-sm leading-relaxed">

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Overview</h2>
          <p>
            HotProducts (<strong className="text-zinc-200">hotproducts.online</strong>) is a static website that
            curates Amazon product recommendations. We take your privacy seriously. This policy explains what
            data is collected and how it is used.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Information We Collect</h2>
          <p>
            This site does not have a backend server, user accounts, or forms that collect personal information.
            We do not directly collect or store any personally identifiable information (PII).
          </p>
          <p className="mt-3">
            If analytics tools are configured, they may collect anonymized data such as page views, session
            duration, browser type, and approximate geographic location. This data is aggregated and not
            linked to individual users.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Third-Party Services</h2>
          <ul className="space-y-3">
            <li>
              <strong className="text-zinc-200">Amazon.com:</strong> When you click an affiliate link, you are
              redirected to Amazon. Amazon&apos;s own{" "}
              <a href="https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ" target="_blank" rel="noopener noreferrer nofollow" className="text-orange-400 hover:text-orange-300 underline">
                Privacy Notice
              </a>{" "}
              governs any data collected on their platform.
            </li>
            <li>
              <strong className="text-zinc-200">Amazon Associates Program:</strong> We participate in the Amazon
              Associates Program, which uses cookies to track purchases. See the{" "}
              <Link href="/disclaimer" className="text-orange-400 hover:text-orange-300 underline">Affiliate Disclaimer</Link>{" "}
              for details.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Cookies</h2>
          <p>
            This site itself does not set cookies. However, when you click a link to Amazon, Amazon may set
            their own cookies on your browser in accordance with their privacy policy. Third-party analytics
            tools, if used, may also set cookies to track aggregate site usage.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Your Rights</h2>
          <p>
            Since we do not collect personal information, there is generally no data to access, correct, or
            delete. If you are an EU resident (GDPR) or California resident (CCPA) and have concerns about
            data collected by third-party tools on this site, please contact us.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Changes to This Policy</h2>
          <p>
            We may update this policy from time to time. The &ldquo;Last updated&rdquo; date at the top of this
            page will reflect any changes. Continued use of the site after changes constitutes acceptance of
            the updated policy.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">Contact</h2>
          <p>
            For privacy-related questions, please contact us through the site. See also our{" "}
            <Link href="/disclaimer" className="text-orange-400 hover:text-orange-300 underline">Affiliate Disclaimer</Link>.
          </p>
        </section>
      </div>
    </div>
  );
}
