"use client";

import dynamic from "next/dynamic";
import * as React from "react";

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
}

export function SquadValueHistoryChart({ rows, height = 360 }: Props) {
  const sans = plotlySansFontFamily();
  const sorted = React.useMemo(
    () => [...rows].sort((a, b) => a.season - b.season),
    [rows],
  );
  const x = sorted.map((r) => seasonLabel(r.season));

  const data = React.useMemo(
    () => [
      {
        type: "bar" as const,
        name: "Total xTV",
        x,
        y: sorted.map((r) => r.total_xtv_eur),
        marker: { color: "#14d1ff", opacity: 0.85 },
        yaxis: "y",
        hovertemplate: "<b>%{x}</b><br>Total xTV: %{y:,.0f} €<extra></extra>",
      },
      {
        type: "scatter" as const,
        mode: "lines+markers" as const,
        name: "Avg player value",
        x,
        y: sorted.map((r) => r.avg_market_value_eur),
        line: { color: "#e879f9", width: 2, dash: "dot" as const },
        marker: { size: 7, color: "#e879f9" },
        yaxis: "y",
        hovertemplate: "<b>%{x}</b><br>Avg MV: %{y:,.0f} €<extra></extra>",
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
        hovertemplate: "<b>%{x}</b><br>Avg age: %{y:.1f}<extra></extra>",
      },
    ],
    [x, sorted],
  );

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
      barmode: "group" as const,
      xaxis: {
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
      legend: { orientation: "h" as const, x: 0, y: 1.12 },
    }),
    [height, sans],
  );

  return (
    <div className="w-full">
      <Plot
        data={data}
        layout={layout}
        config={PLOTLY_APP_CONFIG}
        style={{ width: "100%" }}
        useResizeHandler
      />
      <div className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-content-muted">
        <div>Bars: total squad xTV</div>
        <div>Dotted: avg player value</div>
        <div>Line: avg age (right axis)</div>
      </div>
      <div className="sr-only">
        {sorted.map((r) => (
          <span key={r.season}>
            {seasonLabel(r.season)}: total xTV {fmtEurCompact(r.total_xtv_eur)}, avg MV{" "}
            {fmtEurCompact(r.avg_market_value_eur)}, avg age{" "}
            {r.avg_age?.toFixed(1) ?? "—"}.
          </span>
        ))}
      </div>
    </div>
  );
}
