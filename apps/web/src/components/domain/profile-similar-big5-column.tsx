"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { GlassCard } from "@/components/ui/glass-card";
import { api } from "@/lib/api";
import { BIG_FIVE_LEAGUES } from "@/lib/big-five";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { rolesForApi } from "@/lib/role-filters";
import { cn } from "@/lib/utils";

const MINUTES_MIN = 500;

/**
 * Same raw cosine as Replacement Finder (`similarity.toFixed(3)`).
 * Percent = similarity × 100, clamped to [0, 100] so 0.847 → 85%.
 */
export function cosineSimilarityToPercent(sim: number): number {
  const s = Number.isFinite(sim) ? sim : 0;
  return Math.round(Math.max(0, Math.min(100, s * 100)));
}

interface Props {
  wyscoutId: number;
  season: number;
  /** When false, Similar column waits (no leagues/replacement HTTP). Parent drives idle-after-profile timing. */
  deferFetch: boolean;
  /** Mirrors Replacement Finder ``defaultRole`` so candidate pool + scaler match defaults. */
  defaultRole?: string | null;
}

export function ProfileSimilarBig5Column({
  wyscoutId,
  season,
  deferFetch,
  defaultRole,
}: Props) {
  const router = useRouter();

  const rolesPayload = React.useMemo(
    () =>
      defaultRole?.trim()
        ? rolesForApi({ selectedRoles: [defaultRole.trim()], roleSubTokens: {} })
        : [],
    [defaultRole],
  );

  const leaguesQ = useQuery({
    queryKey: ["similar-big5-leagues", season],
    queryFn: async () => {
      const { data } = await api.GET("/meta/leagues", {
        params: { query: { season } },
      });
      return data ?? [];
    },
    enabled: deferFetch && Number.isFinite(wyscoutId),
  });

  const bigFiveFiltered = React.useMemo(() => {
    const avail = leaguesQ.data;
    const inSeason = BIG_FIVE_LEAGUES.filter((l) =>
      avail == null ? true : avail.includes(l),
    );
    return inSeason.length > 0 ? inSeason : [...BIG_FIVE_LEAGUES];
  }, [leaguesQ.data]);

  const repQ = useQuery({
    queryKey: ["profile-similar-big5", wyscoutId, season, bigFiveFiltered, rolesPayload],
    queryFn: async () => {
      const { data, error } = await api.POST("/replacement", {
        body: {
          target_player_id: wyscoutId,
          target_season: season,
          candidate_seasons: [season],
          candidate_filters: {
            season,
            leagues: bigFiveFiltered,
            roles: rolesPayload.length > 0 ? rolesPayload : null,
            age_min: 15,
            age_max: 42,
            minutes_min: MINUTES_MIN,
            minutes_max: null,
            contract_expires_year_min: null,
            contract_expires_year_max: null,
          },
          limit: 5,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    enabled: deferFetch && leaguesQ.isFetched && Number.isFinite(wyscoutId),
  });

  const showSkeleton = !deferFetch || repQ.isLoading;

  return (
    <GlassCard className="flex min-h-[min(520px,_100%)] flex-col">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-on-surface">Similar (Big 5)</h2>
      </div>

      {showSkeleton && (
        <div className="mx-auto flex w-full max-w-[min(420px,100%)] flex-1 flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-14 animate-pulse rounded-lg bg-white/[0.06] ring-1 ring-white/5"
              aria-hidden
            />
          ))}
        </div>
      )}
      {repQ.isError && (
        <p className="text-sm text-error">Could not load similar players.</p>
      )}
      {repQ.data && repQ.data.candidates.length === 0 && !repQ.isLoading && (
        <p className="text-sm text-on-surface-variant">
          No matches in Big 5 with current filters (try Replacement Finder below).
        </p>
      )}
      {repQ.data && repQ.data.candidates.length > 0 && (
        <ul className="mx-auto flex min-h-0 w-full max-w-[min(420px,100%)] flex-1 flex-col gap-2">
          {repQ.data.candidates.map((c) => (
            <SimilarRow
              key={`${c.wyscout_id ?? c.player}-${c.candidate_season ?? ""}`}
              candidate={c}
              season={season}
              onNavigate={(id, y) => router.push(`/scout/profile/${id}?season=${y}`)}
            />
          ))}
        </ul>
      )}
    </GlassCard>
  );
}

function SimilarPlayerPortrait({ imageUrl, initials }: { imageUrl?: string | null; initials: string }) {
  const [faceFailed, setFaceFailed] = React.useState(false);
  const portraitSrc = imageUrl && !faceFailed ? wyscoutPlayerImageSrc(imageUrl) : null;

  return portraitSrc ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={portraitSrc}
      alt=""
      width={44}
      height={44}
      className="h-full w-full object-cover"
      loading="lazy"
      decoding="async"
      onError={() => setFaceFailed(true)}
    />
  ) : (
    <span
      className="flex h-full w-full items-center justify-center text-[10px] font-bold text-on-surface-variant"
      aria-hidden
    >
      {initials}
    </span>
  );
}

function SimilarRow({
  candidate,
  season,
  onNavigate,
}: {
  candidate: {
    wyscout_id: number | null;
    player: string;
    club: string | null;
    league: string | null;
    position: string | null;
    age: number | null;
    similarity: number;
    minutes?: number | null;
    club_logo?: string | null;
    candidate_season?: number | null;
    player_image_url?: string | null;
  };
  season: number;
  onNavigate: (wyscoutId: number, profileSeason: number) => void;
}) {
  const id = candidate.wyscout_id;
  const yr = candidate.candidate_season ?? season;
  const pct = cosineSimilarityToPercent(candidate.similarity);

  const clickable = id != null && Number.isFinite(id);
  const initials = (candidate.player ?? "?").slice(0, 2).toUpperCase();

  return (
    <li>
      <button
        type="button"
        disabled={!clickable}
        onClick={() => clickable && onNavigate(id, yr)}
        className={cn(
          "flex w-full items-center gap-2.5 rounded-lg border border-outline-variant/30 bg-surface-low/40 px-2 py-2 text-left transition-colors",
          clickable
            ? "hover:border-primary/40 hover:bg-primary/10"
            : "cursor-default opacity-80",
        )}
      >
        <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-lg bg-surface-high ring-1 ring-white/10">
          {clickable ? (
            <SimilarPlayerPortrait key={id} imageUrl={candidate.player_image_url ?? null} initials={initials} />
          ) : (
            <span
              className="flex h-full w-full items-center justify-center text-[10px] font-bold text-on-surface-variant"
              aria-hidden
            >
              {initials}
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-on-surface">{candidate.player}</p>
          <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-on-surface-variant">
            <ClubLogoImg logoUrl={candidate.club_logo} className="h-4 w-4 shrink-0" />
            <span className="max-w-[7rem] truncate font-medium text-on-surface/90">
              {candidate.club ?? "—"}
            </span>
            <span className="opacity-60">·</span>
            <span className="truncate">{candidate.position ?? "—"}</span>
            <span className="opacity-60">·</span>
            <span className="shrink-0 data-mono">
              {candidate.age != null ? `${candidate.age} yrs` : "—"}
            </span>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <span className="label-caps block text-[9px] text-on-surface-variant">Similarity</span>
          <span className="data-mono text-sm font-semibold text-primary">{pct}%</span>
        </div>
      </button>
    </li>
  );
}
