/** Wyscout pitch heatmap → density grid + KDE-style filled contours for SVG. */

import { contours as d3contours } from "d3-contour";

/** Wyscout: x length 0→100 own→opp, y width. Same mapping as PlayerPositionPitch. */
export function wyscoutToNormalizedPitch(p: { x: number; y: number }): { sx: number; sy: number } {
  return { sx: p.y, sy: 100 - p.x };
}

const GRID_W = 52;
const GRID_H = 52;
/** Inner pitch rect inside viewBox — matches SVG pitch rect x,y,w,h */
const PITCH = { x: 2, y: 2, w: 96, h: 96 };
const GAUSS_SIGMA = 2.25;
const BAND_COUNT = 8;

/** Theme primary scale (tokens in globals.css) — avoids runtime CSS reads. */
const THEME_PRIMARY = { r: 20, g: 209, b: 255 };
const THEME_ON_SURFACE = { r: 210, g: 226, b: 242 };

export interface HeatmapContourPoint {
  x: number;
  y: number;
  count: number;
}

export interface HeatmapContourInput {
  points: HeatmapContourPoint[];
  maxCount: number;
}

export interface ContourBand {
  d: string;
  fill: string;
  value: number;
}

function splatGaussian(
  grid: Float32Array,
  gx: number,
  gy: number,
  sigma: number,
  weight: number,
  w: number,
  h: number,
): void {
  const r = Math.ceil(sigma * 3);
  for (let dj = -r; dj <= r; dj++) {
    for (let di = -r; di <= r; di++) {
      const ix = Math.round(gx + di);
      const iy = Math.round(gy + dj);
      if (ix < 0 || ix >= w || iy < 0 || iy >= h) continue;
      const d2 = di * di + dj * dj;
      const g = Math.exp(-d2 / (2 * sigma * sigma)) * weight;
      grid[iy * w + ix] += g;
    }
  }
}

function buildDensityGrid(points: HeatmapContourPoint[], maxCount: number): Float32Array {
  const grid = new Float32Array(GRID_W * GRID_H);
  if (points.length === 0 || maxCount <= 0) return grid;

  for (const p of points) {
    const { sx, sy } = wyscoutToNormalizedPitch(p);
    const px = PITCH.x + (sx / 100) * PITCH.w;
    const py = PITCH.y + (sy / 100) * PITCH.h;
    const gx = ((px - PITCH.x) / PITCH.w) * (GRID_W - 1);
    const gy = ((py - PITCH.y) / PITCH.h) * (GRID_H - 1);
    const weight = Math.sqrt(Math.max(0, p.count) / maxCount);
    splatGaussian(grid, gx, gy, GAUSS_SIGMA, weight, GRID_W, GRID_H);
  }
  return grid;
}

interface ContourLevel {
  type: string;
  value: number;
  coordinates: number[][][][];
}

function multiPolygonToSvgPath(coords: number[][][][], gridW: number, gridH: number): string {
  let d = "";
  for (const polygon of coords) {
    for (const ring of polygon) {
      if (!ring?.length) continue;
      const [x0, y0] = ring[0];
      const sx0 = PITCH.x + (x0 / (gridW - 1)) * PITCH.w;
      const sy0 = PITCH.y + (y0 / (gridH - 1)) * PITCH.h;
      d += ` M ${sx0} ${sy0}`;
      for (let k = 1; k < ring.length; k++) {
        const [x, y] = ring[k];
        const sx = PITCH.x + (x / (gridW - 1)) * PITCH.w;
        const sy = PITCH.y + (y / (gridH - 1)) * PITCH.h;
        d += ` L ${sx} ${sy}`;
      }
      d += " Z";
    }
  }
  return d.trim();
}

/**
 * KDE-like filled isobands: Gaussian splat → d3 marching squares contours,
 * stacked light→saturated primary blue on the pitch.
 */
export function buildHeatmapContourBands(heatmap: HeatmapContourInput | null): ContourBand[] {
  if (!heatmap?.points.length || heatmap.maxCount <= 0) return [];

  const grid = buildDensityGrid(heatmap.points, heatmap.maxCount);
  let max = 0;
  for (let i = 0; i < grid.length; i++) max = Math.max(max, grid[i]);
  if (max <= 1e-10) return [];

  const thresholds: number[] = [];
  for (let i = 1; i <= BAND_COUNT; i++) thresholds.push((max * i) / (BAND_COUNT + 1));

  const contourGen = d3contours().size([GRID_W, GRID_H]).smooth(true).thresholds(thresholds);
  const levels = contourGen(Array.from(grid)) as ContourLevel[];

  levels.sort((a, b) => a.value - b.value);

  return levels
    .map((level, i) => {
      const t = levels.length <= 1 ? 1 : i / (levels.length - 1);
      const alpha = 0.05 + t * 0.42;
      const fill = `rgba(${THEME_PRIMARY.r}, ${THEME_PRIMARY.g}, ${THEME_PRIMARY.b}, ${alpha.toFixed(3)})`;
      const pathD = multiPolygonToSvgPath(level.coordinates, GRID_W, GRID_H);
      return { d: pathD, fill, value: level.value };
    })
    .filter((b) => b.d.length > 0);
}

export interface ScatterDot {
  cx: number;
  cy: number;
  r: number;
  opacity: number;
}

/** Scatter marks for raw Wyscout heat cells (above contour fill, below role zones). */
export function buildHeatmapScatterDots(heatmap: HeatmapContourInput | null): ScatterDot[] {
  if (!heatmap?.points.length || heatmap.maxCount <= 0) return [];
  const max = heatmap.maxCount;
  return heatmap.points.map((p) => {
    const { sx, sy } = wyscoutToNormalizedPitch(p);
    const cx = PITCH.x + (sx / 100) * PITCH.w;
    const cy = PITCH.y + (sy / 100) * PITCH.h;
    const ratio = Math.min(1, Math.max(0, p.count / max));
    const r = 0.28 + Math.sqrt(ratio) * 0.85;
    const opacity = 0.35 + ratio * 0.45;
    return { cx, cy, r, opacity };
  });
}

export function scatterDotStrokeRgb(): string {
  return `rgb(${THEME_PRIMARY.r}, ${THEME_PRIMARY.g}, ${THEME_PRIMARY.b})`;
}

export function scatterDotFillRgb(): string {
  return `rgba(${THEME_ON_SURFACE.r}, ${THEME_ON_SURFACE.g}, ${THEME_ON_SURFACE.b}, 0.22)`;
}
