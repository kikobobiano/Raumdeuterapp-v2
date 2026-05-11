"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { cn } from "@/lib/utils";

export type PiHistoryPoint = {
  season: number;
  performance_index: number;
  club_logo?: string | null;
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
  const innerW = 200 - pad * 2;
  const yMin = 0;
  const yMax = 100;
  const yScale = (v: number) => pad + chartH - ((Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin)) * chartH;

  const gridCols = React.useMemo(
    () => ({ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }) as React.CSSProperties,
    [n],
  );

  const xs = React.useMemo(
    () =>
      n === 1
        ? [pad + innerW / 2]
        : points.map((_, i) => pad + (i / (n - 1)) * innerW),
    [points, n, innerW],
  );

  if (n < 1) return null;

  const linePath =
    points.length > 1
      ? xs
          .map((x, i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${yScale(points[i]!.performance_index).toFixed(2)}`)
          .join(" ")
      : null;

  return (
    <div
      className={cn(
        "flex w-full min-w-[10rem] max-w-[16rem] flex-col gap-1",
        className,
      )}
      aria-label="Performance index last seasons"
    >
      <div className="grid gap-x-1" style={gridCols}>
        {points.map((p) => (
          <div key={p.season} className="flex flex-col items-center gap-1">
            <ClubLogoImg logoUrl={p.club_logo} className="h-6 w-6" />
            <span
              className="data-mono text-[11px] font-semibold leading-none tracking-tight"
              style={{ color: scoutProfileIndexColor(p.performance_index, "text") }}
            >
              {p.performance_index.toFixed(1)}
            </span>
          </div>
        ))}
      </div>

      <svg
        className="w-full shrink-0 overflow-visible text-on-surface/[0.2]"
        viewBox={`0 0 200 ${pad + chartH + pad}`}
        height={pad + chartH + pad}
        aria-hidden
      >
        {/* baseline band */}
        <line
          x1={pad}
          y1={yScale(0)}
          x2={200 - pad}
          y2={yScale(0)}
          stroke="currentColor"
          strokeWidth={1}
        />
        {linePath ? (
          <path d={linePath} fill="none" stroke="currentColor" strokeWidth={1.25} strokeLinecap="round" />
        ) : null}
        {xs.map((x, i) => (
          <circle
            key={points[i]!.season}
            cx={x}
            cy={yScale(points[i]!.performance_index)}
            r={3.75}
            fill={scoutProfileIndexColor(points[i]!.performance_index, "text")}
            stroke="var(--color-surface-high)"
            strokeWidth={1}
          />
        ))}
      </svg>

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
