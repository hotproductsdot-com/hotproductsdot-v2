import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "HotProducts terms of service — the rules for using hotproductsdot.com and our social media accounts.",
  robots: { index: true, follow: true },
};

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-14">
      <nav className="flex items-center gap-2 text-xs text-zinc-500 mb-8">
        <Link href="/" className="hover:text-zinc-300">Home</Link>
        <span>/</span>
        <span className="text-zinc-400">Terms of Service</span>
      </nav>

      <h1 className="text-3xl font-bold text-white mb-2">Terms of Service</h1>
      <p className="text-zinc-500 text-sm mb-10">Last updated: April 2026</p>

      <div className="space-y-8 text-zinc-300 text-sm leading-relaxed">

        <section>
          <h2 className="text-lg font-bold text-white mb-3">1. Acceptance of Terms</h2>
          <p>
            By accessing <strong className="text-zinc-200">hotproductsdot.com</strong> (the &ldquo;Site&rdquo;) or
            interacting with content we publish on third-party platforms — including TikTok
            (<a href="https://www.tiktok.com/@hotproductsdot.of" target="_blank" rel="noopener noreferrer nofollow" className="text-orange-400 hover:text-orange-300 underline">@hotproductsdot.of</a>)
            and Instagram (<a href="https://www.instagram.com/hotproductsdot.official" target="_blank" rel="noopener noreferrer nofollow" className="text-orange-400 hover:text-orange-300 underline">@hotproductsdot.official</a>) —
            you agree to be bound by these Terms of Service. If you do not agree, please do not use the Site
            or our content.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">2. About HotProducts</h2>
          <p>
            HotProducts is a curated affiliate publisher. We research, select, and recommend products
            available through Amazon and other retailers. The Site is informational; we do not sell, ship,
            or fulfill orders. Purchases are completed on the retailer&apos;s own platform under that
            retailer&apos;s terms.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">3. Use of the Site</h2>
          <p>You agree to use the Site lawfully and respectfully. You will not:</p>
          <ul className="list-disc pl-5 mt-3 space-y-1.5">
            <li>Scrape, mirror, or republish substantial portions of the Site without written permission.</li>
            <li>Attempt to disrupt the Site, bypass technical limits, or probe for vulnerabilities.</li>
            <li>Use automated systems to interact with the Site at a rate that degrades service.</li>
            <li>Misrepresent yourself, impersonate HotProducts, or use our trademarks without permission.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">4. Social Media Posting &amp; TikTok</h2>
          <p>
            HotProducts operates official accounts on TikTok and Instagram and uses the platforms&apos;
            APIs to publish our own marketing content (product banners, captions, and links). We post
            only content we own or are licensed to use, and we comply with each platform&apos;s
            developer terms and community guidelines, including the{" "}
            <a href="https://www.tiktok.com/legal/page/global/terms-of-service/en" target="_blank" rel="noopener noreferrer nofollow" className="text-orange-400 hover:text-orange-300 underline">
              TikTok Terms of Service
            </a>{" "}
            and{" "}
            <a href="https://developers.tiktok.com/doc/tiktok-api-policy" target="_blank" rel="noopener noreferrer nofollow" className="text-orange-400 hover:text-orange-300 underline">
              TikTok Developer Policies
            </a>.
          </p>
          <p className="mt-3">
            If you interact with our content on a third-party platform, your interaction is also subject
            to that platform&apos;s own terms. We do not control how those platforms collect, use, or
            display your data.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">5. Affiliate Relationships &amp; Disclosure</h2>
          <p>
            HotProducts participates in the Amazon Associates Program and may participate in other
            affiliate programs. When you click an affiliate link and make a qualifying purchase, we may
            earn a commission at no additional cost to you. Full details are in our{" "}
            <Link href="/disclaimer" className="text-orange-400 hover:text-orange-300 underline">Affiliate Disclaimer</Link>.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">6. Intellectual Property</h2>
          <p>
            All original content on the Site — articles, banners, product write-ups, layouts, and
            branding — is owned by HotProducts or its licensors and is protected by copyright and
            trademark law. Product names, logos, and images belong to their respective owners and are
            used for editorial and identification purposes under fair use. You may not reproduce our
            original content without written permission.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">7. No Warranty</h2>
          <p>
            The Site and all content are provided &ldquo;as is&rdquo; without warranties of any kind,
            express or implied. We make a good-faith effort to keep prices, availability, specs, and
            recommendations accurate, but information changes constantly and may be out of date or
            incorrect at the time you view it. Always confirm critical details on the retailer&apos;s
            page before purchasing.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">8. Limitation of Liability</h2>
          <p>
            To the maximum extent permitted by law, HotProducts and its operators are not liable for any
            indirect, incidental, consequential, or punitive damages arising from your use of the Site or
            reliance on its content — including but not limited to lost savings, missed deals, defective
            products, or disputes with retailers. Your sole remedy is to stop using the Site.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">9. Third-Party Services</h2>
          <p>
            The Site links to third-party services (Amazon, TikTok, Instagram, and others). We are not
            responsible for the content, policies, or practices of those services. Your dealings with
            third parties are solely between you and that third party.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">10. Changes to These Terms</h2>
          <p>
            We may update these Terms from time to time. The &ldquo;Last updated&rdquo; date above will
            reflect any changes. Continued use of the Site or our social content after changes
            constitutes acceptance of the updated Terms.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">11. Governing Law</h2>
          <p>
            These Terms are governed by the laws of the United States. Any disputes will be resolved in
            the courts of the operator&apos;s jurisdiction unless otherwise required by applicable law.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-bold text-white mb-3">12. Contact</h2>
          <p>
            For questions about these Terms, please reach out through the Site. See also our{" "}
            <Link href="/privacy" className="text-orange-400 hover:text-orange-300 underline">Privacy Policy</Link> and{" "}
            <Link href="/disclaimer" className="text-orange-400 hover:text-orange-300 underline">Affiliate Disclaimer</Link>.
          </p>
        </section>
      </div>
    </div>
  );
}
