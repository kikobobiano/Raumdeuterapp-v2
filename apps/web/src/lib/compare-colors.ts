/**
 * Compare overlay chroma — keep in sync with `:root --color-compare-*` in globals.css.
 * Same order as profile comparison (primary tech-blue · pink · amber).
 */
export const COMPARE_PALETTE = ["#14d1ff", "#ff4d9d", "#ffb800"] as const;

export function comparePaletteColor(metricIndex: number): string {
  return COMPARE_PALETTE[metricIndex % COMPARE_PALETTE.length];
}
