"use client";

import dynamic from "next/dynamic";
import * as React from "react";

import { OverlayCard, TRANSPARENT_HOVERLABEL, useOverlayHoverByCurve } from "@/components/charts/hover-overlay";
import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export interface ScatterPoint {
  wyscout_id?: number | null;
  player: string;
  club?: string | null;
  league?: string | null;
  position?: string | null;
  age?: number | null;
  minutes?: number | null;
  x: number | null;
  y: number | null;
  size?: number | null;
  player_image_url?: string | null;
}

/** Non-highlighted points when user picks specific players. */
const NEUTRAL_DOT = "#5c6d82";

/** Mix league colour toward this so non–top performers stay low-luminance. */
const DIM_SURFACE = "#121a26";

function parseRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "").trim();
  if (h.length !== 6) return [94, 109, 130];
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** t = fraction of `toward` (0 = keep `from`). */
function mixHex(from: string, toward: string, t: number): string {
  const [fr, fg, fb] = parseRgb(from);
  const [tr, tg, tb] = parseRgb(toward);
  const r = Math.round(fr + (tr - fr) * t);
  const g = Math.round(fg + (tg - fg) * t);
  const b = Math.round(fb + (tb - fb) * t);
  return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

const LEAGUE_PALETTE = [
  "#14d1ff",
  "#00ff41",
  "#ffd5ae",
  "#e879f9",
  "#fb7185",
  "#38bdf8",
  "#a3e635",
  "#facc15",
  "#c084fc",
  "#2dd4bf",
  "#f97316",
  "#4ade80",
  "#818cf8",
  "#f43f5e",
  "#06b6d4",
  "#eab308",
  "#a78bfa",
  "#5eead4",
  "#f472b6",
  "#94a3b8",
];

function leagueColorMap(leagues: string[]): Map<string, string> {
  const sorted = [...new Set(leagues)].sort((a, b) => a.localeCompare(b));
  const m = new Map<string, string>();
  sorted.forEach((lg, i) => m.set(lg, LEAGUE_PALETTE[i % LEAGUE_PALETTE.length]));
  return m;
}

/** Stable row id (avoids wrong labels when two players share a name). */
function pointIdentity(p: ScatterPoint): string {
  if (p.wyscout_id != null && Number.isFinite(Number(p.wyscout_id))) {
    return `w:${Number(p.wyscout_id)}`;
  }
  const x = p.x as number;
  const y = p.y as number;
  return `xy:${p.player.trim()}:${x}:${y}`;
}

/**
 * 1-based ranks (1 = best on that axis). Higher axis value = better rank.
 * Tie-break: higher x, higher y, then stable id.
 */
function rankByMetric(valid: ScatterPoint[], key: "x" | "y"): Map<string, number> {
  const sorted = [...valid].sort((a, b) => {
    const d = (b[key] as number) - (a[key] as number);
    if (d !== 0) return d;
    const dx = (b.x as number) - (a.x as number);
    if (dx !== 0) return dx;
    const dy = (b.y as number) - (a.y as number);
    if (dy !== 0) return dy;
    return pointIdentity(a).localeCompare(pointIdentity(b));
  });
  const m = new Map<string, number>();
  sorted.forEach((p, i) => m.set(pointIdentity(p), i + 1));
  return m;
}

const AUTO_LABEL_TOP_K = 15;

/** Top k on one axis (rank 1 = best). */
function topKOnAxis(valid: ScatterPoint[], k: number, key: "x" | "y"): Set<string> {
  if (k <= 0 || valid.length === 0) return new Set();
  const rmap = rankByMetric(valid, key);
  const scored = valid.map((p) => ({ p, r: rmap.get(pointIdentity(p))! }));
  scored.sort((a, b) => a.r - b.r || pointIdentity(a.p).localeCompare(pointIdentity(b.p)));
  const out = new Set<string>();
  for (let i = 0; i < Math.min(k, scored.length); i++) {
    out.add(pointIdentity(scored[i].p));
  }
  return out;
}

/** Lowest sum of X-rank + Y-rank (strong on both axes). */
function autoLabelIdentitiesDual(valid: ScatterPoint[], k: number): Set<string> {
  if (k <= 0 || valid.length === 0) return new Set();
  const rx = rankByMetric(valid, "x");
  const ry = rankByMetric(valid, "y");
  const scored = valid.map((p) => {
    const id = pointIdentity(p);
    return { id, score: rx.get(id)! + ry.get(id)! };
  });
  scored.sort((a, b) => a.score - b.score || a.id.localeCompare(b.id));
  const out = new Set<string>();
  for (const row of scored) {
    if (out.size >= k) break;
    out.add(row.id);
  }
  return out;
}

/** Union: top k on X, top k on Y, top k dual-axis combined. */
function autoLabelIdentitiesUnion(valid: ScatterPoint[], k: number): Set<string> {
  const ax = topKOnAxis(valid, k, "x");
  const ay = topKOnAxis(valid, k, "y");
  const dual = autoLabelIdentitiesDual(valid, k);
  return new Set([...ax, ...ay, ...dual]);
}

function labelText(player: string): string {
  const s = player.trim();
  if (s.length <= 16) return s;
  return `${s.slice(0, 14)}…`;
}

function isHighlighted(
  p: ScatterPoint,
  highlightIds: Set<number>,
  highlightClubs: Set<string>,
): boolean {
  if (highlightClubs.size > 0) {
    const key = (p.club ?? p.player).trim();
    if (key && highlightClubs.has(key)) return true;
  }
  if (highlightIds.size === 0) return false;
  if (p.wyscout_id == null) return false;
  return highlightIds.has(Number(p.wyscout_id));
}

/** OLS fit y = intercept + slope * x; returns segment endpoints over x range. */
function linearRegressionSegment(
  pts: { x: number; y: number }[],
): { x1: number; x2: number; y1: number; y2: number } | null {
  if (pts.length < 2) return null;
  const n = pts.length;
  let sumX = 0;
  let sumY = 0;
  let sumXX = 0;
  let sumXY = 0;
  for (const p of pts) {
    sumX += p.x;
    sumY += p.y;
    sumXX += p.x * p.x;
    sumXY += p.x * p.y;
  }
  const denom = n * sumXX - sumX * sumX;
  if (Math.abs(denom) < 1e-12) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  const xs = pts.map((p) => p.x);
  const x1 = Math.min(...xs);
  const x2 = Math.max(...xs);
  return { x1, x2, y1: intercept + slope * x1, y2: intercept + slope * x2 };
}

interface Props {
  points: ScatterPoint[];
  xLabel: string;
  yLabel: string;
  height?: number;
  /** Emphasise these players (Wyscout ids). Others render in neutral when non-empty. */
  highlightWyscoutIds?: number[];
  /** Emphasise clubs by name (team scatters). Matches ``club`` or ``player`` label. */
  highlightClubs?: string[];
  /**
   * When true: automatic top-axis labels; only union-top points keep full league luminance,
   * others are darkened. When false: no automatic labels (only highlighted players show names).
   */
  emphasiseTop?: boolean;
  /** Draw OLS trend line through valid points (markers remain hoverable). */
  showLinearRegression?: boolean;
}

export function ScatterChart({
  points,
  xLabel,
  yLabel,
  height = 520,
  highlightWyscoutIds = [],
  highlightClubs = [],
  emphasiseTop = false,
  showLinearRegression = false,
}: Props) {
  const sans = plotlySansFontFamily();

  const highlightKey = highlightWyscoutIds.join(",");
  const highlightClubsKey = highlightClubs.join("|");

  /** Pixel offset presets for label placement (xshift, yshift). First = directly above. */
  const LABEL_SHIFT_PRESETS: ReadonlyArray<readonly [number, number]> = [
    [0, 14],
    [0, -16],
    [26, 0],
    [-26, 0],
    [22, 12],
    [-22, 12],
    [22, -14],
    [-22, -14],
  ];

  function placeLabels(
    labeled: { p: ScatterPoint; text: string }[],
    valid: ScatterPoint[],
  ): { p: ScatterPoint; text: string; xshift: number; yshift: number }[] {
    if (labeled.length === 0) return [];
    const xs = valid.map((p) => p.x as number);
    const ys = valid.map((p) => p.y as number);
    const xSpan = (Math.max(...xs) - Math.min(...xs)) || 1;
    const ySpan = (Math.max(...ys) - Math.min(...ys)) || 1;
    const xT = xSpan * 0.05;
    const yT = ySpan * 0.05;
    const placed: { x: number; y: number; slot: number }[] = [];
    return labeled.map(({ p, text }) => {
      const x = p.x as number;
      const y = p.y as number;
      const taken = new Set<number>();
      for (const u of placed) {
        if (Math.abs(u.x - x) < xT && Math.abs(u.y - y) < yT) taken.add(u.slot);
      }
      let slot = 0;
      for (let s = 0; s < LABEL_SHIFT_PRESETS.length; s++) {
        if (!taken.has(s)) { slot = s; break; }
      }
      placed.push({ x, y, slot });
      const [xshift, yshift] = LABEL_SHIFT_PRESETS[slot];
      return { p, text, xshift, yshift };
    });
  }

  const { data, labelAnnotations, valid, leagueColors } = React.useMemo(() => {
    const valid = points.filter((p) => p.x != null && p.y != null);
    const highlightSet = new Set(
      highlightWyscoutIds.filter((id) => Number.isFinite(id)),
    );
    const highlightClubSet = new Set(
      highlightClubs.map((c) => c.trim()).filter(Boolean),
    );
    const manualHighlight = highlightSet.size > 0 || highlightClubSet.size > 0;

    const autoLabeled =
      emphasiseTop || manualHighlight
        ? autoLabelIdentitiesUnion(valid, AUTO_LABEL_TOP_K)
        : new Set<string>();

    const labeledPoints: { p: ScatterPoint; text: string }[] = [];
    const labelAllClubs = highlightClubSet.size > 0;
    for (const p of valid) {
      if (isHighlighted(p, highlightSet, highlightClubSet)) {
        labeledPoints.push({ p, text: labelText(p.player) });
        continue;
      }
      if (labelAllClubs) {
        labeledPoints.push({ p, text: labelText(p.player) });
        continue;
      }
      if (manualHighlight) continue;
      if (emphasiseTop && autoLabeled.has(pointIdentity(p))) {
        labeledPoints.push({ p, text: labelText(p.player) });
      }
    }

    const leagues = valid.map((p) => p.league ?? "—");
    const cmap = leagueColorMap(leagues);
    const colors = valid.map((p) => {
      if (manualHighlight && !isHighlighted(p, highlightSet, highlightClubSet)) {
        return NEUTRAL_DOT;
      }
      if (
        manualHighlight &&
        highlightClubSet.size > 0 &&
        isHighlighted(p, highlightSet, highlightClubSet)
      ) {
        return "#14d1ff";
      }
      const base = cmap.get(p.league ?? "—")!;
      if (!emphasiseTop) return base;
      const isTop = autoLabeled.has(pointIdentity(p));
      if (isTop) return base;
      return mixHex(base, DIM_SURFACE, 0.82);
    });

    const baseSize = 10;

    const opacities = valid.map((p) => {
      if (manualHighlight) {
        if (isHighlighted(p, highlightSet, highlightClubSet)) return 1;
        return 0.45;
      }
      if (emphasiseTop) {
        const isTop = autoLabeled.has(pointIdentity(p));
        if (isTop) return 1;
        return 0.5;
      }
      return 0.82;
    });

    const markerTrace = {
      x: valid.map((p) => p.x as number),
      y: valid.map((p) => p.y as number),
      type: (valid.length > 500 ? "scattergl" : "scatter") as "scatter" | "scattergl",
      mode: "markers" as const,
      name: "Players",
      hoverinfo: "none" as const,
      cliponaxis: true,
      marker: {
        color: colors,
        size: baseSize,
        opacity: opacities,
        line: {
          width: valid.map((p) =>
            manualHighlight && isHighlighted(p, highlightSet, highlightClubSet) ? 2 : 0,
          ),
          color: valid.map((p) =>
            isHighlighted(p, highlightSet, highlightClubSet) ? "#14d1ff" : "rgba(0,0,0,0)",
          ),
        },
      },
      showlegend: false,
    };

    const placed = placeLabels(labeledPoints, valid);
    const labelAnnotations = placed.map(({ p, text, xshift, yshift }) => ({
      x: p.x as number,
      y: p.y as number,
      text,
      xref: "x" as const,
      yref: "y" as const,
      showarrow: false,
      xshift,
      yshift,
      font: { family: sans, size: 9, color: "#d2e2f2" },
      bgcolor: "rgba(10,16,24,0.55)",
      borderpad: 1,
      align: "center" as const,
    }));

    const leagueColors = valid.map((p) => cmap.get(p.league ?? "—") ?? "#14d1ff");

    const traces: object[] = [markerTrace];
    if (showLinearRegression) {
      const seg = linearRegressionSegment(
        valid.map((p) => ({ x: p.x as number, y: p.y as number })),
      );
      if (seg) {
        traces.push({
          x: [seg.x1, seg.x2],
          y: [seg.y1, seg.y2],
          type: "scatter" as const,
          mode: "lines" as const,
          hoverinfo: "none" as const,
          cliponaxis: false,
          line: {
            color: "rgba(20,209,255,0.55)",
            width: 2,
            dash: "dot",
          },
          showlegend: false,
        });
      }
    }

    return { data: traces, labelAnnotations, valid, leagueColors };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, highlightKey, highlightClubsKey, emphasiseTop, showLinearRegression, xLabel, yLabel, sans]);

  const layout = React.useMemo(
    () => ({
      autosize: true,
      height,
      margin: { l: 56, r: 16, t: 12, b: 56 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: sans, color: "#d2e2f2", size: 12 },
      dragmode: false as const,
      hovermode: "closest" as const,
      hoverdistance: 24,
      xaxis: {
        title: { text: xLabel },
        gridcolor: "rgba(255,255,255,0.05)",
        zerolinecolor: "rgba(255,255,255,0.1)",
        fixedrange: true,
      },
      yaxis: {
        title: { text: yLabel },
        gridcolor: "rgba(255,255,255,0.05)",
        zerolinecolor: "rgba(255,255,255,0.1)",
        fixedrange: true,
      },
      showlegend: false,
      hoverlabel: TRANSPARENT_HOVERLABEL,
      annotations: labelAnnotations,
    }),
    [height, xLabel, yLabel, labelAnnotations, sans],
  );

  const resolveHover = React.useCallback(
    (curve: number, idx: number) => {
      if (curve !== 0) return null;
      const p = valid[idx];
      if (!p) return null;
      return { p, color: leagueColors[idx] ?? "#14d1ff" };
    },
    [valid, leagueColors],
  );
  const { item, state, onHover, onUnhover, onMouseMove, onInitialized, containerRef } =
    useOverlayHoverByCurve(resolveHover);

  return (
    <div ref={containerRef} className="scatter-chart-root relative w-full" onMouseMove={onMouseMove}>
      <style
        dangerouslySetInnerHTML={{
          __html: `
            .scatter-chart-root svg .scatterlayer g.text { pointer-events: none; }
          `,
        }}
      />
      <Plot
        className="scatter-chart-plot"
        data={data}
        layout={layout}
        config={PLOTLY_APP_CONFIG}
        style={{ width: "100%" }}
        useResizeHandler
        onInitialized={onInitialized}
        onHover={onHover}
        onUnhover={onUnhover}
      />
      {item && state && (
        <div
          className="pointer-events-none absolute z-50"
          style={{
            left: Math.min(state.x + 14, (containerRef.current?.clientWidth ?? 0) - 272),
            top: Math.max(state.y - 64, 4),
          }}
        >
          <OverlayCard
            data={{
              name: item.p.player,
              club: item.p.club,
              league: item.p.league,
              position: item.p.position,
              age: item.p.age,
              color: item.color,
              wyscoutId: item.p.wyscout_id ?? null,
              imageUrl: item.p.player_image_url ?? null,
              rows: [
                { label: xLabel, value: (item.p.x as number).toFixed(2) },
                { label: yLabel, value: (item.p.y as number).toFixed(2) },
                ...(item.p.minutes != null
                  ? [{ label: "Minutes", value: String(item.p.minutes) }]
                  : []),
              ],
            }}
          />
        </div>
      )}
    </div>
  );
}
