/**
 * Blue intensity along 0–100 (percentile or Wyscout-style index).
 * Weaker / more muted at low values, stronger toward primary cyan at high values.
 */
export function leagueScaleBlue(
  value: number | null | undefined,
  kind: "bar" | "text" = "text",
): string {
  if (value == null || Number.isNaN(value)) {
    return kind === "bar" ? "var(--color-surface-mid)" : "var(--color-on-surface-variant)";
  }
  const t = Math.max(0, Math.min(1, value / 100));
  const hue = 197;
  if (kind === "bar") {
    const sat = 16 + t * 62;
    const light = 21 + t * 42;
    return `hsl(${hue} ${sat}% ${light}%)`;
  }
  const sat = 18 + t * 58;
  const light = 46 + t * 26;
  return `hsl(${hue} ${sat}% ${light}%)`;
}

/** Average spoke colour for radar fill/stroke. */
export function averageLeagueScaleBlue(
  values: Array<number | null | undefined>,
  kind: "bar" | "text" = "text",
): string {
  const nums = values.filter((x): x is number => x != null && !Number.isNaN(x));
  if (nums.length === 0) {
    return kind === "bar" ? "var(--color-surface-mid)" : "var(--color-primary)";
  }
  const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
  return leagueScaleBlue(avg, kind);
}
