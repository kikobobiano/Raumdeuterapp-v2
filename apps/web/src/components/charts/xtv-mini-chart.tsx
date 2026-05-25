"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export type XtvHistoryPoint = {
  season: number;
  x_tv_eur: number;
  club_logo?: string | null;
};

function seasonLabel(year: number): string {
  return `${String(year).slice(2)}-${String(year + 1).slice(2)}`;
}

function fmtEurCompact(n: number): string {
  if (n >= 1e6) {
    const m = n / 1e6;
    return m >= 10 ? `€${m.toFixed(0)}M` : `€${m.toFixed(1)}M`;
  }
  if (n >= 1e3) return `€${(n / 1e3).toFixed(0)}k`;
  return `€${Math.round(n)}`;
}

interface Props {
  /** Chronological oldest → newest. */
  points: XtvHistoryPoint[];
  className?: string;
}

/**
 * Mini xTV trajectory: area-filled line across loaded seasons. No club logos
 * (kept clean — club context lives in the PI mini chart alongside).
 */
export function XtvMiniChart({ points, className }: Props) {
  const n = points.length;

  const pad = 10;
  const chartH = 64;
  /** viewBox width; x = column centres so path aligns with season grid */
  const vbW = 100;

  const values = points.map((p) => p.x_tv_eur);
  const yMin = 0;
  const yMaxRaw = values.length ? Math.max(...values) : 0;
  const yMax = yMaxRaw > 0 ? yMaxRaw * 1.1 : 1;
  const yScale = (v: number) =>
    pad + chartH - ((Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin)) * chartH;

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
          .map(
            (x, i) =>
              `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${yScale(points[i]!.x_tv_eur).toFixed(2)}`,
          )
          .join(" ")
      : null;

  const areaPath =
    points.length > 1 && linePath
      ? `${linePath} L ${xs[xs.length - 1]!.toFixed(2)} ${(pad + chartH).toFixed(2)} L ${xs[0]!.toFixed(2)} ${(pad + chartH).toFixed(2)} Z`
      : null;

  const gradId = React.useId();
  const svgH = pad + chartH + pad;

  return (
    <div
      className={cn("flex w-full flex-col gap-1", className)}
      aria-label="xTV last seasons"
    >
      <div className="grid gap-x-1" style={gridCols}>
        {points.map((p) => (
          <div key={p.season} className="flex flex-col items-center">
            <span className="data-mono text-[11px] font-semibold leading-none tracking-tight text-on-surface">
              {fmtEurCompact(p.x_tv_eur)}
            </span>
          </div>
        ))}
      </div>

      <div className="relative w-full shrink-0" style={{ height: svgH }}>
        <svg
          className="block h-full w-full overflow-visible text-primary"
          viewBox={`0 0 ${vbW} ${svgH}`}
          preserveAspectRatio="none"
          width="100%"
          height={svgH}
          aria-hidden
        >
          <defs>
            <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity={0.35} />
              <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
            </linearGradient>
          </defs>
          <line
            x1={0}
            y1={pad + chartH}
            x2={vbW}
            y2={pad + chartH}
            stroke="currentColor"
            strokeOpacity={0.2}
            strokeWidth={1}
            vectorEffect="nonScalingStroke"
          />
          {areaPath ? <path d={areaPath} fill={`url(#${gradId})`} /> : null}
          {linePath ? (
            <path
              d={linePath}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
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
                top: yScale(p.x_tv_eur),
              }}
            >
              <div className="h-2 w-2 shrink-0 rounded-full border border-[var(--color-surface-high)] bg-primary" />
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-x-0.5 text-center" style={gridCols}>
        {points.map((p) => (
          <span
            key={p.season}
            className="text-[9px] font-medium leading-tight text-on-surface-variant"
          >
            {seasonLabel(p.season)}
          </span>
        ))}
      </div>
    </div>
  );
}
