"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { PercentileBar } from "@/components/charts/percentile-bar";
import { PerformanceIndexMiniChart } from "@/components/charts/performance-index-mini-chart";
import { RadarChart } from "@/components/charts/radar-chart";
import { XtvMiniChart } from "@/components/charts/xtv-mini-chart";
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

/** Bundled PI trajectory rows (GET /profile?performance_index_history_limit=…). */
const PROFILE_PI_HISTORY_EMBED = 5;
/** Bundled xTV trajectory rows (GET /profile?x_tv_history_limit=…). */
const PROFILE_XTV_HISTORY_EMBED = 5;

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
    queryKey: [
      "profile",
      wyscoutId,
      season,
      urlClub,
      PROFILE_PI_HISTORY_EMBED,
      PROFILE_XTV_HISTORY_EMBED,
    ],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/players/{wyscout_id}/profile", {
        params: {
          path: { wyscout_id: wyscoutId },
          query: {
            season,
            club: urlClub ?? undefined,
            performance_index_history_limit: PROFILE_PI_HISTORY_EMBED,
            x_tv_history_limit: PROFILE_XTV_HISTORY_EMBED,
          },
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

  const p = profileQ.data;

  const heatmapQ = useQuery({
    queryKey: ["heatmap", wyscoutId, season],
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/players/{wyscout_id}/heatmap",
        {
          params: {
            path: { wyscout_id: wyscoutId },
            query: { season },
          },
        },
      );
      if (error) {
        if (response.status === 404) return null;
        throw error;
      }
      return data ?? null;
    },
    enabled: profileQ.isSuccess && Number.isFinite(wyscoutId),
    staleTime: 60 * 60 * 1000,
  });

  const heatmapForPitch = React.useMemo(() => {
    const h = heatmapQ.data;
    if (!h || !h.points.length) return null;
    return { points: h.points, maxCount: h.max_count };
  }, [heatmapQ.data]);

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
                key={`${p.wyscout_id ?? p.player}-${p.club ?? ""}`}
                playerName={p.player}
                club={p.club}
                league={p.league}
                clubLogoUrl={p.club_logo ?? null}
                age={p.age}
                height={p.height}
                foot={p.foot ?? null}
                performanceIndex={(p.minutes ?? 0) > 500 ? p.performance_index : null}
                performanceIndexPercentile={(p.minutes ?? 0) > 500 ? (p.performance_index_percentile ?? null) : null}
                performanceIndexRoleRank={(p.minutes ?? 0) > 500 ? (p.performance_index_role_rank ?? null) : null}
                role={p.role ?? null}
                games={p.games ?? null}
                goals={p.goals ?? null}
                assists={p.assists ?? null}
                imageUrl={p.player_image_url ?? null}
                wyscoutId={p.wyscout_id ?? null}
                piHistoryPoints={p.performance_index_history ?? undefined}
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

          {((p.x_tv_history?.length ?? 0) > 0 ||
            (p.performance_index_history?.length ?? 0) > 0) && (
            <ExportSection
              id="xtv-pi-progression"
              label="xTV & performance index progression"
              defaultIncluded
            >
              <ProgressionSections
                xtvHistory={p.x_tv_history ?? null}
                piHistory={p.performance_index_history ?? null}
                showPiSeasonHeadline={(p.minutes ?? 0) > 500}
              />
            </ExportSection>
          )}

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
                heatmap={heatmapForPitch}
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

type PiHistoryRow = {
  season: number;
  performance_index: number;
  club?: string | null;
  club_logo?: string | null;
};

type XtvHistoryRow = {
  season: number;
  x_tv_eur: number;
  club?: string | null;
  club_logo?: string | null;
};

function fmtEurCompact(n: number): string {
  if (n >= 1e6) {
    const m = n / 1e6;
    return m >= 10 ? `€${m.toFixed(0)}M` : `€${m.toFixed(1)}M`;
  }
  if (n >= 1e3) return `€${(n / 1e3).toFixed(0)}k`;
  return `€${Math.round(n)}`;
}

