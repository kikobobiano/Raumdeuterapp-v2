"use client";

import dynamic from "next/dynamic";
import * as React from "react";

import {
  OverlayCard,
  type OverlayCardData,
  TRANSPARENT_HOVERLABEL,
  useOverlayHoverByCurve,
} from "@/components/charts/hover-overlay";
import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export interface SquadHistoryRow {
  season: number;
  total_xtv_eur: number | null;
  avg_xtv_eur: number | null;
  total_market_value_eur: number | null;
  avg_market_value_eur: number | null;
  avg_age: number | null;
}

function seasonLabel(year: number): string {
  return `${String(year).slice(2)}-${String(year + 1).slice(2)}`;
}

function fmtEurCompact(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  if (n >= 1e9) return `€${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) {
    const m = n / 1e6;
    return m >= 10 ? `€${m.toFixed(0)}M` : `€${m.toFixed(1)}M`;
  }
  if (n >= 1e3) return `€${(n / 1e3).toFixed(0)}k`;
  return `€${Math.round(n)}`;
}

interface Props {
  rows: SquadHistoryRow[];
  height?: number;
  /** When false, bars show total TM squad value instead of xTV. */
  showXtv?: boolean;
}

export function SquadValueHistoryChart({ rows, height = 360, showXtv = true }: Props) {
  const sans = plotlySansFontFamily();
  const sorted = React.useMemo(
    () => [...rows].sort((a, b) => a.season - b.season),
    [rows],
  );
  const x = sorted.map((r) => seasonLabel(r.season));

  const barLabel = showXtv ? "Total xTV" : "Total squad value (TM)";
  const barValues = sorted.map((r) =>
    showXtv ? r.total_xtv_eur : r.total_market_value_eur,
  );

  const data = React.useMemo(
    () => [
      {
        type: "bar" as const,
        name: barLabel,
        x,
        y: barValues,
        marker: { color: "#14d1ff", opacity: 0.85 },
        yaxis: "y",
        hoverinfo: "none" as const,
      },
      {
        type: "scatter" as const,
        mode: "lines+markers" as const,
        name: "Avg age",
        x,
        y: sorted.map((r) => r.avg_age),
        line: { color: "#ffd5ae", width: 2 },
        marker: { size: 7, color: "#ffd5ae" },
        yaxis: "y2",
        hoverinfo: "none" as const,
      },
    ],
    [x, sorted, barLabel, barValues],
  );

  const resolveHover = React.useCallback(
    (_curve: number, idx: number): OverlayCardData | null => {
      const r = sorted[idx];
      if (!r) return null;
      const valueRow = showXtv
        ? { label: "Total xTV", value: fmtEurCompact(r.total_xtv_eur) }
        : {
            label: "Total squad value (TM)",
            value: fmtEurCompact(r.total_market_value_eur),
          };
      return {
        name: seasonLabel(r.season),
        color: "#14d1ff",
        rows: [
          valueRow,
          {
            label: "Avg age",
            value: r.avg_age != null ? r.avg_age.toFixed(1) : "—",
          },
        ],
      };
    },
    [sorted, showXtv],
  );

  const { item, state, onHover, onUnhover, onMouseMove, onInitialized, containerRef } =
    useOverlayHoverByCurve(resolveHover);

  const layout = React.useMemo(
    () => ({
      autosize: true,
      height,
      margin: { l: 64, r: 64, t: 24, b: 48 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: sans, color: "#d2e2f2", size: 12 },
      dragmode: false as const,
      hovermode: "x unified" as const,
      showlegend: false,
      hoverlabel: TRANSPARENT_HOVERLABEL,
      xaxis: {
        type: "category" as const,
        categoryorder: "array" as const,
        categoryarray: x,
        title: { text: "Season" },
        gridcolor: "rgba(255,255,255,0.05)",
        fixedrange: true,
      },
      yaxis: {
        title: { text: "EUR" },
        gridcolor: "rgba(255,255,255,0.05)",
        zerolinecolor: "rgba(255,255,255,0.1)",
        fixedrange: true,
        tickformat: ".2s",
      },
      yaxis2: {
        title: { text: "Avg age" },
        overlaying: "y" as const,
        side: "right" as const,
        gridcolor: "rgba(0,0,0,0)",
        fixedrange: true,
        rangemode: "tozero" as const,
      },
    }),
    [height, sans, x],
  );

  return (
    <div ref={containerRef} className="relative w-full" onMouseMove={onMouseMove}>
      <Plot
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
          <OverlayCard data={item} />
        </div>
      )}
      <div className="sr-only">
        {sorted.map((r) => (
          <span key={r.season}>
            {seasonLabel(r.season)}:{" "}
            {showXtv
              ? `total xTV ${fmtEurCompact(r.total_xtv_eur)}`
              : `total TM value ${fmtEurCompact(r.total_market_value_eur)}`}
            , avg age {r.avg_age?.toFixed(1) ?? "—"}.
          </span>
        ))}
      </div>
    </div>
  );
}
