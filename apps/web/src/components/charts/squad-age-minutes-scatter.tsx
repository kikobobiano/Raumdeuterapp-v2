"use client";

import dynamic from "next/dynamic";
import type { Layout, PlotMouseEvent } from "plotly.js";
import * as React from "react";
import { useRouter } from "next/navigation";

import { OverlayCard, TRANSPARENT_HOVERLABEL, useOverlayHover } from "@/components/charts/hover-overlay";
import { plotlySansFontFamily } from "@/lib/plotly-font";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

export type AgeZone = "youth" | "peak" | "experienced" | "veteran";

/** Inclusive upper bounds matching the backend cutoffs in
 * ``apps/api/app/routers/team_minutes.py``. Kept in sync manually — there is
 * no shared constant module for static enums of this kind in the repo. */
export const YOUTH_MAX_AGE = 22; // age <= 22 → youth
export const PEAK_MAX_AGE = 28; // age <= 28 → peak
export const EXPERIENCED_MAX_AGE = 33; // age <= 33 → experienced; > 33 → veteran

export interface SquadScatterPoint {
  wyscout_id?: number | null;
  player: string;
  position?: string | null;
  age?: number | null;
  minutes: number;
  matches?: number | null;
  age_zone: AgeZone;
  player_image_url?: string | null;
}

interface Props {
  points: SquadScatterPoint[];
  club: string;
  league: string | null;
  clubLogoUrl?: string | null;
  season: number;
  /** Static league denominator from API (max_games × 90), shown on hover. */
  maxLeagueMinutes: number;
  height?: number;
}

interface ResolvedPoint {
  wyscout_id?: number | null;
  player: string;
  position?: string | null;
  age: number | null;
  minutes: number;
  matches?: number | null;
  age_zone: AgeZone;
  player_image_url?: string | null;
}

export const ZONE_COLOR: Record<AgeZone, string> = {
  youth: "#14d1ff",
  peak: "#00ff41",
  experienced: "#fb923c",
  veteran: "#fbbf24",
};

const ZONE_FILL: Record<AgeZone, string> = {
  youth: "rgba(20,209,255,0.07)",
  peak: "rgba(0,255,65,0.05)",
  experienced: "rgba(251,146,60,0.06)",
  veteran: "rgba(251,191,36,0.07)",
};

export const ZONE_LABEL: Record<AgeZone, string> = {
  youth: "Youth",
  peak: "Peak",
  experienced: "Experienced",
  veteran: "Veteran",
};

export const ZONE_ORDER: AgeZone[] = ["youth", "peak", "experienced", "veteran"];

function shortLabel(name: string, max = 14): string {
  const surname = name.trim().split(/\s+/).pop() ?? name;
  if (surname.length <= max) return surname;
  return `${surname.slice(0, max - 1)}…`;
}