function deltaLabel(curr: number, prev: number, formatter: (n: number) => string): {
  text: string;
  up: boolean;
} | null {
  const d = curr - prev;
  if (!Number.isFinite(d) || Math.abs(d) < 1e-9) return null;
  const sign = d > 0 ? "+" : "−";
  return { text: `${sign}${formatter(Math.abs(d))} YoY`, up: d > 0 };
}

function ProgressionSections({
  xtvHistory,
  piHistory,
  showPiSeasonHeadline,
}: {
  xtvHistory: XtvHistoryRow[] | null;
  piHistory: PiHistoryRow[] | null;
  /** Current-season minutes; below radar threshold we hide PI value + YoY (chart stays). */
  showPiSeasonHeadline: boolean;
}) {
  const hasXtv = (xtvHistory?.length ?? 0) > 0;
  const hasPi = (piHistory?.length ?? 0) > 0;
  if (!hasXtv && !hasPi) return null;

  const xtvLast = hasXtv ? xtvHistory![xtvHistory!.length - 1]!.x_tv_eur : null;
  const xtvPrev =
    hasXtv && xtvHistory!.length >= 2
      ? xtvHistory![xtvHistory!.length - 2]!.x_tv_eur
      : null;
  const xtvDelta =
    xtvLast != null && xtvPrev != null ? deltaLabel(xtvLast, xtvPrev, fmtEurCompact) : null;

  const piLast = hasPi ? piHistory![piHistory!.length - 1]!.performance_index : null;
  const piPrev =
    hasPi && piHistory!.length >= 2
      ? piHistory![piHistory!.length - 2]!.performance_index
      : null;
  const piColor =
    piLast != null ? scoutProfileIndexColor(piLast, "text") : undefined;
  const piDelta =
    piLast != null && piPrev != null
      ? deltaLabel(piLast, piPrev, (n) => n.toFixed(1))
      : null;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <GlassCard>
        <p className="label-caps mb-2">xTV progression</p>
        {hasXtv ? (
          <>
            <div className="flex items-baseline gap-3">
              <p className="data-mono text-2xl text-on-surface">
                {fmtEurCompact(xtvLast!)}
              </p>
              {xtvDelta ? (
                <span
                  className="data-mono text-sm font-semibold"
                  style={{
                    color: xtvDelta.up
                      ? "var(--color-success, #34d399)"
                      : "var(--color-error, #f87171)",
                  }}
                >
                  {xtvDelta.up ? "▲" : "▼"} {xtvDelta.text}
                </span>
              ) : null}
            </div>
            <div className="mt-3">
              <XtvMiniChart points={xtvHistory!} />
            </div>
          </>
        ) : (
          <p className="text-sm text-on-surface-variant">No Market Value data available</p>
        )}
      </GlassCard>
      <GlassCard>
        <p className="label-caps mb-2">Performance index progression</p>
        {hasPi ? (
          <>
            {showPiSeasonHeadline ? (
              <div className="flex items-baseline gap-3">
                <p
                  className="data-mono text-2xl"
                  style={piColor != null ? { color: piColor } : undefined}
                >
                  {piLast!.toFixed(1)}
                </p>
                {piDelta ? (
                  <span
                    className="data-mono text-sm font-semibold"
                    style={{
                      color: piDelta.up
                        ? "var(--color-success, #34d399)"
                        : "var(--color-error, #f87171)",
                    }}
                  >
                    {piDelta.up ? "▲" : "▼"} {piDelta.text}
                  </span>
                ) : null}
              </div>
            ) : null}
            <div className={cn(showPiSeasonHeadline && "mt-3")}>
              <PerformanceIndexMiniChart points={piHistory!} />
            </div>
          </>
        ) : (
          <p className="text-sm text-on-surface-variant">No PI history.</p>
        )}
      </GlassCard>
    </div>
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
