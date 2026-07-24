"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

import {
  ZONE_COLOR,
  ZONE_LABEL,
  ZONE_ORDER,
  type AgeZone,
} from "./squad-age-minutes-scatter";

export interface LeagueMedianBandRow {
  league: string;
  n_clubs: number;
  median_zone_shares: {
    youth: number;
    peak: number;
    experienced: number;
    veteran: number;
  };
}

interface Props {
  rows: LeagueMedianBandRow[];
  season: number;
  sortBy: AgeZone;
  domesticOnly?: boolean;
  onSortByChange: (band: AgeZone) => void;
  onSelectLeague: (league: string) => void;
}

export function AllLeaguesZoneSharesBars({
  rows,
  season,
  sortBy,
  domesticOnly = false,
  onSortByChange,
  onSelectLeague,
}: Props) {
  const sortedRows = React.useMemo(
    () =>
      [...rows].sort((a, b) => {
        const av = a.median_zone_shares[sortBy];
        const bv = b.median_zone_shares[sortBy];
        if (bv !== av) return bv - av;
        return a.league.localeCompare(b.league);
      }),
    [rows, sortBy],
  );

  if (sortedRows.length === 0) {
    return (
      <p className="px-2 py-6 text-sm text-content-muted">
        No leagues to show for this season.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-2">
        <span className="text-[10px] uppercase tracking-widest text-content-muted">
          Sort by median
        </span>
        <div className="flex flex-wrap gap-1.5">
          {ZONE_ORDER.map((zone) => (
            <button
              key={zone}
              type="button"
              onClick={() => onSortByChange(zone)}
              className={cn(
                "rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors",
                sortBy === zone
                  ? "bg-primary/20 text-primary ring-1 ring-primary/40"
                  : "bg-surface-low/50 text-content-muted hover:bg-surface-mid/40",
              )}
            >
              {ZONE_LABEL[zone]}
            </button>
          ))}
        </div>
      </div>

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
          {domesticOnly ? "Domestic players only · " : ""}
          Median squad mix · {sortedRows.length} leagues · {season}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        {sortedRows.map((r, idx) => {
          const shares = r.median_zone_shares;
          const total =
            shares.youth + shares.peak + shares.experienced + shares.veteran;
          const safe = total > 0 ? total : 1;
          return (
            <button
              key={r.league}
              type="button"
              onClick={() => onSelectLeague(r.league)}
              className={cn(
                "grid w-full items-center gap-3 rounded-md px-2 py-1.5 text-left transition-colors",
                "grid-cols-[minmax(0,200px)_minmax(0,1fr)_56px]",
                idx % 2 === 0 ? "bg-surface-low/30" : "bg-transparent",
                "hover:bg-surface-mid/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
              )}
              aria-label={`View ${r.league} overview`}
            >
              <span className="truncate text-sm font-semibold text-on-surface">
                {r.league}
              </span>

              <div
                className="relative flex h-5 w-full overflow-hidden rounded-full ring-1 ring-inset ring-outline-variant/30"
                aria-hidden
              >
                {ZONE_ORDER.map((zone: AgeZone) => {
                  const v = shares[zone];
                  if (v <= 0) return null;
                  const w = (100 * v) / safe;
                  return (
                    <div
                      key={zone}
                      title={`${ZONE_LABEL[zone]} ${v.toFixed(1)}%`}
                      className="flex h-full min-w-0 items-center justify-center overflow-hidden"
                      style={{
                        width: `${w}%`,
                        background: `linear-gradient(180deg, ${ZONE_COLOR[zone]}dd 0%, ${ZONE_COLOR[zone]} 100%)`,
                      }}
                    >
                      {w >= 9 ? (
                        <span className="pointer-events-none select-none text-[10px] font-bold tabular-nums text-[#0a1018]/90">
                          {v.toFixed(0)}%
                        </span>
                      ) : null}
                    </div>
                  );
                })}
              </div>

              <span className="text-right text-[11px] tabular-nums text-content-muted">
                {r.n_clubs} clubs
              </span>
            </button>
          );
        })}
      </div>

      <p className="mt-1 px-2 text-[10px] text-content-muted">
        {domesticOnly
          ? "Age-band shares use only minutes from domestic-passport players in each league. "
          : ""}
        Each bar shows the median % of squad minutes given to each age band
        across clubs in that league. Click a row to open the league overview.
      </p>
    </div>
  );
}
