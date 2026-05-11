"use client";

import dynamic from "next/dynamic";
import type { Layout, PlotMarker, PlotMouseEvent } from "plotly.js";
import * as React from "react";

import { OverlayCard, TRANSPARENT_HOVERLABEL, useOverlayHover } from "@/components/charts/hover-overlay";
import { comparePaletteColor } from "@/lib/compare-colors";
import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";
import { cn } from "@/lib/utils";
import { wyscoutClubLogoSrc } from "@/lib/wyscout-image";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

/** `cornerradius` is supported by Plotly bars at runtime but missing from `@types/plotly.js`. */
type RoundedBarMarker = Partial<PlotMarker> & { cornerradius?: number };

/** Mix `hex` toward black by `amount` ∈ [0, 1]. Used to derive readable inside-bar text colors. */
function darkenHex(hex: string, amount: number): string {
  const h = hex.replace("#", "");
  if (h.length !== 6) return hex;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const k = Math.max(0, Math.min(1, amount));
  const f = (n: number) => Math.round(n * (1 - k)).toString(16).padStart(2, "0");
  return `#${f(r)}${f(g)}${f(b)}`;
}

/** Muted stacked segments / logos when another player row is focused */
const MUTED_SEGMENT = "#556274";
const MUTED_SEGMENT_TEXT = "#dfe8f2";
const MUTED_LOGO_OPACITY = 0.32;

function fillForRowBarSegment(
  focusedRow: number | null,
  rowIdx: number,
  saturated: string,
): string {
  if (focusedRow == null || rowIdx === focusedRow) return saturated;
  return MUTED_SEGMENT;
}

function toggleRowFocus(prev: number | null, rowIdx: number): number | null {
  if (prev === rowIdx) return null;
  return rowIdx;
}

/** Short axis labels free horizontal margin so bars span ~90% of the plot width; overlay keeps full name. */
function compactBarYAxisLabel(rank: number, player: string, maxChars = 26): string {
  const s = `${rank}. ${player}`;
  if (s.length <= maxChars) return s;
  return `${s.slice(0, Math.max(8, maxChars - 1))}…`;
}

interface Row {
  rank: number;
  player: string;
  wyscout_id?: number | null;
  player_image_url?: string | null;
  club?: string | null;
  league?: string | null;
  position?: string | null;
  age?: number | null;
  minutes?: number | null;
  club_logo?: string | null;
  values: Record<string, number | null>;
}

interface Props {
  rows: Row[];
  metrics: string[];
  labels: Record<string, string>;
  /** Cohort ABS maxima from API — matches combined rank denominator. */
  metricMaxAbs?: Record<string, number> | null;
  height?: number;
}

function fmtMetricValue(v: number | null | undefined): string {
  if (v == null || (typeof v === "number" && v !== v)) return "—";
  const a = Math.abs(v);
  if (a >= 100) return v.toFixed(1);
  if (a >= 10) return v.toFixed(2);
  return v.toFixed(3);
}

/** Max |value| per metric across rows — used to scale segments to a common 0–1 band. */
function maxPerMetric(ordered: Row[], metrics: string[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const m of metrics) {
    let maxV = 0;
    for (const r of ordered) {
      const v = r.values[m];
      if (v != null && v === v) maxV = Math.max(maxV, Math.abs(v));
    }
    out[m] = maxV > 0 ? maxV : 1e-9;
  }
  return out;
}

/**
 * Horizontal stacked bar — one bar per player; each segment is the first metric (cyan),
 * second (pink), third (amber), matching profile comparison palette.
 * Segment width = |value| / chart max for that metric so units are comparable on the axis.
 */
