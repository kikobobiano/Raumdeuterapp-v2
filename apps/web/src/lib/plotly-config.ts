import type { Config } from "plotly.js";

/**
 * Default Plotly ``config`` for in-app charts: no wheel zoom, no double-click
 * autosize reset, logo off (mode bar usually off via ``displayModeBar``).
 */
export const PLOTLY_APP_CONFIG: Partial<Config> = {
  responsive: true,
  displaylogo: false,
  displayModeBar: false,
  scrollZoom: false,
  doubleClick: false,
};
