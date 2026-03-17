const icons: Record<string, string> = {
  photography: "📷",
  "smart-home": "🏠",
  laptops: "💻",
  monitors: "🖥️",
  headphones: "🎧",
  speakers: "🔊",
  audio: "🎵",
  "gaming-laptops": "🎮",
  "gaming-peripherals": "🕹️",
  "gaming-headsets": "🎮",
  "gaming-desktops": "🖥️",
  drones: "🚁",
  kitchen: "🍳",
  security: "🔒",
  furniture: "🪑",
  fitness: "💪",
  tablets: "📱",
  streaming: "📺",
  home: "🏡",
  electronics: "⚡",
  "smart-displays": "🖥️",
  computers: "💻",
  "personal-care": "✨",
};

export function getCategoryIcon(slug: string): string {
  return icons[slug] ?? "📦";
}

export default function CategoryIcon({ slug, size = "2xl" }: { slug: string; size?: string }) {
  return <span className={`text-${size}`}>{getCategoryIcon(slug)}</span>;
}
