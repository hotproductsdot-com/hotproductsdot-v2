"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAnalytics, clearAnalytics, type AnalyticsData, type DailyCount } from "../lib/analytics";

const EMPTY: AnalyticsData = {
  totalClicks: 0,
  clicksToday: 0,
  clicksThisWeek: 0,
  clicksThisMonth: 0,
  topProducts: [],
  byCategory: [],
  dailyTrend: [],
  totalViews: 0,
  ctr: 0,
  estimatedEarnings: 0,
};

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="text-[10px] text-zinc-500 uppercase tracking-widest mb-2">{label}</div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {sub && <div className="text-[11px] text-zinc-600 mt-1">{sub}</div>}
    </div>
  );
}

function TrendChart({ data }: { data: DailyCount[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  const chartH = 80;
  const barW = 12;
  const gap = 4;
  const totalW = data.length * (barW + gap);

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${totalW} ${chartH + 20}`}
        style={{ width: "100%", minWidth: totalW, height: chartH + 20 }}
      >
        {data.map((d, i) => {
          const barH = d.count > 0 ? Math.max((d.count / max) * chartH, 3) : 0;
          const x = i * (barW + gap);
          const y = chartH - barH;
          const showLabel = i === 0 || i === 14 || i === data.length - 1;
          return (
            <g key={d.date}>
              <rect
                x={x}
                y={d.count > 0 ? y : chartH}
                width={barW}
                height={barH}
                rx={2}
                fill={d.count > 0 ? "#f97316" : "#27272a"}
              />
              {showLabel && (
                <text
                  x={x + barW / 2}
                  y={chartH + 14}
                  textAnchor="middle"
                  fontSize={8}
                  fill="#52525b"
                >
                  {d.date.slice(5)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<AnalyticsData>(EMPTY);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setData(getAnalytics());
    setLoaded(true);
  }, []);

  function handleClear() {
    if (window.confirm("Clear all tracking data? This cannot be undone.")) {
      clearAnalytics();
      setData({ ...EMPTY });
    }
  }

  function handleRefresh() {
    setData(getAnalytics());
  }

  const maxCategoryClicks = Math.max(...data.byCategory.map((c) => c.clicks), 1);
  const isEmpty = loaded && data.totalClicks === 0 && data.totalViews === 0;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Performance Dashboard</h1>
          <p className="text-zinc-500 text-sm mt-1">
            Affiliate click tracking — stored locally in your browser
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleRefresh}
            className="text-sm border border-zinc-700 text-zinc-300 px-4 py-2 rounded-lg hover:border-zinc-500 transition-colors"
          >
            Refresh
          </button>
          <button
            onClick={handleClear}
            className="text-sm border border-red-900/60 text-red-400 px-4 py-2 rounded-lg hover:border-red-700 transition-colors"
          >
            Clear Data
          </button>
        </div>
      </div>

      {/* Empty state */}
      {isEmpty && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-12 text-center">
          <div className="text-5xl mb-4">📊</div>
          <div className="text-zinc-200 font-semibold text-lg">No data yet</div>
          <p className="text-zinc-500 text-sm mt-2 max-w-sm mx-auto">
            Browse products and click &ldquo;Buy on Amazon&rdquo; to start tracking affiliate clicks.
          </p>
          <Link
            href="/products"
            className="inline-block mt-6 bg-orange-500 hover:bg-orange-600 text-white font-semibold px-5 py-2 rounded-xl transition-colors text-sm"
          >
            Browse Products →
          </Link>
        </div>
      )}

      {loaded && !isEmpty && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard label="Total Clicks" value={data.totalClicks.toLocaleString()} />
            <StatCard label="Today" value={data.clicksToday.toLocaleString()} />
            <StatCard label="This Week" value={data.clicksThisWeek.toLocaleString()} />
            <StatCard label="This Month" value={data.clicksThisMonth.toLocaleString()} />
            <StatCard
              label="CTR"
              value={data.totalViews > 0 ? `${(data.ctr * 100).toFixed(1)}%` : "—"}
              sub={`${data.totalClicks}c / ${data.totalViews}v`}
            />
            <StatCard
              label="Est. Earnings"
              value={`$${data.estimatedEarnings.toFixed(2)}`}
              sub="3% comm × 2% CVR"
            />
          </div>

          {/* 30-day trend */}
          {data.dailyTrend.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-zinc-300 mb-4">30-Day Click Trend</h2>
              <TrendChart data={data.dailyTrend} />
            </div>
          )}

          {/* Top products + category breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top products */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-zinc-300 mb-4">Top Products by Clicks</h2>
              {data.topProducts.length === 0 ? (
                <p className="text-zinc-600 text-sm">No clicks yet</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-zinc-600 text-xs border-b border-zinc-800">
                      <th className="pb-2 font-medium">Product</th>
                      <th className="pb-2 font-medium text-right">Clicks</th>
                      <th className="pb-2 font-medium text-right">Est. $</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.topProducts.map((p) => (
                      <tr key={p.slug} className="border-b border-zinc-800/50 last:border-0">
                        <td className="py-2 pr-3">
                          <Link
                            href={`/products/${p.slug}`}
                            className="text-zinc-200 hover:text-orange-400 transition-colors line-clamp-1 block"
                          >
                            {p.name}
                          </Link>
                          <span className="text-zinc-600 text-xs">{p.category}</span>
                        </td>
                        <td className="py-2 text-right text-orange-400 font-bold">{p.clicks}</td>
                        <td className="py-2 text-right text-zinc-400">
                          ${p.estimatedEarnings.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Category breakdown */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-zinc-300 mb-4">Clicks by Category</h2>
              {data.byCategory.length === 0 ? (
                <p className="text-zinc-600 text-sm">No clicks yet</p>
              ) : (
                <div className="space-y-3">
                  {data.byCategory.map((c) => (
                    <div key={c.category}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-zinc-300">{c.category}</span>
                        <span className="text-zinc-500">{c.clicks}</span>
                      </div>
                      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-orange-500 rounded-full transition-all duration-300"
                          style={{ width: `${(c.clicks / maxCategoryClicks) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Benchmarks */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zinc-300 mb-4">Benchmarks</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 text-sm">
              {[
                {
                  label: "Link CTR target",
                  benchmark: "3–10%",
                  current: data.totalViews > 0 ? `${(data.ctr * 100).toFixed(1)}%` : null,
                  good: data.ctr >= 0.03,
                },
                { label: "Affiliate CVR", benchmark: "1–5%", current: null, good: null },
                { label: "Commission rate", benchmark: "~3% avg", current: null, good: null },
                { label: "RPM target", benchmark: "$5–$25", current: null, good: null },
              ].map((b) => (
                <div key={b.label} className="space-y-1">
                  <div className="text-zinc-600 text-xs uppercase tracking-wide">{b.label}</div>
                  <div className="text-zinc-400">{b.benchmark}</div>
                  {b.current !== null && (
                    <div className={`font-semibold ${b.good ? "text-green-400" : "text-orange-400"}`}>
                      You: {b.current}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Note */}
          <p className="text-xs text-zinc-700 text-center">
            Data is stored in your browser&apos;s localStorage. Clearing browser data or switching browsers resets tracking.
            Last {Math.min(5000, data.totalClicks + data.totalViews).toLocaleString()} events retained.
          </p>
        </>
      )}
    </div>
  );
}
