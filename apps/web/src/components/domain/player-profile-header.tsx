"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { PerformanceIndexMiniChart, type PiHistoryPoint } from "@/components/charts/performance-index-mini-chart";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { cn } from "@/lib/utils";

function fmtStat(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const r = Math.round(n);
  if (Math.abs(n - r) < 1e-6) return String(r);
  return n.toFixed(1);
}

/** Neutral chip: slightly darker than glass card, no accent colour. */
const headerStatChipClass =
  "border-outline-variant/45 bg-surface-low/90 font-normal text-on-surface-variant";

/** Wyscout-style foot → lowercase label, e.g. "left foot". */
function formatFootBadge(raw: string): string {
  const s = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!s) return "";
  if (/\bboth\b|ambidextrous/.test(s)) return "both feet";
  if (/\bleft\b/.test(s)) return "left foot";
  if (/\bright\b/.test(s)) return "right foot";
  const cleaned = s.replace(/\b(feet|foot)\b/g, "").trim();
  if (!cleaned) return "";
  return `${cleaned} foot`;
}

interface Props {
  playerName: string;
  club: string | null;
  league: string | null;
  clubLogoUrl: string | null;
  age: number | null;
  height: number | null;
  foot: string | null;
  performanceIndex: number | null;
  performanceIndexPercentile: number | null;
  games: number | null;
  goals: number | null;
  assists: number | null;
  imageUrl: string | null;
  /** Used for Wyscout public CDN portrait when ``imageUrl`` is empty (same as rankings cards). */
  wyscoutId?: number | null;
  /** Loaded seasons trajectory (omit when not applicable). */
  piHistoryPoints?: PiHistoryPoint[];
  piHistoryLoading?: boolean;
  className?: string;
}

export function PlayerProfileHeader({
  playerName,
  club,
  league,
  clubLogoUrl,
  age,
  height,
  foot,
  performanceIndex,
  games,
  goals,
  assists,
  imageUrl,
  wyscoutId,
  piHistoryPoints,
  piHistoryLoading,
  className,
}: Props) {
  const [faceFailed, setFaceFailed] = React.useState(false);
  const faceKey = `${imageUrl ?? ""}::${wyscoutId ?? ""}`;
  const [prevFaceKey, setPrevFaceKey] = React.useState(faceKey);
  if (prevFaceKey !== faceKey) {
    setPrevFaceKey(faceKey);
    setFaceFailed(false);
  }

  const rawPortraitUrl = imageUrl?.trim() || null;
  const imgSrc =
    rawPortraitUrl && !faceFailed ? wyscoutPlayerImageSrc(rawPortraitUrl) : null;

  const clubLogoTrimmed = clubLogoUrl?.trim();
  const footLabel = foot != null && foot.trim() !== "" ? formatFootBadge(foot) : "";

  const showPiHistory =
    piHistoryLoading === true ||
    (Array.isArray(piHistoryPoints) && piHistoryPoints.length > 0);

  return (
    <GlassCard className={cn(className)}>
      <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-6 sm:flex-row sm:items-start">
          <div className="flex shrink-0 justify-center sm:justify-start">
          {imgSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imgSrc}
              alt=""
              width={112}
              height={112}
              className="h-28 w-28 rounded-2xl object-cover ring-1 ring-white/10"
              loading="lazy"
              decoding="async"
              onError={() => setFaceFailed(true)}
            />
          ) : (
            <div
              className="flex h-28 w-28 items-center justify-center rounded-2xl bg-surface-high text-2xl font-bold text-on-surface-variant ring-1 ring-white/10"
              aria-hidden
            >
              {playerName.slice(0, 2).toUpperCase()}
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-on-surface">{playerName}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-on-surface-variant">
              {clubLogoTrimmed ? (
                <ClubLogoImg logoUrl={clubLogoTrimmed} className="h-8 w-8" />
              ) : null}
              <span>{[club ?? "—", league ?? "—"].filter(Boolean).join(" · ")}</span>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {age != null && (
                <Badge variant="muted" className={headerStatChipClass}>
                  {age} yrs
                </Badge>
              )}
              {height != null && (
                <Badge variant="muted" className={headerStatChipClass}>
                  {height} cm
                </Badge>
              )}
              {footLabel !== "" && (
                <Badge variant="muted" className={headerStatChipClass}>
                  {footLabel}
                </Badge>
              )}
            </div>
          </div>

          <div className="grid gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
            <div>
              <p className="label-caps mb-1">Performance index</p>
              <p
                className={cn(
                  "data-mono text-3xl",
                  performanceIndex == null && "text-secondary",
                )}
                style={
                  performanceIndex != null
                    ? { color: scoutProfileIndexColor(performanceIndex, "text") }
                    : undefined
                }
              >
                {performanceIndex?.toFixed(1) ?? "—"}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center sm:text-left">
              <div>
                <p className="label-caps mb-0.5">Games</p>
                <p className="data-mono text-xl text-on-surface">{fmtStat(games)}</p>
              </div>
              <div>
                <p className="label-caps mb-0.5">Goals</p>
                <p className="data-mono text-xl text-on-surface">{fmtStat(goals)}</p>
              </div>
              <div>
                <p className="label-caps mb-0.5">Assists</p>
                <p className="data-mono text-xl text-on-surface">{fmtStat(assists)}</p>
              </div>
            </div>
          </div>
        </div>
        </div>

        {showPiHistory ? (
          <div className="flex w-full shrink-0 justify-center sm:justify-end lg:w-auto lg:min-w-[10.5rem] lg:justify-end">
            {piHistoryLoading ? (
              <div
                className="h-[9.5rem] w-full max-w-[16rem] animate-pulse rounded-xl bg-white/[0.06] ring-1 ring-white/5"
                aria-hidden
              />
            ) : (
              <PerformanceIndexMiniChart points={piHistoryPoints ?? []} />
            )}
          </div>
        ) : null}
      </div>
    </GlassCard>
  );
}
