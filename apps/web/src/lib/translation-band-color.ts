/**
 * Performance / game-area indices on scout player profile — 0–100 scale.
 * Bounds: (>85]; (70–85]; (55–70]; (35–55]; (≤35).
 */
export function scoutProfileIndexColor(
  value: number | null | undefined,
  kind: "text" | "bar" = "text",
): string {
  if (value == null || Number.isNaN(value)) {
    return kind === "bar" ? "rgba(165,133,133,0.35)" : "var(--color-on-surface-variant)";
  }
  const v = Math.max(0, Math.min(100, value));
  if (v > 85) return "#57C1EA";
  if (v > 70) return "#7DBB8B";
  if (v > 55) return "#4D7F93";
  if (v > 35) return "#BAA994";
  return "#A58585";
}

/**
 * Discrete bands for PI-style 0–100 values (and league percentiles on the same scale).
 * Matches `donut_color` in `apps/api/app/core/team_strength.py` (translation plot markers).
 */
export function translationBandColor(
  value: number | null | undefined,
  kind: "text" | "bar" = "text",
): string {
  if (value == null || Number.isNaN(value)) {
    return kind === "bar" ? "hsl(220 12% 38%)" : "var(--color-on-surface-variant)";
  }
  const v = Math.max(0, Math.min(100, value));
  if (v < 40) return "#DC0C00";
  if (v < 55) return "#ED7E07";
  if (v < 65) return "#D9AF00";
  if (v < 80) return "#00C424";
  if (v < 90) return "#00ADC4";
  return "#374DF5";
}

/** Average band colour for fills (e.g. radar polygon). */
export function averageTranslationBandColor(
  values: Array<number | null | undefined>,
  kind: "text" | "bar" = "text",
): string {
  const nums = values.filter((x): x is number => x != null && !Number.isNaN(x));
  if (nums.length === 0) {
    return kind === "bar" ? "hsl(220 12% 38%)" : "var(--color-primary)";
  }
  const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
  return translationBandColor(avg, kind);
}
