"use client";

import dynamic from "next/dynamic";
import * as React from "react";

import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const PALETTE = [
  "#14d1ff", "#00ff41", "#ffd5ae", "#e879f9", "#fb7185",
  "#a3e635", "#facc15", "#c084fc", "#2dd4bf", "#f97316",
  "#4ade80", "#818cf8",
];

interface PlayerRow {
  player: string;
  values: Record<string, number | null>;
}

interface Props {
  metrics: string[];
  labels: Record<string, string>;
  players: PlayerRow[];
  height?: number;
}

export function StackedBarChart({ metrics, labels, players, height = 480 }: Props) {
  const sans = plotlySansFontFamily();
  const data = React.useMemo(
    () =>
      metrics.map((m, i) => ({
        x: players.map((p) => p.player),
        y: players.map((p) => p.values[m] ?? 0),
        type: "bar" as const,
        name: labels[m] ?? m,
        marker: { color: PALETTE[i % PALETTE.length] },
        hovertemplate: `<b>%{x}</b><br>${labels[m] ?? m}: %{y:.2f}<extra></extra>`,
      })),
    [metrics, labels, players],
  );

  return (
    <Plot
      data={data}
      layout={{
        autosize: true,
        height,
        barmode: "stack",
        margin: { l: 56, r: 16, t: 24, b: 80 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: sans, color: "#d2e2f2", size: 12 },
        dragmode: false,
        xaxis: {
          tickangle: -25,
          gridcolor: "rgba(255,255,255,0.05)",
          fixedrange: true,
        },
        yaxis: {
          gridcolor: "rgba(255,255,255,0.05)",
          zerolinecolor: "rgba(255,255,255,0.1)",
          fixedrange: true,
        },
        showlegend: true,
        legend: {
          orientation: "h",
          y: -0.28,
          font: { size: 11, family: sans },
          bgcolor: "transparent",
        },
        hoverlabel: {
          bgcolor: "#16202e",
          bordercolor: "#374557",
          font: { color: "#d2e2f2", family: sans },
        },
      }}
      config={PLOTLY_APP_CONFIG}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
