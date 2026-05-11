"use client";

import * as React from "react";

export interface QuadrantPoint {
  id: string;
  x: number;
  y: number;
  size: number; // 0–100, drives radius
  label: string;
  sublabel?: string;
  href?: string;
}

interface Props {
  points: QuadrantPoint[];
  /** x-axis range, default 15–25 (Age). */
  xDomain?: [number, number];
  /** y-axis range, default 0–100 (Potential). */
  yDomain?: [number, number];
  /** Vertical split (x value), default 21. */
  xSplit?: number;
  /** Horizontal split (y value), default 70. */
  ySplit?: number;
  xLabel?: string;
  yLabel?: string;
  quadrantLabels?: {
    topLeft: string;
    topRight: string;
    bottomLeft: string;
    bottomRight: string;
  };
  /** Optional callback when a point is clicked. */
  onPointClick?: (p: QuadrantPoint) => void;
}

const DEFAULT_QUADRANTS = {
  topLeft: "Hidden Gems",
  topRight: "Established Stars",
  bottomLeft: "Question Marks",
  bottomRight: "Limited Ceiling",
};

const QUADRANT_TINTS = {
  topLeft: "rgba(20, 209, 255, 0.06)", // primary blue
  topRight: "rgba(0, 255, 65, 0.06)", // green
  bottomLeft: "rgba(255, 184, 0, 0.05)", // amber
  bottomRight: "rgba(255, 255, 255, 0.02)", // muted
};

/** Map potential band → dot colour: amber (low) → pink (high). */
function dotColor(potential: number): string {
  if (potential >= 80) return "#ff4d9d"; // pink
  if (potential >= 65) return "#ff8a4d"; // orange-pink
  if (potential >= 50) return "#ffb800"; // amber
  return "#7e8fa5"; // outline grey
}

