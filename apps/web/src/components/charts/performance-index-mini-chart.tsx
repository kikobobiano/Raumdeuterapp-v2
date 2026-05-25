"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { cn } from "@/lib/utils";

/** Same threshold as profile PI headline / radar (`PROFILE_RADAR_MIN_MINUTES` on API). */
const MINUTES_PI_DISPLAY_MIN = 500;

export type PiHistoryPoint = {
  season: number;
  performance_index: number;
  club_logo?: string | null;
  /** When set and below threshold, the numeric label shows "-". */
  minutes_played?: number | null;
};

function seasonLabel(year: number): string {
  return `${String(year).slice(2)}-${String(year + 1).slice(2)}`;
}

interface Props {
  /** Chronological oldest → newest. */
  points: PiHistoryPoint[];
  className?: string;
}

/**
 * Scout profile mini-trend: club logo per season, PI values (band-coloured),
 * lightweight line across seasons.
 */
export function PerformanceIndexMiniChart({ points, className }: Props) {
  const n = points.length;

  const pad = 10;
  const chartH = 48;
  const vbW = 100;
  const yMin = 0;
  const yMax = 100;
  const yScale = (v: number) => pad + chartH - ((Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin)) * chartH;

  const gridCols = React.useMemo(
    () => ({ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }) as React.CSSProperties,
    [n],
  );

  const xs = React.useMemo(
    () => points.map((_, i) => ((i + 0.5) / n) * vbW),
    [points, n],
  );

  if (n < 1) return null;

  const linePath =
    points.length > 1
      ? xs
          .map((x, i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${yScale(points[i]!.performance_index).toFixed(2)}`)
          .join(" ")
      : null;

  const svgH = pad + chartH + pad;

  return (
    <div
      className={cn("flex w-full flex-col gap-1", className)}
      aria-label="Performance index last seasons"
    >
      <div className="grid gap-x-1" style={gridCols}>
        {points.map((p) => {
          const lowSample =
            p.minutes_played != null && p.minutes_played < MINUTES_PI_DISPLAY_MIN;
          return (
            <div key={p.season} className="flex flex-col items-center gap-1">
              <ClubLogoImg logoUrl={p.club_logo} className="h-6 w-6" />
              <span
                className={cn(
                  "data-mono text-[11px] font-semibold leading-none tracking-tight",
                  lowSample && "text-on-surface-variant",
                )}
                style={
                  lowSample
                    ? undefined
                    : { color: scoutProfileIndexColor(p.performance_index, "text") }
                }
              >
                {lowSample ? "-" : p.performance_index.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="relative w-full shrink-0" style={{ height: svgH }}>
        <svg
          className="block h-full w-full overflow-visible text-on-surface/[0.2]"
          viewBox={`0 0 ${vbW} ${svgH}`}
          preserveAspectRatio="none"
          width="100%"
          height={svgH}
          aria-hidden
        >
          {/* baseline band */}
          <line
            x1={0}
            y1={yScale(0)}
            x2={vbW}
            y2={yScale(0)}
            stroke="currentColor"
            strokeWidth={1}
            vectorEffect="nonScalingStroke"
          />
          {linePath ? (
            <path
              d={linePath}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.25}
              strokeLinecap="round"
              vectorEffect="nonScalingStroke"
            />
          ) : null}
        </svg>
        <div className="pointer-events-none absolute inset-0" aria-hidden>
          {points.map((p, i) => (
            <div
              key={p.season}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{
                left: `${((i + 0.5) / n) * 100}%`,
                top: yScale(p.performance_index),
              }}
            >
              <div
                className="h-2 w-2 shrink-0 rounded-full border border-[var(--color-surface-high)]"
                style={{ backgroundColor: scoutProfileIndexColor(p.performance_index, "text") }}
              />
            </div>
          ))}
        </div>
      </div>

      <div className={cn("grid gap-x-0.5 text-center")} style={gridCols}>
        {points.map((p) => (
          <span key={p.season} className="text-[9px] font-medium leading-tight text-on-surface-variant">
            {seasonLabel(p.season)}
          </span>
        ))}
      </div>
    </div>
  );
}
