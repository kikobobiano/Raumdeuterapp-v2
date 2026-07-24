"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, PanelLeft, PanelLeftClose } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { FilterPanel } from "@/components/domain/filter-panel";
import { FiltersSubtitleLine } from "@/components/domain/filters-subtitle-line";
import { TopPlayerCard } from "@/components/domain/top-player-card";
import {
  ExportButton,
  ExportFilterArea,
  ExportProvider,
  ExportSection,
} from "@/components/export";
import { RankingsTableSkeleton } from "@/components/skeletons/rankings-table-skeleton";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useFiltersSubtitle } from "@/hooks/use-filters-subtitle";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { rolesForApi } from "@/lib/role-filters";
import { DEFAULT_SEASON, useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 21;

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

function parsePage(searchParams: URLSearchParams): number {
  const raw = Number(searchParams.get("page"));
  if (!Number.isFinite(raw) || raw < 1) return 1;
  return Math.floor(raw);
}

export function RankingsIndexClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();
  const urlSeason = searchParams.get("season");

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  const list = seasonsQ.data;
  const season = React.useMemo(
    () => resolveSeason(urlSeason, f.season, list),
    [urlSeason, f.season, list],
  );

  const page = React.useMemo(() => parsePage(searchParams), [searchParams]);
  const offset = (page - 1) * PAGE_SIZE;

  const filterSig = React.useMemo(
    () =>
      `${f.leagues.join(",")}:${f.clubs.join(",")}:${rolesForApi({
        selectedRoles: f.selectedRoles,
        roleSubTokens: f.roleSubTokens,
      }).join(";")}:${f.ageMin}:${f.ageMax}:${f.minutesMin}`,
    [f.leagues, f.clubs, f.selectedRoles, f.roleSubTokens, f.ageMin, f.ageMax, f.minutesMin],
  );
  const prevFilterSig = React.useRef(filterSig);

  React.useEffect(() => {
    if (prevFilterSig.current !== filterSig) {
      prevFilterSig.current = filterSig;
      if (page > 1) {
        const sp = new URLSearchParams(searchParams.toString());
        sp.delete("page");
        router.replace(`/scout/rankings?${sp.toString()}`);
      }
    }
  }, [filterSig, page, router, searchParams]);

  const setPageUrl = React.useCallback(
    (next: number) => {
      const sp = new URLSearchParams(searchParams.toString());
      if (next <= 1) {
        sp.delete("page");
      } else {
        sp.set("page", String(next));
      }
      router.push(`/scout/rankings?${sp.toString()}`);
    },
    [router, searchParams],
  );

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const rankingsQ = useQuery({
    queryKey: [
      "top-performance",
      season,
      f.leagues,
      f.clubs,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      page,
    ],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/players/top-performance", {
        params: {
          query: {
            season,
            minutes_min: f.minutesMin,
            limit: PAGE_SIZE,
            offset,
            leagues: f.leagues.length ? f.leagues : undefined,
            teams: f.clubs.length ? f.clubs : undefined,
            roles: rolesPayload.length ? rolesPayload : undefined,
            age_min: f.ageMin,
            age_max: f.ageMax,
          },
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data ?? { items: [], total: 0 };
    },
    enabled: (list ?? []).includes(season),
    placeholderData: keepPreviousData,
  });

  const showRankingsSkeleton = useDelayedLoading(rankingsQ.isPending);

  const total = rankingsQ.data?.total ?? 0;
  const items = rankingsQ.data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  React.useEffect(() => {
    if (!rankingsQ.isSuccess || total === 0) return;
    if (page > totalPages) {
      setPageUrl(totalPages);
    }
  }, [rankingsQ.isSuccess, total, totalPages, page, setPageUrl]);

  const startRank = offset + 1;

  const subtitlePrefix =
    total > 0
      ? `${total} players · Page ${Math.min(page, totalPages)} of ${totalPages}`
      : "—";
  const subtitle = useFiltersSubtitle({ prefix: subtitlePrefix });

  return (
    <ExportProvider title="Top performance index" filename={`rankings-${String(season).slice(2)}-${String(season + 1).slice(2)}.png`}>
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1.5 text-on-surface-variant hover:text-on-surface"
          onClick={() => setFiltersOpen(!filtersOpen)}
          aria-expanded={filtersOpen}
          aria-controls="scout-filters-panel"
        >
          {filtersOpen ? (
            <>
              <PanelLeftClose className="h-4 w-4" />
              Hide filters
            </>
          ) : (
            <>
              <PanelLeft className="h-4 w-4" />
              Show filters
            </>
          )}
        </Button>
        <ExportButton />
      </div>

      <div className={cn("grid gap-6", filtersOpen ? "lg:grid-cols-[280px_1fr]" : "grid-cols-1")}>
        {filtersOpen ? (
          <GlassCard id="scout-filters-panel">
            <FilterPanel hideSeason />
          </GlassCard>
        ) : null}

        <ExportSection id="cards" label="Rankings cards" required defaultIncluded>
        <section className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 flex-1">
              <h2 className="label-caps">Top performance index</h2>
              <FiltersSubtitleLine size="xs">{subtitle}</FiltersSubtitleLine>
            </div>
            {total > PAGE_SIZE && (
              <ExportFilterArea className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2"
                  disabled={page <= 1 || rankingsQ.isFetching}
                  onClick={() => setPageUrl(page - 1)}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="data-mono px-1 text-xs text-on-surface-variant">
                  {Math.min(page, totalPages)} / {totalPages}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2"
                  disabled={page >= totalPages || rankingsQ.isFetching}
                  onClick={() => setPageUrl(page + 1)}
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </ExportFilterArea>
            )}
          </div>

          {showRankingsSkeleton ? (
            <RankingsTableSkeleton withFilters={filtersOpen} count={PAGE_SIZE} />
          ) : rankingsQ.isError ? (
            <p className="text-sm text-error">Could not load rankings.</p>
          ) : items.filter((r) => r.wyscout_id != null).length === 0 ? (
            <p className="text-sm text-on-surface-variant">
              No players matched the current filters.
            </p>
          ) : (
            <div
              data-export-grid="3"
              className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3"
            >
              {items
                .filter((r) => r.wyscout_id != null)
                .map((row, i) => (
                  <TopPlayerCard
                    key={`rk-${season}-${page}-${row.wyscout_id}`}
                    rank={startRank + i}
                    wyscoutId={row.wyscout_id!}
                    name={row.player}
                    club={row.club ?? null}
                    league={row.league ?? null}
                    age={row.age ?? null}
                    position={row.position ?? null}
                    minutes={row.minutes ?? null}
                    performanceIndex={row.performance_index ?? null}
                    playerImageUrl={row.player_image_url ?? null}
                    clubLogoUrl={row.club_logo ?? null}
                    distribution_index={row.distribution_index ?? null}
                    take_ons_index={row.take_ons_index ?? null}
                    assistance_index={row.assistance_index ?? null}
                    finishing_index={row.finishing_index ?? null}
                    aerial_play_index={row.aerial_play_index ?? null}
                    ground_defense_index={row.ground_defense_index ?? null}
                    onSelect={() =>
                      router.push(`/scout/profile/${row.wyscout_id}?season=${season}`)
                    }
                  />
                ))}
            </div>
          )}
        </section>
        </ExportSection>
      </div>
    </div>
    </ExportProvider>
  );
}
