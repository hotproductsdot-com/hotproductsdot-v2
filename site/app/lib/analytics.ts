const CLICKS_KEY = "hp_clicks";
const VIEWS_KEY = "hp_views";
const MAX_EVENTS = 5000;

export interface ClickEvent {
  ts: number;
  slug: string;
  name: string;
  category: string;
  campaign: string;
  priceMin: number;
}

export interface PageViewEvent {
  ts: number;
  path: string;
}

export interface DailyCount {
  date: string; // YYYY-MM-DD
  count: number;
}

export interface TopProduct {
  slug: string;
  name: string;
  category: string;
  clicks: number;
  estimatedEarnings: number;
}

export interface AnalyticsData {
  totalClicks: number;
  clicksToday: number;
  clicksThisWeek: number;
  clicksThisMonth: number;
  topProducts: TopProduct[];
  byCategory: Array<{ category: string; clicks: number }>;
  dailyTrend: DailyCount[];
  totalViews: number;
  ctr: number;
  estimatedEarnings: number;
}

function safeGetItem(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSetItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage full or unavailable — silently ignore
  }
}

function loadClicks(): ClickEvent[] {
  const raw = safeGetItem(CLICKS_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as ClickEvent[];
  } catch {
    return [];
  }
}

function loadViews(): PageViewEvent[] {
  const raw = safeGetItem(VIEWS_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as PageViewEvent[];
  } catch {
    return [];
  }
}

export function trackClick(event: Omit<ClickEvent, "ts">): void {
  const clicks = loadClicks();
  const updated = [...clicks, { ...event, ts: Date.now() }].slice(-MAX_EVENTS);
  safeSetItem(CLICKS_KEY, JSON.stringify(updated));
}

export function trackPageView(path: string): void {
  const views = loadViews();
  const updated = [...views, { ts: Date.now(), path }].slice(-MAX_EVENTS);
  safeSetItem(VIEWS_KEY, JSON.stringify(updated));
}

function toDateStr(ts: number): string {
  return new Date(ts).toISOString().slice(0, 10);
}

function startOfDay(date: Date): number {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

// Amazon avg commission ~3%, typical affiliate conversion rate ~2%
const COMMISSION_RATE = 0.03;
const CONVERSION_RATE = 0.02;

export function getAnalytics(): AnalyticsData {
  const clicks = loadClicks();
  const views = loadViews();

  const todayStart = startOfDay(new Date());
  const weekStart = todayStart - 6 * 86_400_000;
  const monthStart = todayStart - 29 * 86_400_000;

  const clicksToday = clicks.filter((c) => c.ts >= todayStart).length;
  const clicksThisWeek = clicks.filter((c) => c.ts >= weekStart).length;
  const clicksThisMonth = clicks.filter((c) => c.ts >= monthStart).length;

  // Aggregate by product
  const productMap = new Map<string, { name: string; category: string; clicks: number; totalPrice: number }>();
  for (const c of clicks) {
    const existing = productMap.get(c.slug);
    if (existing) {
      existing.clicks++;
      existing.totalPrice += c.priceMin;
    } else {
      productMap.set(c.slug, { name: c.name, category: c.category, clicks: 1, totalPrice: c.priceMin });
    }
  }

  const topProducts: TopProduct[] = Array.from(productMap.entries())
    .map(([slug, d]) => ({
      slug,
      name: d.name,
      category: d.category,
      clicks: d.clicks,
      estimatedEarnings: (d.totalPrice / d.clicks) * d.clicks * COMMISSION_RATE * CONVERSION_RATE,
    }))
    .sort((a, b) => b.clicks - a.clicks)
    .slice(0, 10);

  // Aggregate by category
  const categoryMap = new Map<string, number>();
  for (const c of clicks) {
    categoryMap.set(c.category, (categoryMap.get(c.category) ?? 0) + 1);
  }
  const byCategory = Array.from(categoryMap.entries())
    .map(([category, count]) => ({ category, clicks: count }))
    .sort((a, b) => b.clicks - a.clicks);

  // Daily trend — last 30 days
  const dailyMap = new Map<string, number>();
  for (let i = 0; i < 30; i++) {
    const d = new Date(todayStart - i * 86_400_000);
    dailyMap.set(toDateStr(d.getTime()), 0);
  }
  for (const c of clicks) {
    if (c.ts >= monthStart) {
      const key = toDateStr(c.ts);
      if (dailyMap.has(key)) {
        dailyMap.set(key, (dailyMap.get(key) ?? 0) + 1);
      }
    }
  }
  const dailyTrend: DailyCount[] = Array.from(dailyMap.entries())
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const totalViews = views.length;
  const ctr = totalViews > 0 ? clicks.length / totalViews : 0;
  const estimatedEarnings = topProducts.reduce((sum, p) => sum + p.estimatedEarnings, 0);

  return {
    totalClicks: clicks.length,
    clicksToday,
    clicksThisWeek,
    clicksThisMonth,
    topProducts,
    byCategory,
    dailyTrend,
    totalViews,
    ctr,
    estimatedEarnings,
  };
}

export function clearAnalytics(): void {
  try {
    localStorage.removeItem(CLICKS_KEY);
    localStorage.removeItem(VIEWS_KEY);
  } catch {
    // ignore
  }
}
