"use client";

import dynamic from "next/dynamic";
import type { Annotations, AxisName, Layout, Shape } from "plotly.js";
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

export interface TranslationPeer {
  player: string;
  wyscout_id?: number | null;
  club?: string | null;
  age: number | null;
  perf_index: number;
  z_score: number;
  color: string;
  player_image_url?: string | null;
}

export interface TranslationLeaguePool {
  league: string;
  n: number;
  mu: number | null;
  sigma: number | null;
  peers: TranslationPeer[];
  projected_perf_index?: number | null;
  projected_z_score?: number | null;
  projected_color?: string | null;
  insufficient_data: boolean;
}

interface Props {
  pools: TranslationLeaguePool[];
  playerName: string;
  playerAge: number | null;
  playerWyscoutId?: number | null;
  playerImageUrl?: string | null;
  height?: number;
}

type Trace = Partial<Plotly.PlotData>;

/** Keep in sync with ``layout.margin`` — use under the plot for aligning tables. */
export const TRANSLATION_GRID_MARGIN_PX = {
  left: 56,
  right: 16,
  bottom: 40,
  topMulti: 56,
  topSingle: 48,
} as const;

/** Subplot grid: 1 plot per league, x=age, y=z-score. Uses xaxis2/yaxis2/... domains. */
export function TranslationGrid({ pools, playerName, playerAge, playerWyscoutId, playerImageUrl, height }: Props) {
  const n = pools.length;
  const cols = Math.min(n, 3) || 1;
  const rows = Math.ceil(n / cols);

  const totalHeight = height ?? rows * 300 + 120;

  const sans = plotlySansFontFamily();

  // Reserve top band in paper coords so first-row subplot titles stay visible (y was clipping at 1.025).
  const topReserve = 0.075;
  const plotStackTop = 1 - topReserve;

  // Build domain per subplot (column-major within row, then next row downward)
  const xGap = 0.08;
  const yGap = 0.2;
  const subplotW = (1 - xGap * (cols - 1)) / cols;
  const subplotH = (plotStackTop - yGap * (rows - 1)) / rows;

  const data: Trace[] = [];
  const annotations: Partial<Annotations>[] = [];
  const shapes: Partial<Shape>[] = [];
  const axisOverrides: Record<string, Partial<Layout["xaxis"] | Layout["yaxis"]>> = {};
  /** Map curveNumber → resolver for hover overlay (peers indexed by pointIndex; target = single point). */
  type TraceMeta =
    | { kind: "peers"; pool: TranslationLeaguePool }
    | { kind: "target"; pool: TranslationLeaguePool };
  const curveMeta: TraceMeta[] = [];

  pools.forEach((pool, i) => {
    const rowIdx = Math.floor(i / cols);
    const colIdx = i % cols;
    const xStart = colIdx * (subplotW + xGap);
    const xEnd = xStart + subplotW;
    // Plotly y domain origin is bottom, so first row sits highest (below topReserve band).
    const yEnd = plotStackTop - rowIdx * (subplotH + yGap);
    const yStart = yEnd - subplotH;

    const xaxisName = (i === 0 ? "x" : `x${i + 1}`) as AxisName;
    const yaxisName = (i === 0 ? "y" : `y${i + 1}`) as AxisName;
    const xaxisRef = (i === 0 ? "x" : `x${i + 1}`) as AxisName;
    const yaxisRef = (i === 0 ? "y" : `y${i + 1}`) as AxisName;

    axisOverrides[i === 0 ? "xaxis" : `xaxis${i + 1}`] = {
      domain: [xStart, xEnd],
      anchor: yaxisRef,
      title: { text: "Age", font: { size: 10, family: sans } },
      gridcolor: "rgba(255,255,255,0.05)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { size: 10, family: sans },
      fixedrange: true,
    };
    axisOverrides[i === 0 ? "yaxis" : `yaxis${i + 1}`] = {
      domain: [yStart, yEnd],
      anchor: xaxisRef,
      title: { text: "Z-Score", font: { size: 10, family: sans } },
      gridcolor: "rgba(255,255,255,0.05)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { size: 10, family: sans },
      fixedrange: true,
    };

    // Subplot title (annotation in paper coords; slot sits in band above each subplot)
    annotations.push({
      text: `<b>${pool.league}</b>${
        pool.insufficient_data ? "" : ` · n=${pool.n}`
      }`,
      x: (xStart + xEnd) / 2,
      y: Math.min(yEnd + 0.032, 0.998),
      xref: "paper",
      yref: "paper",
      xanchor: "center",
      yanchor: "bottom",
      showarrow: false,
      font: { size: 12, color: "#d2e2f2", family: sans },
    });

    if (pool.insufficient_data || pool.peers.length === 0) {
      annotations.push({
        text: "Insufficient data",
        x: (xStart + xEnd) / 2,
        y: (yStart + yEnd) / 2,
        xref: "paper",
        yref: "paper",
        xanchor: "center",
        yanchor: "middle",
        showarrow: false,
        font: { size: 11, color: "#7e8fa5", family: sans },
      });
      return;
    }

    // Reference line at z=0
    shapes.push({
      type: "line",
      xref: xaxisRef as "x",
      yref: yaxisRef as "y",
      x0: 0,
      x1: 1,
      xsizemode: "scaled",
      // Use paper-x via separate shape per axis; safer: just compute min/max of ages in this pool.
    });

    const ages = pool.peers.map((p) => p.age ?? 0);
    const xMin = Math.min(...ages, playerAge ?? 25) - 1;
    const xMax = Math.max(...ages, playerAge ?? 25) + 1;

    // Replace placeholder shape with actual ref line
    shapes[shapes.length - 1] = {
      type: "line",
      xref: xaxisRef as "x",
      yref: yaxisRef as "y",
      x0: xMin,
      x1: xMax,
      y0: 0,
      y1: 0,
      line: { color: "rgba(255,255,255,0.25)", width: 1, dash: "dash" },
    };

    // Peer scatter (one trace per league for color array)
    data.push({
      x: ages,
      y: pool.peers.map((p) => p.z_score),
      type: "scatter",
      mode: "markers",
      xaxis: xaxisName,
      yaxis: yaxisName,
      marker: {
        color: pool.peers.map((p) => p.color),
        size: 8,
        opacity: 0.55,
        line: { width: 0 },
      },
      hoverinfo: "none",
      showlegend: false,
      name: `${pool.league} peers`,
    });
    curveMeta.push({ kind: "peers", pool });

    // Target player projected marker
    if (
      pool.projected_z_score != null &&
      pool.projected_perf_index != null &&
      playerAge !== null
    ) {
      const z = pool.projected_z_score;
      const proj = pool.projected_perf_index;
      data.push({
        x: [playerAge],
        y: [z],
        type: "scatter",
        mode: "text+markers",
        xaxis: xaxisName,
        yaxis: yaxisName,
        marker: {
          color: pool.projected_color ?? "#14d1ff",
          size: 16,
          symbol: "circle",
          line: { width: 2, color: "#0a1018" },
        },
        text: [`Z ${z >= 0 ? "+" : ""}${z.toFixed(2)}`],
        textposition: "top center",
        textfont: { size: 11, color: "#d2e2f2", family: sans },
        hoverinfo: "none",
        showlegend: false,
        name: playerName,
      });
      curveMeta.push({ kind: "target", pool });
    }
  });

  const resolveHover = React.useCallback(
    (curveNumber: number, pointIndex: number): OverlayCardData | null => {
      const meta = curveMeta[curveNumber];
      if (!meta) return null;
      if (meta.kind === "peers") {
        const peer = meta.pool.peers[pointIndex];
        if (!peer) return null;
        return {
          name: peer.player,
          club: peer.club,
          league: meta.pool.league,
          age: peer.age,
          color: peer.color,
          wyscoutId: peer.wyscout_id,
          imageUrl: peer.player_image_url ?? null,
          rows: [
            { label: "Perf", value: peer.perf_index.toFixed(1) },
            { label: "Z", value: peer.z_score.toFixed(2) },
          ],
        };
      }
      return {
        name: playerName,
        league: meta.pool.league,
        age: playerAge,
        color: meta.pool.projected_color ?? "#14d1ff",
        wyscoutId: playerWyscoutId ?? null,
        imageUrl: playerImageUrl ?? null,
        rows: [
          {
            label: "Projected perf",
            value: meta.pool.projected_perf_index?.toFixed(1) ?? "—",
          },
          {
            label: "Projected Z",
            value: meta.pool.projected_z_score?.toFixed(2) ?? "—",
          },
        ],
      };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pools, playerName, playerAge, playerWyscoutId],
  );
  const { item, state, onInitialized, containerRef } = useOverlayHoverByCurve(resolveHover);

  return (
    <div ref={containerRef} className="relative w-full">
      <Plot
        data={data as Plotly.Data[]}
        layout={{
          autosize: true,
          height: totalHeight,
          margin: {
            l: TRANSLATION_GRID_MARGIN_PX.left,
            r: TRANSLATION_GRID_MARGIN_PX.right,
            t: rows > 1 ? TRANSLATION_GRID_MARGIN_PX.topMulti : TRANSLATION_GRID_MARGIN_PX.topSingle,
            b: TRANSLATION_GRID_MARGIN_PX.bottom,
          },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: sans, color: "#d2e2f2", size: 12 },
          dragmode: false,
          showlegend: false,
          annotations,
          shapes,
          ...axisOverrides,
          hoverlabel: TRANSPARENT_HOVERLABEL,
        }}
        config={PLOTLY_APP_CONFIG}
        style={{ width: "100%" }}
        useResizeHandler
        onInitialized={onInitialized}
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
    </div>
  );
}
