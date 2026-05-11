"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

/** Zone anchors (viewBox 0–100); drawn inset so highlights stay compact */
const ZONES: { tokens: string[]; x: number; y: number; w: number; h: number }[] = [
  { tokens: ["GK"], x: 38, y: 86, w: 24, h: 12 },
  { tokens: ["CB", "DF"], x: 34, y: 68, w: 32, h: 14 },
  { tokens: ["LB"], x: 6, y: 66, w: 22, h: 16 },
  { tokens: ["RB"], x: 72, y: 66, w: 22, h: 16 },
  { tokens: ["LWB"], x: 6, y: 50, w: 22, h: 14 },
  { tokens: ["RWB"], x: 72, y: 50, w: 22, h: 14 },
  { tokens: ["DMF"], x: 32, y: 52, w: 36, h: 12 },
  { tokens: ["CMF"], x: 32, y: 40, w: 36, h: 12 },
  { tokens: ["AMF"], x: 36, y: 28, w: 28, h: 12 },
  { tokens: ["LAMF"], x: 10, y: 26, w: 24, h: 14 },
  { tokens: ["RAMF"], x: 66, y: 26, w: 24, h: 14 },
  { tokens: ["LW", "LWF"], x: 8, y: 12, w: 26, h: 14 },
  { tokens: ["RW", "RWF"], x: 66, y: 12, w: 26, h: 14 },
  { tokens: ["WF"], x: 8, y: 12, w: 26, h: 14 },
  { tokens: ["WF"], x: 66, y: 12, w: 26, h: 14 },
  { tokens: ["CF", "ST", "STRIKER", "FW"], x: 38, y: 8, w: 24, h: 14 },
];

const PITCH_FILL = "#151e2c";
const LINE = "rgba(255,255,255,0.08)";
/** Primary position — stronger */
const PRIMARY_FILL = "rgba(20, 209, 255, 0.34)";
const PRIMARY_STROKE = "#14d1ff";
/** Secondary positions — more transparent */
const SECONDARY_FILL = "rgba(20, 209, 255, 0.1)";
const SECONDARY_STROKE = "rgba(20, 209, 255, 0.38)";

function insetRect(
  z: { x: number; y: number; w: number; h: number },
  factor: number,
): { x: number; y: number; w: number; h: number } {
  const nw = z.w * factor;
  const nh = z.h * factor;
  return {
    x: z.x + (z.w - nw) / 2,
    y: z.y + (z.h - nh) / 2,
    w: nw,
    h: nh,
  };
}

/** Circle inscribed in the inset zone box (same center as former rect). */
function zoneCircle(
  z: { x: number; y: number; w: number; h: number },
  factor: number,
): { cx: number; cy: number; r: number } {
  const box = insetRect(z, factor);
  return {
    cx: box.x + box.w / 2,
    cy: box.y + box.h / 2,
    r: Math.min(box.w, box.h) / 2,
  };
}

function zoneKind(
  z: { tokens: string[] },
  primary: Set<string>,
  secondary: Set<string>,
): "primary" | "secondary" | null {
  if (z.tokens.some((t) => primary.has(t))) return "primary";
  if (z.tokens.some((t) => secondary.has(t))) return "secondary";
  return null;
}

export interface HeatmapInput {
  points: { x: number; y: number; count: number }[];
  maxCount: number;
}

interface Props {
  primaryTokens: string[];
  secondaryTokens?: string[];
  heatmap?: HeatmapInput | null;
  className?: string;
}

