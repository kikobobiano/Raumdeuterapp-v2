"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import type { PiHistoryPoint } from "@/components/charts/performance-index-mini-chart";
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

const headerStatChipClass =
  "border-outline-variant/45 bg-surface-low/90 font-normal text-on-surface-variant";

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
  /** 1-based rank among same-role peers in the percentile cohort. */
  performanceIndexRoleRank: number | null;
  /** Role label used for "Top N {role}s" (already pluralizable). */
  role: string | null;
  games: number | null;
  goals: number | null;
  assists: number | null;
  imageUrl: string | null;
  wyscoutId?: number | null;
  /** Used to derive the PI YoY delta shown inside the hero card. */
  piHistoryPoints?: PiHistoryPoint[];
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
  performanceIndexPercentile,
  performanceIndexRoleRank,
  role,
  games,
  goals,
  assists,
  imageUrl,
  wyscoutId,
  piHistoryPoints,
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

  const piColor =
    performanceIndex != null
      ? scoutProfileIndexColor(performanceIndex, "text")
      : undefined;

  const piDelta = React.useMemo(() => {
    if (!piHistoryPoints || piHistoryPoints.length < 2) return null;
    const last = piHistoryPoints[piHistoryPoints.length - 1]!.performance_index;
    const prev = piHistoryPoints[piHistoryPoints.length - 2]!.performance_index;
    if (!Number.isFinite(last) || !Number.isFinite(prev)) return null;
    return last - prev;
  }, [piHistoryPoints]);

  const subLine = React.useMemo(() => {
    if (performanceIndexRoleRank != null && role) {
      const plural = role.endsWith("s") ? role : `${role}s`;
      return `Top ${performanceIndexRoleRank} League ${plural}`;
    }
    if (performanceIndexPercentile != null) {
      return `Percentile ${Math.round(performanceIndexPercentile)}`;
    }
    return null;
  }, [performanceIndexRoleRank, role, performanceIndexPercentile]);

  return (
    <GlassCard className={cn(className)}>
      {/* Top row: face + identity (flex-1) + PI hero card */}
      <div className="flex flex-col gap-6 lg:flex-row lg:items-stretch">
        <div className="flex min-w-0 flex-1 items-start gap-5">
          {imgSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imgSrc}
              alt=""
              width={112}
              height={112}
              className="h-28 w-28 shrink-0 rounded-2xl object-cover ring-1 ring-white/10"
              loading="lazy"
              decoding="async"
              onError={() => setFaceFailed(true)}
            />
          ) : (
            <div
              className="flex h-28 w-28 shrink-0 items-center justify-center rounded-2xl bg-surface-high text-2xl font-bold text-on-surface-variant ring-1 ring-white/10"
              aria-hidden
            >
              {playerName.slice(0, 2).toUpperCase()}
            </div>
          )}

          <div className="min-w-0 flex-1">
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
        </div>

        {/* PI hero card */}
        <div
          className="flex w-full shrink-0 flex-col justify-center gap-2 rounded-2xl border p-5 lg:w-[16rem]"
          style={{
            borderColor: piColor != null ? `${piColor}55` : "rgba(255,255,255,0.10)",
            borderLeftWidth: 3,
            borderLeftColor: piColor ?? "rgba(255,255,255,0.10)",
            background:
              piColor != null
                ? `linear-gradient(135deg, ${piColor}1A, ${piColor}05)`
                : "rgba(255,255,255,0.03)",
          }}
        >
          <p className="label-caps">Performance index</p>
          <div className="flex items-baseline gap-3">
            <p
              className={cn(
                "data-mono text-5xl leading-none",
                performanceIndex == null && "text-secondary",
              )}
              style={piColor != null ? { color: piColor } : undefined}
            >
              {performanceIndex?.toFixed(1) ?? "—"}
            </p>
            {piDelta != null && Math.abs(piDelta) >= 0.05 && performanceIndex != null ? (
              <span
                className="data-mono text-sm font-semibold"
                style={{
                  color:
                    piDelta > 0
                      ? "var(--color-success, #34d399)"
                      : "var(--color-error, #f87171)",
                }}
                title="Δ vs previous season"
              >
                {piDelta > 0 ? "▲" : "▼"} {(piDelta > 0 ? "+" : "−") + Math.abs(piDelta).toFixed(1)}
              </span>
            ) : null}
          </div>
          {subLine ? (
            <p className="text-xs text-on-surface-variant">{subLine}</p>
          ) : null}
        </div>
      </div>

      {/* Bottom row: full-width stats */}
      <div className="mt-5 flex flex-wrap items-end gap-x-10 gap-y-3 border-t border-white/10 pt-4">
        <div>
          <p className="label-caps mb-1">Games</p>
          <p className="data-mono text-2xl text-on-surface">{fmtStat(games)}</p>
        </div>
        <div>
          <p className="label-caps mb-1">Goals</p>
          <p className="data-mono text-2xl text-on-surface">{fmtStat(goals)}</p>
        </div>
        <div>
          <p className="label-caps mb-1">Assists</p>
          <p className="data-mono text-2xl text-on-surface">{fmtStat(assists)}</p>
        </div>
      </div>
    </GlassCard>
  );
}
