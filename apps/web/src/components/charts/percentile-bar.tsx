"use client";

import * as React from "react";

import { leagueScaleBlue } from "@/lib/league-scale-blue";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: number | null;
  percentile: number | null;
  className?: string;
  /**
   * elite: primary if ≥80p;
   * leagueGradient: blue strength scales 0–100p (full range);
   * profileBands: scout profile PI / game-area band colours on 0–100p.
   */
  variant?: "elite" | "leagueGradient" | "profileBands";
}

export function PercentileBar({ label, value, percentile, className, variant = "elite" }: Props) {
  const pct = Math.max(0, Math.min(100, percentile ?? 0));
  const isElite = pct >= 80;
  const fill =
    variant === "leagueGradient"
      ? leagueScaleBlue(percentile, "bar")
      : variant === "profileBands"
        ? scoutProfileIndexColor(percentile, "bar")
        : undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-on-surface-variant">{label}</span>
        <span className="data-mono text-on-surface">
          {value == null ? "—" : value.toFixed(2)}
          <span
            className={cn(
              "ml-2",
              variant !== "profileBands" && "text-on-surface-variant",
            )}
            style={
              variant === "profileBands" && percentile != null
                ? { color: scoutProfileIndexColor(percentile, "text") }
                : undefined
            }
          >
            {percentile == null ? "" : `${Math.round(pct)}%`}
          </span>
        </span>
      </div>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-surface-high">
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full",
            variant === "elite" && (isElite ? "bg-primary" : "bg-secondary"),
          )}
          style={{
            width: `${pct}%`,
            ...(fill != null ? { backgroundColor: fill } : {}),
          }}
        />
      </div>
    </div>
  );
}
