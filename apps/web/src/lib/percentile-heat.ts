/**
 * League-percentile heat scale (red → yellow → green), same basis as legacy-style
 * percentile bars in this app (hue 0–128 on poor→strong).
 */
export function percentileHeatColor(
  percentile: number | null | undefined,
  kind: "bar" | "text" = "text",
): string {
  if (percentile == null || Number.isNaN(percentile)) {
    return kind === "bar" ? "hsl(220 12% 38%)" : "var(--color-on-surface-variant)";
  }
  const p = Math.max(0, Math.min(100, percentile));
  const hue = (p / 100) * 128;
  if (kind === "bar") {
    return `hsl(${hue} 58% 42%)`;
  }
  return `hsl(${hue} 72% 58%)`;
}

/** Average percentile for aggregate fills (e.g. radar polygon). */
export function averagePercentileHeatColor(
  percentiles: Array<number | null | undefined>,
  kind: "bar" | "text" = "text",
): string {
  const nums = percentiles.filter((x): x is number => x != null && !Number.isNaN(x));
  if (nums.length === 0) return "var(--color-primary)";
  const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
  return percentileHeatColor(avg, kind);
}

/**
 * Ordered lists (e.g. top 20): rank 1 → 100p, last → ~72p so colours stay in strong green/yellow band.
 */
export function rankToHeatPercentile(rank: number, listSize: number): number {
  if (listSize <= 1) return 100;
  const r = Math.max(1, Math.min(rank, listSize));
  const lo = 72;
  return lo + ((100 - lo) * (listSize - r)) / (listSize - 1);
}
