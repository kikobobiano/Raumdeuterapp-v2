"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { cn } from "@/lib/utils";

import {
  ZONE_COLOR,
  ZONE_LABEL,
  ZONE_ORDER,
  type AgeZone,
} from "./squad-age-minutes-scatter";

export interface LeagueClubBandRow {
  club: string;
  club_logo?: string | null;
  total_minutes: number;
  zone_shares: {
    youth: number;
    peak: number;
    experienced: number;
    veteran: number;
  };
}

interface Props {
  rows: LeagueClubBandRow[];
  league: string;
  season: number;
  /** Called when the user clicks a club row — used to drill into the
   * per-club view. */
  onSelectClub: (club: string) => void;
}

export function LeagueZoneSharesBars({
  rows,
  league,
  season,
  onSelectClub,
}: Props) {
  if (rows.length === 0) {
    return (
      <p className="px-2 py-6 text-sm text-content-muted">
        No clubs to show for {league}.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-2 pb-1 text-[11px] text-content-muted">
        {ZONE_ORDER.map((zone) => (
          <span key={zone} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: ZONE_COLOR[zone] }}
            />
            <span className="text-on-surface-variant">{ZONE_LABEL[zone]}</span>
          </span>
        ))}
        <span className="ml-auto text-[10px] uppercase tracking-widest">
          Sorted by youth share · {rows.length} clubs · {season}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        {rows.map((r, idx) => {
          const total =
            r.zone_shares.youth +
            r.zone_shares.peak +
            r.zone_shares.experienced +
            r.zone_shares.veteran;
          const safe = total > 0 ? total : 1;
          return (
            <button
              key={r.club}
              type="button"
              onClick={() => onSelectClub(r.club)}
              className={cn(
                "grid w-full items-center gap-3 rounded-md px-2 py-1.5 text-left transition-colors",
                "grid-cols-[28px_minmax(0,160px)_minmax(0,1fr)_56px]",
                idx % 2 === 0 ? "bg-surface-low/30" : "bg-transparent",
                "hover:bg-surface-mid/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
              )}
              aria-label={`View ${r.club} squad`}
            >
              {r.club_logo ? (
                <ClubLogoImg logoUrl={r.club_logo} className="h-6 w-6" />
              ) : (
                <span className="h-6 w-6 rounded-sm bg-surface-mid/40" />
              )}

              <span className="truncate text-sm font-semibold text-on-surface">
                {r.club}
              </span>

              <div
                className="relative flex h-5 w-full overflow-hidden rounded-full ring-1 ring-inset ring-outline-variant/30"
                aria-hidden
              >
                {ZONE_ORDER.map((zone: AgeZone) => {
                  const v = r.zone_shares[zone];
                  if (v <= 0) return null;
                  const w = (100 * v) / safe;
                  return (
                    <div
                      key={zone}
                      title={`${ZONE_LABEL[zone]} ${v.toFixed(1)}%`}
                      className="h-full"
                      style={{
                        width: `${w}%`,
                        background: `linear-gradient(180deg, ${ZONE_COLOR[zone]}dd 0%, ${ZONE_COLOR[zone]} 100%)`,
                      }}
                    />
                  );
                })}
              </div>

              <span
                className="text-right text-xs font-bold tabular-nums"
                style={{ color: ZONE_COLOR.youth }}
              >
                {r.zone_shares.youth.toFixed(0)}%
              </span>
            </button>
          );
        })}
      </div>

      <p className="mt-2 px-2 text-[10px] text-content-muted">
        Each bar shows the % of that club&apos;s squad minutes given to each
        age band. Right-side number is the youth share. Click a row to inspect
        the full squad.
      </p>
    </div>
  );
}
