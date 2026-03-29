/**
 * FTC-required affiliate disclosure component.
 * Per FTC guidelines, disclosure must be "clear and conspicuous" and appear
 * BEFORE any affiliate links on the page.
 *
 * variant="banner"  — sitewide banner rendered in layout (above all content)
 * variant="inline"  — small inline note beneath individual affiliate links
 */
export default function AffiliateDisclosure({
  variant = "banner",
}: {
  variant?: "banner" | "inline";
}) {
  if (variant === "inline") {
    return (
      <p className="text-[11px] text-zinc-600 text-center">
        As an Amazon Associate we earn from qualifying purchases. Price subject to change.
      </p>
    );
  }

  return (
    <div className="bg-amber-950/20 border-b border-amber-900/20 py-2 px-4 text-center">
      <p className="text-xs text-amber-200/60">
        <strong className="text-amber-200/80">Affiliate Disclosure:</strong>{" "}
        As an Amazon Associate I earn from qualifying purchases — at no extra cost to you.{" "}
        <a href="/disclaimer" className="underline hover:text-amber-200/80 transition-colors">
          Learn more
        </a>
      </p>
    </div>
  );
}
