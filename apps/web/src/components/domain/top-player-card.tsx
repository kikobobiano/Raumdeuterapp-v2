"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { cn } from "@/lib/utils";

const AREA_LEFT = [
  ["distribution_index", "Distrib."],
  ["take_ons_index", "Take ons"],
  ["assistance_index", "Assist"],
] as const;
const AREA_RIGHT = [
  ["finishing_index", "Finish"],
  ["aerial_play_index", "Aerial"],
  ["ground_defense_index", "Ground"],
] as const;

type AreasMap = Partial<
  Record<
    (typeof AREA_LEFT)[number][0] | (typeof AREA_RIGHT)[number][0],
    number | null | undefined
  >
>;

function AreaBar({ label, value }: { label: string; value: number | null | undefined }) {
  const v = value;
  const widthPct = v != null && !Number.isNaN(v) ? Math.max(0, Math.min(100, v)) : 0;
  const filled = v != null && !Number.isNaN(v);
  return (
    <div className="min-w-0 space-y-1">
      <div className="flex items-center justify-between gap-1 text-[10px] leading-tight">
        <span className="truncate font-medium text-on-surface-variant">{label}</span>
        <span
          className="data-mono shrink-0 tabular-nums text-on-surface"
          style={filled ? { color: scoutProfileIndexColor(v, "text") } : undefined}
        >
          {filled ? v.toFixed(0) : "—"}
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-surface-low/90 ring-1 ring-white/5" aria-hidden>
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: `${widthPct}%`,
            background: filled ? scoutProfileIndexColor(v, "bar") : "transparent",
          }}
        />
      </div>
    </div>
  );
}

export function TopPlayerCard({
  rank,
  wyscoutId,
  name,
  club,
  league,
  position,
  age,
  minutes,
  performanceIndex,
  playerImageUrl,
  clubLogoUrl,
  distribution_index,
  take_ons_index,
  assistance_index,
  finishing_index,
  aerial_play_index,
  ground_defense_index,
  onSelect,
}: {
  rank: number;
  wyscoutId: number;
  name: string;
  club: string | null;
  league: string | null;
  position: string | null;
  age: number | null;
  minutes: number | null;
  performanceIndex: number | null;
  /** HTTPS URL (Wyscout or TM ``image_url`` in parquet); proxied via ``/api/player-image``. */
  playerImageUrl?: string | null;
  /** Wyscout club crest URL. */
  clubLogoUrl?: string | null;
  distribution_index?: number | null;
  take_ons_index?: number | null;
  assistance_index?: number | null;
  finishing_index?: number | null;
  aerial_play_index?: number | null;
  ground_defense_index?: number | null;
  onSelect: () => void;
}) {
  const areas: AreasMap = {
    distribution_index,
    take_ons_index,
    assistance_index,
    finishing_index,
    aerial_play_index,
    ground_defense_index,
  };

  const [faceFailed, setFaceFailed] = React.useState(false);
  const rawPortraitUrl = playerImageUrl?.trim() || null;
  const imgSrc =
    rawPortraitUrl && !faceFailed ? wyscoutPlayerImageSrc(rawPortraitUrl) : null;

  const identityLine = [age != null ? `${age}y` : null, club, league]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "group relative flex w-full overflow-hidden rounded-xl border border-outline-variant/40 bg-surface-high text-left",
        "transition-all duration-300 hover:border-primary/35 hover:glow-primary",
      )}
    >
      {/* Left: face thumb + rank badge + club crest overlay */}
      <div className="relative flex h-[140px] w-[100px] shrink-0 items-center justify-center overflow-hidden bg-surface-mid">
        <span className="absolute left-1.5 top-1.5 z-20 flex h-[18px] min-w-[18px] items-center justify-center rounded bg-primary-deep/95 px-0.5 text-[9px] font-bold text-primary ring-1 ring-primary/35">
          {rank}
        </span>
        {imgSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imgSrc}
            alt=""
            className="h-full w-full object-cover object-[center_22%]"
            loading="lazy"
            decoding="async"
            onError={() => setFaceFailed(true)}
          />
        ) : (
          <span className="text-lg font-bold text-on-surface-variant/60">
            {name.slice(0, 2).toUpperCase()}
          </span>
        )}
        <div className="absolute bottom-1 right-1 z-20 rounded-md bg-surface-high/85 p-0.5 ring-1 ring-outline-variant/40 backdrop-blur">
          <ClubLogoImg logoUrl={clubLogoUrl} className="h-5 w-5" />
        </div>
      </div>

      {/* Right: identity + scout idx + 6 area bars */}
      <div className="flex min-w-0 flex-1 flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-on-surface">{name}</p>
            <p className="mt-0.5 truncate text-[10px] text-on-surface-variant">
              {identityLine || "—"}
            </p>
            <p className="mt-0.5 truncate text-[10px] text-on-surface-variant/85">
              {[position ?? "—", minutes != null ? `${minutes}′` : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <span className="label-caps block text-[8px] text-on-surface-variant">
              Scout idx
            </span>
            <p
              className={cn(
                "data-mono text-2xl font-bold leading-none",
                performanceIndex == null && "text-on-surface-variant",
              )}
              style={
                performanceIndex != null
                  ? { color: scoutProfileIndexColor(performanceIndex, "text") }
                  : undefined
              }
            >
              {performanceIndex != null ? performanceIndex.toFixed(1) : "—"}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="flex flex-col gap-1">
            {AREA_LEFT.map(([key, label]) => (
              <AreaBar key={key} label={label} value={areas[key]} />
            ))}
          </div>
          <div className="flex flex-col gap-1 border-l border-outline-variant/30 pl-3">
            {AREA_RIGHT.map(([key, label]) => (
              <AreaBar key={key} label={label} value={areas[key]} />
            ))}
          </div>
        </div>
      </div>
    </button>
  );
}
