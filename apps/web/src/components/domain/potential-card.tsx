"use client";

import * as React from "react";

import { potentialDotColor } from "@/components/charts/quadrant-chart";
import { GlassCard } from "@/components/ui/glass-card";
import { wyscoutClubLogoSrc, wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { cn } from "@/lib/utils";

export interface PotentialCardData {
  wyscoutId: number | null;
  player: string;
  club: string | null;
  clubLogo: string | null;
  league: string | null;
  age: number | null;
  minutes: number | null;
  currentPi: number | null;
  potentialScore: number;
  playerImageUrl: string | null;
  rank: number;
}

interface Props {
  data: PotentialCardData;
  onClick?: () => void;
}

const PRIMARY = "#14d1ff";

export function PotentialCard({ data, onClick }: Props) {
  const [imgFailed, setImgFailed] = React.useState(false);
  const [logoFailed, setLogoFailed] = React.useState(false);

  const portrait = (() => {
    if (imgFailed) return null;
    if (data.playerImageUrl) return wyscoutPlayerImageSrc(data.playerImageUrl);
    return null;
  })();

  const logo = data.clubLogo && !logoFailed ? wyscoutClubLogoSrc(data.clubLogo) : null;
  const potColor = potentialDotColor(data.potentialScore);
  const piRaw = (data.minutes ?? 0) > 500 ? (data.currentPi ?? null) : null;
  const pi = piRaw ?? 0;
  const gap = Math.max(0, data.potentialScore - pi);

  return (
    <GlassCard
      className={cn(
        "group cursor-pointer transition-all hover:!bg-surface-mid/40 hover:scale-[1.01]",
        "!p-3",
      )}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        {/* Rank */}
        <div className="grid h-12 w-7 place-items-center text-2xl font-bold tabular-nums text-on-surface-variant">
          {data.rank}
        </div>

        {/* Portrait */}
        <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-md bg-surface-mid">
          {portrait ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={portrait}
              alt={data.player}
              className="h-full w-full object-cover"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <div className="grid h-full w-full place-items-center text-xs text-on-surface-variant">
              {data.player.split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </div>
          )}
        </div>

        {/* Player info + bar */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-on-surface">
                {data.player}
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-on-surface-variant">
                {logo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={logo}
                    alt=""
                    width={12}
                    height={12}
                    className="shrink-0 object-contain"
                    onError={() => setLogoFailed(true)}
                  />
                ) : (
                  <span className="h-3 w-3 shrink-0 rounded-sm bg-outline-variant/40" />
                )}
                <span className="truncate">{data.club ?? "—"}</span>
                <span className="opacity-60">·</span>
                <span className="truncate">{data.league ?? ""}</span>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="data-mono text-lg font-bold leading-none" style={{ color: potColor }}>
                {data.potentialScore.toFixed(1)}
              </div>
              <div className="mt-0.5 text-[9px] uppercase tracking-wider text-on-surface-variant">
                Potential
              </div>
            </div>
          </div>

          {/* Gap bar: PI → Potential */}
          <div className="mt-2">
            <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface-mid">
              {/* PI fill */}
              <div
                className="absolute left-0 top-0 h-full rounded-full"
                style={{
                  width: `${pi}%`,
                  backgroundColor: PRIMARY,
                  opacity: 0.85,
                }}
              />
              {/* Gap zone (PI to Potential) */}
              <div
                className="absolute top-0 h-full"
                style={{
                  left: `${pi}%`,
                  width: `${gap}%`,
                  background: `repeating-linear-gradient(90deg, ${potColor}55 0 2px, transparent 2px 4px)`,
                }}
              />
              {/* Potential marker */}
              <div
                className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2"
                style={{
                  left: `calc(${data.potentialScore}% - 1px)`,
                  backgroundColor: potColor,
                }}
              />
            </div>
            <div className="mt-1 flex justify-between text-[10px] data-mono text-on-surface-variant">
              <span>
                Age {data.age ?? "—"} · {data.minutes ?? 0}&apos;
              </span>
              <span>
                {piRaw != null ? (
                  <>
                    <span style={{ color: PRIMARY }}>PI {pi.toFixed(1)}</span>
                    <span className="mx-1 opacity-60">→</span>
                    <span style={{ color: potColor }}>+{gap.toFixed(1)}</span>
                  </>
                ) : (
                  <span className="opacity-40">PI —</span>
                )}
              </span>
            </div>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
