"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { cn } from "@/lib/utils";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";

import type { components } from "shared-types";

type Row = components["schemas"]["DiscoverRow"];

interface Props {
  rows: Row[];
  season: number;
  showStyleFit: boolean;
  metricLabels: Record<string, string>;
}

function formatEur(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1_000_000) return `€${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `€${(v / 1_000).toFixed(0)}K`;
  return `€${v.toFixed(0)}`;
}

function zBar(z: number | null | undefined): React.ReactNode {
  if (z == null) return <span className="text-on-surface-variant">—</span>;
  const clamped = Math.max(-3, Math.min(3, z));
  const pct = ((clamped + 3) / 6) * 100;
  const color = z >= 0 ? "bg-primary" : "bg-error";
  return (
    <div className="flex items-center gap-1.5">
      <div className="relative h-1.5 w-12 overflow-hidden rounded-full bg-surface-mid">
        <div
          className={cn("absolute top-0 h-full", color)}
          style={{
            left: z >= 0 ? "50%" : `${pct}%`,
            width: `${Math.abs(pct - 50)}%`,
          }}
        />
        <div className="absolute left-1/2 top-0 h-full w-px bg-outline-variant" />
      </div>
      <span className="data-mono text-xs text-on-surface">{z.toFixed(1)}</span>
    </div>
  );
}

export function ShortlistTable({ rows, season, showStyleFit, metricLabels }: Props) {
  const router = useRouter();
  const metricKeys = React.useMemo(() => {
    const seen = new Set<string>();
    for (const r of rows) {
      for (const mv of r.metric_values) seen.add(mv.metric);
    }
    return Array.from(seen);
  }, [rows]);

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
            <th className="px-2 py-2 label-caps text-right">xTV</th>
            <th className="px-2 py-2 label-caps text-right">Score</th>
            {showStyleFit && <th className="px-2 py-2 label-caps text-right">Fit</th>}
            {metricKeys.map((k) => (
              <th key={k} className="px-2 py-2 label-caps text-right">
                {metricLabels[k] ?? k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
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
              <td className="px-2 py-2 data-mono text-on-surface-variant">{i + 1}</td>
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
                  <span className="min-w-0 truncate font-medium text-on-surface">{r.player}</span>
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
              <td className="px-2 py-2 text-right data-mono text-on-surface">{formatEur(r.x_tv_eur)}</td>
              <td className="px-2 py-2 text-right data-mono text-primary">
                {r.composite_score.toFixed(2)}
              </td>
              {showStyleFit && (
                <td className="px-2 py-2 text-right data-mono text-on-surface">
                  {r.style_fit != null ? r.style_fit.toFixed(2) : "—"}
                </td>
              )}
              {metricKeys.map((k) => {
                const mv = r.metric_values.find((m) => m.metric === k);
                return (
                  <td key={k} className="px-2 py-2 text-right">
                    {zBar(mv?.z ?? null)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
