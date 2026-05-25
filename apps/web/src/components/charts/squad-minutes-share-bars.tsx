"use client";

import Link from "next/link";
import * as React from "react";

import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { cn } from "@/lib/utils";

import type { AgeZone } from "./squad-age-minutes-scatter";

export interface SquadShareRow {
  wyscout_id?: number | null;
  player: string;
  position?: string | null;
  age?: number | null;
  age_zone: AgeZone;
  minutes: number;
  matches?: number | null;
  league_minutes_pct: number;
  player_image_url?: string | null;
}

interface Props {
  rows: SquadShareRow[];
  season: number;
  /** Static league denominator (max games × 90); shown in header subtitle. */
  maxLeagueMinutes: number;
  maxLeagueGames: number;
}

const ZONE_TINT: Record<AgeZone, string> = {
  youth: "#14d1ff",
  peak: "#00ff41",
  experienced: "#fb923c",
  veteran: "#fbbf24",
};

function PlayerAvatar({ player, imageUrl }: { player: string; imageUrl?: string | null }) {
  const [failed, setFailed] = React.useState(false);
  const direct = imageUrl?.trim();
  const src = direct && !failed ? wyscoutPlayerImageSrc(direct) : null;
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className="h-9 w-9 shrink-0 rounded-full object-cover object-[center_22%] ring-1 ring-outline-variant/40"
      />
    );
  }
  const initials = player
    .split(" ")
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-mid text-[10px] font-bold text-on-surface-variant ring-1 ring-outline-variant/40">
      {initials || "?"}
    </div>
  );
}

export function SquadMinutesShareBars({
  rows,
  season,
  maxLeagueMinutes,
  maxLeagueGames,
}: Props) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className={cn(
          "grid items-center gap-3 px-2 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-wider text-content-muted",
          "grid-cols-[36px_1fr_56px_minmax(0,1fr)]",
          "sm:grid-cols-[36px_minmax(0,1.5fr)_44px_56px_72px_minmax(0,1fr)]",
        )}
      >
        <span aria-hidden />
        <span>Player</span>
        <span className="hidden text-right tabular-nums sm:block">Matches</span>
        <span className="text-right tabular-nums">Min Played</span>
        <span className="hidden text-right sm:block" />
        <span>% of League Mins. Played</span>
      </div>

      {rows.map((r, idx) => {
        const tint = ZONE_TINT[r.age_zone];
        const pct = Math.max(0, Math.min(100, r.league_minutes_pct));
        const profileHref =
          r.wyscout_id != null
            ? `/scout/profile/${r.wyscout_id}?season=${season}`
            : null;

        const Inner = (
          <div
            className={cn(
              "grid items-center gap-3 rounded-md px-2 py-1.5 transition-colors",
              "grid-cols-[36px_1fr_56px_minmax(0,1fr)]",
              "sm:grid-cols-[36px_minmax(0,1.5fr)_44px_56px_72px_minmax(0,1fr)]",
              idx % 2 === 0 ? "bg-surface-low/30" : "bg-transparent",
              profileHref ? "hover:bg-surface-mid/40" : "",
            )}
          >
            <PlayerAvatar player={r.player} imageUrl={r.player_image_url} />

            <div className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-semibold text-on-surface">
                {r.player}
              </span>
              {(r.position || r.age != null) && (
                <span className="mt-0.5 flex items-center gap-1.5 text-[10px] text-content-muted">
                  {r.position && (
                    <span
                      className="rounded bg-surface-low/80 px-1.5 py-0.5 font-semibold uppercase tracking-wide"
                      style={{ color: tint }}
                    >
                      {r.position}
                    </span>
                  )}
                  {r.age != null && <span>{r.age}y</span>}
                </span>
              )}
            </div>

            <span className="hidden text-right text-sm tabular-nums text-on-surface sm:block">
              {r.matches ?? "—"}
            </span>

            <span className="text-right text-sm font-semibold tabular-nums text-on-surface">
              {r.minutes.toLocaleString()}
            </span>

            <span className="hidden text-right sm:block" />

            <div className="flex w-full min-w-0 items-center gap-2">
              <div className="relative h-3 w-full overflow-hidden rounded-full bg-surface-mid/60 ring-1 ring-inset ring-outline-variant/30">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, ${tint}cc 0%, ${tint} 100%)`,
                    boxShadow: `0 0 12px ${tint}55`,
                  }}
                />
              </div>
              <span
                className="w-10 shrink-0 text-right text-xs font-bold tabular-nums"
                style={{ color: tint }}
              >
                {pct.toFixed(0)}%
              </span>
            </div>
          </div>
        );

        if (profileHref) {
          return (
            <Link
              key={r.wyscout_id ?? `${r.player}-${idx}`}
              href={profileHref}
              className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded-md"
            >
              {Inner}
            </Link>
          );
        }
        return (
          <div key={`${r.player}-${idx}`}>
            {Inner}
          </div>
        );
      })}

      <p className="mt-3 px-2 text-[10px] text-content-muted">
        Bar shows each player&apos;s share of the league&apos;s theoretical maximum minutes —
        {" "}{maxLeagueGames} games × 90 = {maxLeagueMinutes.toLocaleString()} min.
        End-of-season top minute earners approach 100%.
      </p>
    </div>
  );
}
