export interface Guide {
  slug: string;
  title: string;
  description: string;
  category: string;
  categorySlug: string;
  publishedAt?: string;
  sections: {
    heading: string;
    body: string;
    productSlugs?: string[];
  }[];
}

export const guides: Guide[] = [
  {
    slug: "best-laptops",
    title: "Best Laptops Buying Guide",
    description:
      "Everything you need to know before buying a laptop — from ultrabooks to gaming powerhouses.",
    category: "Laptops",
    categorySlug: "laptops",
    sections: [
      {
        heading: "What to Look For",
        body: "The right laptop depends on your use case. Casual users prioritise battery life and portability; creative professionals need colour-accurate displays and fast CPUs; gamers require a dedicated GPU. Settle on your primary use case before comparing specs.",
      },
      {
        heading: "Key Specs Explained",
        body: "Processor: Apple M4 and Intel Core Ultra chips lead in performance-per-watt. RAM: 16 GB is the comfortable minimum in 2026 — 32 GB if you run VMs or creative apps. Storage: 512 GB SSD minimum; NVMe drives are significantly faster than SATA. Display: look for at least 1080p; OLED panels offer better contrast and colour than IPS.",
      },
      {
        heading: "Our Top Picks",
        body: "We rank laptops by a combination of performance, build quality, battery life, and value. The MacBook Air M4 leads for portability and battery. The Dell XPS 15 is our pick for Windows power users. Gaming laptops from ASUS ROG and Razer Blade offer the best GPU performance.",
        productSlugs: ["apple-macbook-air-13-m4", "dell-xps-15-laptop", "asus-rog-strix-g16-gaming-laptop"],
      },
      {
        heading: "Budget vs Premium",
        body: "Budget laptops (under $600) work fine for web browsing and documents but often compromise on display quality and build materials. Mid-range ($600–$1,200) is the sweet spot for most users. Premium ($1,200+) buys thinner chassis, better displays, and longer support cycles.",
      },
    ],
  },
  {
    slug: "best-smart-home-devices",
    title: "Best Smart Home Devices Buying Guide",
    description:
      "Build a smarter home without the headaches — our guide to choosing compatible, reliable smart home gear.",
    category: "Smart Home",
    categorySlug: "smart-home",
    sections: [
      {
        heading: "Choosing an Ecosystem",
        body: "Before buying any smart home device, pick an ecosystem: Amazon Alexa, Google Home, or Apple HomeKit. Mixing ecosystems creates friction. Alexa has the widest device compatibility; HomeKit offers the strongest privacy controls; Google Home integrates best with Android and Google services.",
      },
      {
        heading: "Start With the Essentials",
        body: "A smart speaker or display acts as your hub. The Amazon Echo Show 10 is ideal for Alexa households — it has a screen, rotates to follow you, and acts as a Zigbee hub for compatible bulbs and sensors. For Google users, Nest Hub Max fills the same role.",
        productSlugs: ["amazon-echo-show-10-4th-gen"],
      },
      {
        heading: "Security Cameras",
        body: "Look for cameras with local storage options to avoid ongoing subscription costs. Resolution of 2K or higher is now standard. Key features: person detection, two-way audio, and weather resistance (IP65+) for outdoor units. Arlo and Eufy lead on image quality; Aqara integrates best with HomeKit.",
        productSlugs: ["arlo-ultra-2-plus", "aqara-camera-hub-g5-pro"],
      },
      {
        heading: "Avoid Common Mistakes",
        body: "Don't buy devices that only work over Wi-Fi if you have a large home — Zigbee and Z-Wave mesh protocols are more reliable. Check that any device works with your chosen voice assistant before purchasing. Prioritise brands with long firmware support histories.",
      },
    ],
  },
  {
    slug: "best-photography-gear",
    title: "Best Photography Gear Buying Guide",
    description:
      "Cameras, lenses, and accessories for every skill level — from first camera to professional kit.",
    category: "Photography",
    categorySlug: "photography",
    sections: [
      {
        heading: "Mirrorless vs DSLR",
        body: "Mirrorless cameras have largely replaced DSLRs for new purchases. They offer faster autofocus, better video capability, and lighter bodies with no optical viewfinder mirror. DSLRs still have advantages in battery life and lens catalogue depth for Canon/Nikon shooters already invested in the system.",
      },
      {
        heading: "Sensor Size Matters",
        body: "Full-frame sensors (35mm) capture more light and produce shallower depth of field — ideal for portraits and low-light work. APS-C sensors are smaller, cheaper, and offer a crop factor useful for wildlife and sports photography. Micro Four Thirds is a compact system with an excellent lens ecosystem.",
      },
      {
        heading: "Top Camera Picks",
        body: "The Sony A7R V is our full-frame recommendation for resolution-hungry shooters. The Canon EOS R5 excels at both stills and video. For APS-C, the Fujifilm X-T5 punches well above its price with superb image quality and film simulations.",
        productSlugs: ["sony-a7r-v-camera", "canon-eos-r5-camera", "nikon-z9-camera"],
      },
      {
        heading: "Don't Neglect the Lens",
        body: "A great lens on an average body will outperform a great body with a cheap lens. Budget at least 50% of your total camera spend on lenses. Prime lenses (fixed focal length) are sharper and faster than zooms at the same price point. A 50mm f/1.8 is an excellent first prime for any system.",
      },
    ],
  },
  {
    slug: "best-kitchen-gadgets",
    title: "Best Kitchen Gadgets Buying Guide",
    description:
      "The tools that actually earn their counter space — our curated picks for home cooks at every level.",
    category: "Kitchen",
    categorySlug: "kitchen",
    sections: [
      {
        heading: "The Foundation",
        body: "Before buying specialty gadgets, get the basics right: a good chef's knife, a heavy cutting board, and a reliable instant-read thermometer. These three items will improve your cooking more than any appliance.",
        productSlugs: ["alpha-grillers-meat-thermometer-digital-instant-read-food-thermometer-for-cooking-grilling-professional-kitchen-gift-for-men-dad-mom"],
      },
      {
        heading: "Instant-Read Thermometers",
        body: "A good instant-read thermometer removes guesswork from cooking meat, bread, and candy. Look for a response time under 3 seconds, a range of at least -58°F to 572°F, and waterproofing. The Alpha Grillers thermometer is a top-rated option that delivers professional accuracy at an accessible price.",
      },
      {
        heading: "High-Impact Appliances",
        body: "If you're buying one appliance, make it a good blender or a cast iron pan — both last decades. An air fryer earns its place for anyone who cooks proteins frequently. A stand mixer is worth the investment if you bake more than twice a month. Avoid unitaskers that solve problems you don't have.",
      },
      {
        heading: "Buying Tips",
        body: "Read the one-star reviews before buying any kitchen gadget — they reveal real failure modes. Check that replacement parts (gaskets, blades, carafes) are available. Prefer products with at least 1,000 reviews over newer alternatives with fewer. Kitchen gear is one category where established brands consistently outperform no-name alternatives.",
      },
    ],
  },
  {
    slug: "best-water-bottles",
    title: "Best Water Bottles & Tumblers Buying Guide",
    description:
      "Insulated bottles, tumblers, and flasks — find the right one for your lifestyle.",
    category: "Kitchen",
    categorySlug: "kitchen",
    sections: [
      {
        heading: "Insulated vs Non-Insulated",
        body: "Double-wall vacuum insulation keeps drinks cold for 24 hours and hot for 12. If you primarily drink cold water, any quality stainless steel bottle works. For hot drinks on the go, insulation is essential. Avoid plastic for hot drinks — even BPA-free plastics can leach at high temperatures.",
      },
      {
        heading: "Top Picks",
        body: "The Stanley Quencher H2.0 dominates the tumbler category with its handle, straw, and generous capacity — ideal for all-day hydration. The Owala FreeSip offers a clever dual-use lid that lets you sip or chug without removing the lid, making it excellent for active use.",
        productSlugs: [
          "stanley-quencher-h2-0-tumbler-with-handle-and-straw-30-oz-flowstate-3-position-lid-cup-holder-compatible-for-travel-insulated-stainless-steel-cup-bpa-free-rose-quartz-2-0",
          "owala-freesip-insulated-stainless-steel-water-bottle-with-straw-bpa-free-sports-water-bottle-great-for-travel-24-oz-denim",
        ],
      },
      {
        heading: "What Size?",
        body: "20–24 oz is right for most handbag or backpack side pockets. 30–40 oz suits desk or car cup holder use. Anything larger is awkward to carry but fine for the gym. Wide-mouth openings are easier to clean and accept ice cubes; narrow mouths are better for drinking while moving.",
      },
      {
        heading: "Care & Longevity",
        body: "Hand wash insulated bottles — dishwashers can compromise the vacuum seal over time. Replace lids and straws every 6–12 months as they harbour bacteria. A bottle brush is essential for wide-mouth bottles. Avoid leaving acidic drinks like citrus juice in stainless steel for extended periods.",
      },
    ],
  },
];

