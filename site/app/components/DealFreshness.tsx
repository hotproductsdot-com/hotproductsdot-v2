"use client";

import { useEffect, useState } from "react";

/**
 * Client-side "date added" freshness tag for limited-time deals.
 *
 * The homepage is a static export, so the build-time `getLimitedTimeDeals`
 * filter freezes whatever batch was current at build. This badge recomputes
 * the deal's age in the visitor's browser from `dealDateTs`, so revisitors
 * always see an honest, self-correcting label ("Added today" / "Yesterday" /
 * "Added 2d ago") regardless of when the page was last rebuilt.
 *
 * Renders nothing until mounted to avoid a hydration mismatch (server has no
 * stable "now").
 */
export default function DealFreshness({ dealDateTs }: { dealDateTs?: number }) {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    if (!dealDateTs || dealDateTs <= 0) return;
    const startOfDay = (ts: number) => {
      const d = new Date(ts);
      d.setHours(0, 0, 0, 0);
      return d.getTime();
    };
    const days = Math.round(
      (startOfDay(Date.now()) - startOfDay(dealDateTs)) / 86_400_000,
    );
    if (days <= 0) setLabel("Added today");
    else if (days === 1) setLabel("Added yesterday");
    else setLabel(`Added ${days}d ago`);
  }, [dealDateTs]);

  if (!label) return null;

  return (
    <span className="bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full">
      🕒 {label}
    </span>
  );
}
