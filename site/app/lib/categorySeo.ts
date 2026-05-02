/**
 * Per-category SEO overrides for /best/[slug] money pages.
 *
 * Generic titles like "Best Kitchen for 2026" don't match how people search.
 * Real queries: "best kitchen gadgets amazon", "best gaming pc under $2000".
 * Each entry below is tuned for actual high-intent commercial keywords.
 *
 * Falls back to a sensible generic for any slug not in this table.
 */

export interface CategorySeo {
  /** <title> + og:title — what shows in Google SERP */
  title: string;
  /** meta description — first impression in SERP, drives CTR */
  description: string;
  /** H1 on the page itself — can differ slightly from <title> */
  h1: string;
  /** Hero subhead that anchors the article */
  intro: string;
}

const SEO_BY_SLUG: Record<string, CategorySeo> = {
  kitchen: {
    title: "Best Amazon Kitchen Gadgets for 2026 — Tested & Reviewed",
    description:
      "The kitchen gadgets, blenders, air fryers, and cookware Amazon shoppers actually keep. Top picks with verified reviews, real prices, and honest verdicts.",
    h1: "Best Amazon Kitchen Gadgets for 2026",
    intro:
      "We pulled the highest-rated, most-bought kitchen products on Amazon and ranked the ones that actually earn their counter space. No filler — just what works.",
  },
  "gaming-pcs": {
    title: "Best Gaming PCs on Amazon 2026 — Pre-Built Picks Under $5,000",
    description:
      "The pre-built gaming PCs serious players are buying on Amazon. RTX 50-series rigs, mid-range workhorses, and budget contenders ranked by real-world performance.",
    h1: "Best Gaming PCs on Amazon for 2026",
    intro:
      "Pre-built gaming desktops cut the headache of parts-picking and warranties. We ranked the strongest options on Amazon by performance per dollar.",
  },
  laptops: {
    title: "Best Laptops on Amazon 2026 — MacBooks, Gaming, Ultrabooks",
    description:
      "The laptops worth buying on Amazon this year — for students, creators, gamers, and professionals. MacBook Pro to Chromebook, ranked.",
    h1: "Best Laptops on Amazon for 2026",
    intro:
      "Cutting through the spec-sheet noise: here are the laptops that actually deliver on what they promise, ranked by buyer satisfaction.",
  },
  "smart-home": {
    title: "Best Smart Home Devices on Amazon 2026 — Renter-Friendly Picks",
    description:
      "Smart locks, plugs, cameras, lights, and thermostats Amazon shoppers swear by. Ranked picks — no install required for most.",
    h1: "Best Smart Home Devices on Amazon for 2026",
    intro:
      "The smart home category is half hype, half hidden gems. Here are the devices that actually make daily life easier, ranked.",
  },
  fitness: {
    title: "Best Home Gym Equipment on Amazon 2026 — Reviewed",
    description:
      "Home gym equipment, dumbbells, rowers, treadmills, and recovery tools Amazon shoppers love. Ranked picks for every space and budget.",
    h1: "Best Home Gym Equipment on Amazon for 2026",
    intro:
      "Build your home gym without the guesswork. We ranked the strongest-reviewed fitness gear on Amazon for serious training and gentle starts alike.",
  },
  beauty: {
    title: "Best Beauty Products on Amazon 2026 — Skincare, Hair, Makeup",
    description:
      "The beauty products Amazon shoppers re-buy. Serums, moisturizers, makeup, and tools ranked by verified reviews.",
    h1: "Best Beauty Products on Amazon for 2026",
    intro:
      "Skincare, makeup, and hair tools that earned their five-star ratings. Ranked picks for routines that actually deliver.",
  },
  "luxury-beauty": {
    title: "Best Luxury Beauty on Amazon 2026 — Premium Skincare & Makeup",
    description:
      "Luxury skincare, anti-aging, and makeup on Amazon. Premium picks ranked by real-world results and verified reviews.",
    h1: "Best Luxury Beauty on Amazon for 2026",
    intro:
      "When budget isn't the constraint, results are. The luxury beauty picks below earned the spend across thousands of verified Amazon reviews.",
  },
  photography: {
    title: "Best Photography Gear on Amazon 2026 — Cameras, Lenses, Lighting",
    description:
      "Mirrorless cameras, lenses, lighting, and tripods Amazon-rated for working creators. Ranked by real reviews.",
    h1: "Best Photography Gear on Amazon for 2026",
    intro:
      "From content creators to commercial shoots — here's the photography gear Amazon buyers say is worth the spend.",
  },
  audio: {
    title: "Best Headphones & Audio on Amazon 2026 — Earbuds, Soundbars",
    description:
      "Wireless earbuds, noise-cancelling headphones, soundbars, and speakers Amazon shoppers stand by. Ranked picks.",
    h1: "Best Headphones & Audio on Amazon for 2026",
    intro:
      "Sound quality, noise cancellation, battery life — we weighted what listeners actually rate, then ranked the picks.",
  },
  drones: {
    title: "Best Drones on Amazon 2026 — DJI, Beginner & Pro Picks",
    description:
      "DJI Mavic, Mini, FPV — the drones Amazon shoppers actually fly. Ranked beginner-to-pro picks with real-flight reviews.",
    h1: "Best Drones on Amazon for 2026",
    intro:
      "Drone tech moves fast and most listings exaggerate. Here are the drones Amazon buyers actually keep flying — ranked.",
  },
  wearables: {
    title: "Best Smartwatches & Fitness Trackers on Amazon 2026",
    description:
      "Apple Watch, Garmin, Fitbit, Whoop — the smartwatches Amazon buyers re-up. Ranked picks for fitness, sleep, and health.",
    h1: "Best Smartwatches on Amazon for 2026",
    intro:
      "Wearables only earn wrist-time if they actually help. We ranked the smartwatches and trackers Amazon buyers keep wearing.",
  },
  "power-tools": {
    title: "Best Power Tools on Amazon 2026 — DeWalt, Milwaukee, Makita",
    description:
      "DeWalt, Milwaukee, Makita, Ryobi — the power tools Amazon buyers and pros stand behind. Ranked by reviews and real use.",
    h1: "Best Power Tools on Amazon for 2026",
    intro:
      "Pro-grade and weekend-DIY picks ranked by buyer reviews. Skip the marketing copy — these are the cordless drills, drivers, and saws that earn their bay.",
  },
  furniture: {
    title: "Best Amazon Furniture 2026 — Sofas, Desks, Bookshelves",
    description:
      "Stylish, affordable Amazon furniture for any room. Sofas, desks, bookshelves, and dining sets ranked by buyer satisfaction.",
    h1: "Best Amazon Furniture for 2026",
    intro:
      "Furniture from Amazon is hit-or-miss until you know where to look. Here are the picks that buyers actually love after assembly.",
  },
  headphones: {
    title: "Best Headphones on Amazon 2026 — Over-Ear, In-Ear, Noise-Cancelling",
    description:
      "Over-ear, in-ear, noise-cancelling — the headphones Amazon buyers swear by. Ranked picks for music, calls, and travel.",
    h1: "Best Headphones on Amazon for 2026",
    intro:
      "Whether it's music, work calls, or flights — here are the headphones Amazon buyers consistently rate worth the money.",
  },
  tablets: {
    title: "Best Tablets on Amazon 2026 — iPad, Galaxy Tab, Fire",
    description:
      "iPad, Galaxy Tab, Fire HD, and more — the tablets Amazon buyers actually keep using. Ranked by use case and budget.",
    h1: "Best Tablets on Amazon for 2026",
    intro:
      "From work to play to kids' learning — the tablet picks below earn their daily use, according to thousands of Amazon reviews.",
  },
};

const FALLBACK = (categoryName: string): CategorySeo => ({
  title: `Best ${categoryName} on Amazon for 2026 — Tested & Reviewed`,
  description: `The top-rated ${categoryName.toLowerCase()} on Amazon, ranked by verified buyer reviews and real-world value.`,
  h1: `Best ${categoryName} on Amazon for 2026`,
  intro: `We ranked the most-bought, highest-rated ${categoryName.toLowerCase()} on Amazon. Honest picks — no filler.`,
});

export function getCategorySeo(slug: string, categoryName: string): CategorySeo {
  return SEO_BY_SLUG[slug] ?? FALLBACK(categoryName);
}