export function QuadrantChart({
  points,
  xDomain = [15, 26],
  yDomain = [0, 100],
  xSplit = 21,
  ySplit = 70,
  xLabel = "Age",
  yLabel = "Potential",
  quadrantLabels = DEFAULT_QUADRANTS,
  onPointClick,
}: Props) {
  const [hover, setHover] = React.useState<QuadrantPoint | null>(null);
  const [hoverPos, setHoverPos] = React.useState<{ x: number; y: number } | null>(null);

  // SVG canvas — viewBox 0 0 100 100; padding for axis labels
  const PAD_L = 10;
  const PAD_R = 6;
  const PAD_T = 6;
  const PAD_B = 10;

  const xRange = xDomain[1] - xDomain[0];
  const yRange = yDomain[1] - yDomain[0];

  const fx = (v: number) =>
    PAD_L + ((v - xDomain[0]) / xRange) * (100 - PAD_L - PAD_R);
  const fy = (v: number) =>
    100 - PAD_B - ((v - yDomain[0]) / yRange) * (100 - PAD_T - PAD_B);

  const fr = (size: number) => {
    // Radius 0.6 → 1.6 in viewBox units, scaled by current PI.
    const clamped = Math.max(20, Math.min(100, size));
    return 0.6 + ((clamped - 20) / 80) * 1.0;
  };

  const xSplitPx = fx(xSplit);
  const ySplitPx = fy(ySplit);

  // x ticks every 1 yr, y ticks every 25
  const xTicks: number[] = [];
  for (let v = Math.ceil(xDomain[0]); v <= Math.floor(xDomain[1]); v++) xTicks.push(v);
  const yTicks: number[] = [];
  for (let v = yDomain[0]; v <= yDomain[1]; v += 25) yTicks.push(v);

  return (
    <div className="relative w-full">
      <svg
        viewBox="0 0 100 100"
        className="w-full h-auto"
        style={{ fontFamily: "var(--font-mono, monospace)" }}
      >
        {/* Quadrant tints */}
        <rect x={PAD_L} y={PAD_T} width={xSplitPx - PAD_L} height={ySplitPx - PAD_T} fill={QUADRANT_TINTS.topLeft} />
        <rect x={xSplitPx} y={PAD_T} width={100 - PAD_R - xSplitPx} height={ySplitPx - PAD_T} fill={QUADRANT_TINTS.topRight} />
        <rect x={PAD_L} y={ySplitPx} width={xSplitPx - PAD_L} height={100 - PAD_B - ySplitPx} fill={QUADRANT_TINTS.bottomLeft} />
        <rect x={xSplitPx} y={ySplitPx} width={100 - PAD_R - xSplitPx} height={100 - PAD_B - ySplitPx} fill={QUADRANT_TINTS.bottomRight} />

        {/* Grid */}
        {xTicks.map((t) => (
          <line
            key={`xg-${t}`}
            x1={fx(t)}
            y1={PAD_T}
            x2={fx(t)}
            y2={100 - PAD_B}
            stroke="rgba(255,255,255,0.04)"
            strokeWidth="0.15"
          />
        ))}
        {yTicks.map((t) => (
          <line
            key={`yg-${t}`}
            x1={PAD_L}
            y1={fy(t)}
            x2={100 - PAD_R}
            y2={fy(t)}
            stroke="rgba(255,255,255,0.04)"
            strokeWidth="0.15"
          />
        ))}

        {/* Split lines */}
        <line
          x1={xSplitPx}
          y1={PAD_T}
          x2={xSplitPx}
          y2={100 - PAD_B}
          stroke="rgba(255,255,255,0.18)"
          strokeWidth="0.2"
          strokeDasharray="0.6 0.6"
        />
        <line
          x1={PAD_L}
          y1={ySplitPx}
          x2={100 - PAD_R}
          y2={ySplitPx}
          stroke="rgba(255,255,255,0.18)"
          strokeWidth="0.2"
          strokeDasharray="0.6 0.6"
        />

        {/* Axis lines */}
        <line x1={PAD_L} y1={100 - PAD_B} x2={100 - PAD_R} y2={100 - PAD_B} stroke="var(--color-outline-variant)" strokeWidth="0.25" />
        <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={100 - PAD_B} stroke="var(--color-outline-variant)" strokeWidth="0.25" />

        {/* X tick labels */}
        {xTicks.map((t) => (
          <text
            key={`xt-${t}`}
            x={fx(t)}
            y={100 - PAD_B + 3.2}
            textAnchor="middle"
            fontSize="2.3"
            fill="var(--color-on-surface-variant)"
          >
            {t}
          </text>
        ))}
        {yTicks.map((t) => (
          <text
            key={`yt-${t}`}
            x={PAD_L - 1.5}
            y={fy(t) + 0.8}
            textAnchor="end"
            fontSize="2.3"
            fill="var(--color-on-surface-variant)"
          >
            {t}
          </text>
        ))}

        {/* Quadrant labels */}
        <text
          x={(PAD_L + xSplitPx) / 2}
          y={PAD_T + 3.5}
          textAnchor="middle"
          fontSize="2.4"
          fontWeight="600"
          fill="#14d1ff"
          opacity="0.85"
        >
          {quadrantLabels.topLeft}
        </text>
        <text
          x={(xSplitPx + 100 - PAD_R) / 2}
          y={PAD_T + 3.5}
          textAnchor="middle"
          fontSize="2.4"
          fontWeight="600"
          fill="#00ff41"
          opacity="0.85"
        >
          {quadrantLabels.topRight}
        </text>
        <text
          x={(PAD_L + xSplitPx) / 2}
          y={100 - PAD_B - 1.2}
          textAnchor="middle"
          fontSize="2.4"
          fontWeight="600"
          fill="#ffb800"
          opacity="0.7"
        >
          {quadrantLabels.bottomLeft}
        </text>
        <text
          x={(xSplitPx + 100 - PAD_R) / 2}
          y={100 - PAD_B - 1.2}
          textAnchor="middle"
          fontSize="2.4"
          fontWeight="600"
          fill="var(--color-on-surface-variant)"
          opacity="0.7"
        >
          {quadrantLabels.bottomRight}
        </text>

        {/* Axis titles */}
        <text
          x={(PAD_L + 100 - PAD_R) / 2}
          y={99.5}
          textAnchor="middle"
          fontSize="2.6"
          fill="var(--color-on-surface)"
          fontWeight="500"
        >
          {xLabel}
        </text>
        <text
          x={2.2}
          y={(PAD_T + 100 - PAD_B) / 2}
          textAnchor="middle"
          fontSize="2.6"
          fill="var(--color-on-surface)"
          fontWeight="500"
          transform={`rotate(-90, 2.2, ${(PAD_T + 100 - PAD_B) / 2})`}
        >
          {yLabel}
        </text>

        {/* Points (sorted asc by potential so highest renders on top) */}
        {[...points]
          .sort((a, b) => a.y - b.y)
          .map((p) => {
            const cx = fx(Math.max(xDomain[0], Math.min(xDomain[1], p.x)));
            const cy = fy(Math.max(yDomain[0], Math.min(yDomain[1], p.y)));
            const r = fr(p.size);
            const fill = dotColor(p.y);
            const isHover = hover?.id === p.id;
            return (
              <circle
                key={p.id}
                cx={cx}
                cy={cy}
                r={isHover ? r * 1.4 : r}
                fill={fill}
                fillOpacity={isHover ? 0.95 : 0.78}
                stroke={isHover ? "white" : "rgba(0,0,0,0.4)"}
                strokeWidth={isHover ? 0.25 : 0.1}
                style={{ cursor: onPointClick ? "pointer" : "default", transition: "r 120ms ease" }}
                onMouseEnter={(e) => {
                  setHover(p);
                  const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement)?.getBoundingClientRect();
                  if (rect) {
                    setHoverPos({
                      x: ((cx / 100) * rect.width),
                      y: ((cy / 100) * rect.height),
                    });
                  }
                }}
                onMouseLeave={() => {
                  setHover(null);
                  setHoverPos(null);
                }}
                onClick={() => onPointClick?.(p)}
              />
            );
          })}
      </svg>

      {/* Tooltip */}
      {hover && hoverPos && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-outline-variant/60 bg-surface-high/95 px-2 py-1.5 text-xs shadow-xl backdrop-blur-sm"
          style={{
            left: hoverPos.x + 8,
            top: hoverPos.y - 32,
          }}
        >
          <div className="font-semibold text-on-surface">{hover.label}</div>
          {hover.sublabel && (
            <div className="text-[10px] text-on-surface-variant">{hover.sublabel}</div>
          )}
          <div className="mt-1 flex gap-3 data-mono text-[10px]">
            <span style={{ color: dotColor(hover.y) }}>Pot {hover.y.toFixed(1)}</span>
            <span className="text-on-surface-variant">PI {hover.size.toFixed(1)}</span>
            <span className="text-on-surface-variant">{xLabel} {hover.x}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export const potentialDotColor = dotColor;