export function HorizontalBarRanking({
  rows,
  metrics,
  labels,
  metricMaxAbs,
  height,
}: Props) {
  const sans = plotlySansFontFamily();
  const ordered = [...rows].reverse();

  const [focusedRowIndex, setFocusedRowIndex] = React.useState<number | null>(null);

  const rowSig = React.useMemo(
    () =>
      [...rows]
        .reverse()
        .map((r) => String(r.wyscout_id ?? r.rank))
        .join(","),
    [rows],
  );

  React.useEffect(() => {
    setFocusedRowIndex(null);
  }, [rowSig, metrics.join("|")]);

  const safeFocusedRow = React.useMemo((): number | null => {
    if (focusedRowIndex == null) return null;
    if (focusedRowIndex < 0 || focusedRowIndex >= ordered.length) return null;
    return focusedRowIndex;
  }, [focusedRowIndex, ordered.length]);

  React.useEffect(() => {
    if (safeFocusedRow == null) return;
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setFocusedRowIndex(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [safeFocusedRow]);

  const yLabels = ordered.map((r) => compactBarYAxisLabel(r.rank, r.player));

  const maxByMetric = React.useMemo(() => {
    if (metricMaxAbs != null && Object.keys(metricMaxAbs).length > 0) {
      const out: Record<string, number> = {};
      for (const m of metrics) {
        const v = metricMaxAbs[m];
        out[m] = typeof v === "number" && v > 0 && v === v ? v : 1e-9;
      }
      return out;
    }
    return maxPerMetric(rows, metrics);
  }, [metricMaxAbs, metrics, rows]);

  const stackedEnd = ordered.map((r) =>
    metrics.reduce((sum, m) => {
      const v = r.values[m];
      if (v == null || v !== v) return sum;
      return sum + Math.abs(v) / maxByMetric[m]!;
    }, 0),
  );

  const xDomainMax = Math.max(...stackedEnd, 1e-6);
  const logoOffset = xDomainMax * 0.03 || 0.02;
  const logoExtentX =
    xDomainMax > 0 ? Math.max(xDomainMax * 0.055, 0.06) : 0.5;

  const xMaxIncludingLogos = Math.max(
    xDomainMax,
    ...ordered.map((r, idx) => {
      if (!r.club_logo?.trim()) return stackedEnd[idx]!;
      return stackedEnd[idx]! + logoOffset + logoExtentX;
    }),
  );
  /** Pad X so rightmost club crest (x-ref + width) stays inside subplot. */
  const xPlotUpper = Math.max(xMaxIncludingLogos * 1.06, xDomainMax * 1.02);

  const data = metrics.map((m, metricIdx) => {
    const baseColor = comparePaletteColor(metricIdx);
    const fills = ordered.map((_, rowIdx) =>
      fillForRowBarSegment(safeFocusedRow, rowIdx, baseColor),
    );
    const insideTextColors = ordered.map((_, rowIdx) =>
      fillForRowBarSegment(safeFocusedRow, rowIdx, baseColor) === MUTED_SEGMENT
        ? MUTED_SEGMENT_TEXT
        : darkenHex(baseColor, 0.78),
    );
    const marker: RoundedBarMarker = {
      color: fills,
      line: { width: 0, color: fills },
      cornerradius: 6,
    };
    return {
      type: "bar" as const,
      orientation: "h" as const,
      name: labels[m] ?? m,
      y: yLabels,
      x: ordered.map((r) => {
        const v = r.values[m];
        if (v == null || v !== v) return 0;
        return Math.abs(v) / maxByMetric[m]!;
      }),
      text: ordered.map((r) => fmtMetricValue(r.values[m])),
      textposition: "inside" as const,
      insidetextanchor: "middle" as const,
      constraintext: "inside" as const,
      cliponaxis: false,
      textfont: {
        color: insideTextColors,
        size: 11,
        family: sans,
      },
      customdata: ordered.map((r) => fmtMetricValue(r.values[m])),
      hoverinfo: "none" as const,
      marker,
    };
  });

  const layoutImages: NonNullable<Layout["images"]> = ordered
    .map((r, idx) => {
      const raw = r.club_logo?.trim();
      if (!raw) return null;
      const x = stackedEnd[idx]! + logoOffset;
      const logoMuted =
        safeFocusedRow != null && idx !== safeFocusedRow ? MUTED_LOGO_OPACITY : 1;
      return {
        source: wyscoutClubLogoSrc(raw),
        xref: "x" as const,
        yref: "y" as const,
        x,
        y: yLabels[idx],
        xanchor: "left" as const,
        yanchor: "middle" as const,
        sizex: logoExtentX,
        sizey: 0.7,
        sizing: "contain" as const,
        layer: "above" as const,
        opacity: logoMuted,
      };
    })
    .filter((v): v is NonNullable<typeof v> => v !== null);

  const totalHeight = height ?? Math.max(420, rows.length * 28 + 80);

  const plotAreaRef = React.useRef<HTMLDivElement | null>(null);
  const [plotMargins, setPlotMargins] = React.useState({ l: 208, r: 68 });

  React.useLayoutEffect(() => {
    const el = plotAreaRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      if (w < 260) return;
      const r = Math.round(Math.min(92, Math.max(52, w * 0.036)));
      const l = Math.round(Math.min(248, Math.max(160, w * 0.074)));
      setPlotMargins((p) => (p.l === l && p.r === r ? p : { l, r }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { item, state, onInitialized: onHoverInitialized, containerRef } =
    useOverlayHover(ordered);

  const onPlotClick = React.useCallback((ev: Readonly<PlotMouseEvent>) => {
    const p = ev.points?.[0];
    if (!p || p.curveNumber == null || p.pointIndex == null) return;
    const xv = p.x;
    if (typeof xv === "number" && xv <= 0) return;
    setFocusedRowIndex((prev) => toggleRowFocus(prev, p.pointIndex));
  }, []);

  return (
    <div
      ref={plotAreaRef}
      className="mx-auto flex w-[90%] max-w-full min-w-0 flex-col gap-4"
    >
      <div
        role="toolbar"
        aria-label="Metric legend"
        className="flex flex-wrap items-center justify-end gap-2.5 sm:justify-center"
      >
        {metrics.map((m, i) => (
          <div
            key={m}
            className={cn(
              "flex max-w-[min(100%,20rem)] items-center gap-2 rounded-full px-4 py-2",
              "border border-outline-variant/40 bg-surface-high/65 text-on-surface shadow-sm",
              "backdrop-blur-sm",
            )}
          >
            <span
              className="h-3 w-3 shrink-0 rounded-sm ring-2 ring-black/25"
              style={{
                backgroundColor: comparePaletteColor(i),
                boxShadow: `inset 0 0 0 1px ${comparePaletteColor(i)}`,
              }}
            />
            <span className="truncate text-xs font-semibold leading-snug tracking-tight">
              {labels[m] ?? m}
            </span>
          </div>
        ))}
      </div>

      <div ref={containerRef} className="relative w-full min-w-0">
        <Plot
          data={data}
          layout={{
            autosize: true,
            height: totalHeight,
            barmode: "stack",
            bargap: 0.22,
            margin: { l: plotMargins.l, r: plotMargins.r, t: 12, b: 64 },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: { family: sans, color: "#d2e2f2", size: 12 },
            dragmode: false,
            xaxis: {
              range: [0, xPlotUpper] as [number, number],
              fixedrange: true,
              showticklabels: true,
              showgrid: true,
              gridcolor: "rgba(255,255,255,0.05)",
              zeroline: false,
              showline: false,
              ticks: "outside",
              tickcolor: "rgba(255,255,255,0.12)",
              ticklen: 4,
              tick0: 0,
              dtick: 1,
              tickfont: { size: 10, color: "#7e8fa5" },
              title: {
                text: "Combined normalized score · 1.0 = cohort max per metric",
                standoff: 10,
                font: { size: 10, color: "#b2c4d8" },
              },
            },
            yaxis: {
              automargin: false,
              tickfont: { size: 11 },
              fixedrange: true,
              /** Breathing room between label and bars. */
              ticksuffix: "\u00a0\u00a0\u00a0\u00a0",
            },
            showlegend: false,
            hoverlabel: TRANSPARENT_HOVERLABEL,
            images: layoutImages,
          }}
          config={PLOTLY_APP_CONFIG}
          style={{ width: "100%" }}
          useResizeHandler
          onInitialized={onHoverInitialized}
          onClick={onPlotClick}
        />
        {item && state && (
          <div
            className="pointer-events-none absolute z-50"
            style={{
              left: Math.min(state.x + 14, (containerRef.current?.clientWidth ?? 0) - 252),
              top: Math.max(state.y - 64, 4),
            }}
          >
            <OverlayCard
              data={{
                name: item.player,
                club: item.club,
                league: item.league,
                position: item.position,
                age: item.age,
                clubLogoUrl: item.club_logo,
                imageUrl: item.player_image_url,
                wyscoutId: item.wyscout_id,
                value: item.minutes != null ? `${item.minutes}'` : undefined,
                color: comparePaletteColor(0),
                rows: metrics.map((m) => ({
                  label: labels[m] ?? m,
                  value: fmtMetricValue(item.values[m]),
                })),
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
