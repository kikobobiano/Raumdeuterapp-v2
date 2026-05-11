"use client";

import * as React from "react";

import {
  averageLeagueScaleBlue,
  leagueScaleBlue,
} from "@/lib/league-scale-blue";

export interface RadarMetric {
  label: string;
  percentile: number | null;
  /** Raw game-area index (0–100); drives spoke length. Falls back to percentile if null. */
  value: number | null;
}

interface Props {
  metrics: RadarMetric[];
  size?: number;
  /** When set, overrides percentile-based blue scale; used in multi-player compare overlays. */
  colorOverride?: string;
  /** Hide axis labels (used when stacking radars on top of a primary that already shows labels). */
  hideLabels?: boolean;
}

/** Normalized radius 0–1 from index value (Wyscout-style 0–100 scale). */
function spokeFrac(m: RadarMetric): number {
  if (m.value != null && !Number.isNaN(m.value)) {
    return Math.max(0, Math.min(1, m.value / 100));
  }
  return Math.max(0, Math.min(1, (m.percentile ?? 0) / 100));
}

export function RadarChart({ metrics, size = 360, colorOverride, hideLabels }: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.38;
  const n = metrics.length;
  if (n === 0) return null;

  const bandForSpoke = (m: RadarMetric) => m.value ?? m.percentile;
  const polyColor = colorOverride ?? averageLeagueScaleBlue(metrics.map(bandForSpoke), "text");
  const polyStroke = colorOverride ?? averageLeagueScaleBlue(metrics.map(bandForSpoke), "bar");

  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n;

  /** Tangent to the radar at spoke ``i`` (~perpendicular to radius), snapped upright for readability. */
  function labelRotationDeg(aRad: number): number {
    let rot = (aRad * 180) / Math.PI + 90;
    rot = ((rot % 360) + 360) % 360;
    if (rot > 180) rot -= 360;
    if (rot > 90) rot -= 180;
    else if (rot < -90) rot += 180;
    return rot;
  }

  const point = (i: number, frac: number) => {
    const a = angle(i);
    return [cx + Math.cos(a) * r * frac, cy + Math.sin(a) * r * frac] as const;
  };

  const rings = [0.25, 0.5, 0.75, 1];
  const polygon = metrics
    .map((m, i) => {
      const [x, y] = point(i, spokeFrac(m));
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible">
      {rings.map((f) => (
        <circle
          key={f}
          cx={cx}
          cy={cy}
          r={r * f}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={1}
        />
      ))}
      {metrics.map((_, i) => {
        const [x, y] = point(i, 1);
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        );
      })}

      <polygon
        points={polygon}
        fill={polyColor}
        fillOpacity={0.2}
        stroke={polyStroke}
        strokeWidth={1.5}
      />

      {metrics.map((m, i) => {
        const [x, y] = point(i, spokeFrac(m));
        const c = colorOverride ?? leagueScaleBlue(bandForSpoke(m), "text");
        return <circle key={i} cx={x} cy={y} r={3} fill={c} />;
      })}

      {!hideLabels &&
        metrics.map((m, i) => {
          const [x, y] = point(i, 1.16);
          const deg = labelRotationDeg(angle(i));
          return (
            <g key={`l-${i}`} transform={`translate(${x}, ${y}) rotate(${deg})`}>
              <text
                x={0}
                y={0}
                fill="var(--color-on-surface-variant)"
                fontSize={10}
                textAnchor="middle"
                dominantBaseline="middle"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {m.label}
              </text>
            </g>
          );
        })}
    </svg>
  );
}
