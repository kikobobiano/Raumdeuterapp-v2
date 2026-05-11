"use client";

import dynamic from "next/dynamic";
import * as React from "react";

import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface LeagueDistribution {
  league: string;
  mean: number | null;
  std: number | null;
  p10: number | null;
  p50: number | null;
  p90: number | null;
}

interface Props {
  source: LeagueDistribution & { value: number };
  targets: Array<LeagueDistribution & { projected: number | null }>;
  height?: number;
}

/** Range plot per league: p10–p90 band, median dot, source/projected marker. */
export function LeaguePIDistribution({ source, targets, height = 360 }: Props) {
  const sans = plotlySansFontFamily();
  const all = [source, ...targets];
  const labels = all.map((d) => d.league);

  const bandLow = all.map((d) => d.p10 ?? null);
  const bandHigh = all.map((d) => d.p90 ?? null);
  const median = all.map((d) => d.p50 ?? null);
  const projection = all.map((_, i) =>
    i === 0 ? source.value : targets[i - 1]?.projected ?? null,
  );
  const colors = all.map((_, i) => (i === 0 ? "#14d1ff" : "#00ff41"));

  return (
    <Plot
      data={[
        {
          type: "scatter" as const,
          mode: "lines" as const,
          name: "p10–p90",
          x: labels.flatMap((l) => [l, l]),
          y: labels.flatMap((_, i) => [bandLow[i], bandHigh[i]]),
          line: { color: "rgba(178,196,216,0.45)", width: 14 },
          hoverinfo: "skip" as const,
          showlegend: false,
          connectgaps: false,
        },
        {
          type: "scatter" as const,
          mode: "markers" as const,
          name: "Median",
          x: labels,
          y: median,
          marker: { color: "#b2c4d8", size: 8, symbol: "line-ew", line: { width: 2, color: "#b2c4d8" } },
          hovertemplate: "<b>%{x}</b><br>median: %{y:.1f}<extra></extra>",
        },
        {
          type: "scatter" as const,
          mode: "text+markers" as const,
          name: "Projected",
          x: labels,
          y: projection,
          marker: {
            color: colors,
            size: 14,
            symbol: "diamond",
            line: { width: 2, color: "#0a1018" },
          },
          text: projection.map((v) => (v != null ? v.toFixed(1) : "")),
          textposition: "top center" as const,
          textfont: { color: "#d2e2f2", size: 11, family: sans },
          hovertemplate: "<b>%{x}</b><br>projected: %{y:.2f}<extra></extra>",
        },
      ]}
      layout={{
        autosize: true,
        height,
        margin: { l: 56, r: 16, t: 24, b: 90 },
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
          title: { text: "Performance index" },
          range: [0, 100],
          gridcolor: "rgba(255,255,255,0.05)",
          zerolinecolor: "rgba(255,255,255,0.1)",
          fixedrange: true,
        },
        showlegend: false,
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
