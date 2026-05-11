"use client";

import dynamic from "next/dynamic";
import type { Layout } from "plotly.js";
import * as React from "react";

import {
  OverlayCard,
  type OverlayCardData,
  TRANSPARENT_HOVERLABEL,
  useOverlayHoverByCurve,
} from "@/components/charts/hover-overlay";
import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";
import { wyscoutClubLogoSrc } from "@/lib/wyscout-image";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export interface ProgressionPoint {
  season: number;
  value: number | null;
  club?: string | null;
  league?: string | null;
  club_logo?: string | null;
}

export interface ProgressionSeries {
  metric: string;
  label: string;
  points: ProgressionPoint[];
}

const PALETTE = [
  "#14d1ff", "#00ff41", "#ffd5ae", "#e879f9", "#fb7185",
  "#a3e635", "#facc15", "#c084fc", "#2dd4bf", "#f97316",
];

function seasonLabel(year: number): string {
  return `${String(year).slice(2)}-${String(year + 1).slice(2)}`;
}

interface Props {
  series: ProgressionSeries[];
  seasons: number[];
  playerWyscoutId?: number | null;
  playerImageUrl?: string | null;
  playerName?: string | null;
  height?: number;
}

export function ProgressionChart({ series, seasons, playerWyscoutId, playerImageUrl, playerName, height = 380 }: Props) {
  const sans = plotlySansFontFamily();
  const logoBySeason = React.useMemo(() => {
    const m = new Map<number, string>();
    for (const s of series) {
      for (const p of s.points) {
        const raw = p.club_logo?.trim();
        if (raw && !m.has(p.season)) m.set(p.season, raw);
      }
    }
    return m;
  }, [series]);

  /** One logo per season, aligned to x categories; y in paper coords (top band). */
  const layoutImages = React.useMemo((): NonNullable<Layout["images"]> => {
    const imgs: NonNullable<Layout["images"]> = [];
    for (const seasonYear of seasons) {
      const raw = logoBySeason.get(seasonYear)?.trim();
      if (!raw) continue;
      imgs.push({
        source: wyscoutClubLogoSrc(raw),
        xref: "x",
        yref: "paper",
        x: seasonLabel(seasonYear),
        y: 1,
        xanchor: "center",
        yanchor: "top",
        sizex: 0.58,
        sizey: 0.118,
        sizing: "contain",
        layer: "above",
      });
    }
    return imgs;
  }, [seasons, logoBySeason]);

  const data = React.useMemo(
    () =>
      series.map((s, i) => ({
        x: s.points.map((p) => seasonLabel(p.season)),
        y: s.points.map((p) => p.value),
        type: "scatter" as const,
        mode: "lines+markers" as const,
        name: s.label,
        line: { color: PALETTE[i % PALETTE.length], width: 2 },
        marker: { size: 7, color: PALETTE[i % PALETTE.length] },
        hoverinfo: "none" as const,
        connectgaps: false,
      })),
    [series],
  );

  const resolveHover = React.useCallback(
    (curve: number, idx: number): OverlayCardData | null => {
      const s = series[curve];
      if (!s) return null;
      const p = s.points[idx];
      if (!p) return null;
      return {
        name: playerName ?? s.label,
        club: p.club,
        league: p.league,
        clubLogoUrl: p.club_logo,
        color: PALETTE[curve % PALETTE.length],
        wyscoutId: playerWyscoutId ?? null,
        imageUrl: playerImageUrl ?? null,
        rows: [
          { label: "Metric", value: s.label },
          { label: "Season", value: seasonLabel(p.season) },
          { label: "Value", value: p.value != null ? p.value.toFixed(2) : "—" },
        ],
      };
    },
    [series, playerWyscoutId, playerName],
  );
  const { item, state, onInitialized, containerRef } = useOverlayHoverByCurve(resolveHover);

  return (
    <div ref={containerRef} className="relative w-full">
      <Plot
        data={data}
        layout={{
          autosize: true,
          height,
          margin: { l: 56, r: 16, t: 70, b: 56 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: sans, color: "#d2e2f2", size: 12 },
          dragmode: false,
          xaxis: {
            type: "category",
            categoryorder: "array",
            categoryarray: seasons.map(seasonLabel),
            gridcolor: "rgba(255,255,255,0.05)",
            zerolinecolor: "rgba(255,255,255,0.1)",
            fixedrange: true,
          },
          yaxis: {
            gridcolor: "rgba(255,255,255,0.05)",
            zerolinecolor: "rgba(255,255,255,0.1)",
            fixedrange: true,
          },
          images: layoutImages,
          showlegend: true,
          legend: {
            orientation: "h",
            y: -0.18,
            font: { size: 11, family: sans },
            bgcolor: "transparent",
          },
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