export function PlayerPositionPitch({
  primaryTokens,
  secondaryTokens = [],
  heatmap = null,
  className,
}: Props) {
  const primary = React.useMemo(() => new Set(primaryTokens), [primaryTokens]);
  const secondary = React.useMemo(() => new Set(secondaryTokens), [secondaryTokens]);
  const inset = 0.52;
  const hasAny = primaryTokens.length > 0 || secondaryTokens.length > 0;

  const heatmapId = React.useId();
  const heatmapPoints = React.useMemo(() => {
    if (!heatmap || !heatmap.points.length || heatmap.maxCount <= 0) return [];
    const R_BASE = 0.5;
    const R_SCALE = 2.3;
    const max = heatmap.maxCount;
    return heatmap.points.map((p) => {
      const ratio = Math.min(1, Math.max(0, p.count / max));
      const r = R_BASE + R_SCALE * Math.sqrt(ratio);
      const opacity = 0.22 + 0.55 * ratio;
      // Wyscout: x = pitch length (0 own → 100 opponent), y = pitch width.
      // SVG: y axis is flipped (attacking up = small y).
      const svgX = p.y;
      const svgY = 100 - p.x;
      return { svgX, svgY, r, opacity };
    });
  }, [heatmap]);

  return (
    <div className={cn("w-full", className)}>
      <svg
        viewBox="0 0 100 100"
        className="mx-auto h-auto w-full max-h-[min(420px,85vw)] max-w-[min(420px,100%)]"
        role="img"
        aria-label="Positions on pitch"
      >
          <title>Positions on pitch</title>
          <defs>
            <linearGradient id="pitchSheen" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="rgba(255,255,255,0.04)" />
              <stop offset="45%" stopColor="transparent" />
              <stop offset="100%" stopColor="rgba(20,209,255,0.03)" />
            </linearGradient>
          </defs>

          <rect
            x="2"
            y="2"
            width="96"
            height="96"
            rx="2"
            fill={PITCH_FILL}
            stroke={LINE}
            strokeWidth="0.55"
          />
          <rect x="2" y="2" width="96" height="96" rx="2" fill="url(#pitchSheen)" />

          <line x1="2" y1="50" x2="98" y2="50" stroke={LINE} strokeWidth="0.45" />
          <circle cx="50" cy="50" r="12" fill="none" stroke={LINE} strokeWidth="0.4" />
          <rect x="32" y="2" width="36" height="14" fill="none" stroke={LINE} strokeWidth="0.4" />
          <rect x="32" y="84" width="36" height="14" fill="none" stroke={LINE} strokeWidth="0.4" />

          {heatmapPoints.length > 0 && (
            <>
              <defs>
                <radialGradient id={`hm-${heatmapId}`} cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#14d1ff" stopOpacity="0.95" />
                  <stop offset="60%" stopColor="#14d1ff" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#14d1ff" stopOpacity="0" />
                </radialGradient>
                <filter id={`hmblur-${heatmapId}`} x="-10%" y="-10%" width="120%" height="120%">
                  <feGaussianBlur stdDeviation="0.6" />
                </filter>
              </defs>
              <g
                filter={`url(#hmblur-${heatmapId})`}
                style={{ mixBlendMode: "screen" }}
              >
                {heatmapPoints.map((p, i) => (
                  <circle
                    key={`hm-${i}`}
                    cx={p.svgX}
                    cy={p.svgY}
                    r={p.r}
                    fill={`url(#hm-${heatmapId})`}
                    opacity={p.opacity}
                  />
                ))}
              </g>
            </>
          )}

          {ZONES.map((z, i) => {
            const kind = zoneKind(z, primary, secondary);
            if (kind !== "secondary") return null;
            const c = zoneCircle(z, inset);
            return (
              <circle
                key={`sec-${z.x}-${z.y}-${i}`}
                cx={c.cx}
                cy={c.cy}
                r={c.r}
                fill={SECONDARY_FILL}
                stroke={SECONDARY_STROKE}
                strokeWidth={0.5}
              />
            );
          })}
          {ZONES.map((z, i) => {
            const kind = zoneKind(z, primary, secondary);
            if (kind !== "primary") return null;
            const c = zoneCircle(z, inset);
            return (
              <circle
                key={`pri-${z.x}-${z.y}-${i}`}
                cx={c.cx}
                cy={c.cy}
                r={c.r}
                fill={PRIMARY_FILL}
                stroke={PRIMARY_STROKE}
                strokeWidth={0.72}
              />
            );
          })}
        </svg>
      {!hasAny ? (
        <p className="mt-3 text-center text-xs text-on-surface-variant">No position tokens</p>
      ) : (
        <div className="mt-3 space-y-1.5 text-center text-xs">
          {primaryTokens.length > 0 && (
            <p className="text-on-surface">
              <span className="font-mono text-[0.65rem] font-semibold tracking-wider text-primary">
                Primary
              </span>
              <span className="mx-2 text-on-surface-variant">·</span>
              <span className="data-mono font-medium">{primaryTokens.join(" · ")}</span>
            </p>
          )}
          {secondaryTokens.length > 0 && (
            <p className="text-on-surface-variant">
              <span className="font-mono text-[0.65rem] font-semibold tracking-wider text-on-surface-variant/90">
                Secondary
              </span>
              <span className="mx-2 opacity-50">·</span>
              <span className="data-mono opacity-85">{secondaryTokens.join(" · ")}</span>
            </p>
          )}
          {heatmap && heatmap.points.length > 0 && (
            <p className="text-on-surface-variant/80">
              <span className="font-mono text-[0.65rem] font-semibold tracking-wider text-on-surface-variant/90">
                Heatmap
              </span>
              <span className="mx-2 opacity-50">·</span>
              <span className="data-mono opacity-85">
                {heatmap.points.length} zones
              </span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
