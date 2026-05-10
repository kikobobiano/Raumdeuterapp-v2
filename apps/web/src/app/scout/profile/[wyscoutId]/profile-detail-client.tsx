"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { PercentileBar } from "@/components/charts/percentile-bar";
import { RadarChart } from "@/components/charts/radar-chart";
import { PlayerPositionPitch } from "@/components/domain/player-position-pitch";
import { PlayerProfileHeader } from "@/components/domain/player-profile-header";
import { PlayerTraitsBlock } from "@/components/domain/player-traits-block";
import { ProfileComparePanel } from "@/components/domain/profile-compare-panel";
import { ProfileProgressionPanel } from "@/components/domain/profile-progression-panel";
import { ProfileReplacementPanel } from "@/components/domain/profile-replacement-panel";
import { ProfileSimilarBig5Column } from "@/components/domain/profile-similar-big5-column";
import { ProfileTranslationPanel } from "@/components/domain/profile-translation-panel";
import { ExportButton, ExportProvider, ExportSection } from "@/components/export";
import { ProfileHeaderSkeleton } from "@/components/skeletons/profile-header-skeleton";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useIdleReady } from "@/hooks/use-idle-ready";
import { api } from "@/lib/api";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { useProfilePrefs } from "@/lib/profile-prefs";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { DEFAULT_SEASON, useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

function buildExportFilename(player: string | undefined | null, season: number): string {
  const base = player
    ? player.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
    : "player";
  const seasonLabel = `${String(season).slice(2)}-${String(season + 1).slice(2)}`;
  return `${base || "player"}-profile-${seasonLabel}.png`;
}

function resolveSeason(
  urlSeason: string | null,
  globalSeason: number,
  list: number[] | undefined,
): number {
  let y =
    urlSeason != null && urlSeason !== ""
      ? Number(urlSeason)
      : globalSeason;
  if (Number.isNaN(y)) y = globalSeason;
  if (list && list.length > 0 && !list.includes(y)) {
    y = list.includes(DEFAULT_SEASON) ? DEFAULT_SEASON : list[0];
  }
  return y;
}

export function ProfileDetailClient() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const globalSeason = useGlobalFilters((s) => s.season);
  const urlSeason = searchParams.get("season");
  const urlClub = searchParams.get("club");

  const rawId = params.wyscoutId;
  const wyscoutId = typeof rawId === "string" ? Number(rawId) : Number.NaN;

  const buildHref = React.useCallback(
    (id: number, year: number, club?: string | null) => {
      const qp = new URLSearchParams();
      qp.set("season", String(year));
      if (club) qp.set("club", club);
      return `/scout/profile/${id}?${qp.toString()}`;
    },
    [],
  );

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  const list = seasonsQ.data;
  const season = React.useMemo(
    () => resolveSeason(urlSeason, globalSeason, list),
    [urlSeason, globalSeason, list],
  );
  const seasonsReadyNotEmpty =
    seasonsQ.isFetched && (list?.length ?? 0) > 0;
  const seasonProbablyValid = list?.includes(season) ?? true;
  const profileQueriesEnabled =
    Number.isFinite(wyscoutId) &&
    (!seasonsReadyNotEmpty || seasonProbablyValid);

  const profileQ = useQuery({
    queryKey: ["profile", wyscoutId, season, urlClub],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/players/{wyscout_id}/profile", {
        params: {
          path: { wyscout_id: wyscoutId },
          query: { season, club: urlClub ?? undefined },
        },
      });
      if (error) {
        const e = Object.assign(new Error(JSON.stringify(error)), { status: response.status });
        throw e;
      }
      return data!;
    },
    enabled: profileQueriesEnabled,
  });

  const piHistoryQ = useQuery({
    queryKey: ["performance-index-history", wyscoutId, season],
    queryFn: async () => {
      const { data, error } = await api.GET("/players/{wyscout_id}/performance-index-history", {
        params: {
          path: { wyscout_id: wyscoutId },
          query: { season, limit: 5 },
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    enabled: profileQueriesEnabled,
  });

  const p = profileQ.data;

  const similarDeferGate = profileQ.isSuccess && !profileQ.isFetching;
  const similarFetchReady = useIdleReady(similarDeferGate);
  const showProfileSkeleton = useDelayedLoading(profileQ.isPending);
  const exportTitle = p?.player ?? "Player profile";
  const exportFilename = buildExportFilename(p?.player, season);

  React.useEffect(() => {
    const wid = profileQ.data?.wyscout_id;
    if (wid != null && Number.isFinite(wid)) {
      useProfilePrefs.getState().setLastWyscoutId(wid);
    }
  }, [profileQ.data?.wyscout_id]);

  if (!Number.isFinite(wyscoutId)) {
    return (
      <GlassCard>
        <p className="text-error">Invalid player id.</p>
        <Link href="/scout/profile" className="mt-2 inline-block text-sm text-primary hover:underline">
          ← Profile
        </Link>
      </GlassCard>
    );
  }

  return (
    <ExportProvider title={exportTitle} filename={exportFilename}>
    <div className="space-y-6">
      <div className="flex justify-end">
        <ExportButton />
      </div>

      {showProfileSkeleton && <ProfileHeaderSkeleton />}

      {profileQ.isError && (() => {
        const status = (profileQ.error as Error & { status?: number })?.status;
        const seasonLabel = `${String(season).slice(2)}-${String(season + 1).slice(2)}`;
        if (status === 404 || status === 422) {
          return (
            <GlassCard className="flex flex-col items-center gap-3 py-12 text-center">
              <p className="text-base font-semibold text-content">No data for {seasonLabel}</p>
              <p className="text-sm text-content-muted max-w-xs">
                This player has no recorded stats for the {seasonLabel} season. Try selecting a different season above.
              </p>
            </GlassCard>
          );
        }
        return (
          <GlassCard>
            <p className="text-error">Could not load this profile.</p>
          </GlassCard>
        );
      })()}

      {p && (
        <div className="space-y-6">
          <ExportSection id="header" label="Player header" required defaultIncluded>
            <div className="space-y-6">
              <PlayerProfileHeader
                key={p.wyscout_id ?? p.player}
                playerName={p.player}
                club={p.club}
                league={p.league}
                clubLogoUrl={p.club_logo ?? null}
                age={p.age}
                height={p.height}
                foot={p.foot ?? null}
                performanceIndex={p.performance_index}
                performanceIndexPercentile={p.performance_index_percentile ?? null}
                games={p.games ?? null}
                goals={p.goals ?? null}
                assists={p.assists ?? null}
                imageUrl={p.player_image_url ?? null}
                wyscoutId={p.wyscout_id ?? null}
                piHistoryPoints={piHistoryQ.data?.points}
                piHistoryLoading={piHistoryQ.isLoading}
              />

              {(p.clubs_in_season?.length ?? 0) > 1 && (
                <ClubSwitcher
                  stints={p.clubs_in_season ?? []}
                  activeClub={p.club ?? null}
                  onSelect={(c) => router.replace(buildHref(wyscoutId, season, c))}
                />
              )}
            </div>
          </ExportSection>

          <ExportSection id="overview" label="Radar, positions & similar" defaultIncluded>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:gap-6">
            <GlassCard className="min-w-0">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-on-surface">Radar</h2>
                <Badge variant="primary">{p.minutes ?? 0}&apos;</Badge>
              </div>
              <div className="flex justify-center">
                <RadarChart
                  metrics={p.radar.map((m) => ({
                    label: m.label,
                    percentile: m.percentile,
                    value: m.value,
                  }))}
                  size={400}
                />
              </div>
            </GlassCard>

            <GlassCard className="min-w-0">
              <h2 className="mb-4 text-lg font-semibold text-on-surface">Positions</h2>
              <PlayerPositionPitch
                primaryTokens={p.position_tokens_primary ?? (p.position_tokens ?? [])}
                secondaryTokens={p.position_tokens_secondary ?? []}
              />
            </GlassCard>

            {p.wyscout_id != null && Number.isFinite(p.wyscout_id) ? (
              <ProfileSimilarBig5Column
                wyscoutId={p.wyscout_id}
                season={season}
                defaultRole={p.role ?? null}
                deferFetch={similarFetchReady}
              />
            ) : (
              <GlassCard className="min-w-0">
                <h2 className="mb-4 text-lg font-semibold text-on-surface">Similar (Big 5)</h2>
                <p className="text-sm text-on-surface-variant">
                  Missing Wyscout id for this profile.
                </p>
              </GlassCard>
            )}
          </div>
          </ExportSection>

          {(p.game_areas?.length ?? 0) > 0 && (
            <ExportSection id="breakdown" label="Game area breakdown" defaultIncluded>
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-on-surface">Game area breakdown</h2>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
                {[p.game_areas!.slice(0, 3), p.game_areas!.slice(3, 6)].map((column, colIdx) => (
                  <div key={colIdx} className="space-y-6">
                    {column.map((block) => (
                      <GlassCard key={block.area}>
                        <div className="flex flex-col gap-5 xl:flex-row xl:items-stretch">
                          <div className="flex w-full shrink-0 flex-col justify-center border-b border-white/10 pb-4 xl:w-40 xl:border-b-0 xl:border-r xl:pb-0 xl:pr-5">
                            <p className="label-caps mb-1">{block.area}</p>
                            <p className="text-sm text-on-surface-variant">{block.index.label}</p>
                            <p
                              className={cn(
                                "data-mono mt-2 text-3xl",
                                block.index.value == null &&
                                  block.index.percentile == null &&
                                  "text-secondary",
                              )}
                              style={
                                block.index.value != null || block.index.percentile != null
                                  ? {
                                      color: scoutProfileIndexColor(
                                        block.index.value ?? block.index.percentile,
                                        "text",
                                      ),
                                    }
                                  : undefined
                              }
                            >
                              {block.index.value?.toFixed(1) ?? "—"}
                            </p>
                            {block.index.percentile != null ? (
                              <p
                                className="mt-1 text-xs"
                                style={{
                                  color: scoutProfileIndexColor(block.index.percentile, "text"),
                                  opacity: 0.85,
                                }}
                              >
                                {`${Math.round(block.index.percentile)}p in league`}
                              </p>
                            ) : null}
                          </div>
                          <div className="min-w-0 flex-1 space-y-3">
                            {block.metrics.map((m) => (
                              <PercentileBar
                                key={`${block.area}-${m.metric}`}
                                label={m.label}
                                value={m.value}
                                percentile={m.percentile}
                                variant="profileBands"
                              />
                            ))}
                          </div>
                        </div>
                      </GlassCard>
                    ))}
                  </div>
                ))}
              </div>
            </div>
            </ExportSection>
          )}

          <ExportSection id="traits" label="Player traits" defaultIncluded>
            <PlayerTraitsBlock traits={p.traits ?? []} />
          </ExportSection>

          <ProfileComparePanel
            primaryName={p.player}
            primaryPosition={p.position ?? null}
            primaryRadar={p.radar}
            primaryTable={p.table}
            season={season}
          />

          {p.wyscout_id != null && (
            <ProfileProgressionPanel
              key={`progression-${p.wyscout_id}-${season}`}
              wyscoutId={p.wyscout_id}
              targetSeason={season}
              playerImageUrl={p.player_image_url ?? null}
            />
          )}

          {p.wyscout_id != null && (
            <ProfileReplacementPanel
              key={`replacement-${p.wyscout_id}-${season}`}
              wyscoutId={p.wyscout_id}
              season={season}
              defaultRole={p.role ?? null}
            />
          )}

          {p.wyscout_id != null && (
            <ProfileTranslationPanel wyscoutId={p.wyscout_id} season={season} playerImageUrl={p.player_image_url ?? null} />
          )}
        </div>
      )}
    </div>
    </ExportProvider>
  );
}

interface ClubStint {
  club: string;
  minutes?: number | null;
  club_logo?: string | null;
}

function ClubSwitcher({
  stints,
  activeClub,
  onSelect,
}: {
  stints: ClubStint[];
  activeClub: string | null;
  onSelect: (club: string) => void;
}) {
  return (
    <GlassCard className="!py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="label-caps mr-1">Clubs this season</span>
        {stints.map((s) => {
          const active = s.club === activeClub;
          return (
            <button
              key={s.club}
              type="button"
              onClick={() => onSelect(s.club)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs transition-colors",
                active
                  ? "border-primary/60 bg-primary/15 text-primary"
                  : "border-outline-variant/60 text-on-surface-variant hover:bg-surface-mid",
              )}
            >
              <span>{s.club}</span>
              {s.minutes != null && (
                <span className="data-mono text-[10px] opacity-75">
                  {s.minutes}&apos;
                </span>
              )}
            </button>
          );
        })}
      </div>
    </GlassCard>
  );
}