// ─── growth-engine: load JSON guides from site/content/guides-generated/ ───
// These files are written by the Python growth-engine. They use the same
// Guide schema and are merged with the inline `guides` array above. The
// merge prefers inline guides on slug collision so editorial overrides win.
import fs from "fs";
import path from "path";

function loadGeneratedGuides(): Guide[] {
  // When Next.js runs from inside site/, process.cwd() is site/.
  const candidates = [
    path.join(process.cwd(), "content", "guides-generated"),
    path.join(process.cwd(), "..", "site", "content", "guides-generated"),
    path.join(process.cwd(), "site", "content", "guides-generated"),
  ];
  const target = candidates.find((p) => {
    try {
      return fs.existsSync(p) && fs.statSync(p).isDirectory();
    } catch {
      return false;
    }
  });
  if (!target) return [];
  const files = fs.readdirSync(target).filter((f) => f.endsWith(".json"));
  const out: Guide[] = [];
  for (const file of files) {
    try {
      const raw = fs.readFileSync(path.join(target, file), "utf8");
      const obj = JSON.parse(raw);
      if (
        typeof obj?.slug === "string" &&
        typeof obj?.title === "string" &&
        Array.isArray(obj?.sections)
      ) {
        out.push(obj as Guide);
      }
    } catch {
      // skip malformed
    }
  }
  return out;
}

// Generated guides come from many independent growth-engine runs and drift in
// casing ("kitchen" vs "Kitchen"). Derive one canonical display name per
// categorySlug so the guides page never shows duplicate category chips.
function titleCaseFromSlug(slug: string): string {
  return slug
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function normalizeCategory(guide: Guide): Guide {
  if (!guide.categorySlug) return guide;
  return { ...guide, category: titleCaseFromSlug(guide.categorySlug) };
}

const generatedGuides: Guide[] = loadGeneratedGuides();
const inlineSlugs = new Set(guides.map((g) => g.slug));
const mergedGuides: Guide[] = [
  ...guides,
  ...generatedGuides.filter((g) => !inlineSlugs.has(g.slug)),
].map(normalizeCategory);

export function getAllGuides(): Guide[] {
  return mergedGuides;
}

export function getGuideBySlug(slug: string): Guide | undefined {
  return mergedGuides.find((g) => g.slug === slug);
}

