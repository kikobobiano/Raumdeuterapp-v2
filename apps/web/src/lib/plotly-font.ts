/**
 * Plotly writes SVG `font-family` literals; `"Inter"` alone often misses the
 * Next.js `next/font` stack (`--font-inter`), so exports (`Plotly.toImage`) fall
 * back to system UI while the page looks correct via CSS inheritance.
 */
export function plotlySansFontFamily(): string {
  if (typeof document === "undefined") {
    return "Inter, ui-sans-serif, system-ui, sans-serif";
  }
  const stack = getComputedStyle(document.body).fontFamily?.trim();
  return stack && stack.length > 0
    ? stack
    : "Inter, ui-sans-serif, system-ui, sans-serif";
}
