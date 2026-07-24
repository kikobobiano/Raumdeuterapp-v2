"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { cn } from "@/lib/utils";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";

import type { components } from "shared-types";

type Row = components["schemas"]["StandoutRow"];
type Dimension = components["schemas"]["StandoutDimension"];

interface Props {
  rows: Row[];
  season: number;
  /** Rank offset for the first row (for pagination). */
  startIndex?: number;
  /** Show a Performance Index column (overall mode). */
  showPerformanceIndex: boolean;
}

const STRENGTH_MIN_Z = 1.0;
const MAX_CHIPS = 3;

function strengthChips(dimensions: Dimension[]): Dimension[] {
  const strong = dimensions.filter((d) => d.z != null && d.z >= STRENGTH_MIN_Z);
  const pool = strong.length > 0 ? strong : dimensions.filter((d) => d.z != null);
  return pool.slice(0, MAX_CHIPS);
}

/** Cyan for a positive standout, amber for a modest one. */
function sigmaColor(z: number): string {
  if (z >= 2) return "text-primary";
  if (z >= 1) return "text-secondary";
  return "text-on-surface";
}

export function StandoutsTable({ rows, season, startIndex = 0, showPerformanceIndex }: Props) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th className="px-2 py-2 label-caps">#</th>
            <th className="px-2 py-2 label-caps">Player</th>
            <th className="px-2 py-2 label-caps">Club</th>
            <th className="px-2 py-2 label-caps">Pos</th>
            <th className="px-2 py-2 label-caps">Age</th>
            <th className="px-2 py-2 label-caps">Min</th>
            {showPerformanceIndex && <th className="px-2 py-2 label-caps text-right">PI</th>}
            <th className="px-2 py-2 label-caps text-right">Standout σ</th>
            <th className="px-2 py-2 label-caps">Stands out for</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const chips = strengthChips(r.dimensions ?? []);
            return (
              <tr
                key={`${r.wyscout_id}-${i}`}
                onClick={() =>
                  r.wyscout_id != null &&
                  router.push(`/scout/profile/${r.wyscout_id}?season=${season}`)
                }
                className={cn(
                  "border-t border-outline-variant/40 hover:bg-surface-mid/40",
                  r.wyscout_id != null && "cursor-pointer",
                )}
              >
                <td className="px-2 py-2 data-mono text-on-surface-variant">
                  {startIndex + i + 1}
                </td>
                <td className="px-2 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {r.player_image_url ? (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img
                        src={wyscoutPlayerImageSrc(r.player_image_url)}
                        alt=""
                        className="h-8 w-8 rounded-full object-cover bg-surface-mid"
                      />
                    ) : (
                      <div className="h-8 w-8 rounded-full bg-surface-mid" />
                    )}
                    <span className="min-w-0 truncate font-medium text-on-surface">
                      {r.player}
                    </span>
                  </div>
                </td>
                <td className="px-2 py-2">
                  <div className="flex items-center gap-2 max-w-[200px] min-w-0">
                    <ClubLogoImg logoUrl={r.club_logo} className="h-6 w-6" />
                    <span className="min-w-0 truncate text-on-surface">{r.club ?? "—"}</span>
                  </div>
                </td>
                <td className="px-2 py-2 data-mono text-on-surface">{r.position ?? "—"}</td>
                <td className="px-2 py-2 data-mono text-on-surface">{r.age ?? "—"}</td>
                <td className="px-2 py-2 data-mono text-on-surface">{r.minutes ?? "—"}</td>
                {showPerformanceIndex && (
                  <td className="px-2 py-2 text-right data-mono text-on-surface">
                    {r.performance_index != null ? r.performance_index.toFixed(1) : "—"}
                  </td>
                )}
                <td
                  className={cn(
                    "px-2 py-2 text-right data-mono font-semibold",
                    sigmaColor(r.standout_score),
                  )}
                >
                  +{r.standout_score.toFixed(2)}
                </td>
                <td className="px-2 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {chips.map((d) => (
                      <span
                        key={d.key}
                        className="inline-flex items-center gap-1 rounded-md border border-outline-variant/50 bg-surface-low px-2 py-0.5 text-xs"
                      >
                        <span className="text-on-surface">{d.label}</span>
                        <span
                          className={cn(
                            "data-mono",
                            d.z != null && d.z >= 0 ? "text-primary" : "text-error",
                          )}
                        >
                          {d.z != null ? `${d.z >= 0 ? "+" : ""}${d.z.toFixed(1)}σ` : "—"}
                        </span>
                      </span>
                    ))}
                    {chips.length === 0 && (
                      <span className="text-xs text-on-surface-variant">—</span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