export function SquadAgeMinutesScatter({
  points,
  club,
  league,
  clubLogoUrl,
  season,
  maxLeagueMinutes,
  height = 460,
}: Props) {
  const youngMaxAge = YOUTH_MAX_AGE;
  const peakMaxAge = PEAK_MAX_AGE;
  const expMaxAge = EXPERIENCED_MAX_AGE;
  const router = useRouter();
  const sans = plotlySansFontFamily();

  const valid = React.useMemo<ResolvedPoint[]>(
    () =>
      points
        .filter((p) => p.age != null && Number.isFinite(p.age))
        .map((p) => ({
          wyscout_id: p.wyscout_id,
          player: p.player,
          position: p.position,
          age: p.age ?? null,
          minutes: p.minutes,
          matches: p.matches,
          age_zone: p.age_zone,
          player_image_url: p.player_image_url,
        })),
    [points],
  );

  const xMin = 15;
  const xMax = React.useMemo(() => {
    const ages = valid.map((p) => p.age as number);
    return Math.max(40, ages.length > 0 ? Math.max(...ages) + 1 : 40);
  }, [valid]);

  const yMax = React.useMemo(() => {
    const upper = Math.max(maxLeagueMinutes, ...valid.map((p) => p.minutes));
    return Math.ceil(upper / 500) * 500;
  }, [valid, maxLeagueMinutes]);

  const data = React.useMemo(
    () => [
      {
        type: "scatter" as const,
        mode: "text+markers" as const,
        x: valid.map((p) => p.age as number),
        y: valid.map((p) => p.minutes),
        text: valid.map((p) => shortLabel(p.player)),
        textposition: "top center" as const,
        textfont: { family: sans, size: 10, color: "#d2e2f2" },
        cliponaxis: false,
        hoverinfo: "none" as const,
        marker: {
          size: 13,
          color: valid.map((p) => ZONE_COLOR[p.age_zone]),
          opacity: 0.92,
          line: { width: 1.5, color: "rgba(10,16,24,0.7)" },
        },
        showlegend: false,
      },
    ],
    [valid, sans],
  );

  const shapes: NonNullable<Layout["shapes"]> = React.useMemo(
    () => [
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: xMin - 0.5,
        x1: youngMaxAge + 0.5,
        y0: 0,
        y1: 1,
        fillcolor: ZONE_FILL.youth,
        line: { width: 0 },
        layer: "below",
      },
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: youngMaxAge + 0.5,
        x1: peakMaxAge + 0.5,
        y0: 0,
        y1: 1,
        fillcolor: ZONE_FILL.peak,
        line: { width: 0 },
        layer: "below",
      },
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: peakMaxAge + 0.5,
        x1: expMaxAge + 0.5,
        y0: 0,
        y1: 1,
        fillcolor: ZONE_FILL.experienced,
        line: { width: 0 },
        layer: "below",
      },
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: expMaxAge + 0.5,
        x1: xMax + 0.5,
        y0: 0,
        y1: 1,
        fillcolor: ZONE_FILL.veteran,
        line: { width: 0 },
        layer: "below",
      },
      {
        type: "line",
        xref: "x",
        yref: "y",
        x0: xMin - 0.5,
        x1: xMax + 0.5,
        y0: maxLeagueMinutes,
        y1: maxLeagueMinutes,
        line: { color: "rgba(255,255,255,0.18)", width: 1, dash: "dot" },
        layer: "below",
      },
    ],
    [xMin, xMax, youngMaxAge, peakMaxAge, expMaxAge, maxLeagueMinutes],
  );

  const annotations: NonNullable<Layout["annotations"]> = React.useMemo(() => {
    const youthMid = (xMin - 0.5 + youngMaxAge + 0.5) / 2;
    const peakMid = (youngMaxAge + 0.5 + peakMaxAge + 0.5) / 2;
    const expMid = (peakMaxAge + 0.5 + expMaxAge + 0.5) / 2;
    const vetMid = (expMaxAge + 0.5 + xMax + 0.5) / 2;
    return [
      {
        xref: "x",
        yref: "paper",
        x: youthMid,
        y: 1.04,
        text: `${ZONE_LABEL.youth} (<${youngMaxAge + 1})`,
        showarrow: false,
        font: { family: sans, size: 11, color: ZONE_COLOR.youth },
      },
      {
        xref: "x",
        yref: "paper",
        x: peakMid,
        y: 1.04,
        text: `${ZONE_LABEL.peak} (${youngMaxAge + 1}–${peakMaxAge})`,
        showarrow: false,
        font: { family: sans, size: 11, color: ZONE_COLOR.peak },
      },
      {
        xref: "x",
        yref: "paper",
        x: expMid,
        y: 1.04,
        text: `${ZONE_LABEL.experienced} (${peakMaxAge + 1}–${expMaxAge})`,
        showarrow: false,
        font: { family: sans, size: 11, color: ZONE_COLOR.experienced },
      },
      {
        xref: "x",
        yref: "paper",
        x: vetMid,
        y: 1.04,
        text: `${ZONE_LABEL.veteran} (≥${expMaxAge + 1})`,
        showarrow: false,
        font: { family: sans, size: 11, color: ZONE_COLOR.veteran },
      },
      {
        xref: "x",
        yref: "y",
        x: xMax,
        y: maxLeagueMinutes,
        xanchor: "right",
        yanchor: "bottom",
        text: `Max league min · ${maxLeagueMinutes.toLocaleString()}`,
        showarrow: false,
        font: { family: sans, size: 9, color: "#7e8fa5" },
      },
    ];
  }, [xMin, xMax, youngMaxAge, peakMaxAge, expMaxAge, maxLeagueMinutes, sans]);

  const layout = React.useMemo<Partial<Layout>>(
    () => ({
      autosize: true,
      height,
      margin: { l: 64, r: 24, t: 36, b: 56 },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { family: sans, color: "#d2e2f2", size: 12 },
      dragmode: false,
      hovermode: "closest",
      hoverdistance: 22,
      xaxis: {
        title: { text: "Age" },
        range: [xMin - 0.5, xMax + 0.5],
        dtick: 2,
        gridcolor: "rgba(255,255,255,0.05)",
        zeroline: false,
        fixedrange: true,
      },
      yaxis: {
        title: { text: "Minutes played" },
        range: [0, yMax],
        gridcolor: "rgba(255,255,255,0.05)",
        zeroline: false,
        fixedrange: true,
      },
      showlegend: false,
      hoverlabel: TRANSPARENT_HOVERLABEL,
      shapes,
      annotations,
    }),
    [height, xMin, xMax, yMax, sans, shapes, annotations],
  );

  const { item, state, onHover, onUnhover, onMouseMove, onInitialized, containerRef } = useOverlayHover(valid);

  const onClick = React.useCallback(
    (ev: Readonly<PlotMouseEvent>) => {
      const p = ev.points?.[0];
      if (!p || p.pointIndex == null) return;
      const point = valid[p.pointIndex];
      if (!point?.wyscout_id) return;
      router.push(`/scout/profile/${point.wyscout_id}?season=${season}`);
    },
    [valid, router, season],
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
        onClick={onClick}
      />
      {item && state && (
        <div
          className="pointer-events-none absolute z-50"
          style={{
            left: Math.min(state.x + 14, (containerRef.current?.clientWidth ?? 0) - 280),
            top: Math.max(state.y - 64, 4),
          }}
        >
          <OverlayCard
            data={{
              name: item.player,
              club,
              league,
              position: item.position,
              age: item.age,
              clubLogoUrl,
              imageUrl: item.player_image_url,
              wyscoutId: item.wyscout_id ?? null,
              color: ZONE_COLOR[item.age_zone],
              value: `${item.minutes.toLocaleString()}'`,
              rows: [
                ...(item.matches != null
                  ? [{ label: "Matches", value: String(item.matches) }]
                  : []),
                {
                  label: "% league min",
                  value: `${(
                    Math.min(100, (100 * item.minutes) / Math.max(1, maxLeagueMinutes))
                  ).toFixed(0)}%`,
                },
              ],
            }}
          />
        </div>
      )}
    </div>
  );
}
