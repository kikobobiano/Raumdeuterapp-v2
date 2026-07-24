"use client";

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { PanelLeft, PanelLeftClose } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import type { components } from "shared-types";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { SeasonSelect } from "@/components/domain/season-select";
import {
  ExportButton,
  ExportFilterArea,
  ExportProvider,
  ExportSection,
} from "@/components/export";
import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { Skeleton } from "@/components/ui/loading";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

import { SquadAgeMinutesScatter } from "@/components/charts/squad-age-minutes-scatter";
import {
  SquadMinutesShareBars,
  type SquadShareRow,
} from "@/components/charts/squad-minutes-share-bars";
import { LeagueZoneSharesBars } from "@/components/charts/league-zone-shares-bars";
import { AllLeaguesZoneSharesBars } from "@/components/charts/all-leagues-zone-shares-bars";
import { ZoneSharesStrip } from "@/components/charts/zone-shares-strip";
import type { AgeZone } from "@/components/charts/squad-age-minutes-scatter";

type Response = components["schemas"]["MinutesDistributionResponse"];
type Player = components["schemas"]["MinutesDistributionPlayer"];
type LeagueOverview =
  components["schemas"]["LeagueMinutesOverviewResponse"];
type AllLeaguesOverview =
  components["schemas"]["LeaguesMinutesOverviewResponse"];

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

/** Slugify a string for filenames: ASCII letters/digits/underscore only. */
function slugifyForFilename(s: string): string {
  return (
    s
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase() || "all"
  );
}

export function MinutesDistributionClient() {
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();

  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const league = searchParams.get("league") ?? "";
  const club = searchParams.get("club") ?? "";
  const sortByParam = searchParams.get("sort") ?? "youth";
  const sortBy: AgeZone =
    sortByParam === "peak" ||
    sortByParam === "experienced" ||
    sortByParam === "veteran"
      ? sortByParam
      : "youth";
  const domesticOnly = searchParams.get("domestic") === "1";

  const updateParams = React.useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v == null || v === "") next.delete(k);
        else next.set(k, v);
      }
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  const setLeague = (v: string) => {
    // Switching league always clears the club so the league overview can
    // render until the user drills back in.
    updateParams({ league: v || null, club: null });
  };
  const setClub = (v: string) => updateParams({ club: v || null });
  const setSortBy = (band: AgeZone) =>
    updateParams({ sort: band === "youth" ? null : band });
  const setDomesticOnly = (checked: boolean) =>
    updateParams({ domestic: checked ? "1" : null });

  const domesticQuery = domesticOnly ? { domestic_only: true } : {};

  const leaguesQ = useQuery({
    queryKey: ["meta-leagues", f.season],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/leagues", {
        params: { query: { season: f.season } },
      });
      if (error) throw new Error("leagues");
      return (data ?? []) as string[];
    },
  });

  const clubsQ = useQuery({
    queryKey: ["meta-teams", f.season, league || null],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/teams", {
        params: {
          query: {
            season: f.season,
            ...(league ? { league } : {}),
          },
        },
      });
      if (error) throw new Error("clubs");
      return (data ?? []) as string[];
    },
  });

  const clubs = clubsQ.data ?? [];

  // Drop a stale league param when it no longer exists for this season.
  React.useEffect(() => {
    const leagues = leaguesQ.data;
    if (leaguesQ.isPending || !leagues?.length || !league) return;
    if (leagues.includes(league)) return;
    updateParams({ league: null, club: null });
  }, [league, leaguesQ.data, leaguesQ.isPending, updateParams]);

  // Drop an invalid club param when it no longer matches the league filter.
  // Do NOT auto-pick a club when none is set — that hides the league overview.
  React.useEffect(() => {
    if (clubsQ.isPending || clubs.length === 0) return;
    if (club && !clubs.includes(club)) {
      updateParams({ club: null });
    }
  }, [clubs, club, clubsQ.isPending, updateParams]);

  const distQ = useQuery({
    enabled: !!club,
    queryKey: ["team-minutes", f.season, club, domesticOnly],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET("/teams/minutes-distribution", {
        params: { query: { season: f.season, club, ...domesticQuery } },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data as Response;
    },
  });

  const leagueOverviewQ = useQuery({
    enabled: !!league && !club,
    queryKey: ["team-minutes-league", f.season, league, domesticOnly],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/teams/minutes-distribution/league",
        { params: { query: { season: f.season, league, ...domesticQuery } } },
      );
      if (error) throw new Error(JSON.stringify(error));
      return data as LeagueOverview;
    },
  });

  const allLeaguesQ = useQuery({
    enabled: !league && !club,
    queryKey: ["team-minutes-leagues", f.season, domesticOnly],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/teams/minutes-distribution/leagues",
        {
          params: {
            query: { season: f.season, sort_by: "youth", ...domesticQuery },
          },
        },
      );
      if (error) throw new Error(JSON.stringify(error));
      return data as AllLeaguesOverview;
    },
  });

  const result = distQ.data;
  const overview = leagueOverviewQ.data;
  const allLeagues = allLeaguesQ.data;

  const showClubSkeleton = useDelayedLoading(!!club && distQ.isPending);
  const showLeagueSkeleton = useDelayedLoading(
    !!league && !club && leagueOverviewQ.isPending,
  );
  const showAllLeaguesSkeleton = useDelayedLoading(
    !league && !club && allLeaguesQ.isPending,
  );

  const shareRows: SquadShareRow[] = React.useMemo(
    () =>
      (result?.players ?? []).map((p: Player) => ({
        wyscout_id: p.wyscout_id,
        player: p.player,
        position: p.position,
        age: p.age,
        age_zone: p.age_zone,
        minutes: p.minutes,
        matches: p.matches,
        league_minutes_pct: p.league_minutes_pct,
        player_image_url: p.player_image_url,
      })),
    [result],
  );

  const filename = club
    ? `minutes-distribution-${slugifyForFilename(club)}-${pad2(f.season % 100)}-${pad2((f.season + 1) % 100)}.png`
    : league
      ? `minutes-distribution-${slugifyForFilename(league)}-overview-${pad2(f.season % 100)}-${pad2((f.season + 1) % 100)}.png`
      : `minutes-distribution-all-leagues-${pad2(f.season % 100)}-${pad2((f.season + 1) % 100)}.png`;

  const showingLeagueOverview = !!league && !club;
  const showingAllLeagues = !league && !club;

  const seasonLabel = `${f.season}/${pad2((f.season + 1) % 100)}`;

  const headerTitle =
    result && club
      ? result.club
      : showingLeagueOverview
        ? (overview?.league ?? league)
        : showingAllLeagues
          ? "All Leagues"
          : "Minutes Distribution";

  const domesticCountryLabel =
    result?.domestic_country ?? overview?.domestic_country ?? null;

  const domesticSuffix = domesticOnly
    ? domesticCountryLabel
      ? ` · ${domesticCountryLabel} passport only`
      : " · domestic players only"
    : "";

  const headerSubtitle =
    result && club
      ? `${result.league ?? "Unknown league"} · ${seasonLabel} · max ${result.max_league_games} games (${result.max_league_minutes.toLocaleString()} min)${domesticSuffix}`
      : showingLeagueOverview
        ? overview
          ? `${seasonLabel} · Squad age mix · ${overview.clubs.length} clubs${domesticSuffix}`
          : `${seasonLabel} · Squad age mix${domesticSuffix}`
        : showingAllLeagues
          ? allLeagues
            ? `${seasonLabel} · Median squad age mix · ${allLeagues.leagues.length} leagues${domesticSuffix}`
            : `${seasonLabel} · Median squad age mix${domesticSuffix}`
          : "Pick a league or club to explore squad minutes by age band";

  const showClubLogo = !!(result && club && result.club_logo);

  return (
    <ExportProvider title="Minutes Distribution" filename={filename}>
      <div
        className={cn(
          "grid gap-6",
          filtersOpen ? "grid-cols-[280px_1fr]" : "grid-cols-1",
        )}
      >
        {filtersOpen ? (
          <ExportFilterArea>
            <aside className="flex min-w-0 flex-col gap-4">
              <GlassCard
                id="minutes-dist-filters-panel"
                className="flex flex-col gap-4 p-4"
              >
                <p className="label-caps">Squad selection</p>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-content-muted">
                    Season
                  </h3>
                  <SeasonSelect />
                </div>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-content-muted">
                    League
                  </h3>
                  <Combobox
                    options={[
                      { value: "", label: "All leagues" },
                      ...(leaguesQ.data ?? []).map((l) => ({
                        value: l,
                        label: l,
                      })),
                    ]}
                    value={league}
                    onChange={setLeague}
                    placeholder="Filter by league"
                  />
                </div>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-content-muted">
                    Club
                  </h3>
                  <Combobox
                    options={[
                      { value: "", label: league ? "League overview" : "Pick a club" },
                      ...clubs.map((c) => ({ value: c, label: c })),
                    ]}
                    value={club}
                    onChange={setClub}
                    placeholder={
                      clubsQ.isPending ? "Loading clubs…" : "Pick a club"
                    }
                  />
                </div>

                <div className="rounded bg-surface-low/40 px-3 py-2 text-[10px] leading-snug text-content-muted">
                  Age bands · Youth &lt; 23 · Peak &lt; 29 · Experienced &lt; 34 · Veteran ≥ 34
                </div>

                <div>
                  <label className="flex cursor-pointer items-start gap-3 text-sm text-on-surface">
                    <input
                      type="checkbox"
                      checked={domesticOnly}
                      onChange={(e) => setDomesticOnly(e.target.checked)}
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-outline-variant bg-surface-mid text-primary focus-visible:ring-2 focus-visible:ring-primary/40"
                    />
                    <span>
                      <span className="font-medium">Domestic players only</span>
                      <span className="mt-0.5 block text-xs text-on-surface-variant">
                        Recalculate youth / peak / experienced / veteran shares
                        using only minutes from players with the league&apos;s
                        domestic passport.
                      </span>
                    </span>
                  </label>
                </div>
              </GlassCard>
            </aside>
          </ExportFilterArea>
        ) : null}

        <main className="min-w-0 overflow-auto p-6">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <ExportSection id="header" label="Title" required defaultIncluded>
              <div className="flex items-center gap-3">
                {showClubLogo ? (
                  <ClubLogoImg
                    logoUrl={result!.club_logo!}
                    className="h-12 w-12"
                  />
                ) : null}
                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-on-surface">
                    {headerTitle}
                  </h1>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    {headerSubtitle}
                  </p>
                </div>
              </div>
            </ExportSection>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
              <ExportFilterArea>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => setFiltersOpen(!filtersOpen)}
                  aria-expanded={filtersOpen}
                  aria-controls={filtersOpen ? "minutes-dist-filters-panel" : undefined}
                  aria-label={filtersOpen ? "Hide filters" : "Show filters"}
                >
                  {filtersOpen ? (
                    <>
                      <PanelLeftClose className="h-4 w-4 shrink-0" />
                      Hide filters
                    </>
                  ) : (
                    <>
                      <PanelLeft className="h-4 w-4 shrink-0" />
                      Filters
                    </>
                  )}
                </Button>
              </ExportFilterArea>
              <ExportButton />
            </div>
          </div>

          {showAllLeaguesSkeleton && (
            <GlassCard className="p-6">
              <div className="space-y-2">
                {Array.from({ length: 16 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full rounded-md" />
                ))}
              </div>
            </GlassCard>
          )}

          {allLeaguesQ.isError && showingAllLeagues && (
            <div className="flex min-h-[40vh] items-center justify-center text-sm text-red-400">
              Error loading leagues overview: {String(allLeaguesQ.error)}
            </div>
          )}

          {showingAllLeagues && allLeagues && (
            <ExportSection
              id="all-leagues-overview"
              label="All leagues median age mix"
              defaultIncluded
            >
              <GlassCard className="p-4 sm:p-6">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-content-muted">
                  Squad Age Mix · All Leagues
                  {domesticOnly ? " · Domestic" : ""}
                </h2>
                <AllLeaguesZoneSharesBars
                  rows={allLeagues.leagues}
                  season={allLeagues.season}
                  sortBy={sortBy}
                  domesticOnly={domesticOnly}
                  onSortByChange={setSortBy}
                  onSelectLeague={setLeague}
                />
              </GlassCard>
            </ExportSection>
          )}

          {showLeagueSkeleton && (
            <GlassCard className="p-6">
              <div className="space-y-2">
                {Array.from({ length: 12 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full rounded-md" />
                ))}
              </div>
            </GlassCard>
          )}

          {leagueOverviewQ.isError && showingLeagueOverview && (
            <div className="flex min-h-[40vh] items-center justify-center text-sm text-red-400">
              Error loading league overview: {String(leagueOverviewQ.error)}
            </div>
          )}

          {showingLeagueOverview && overview && (
            <ExportSection
              id="league-overview"
              label="League youth-share bars"
              defaultIncluded
            >
              <GlassCard className="p-4 sm:p-6">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-content-muted">
                  Squad Age Mix · {overview.league}
                  {domesticOnly ? " · Domestic" : ""}
                </h2>
                <LeagueZoneSharesBars
                  rows={overview.clubs}
                  league={overview.league}
                  season={overview.season}
                  domesticOnly={domesticOnly}
                  domesticCountry={overview.domestic_country}
                  onSelectClub={setClub}
                />
              </GlassCard>
            </ExportSection>
          )}

          {showClubSkeleton && (
            <div className="space-y-6">
              <GlassCard className="p-6">
                <ChartSkeleton variant="scatter" height={420} />
              </GlassCard>
              <GlassCard className="p-6">
                <div className="space-y-2">
                  {Array.from({ length: 10 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-md" />
                  ))}
                </div>
              </GlassCard>
            </div>
          )}

          {distQ.isError && club && (
            <div className="flex min-h-[40vh] items-center justify-center text-sm text-red-400">
              Error loading squad: {String(distQ.error)}
            </div>
          )}

          {result && club && (
            <div className="flex flex-col gap-6">
              <ExportSection id="zone-shares" label="Squad age mix" defaultIncluded>
                <GlassCard className="p-4 sm:p-6">
                  <ZoneSharesStrip
                    shares={result.zone_shares}
                    caption={
                      domesticOnly
                        ? `${result.club} · age mix · ${result.domestic_country ?? "domestic"} passport only`
                        : `${result.club} · share of minutes by age band`
                    }
                  />
                </GlassCard>
              </ExportSection>

              <ExportSection id="scatter" label="Age vs Minutes scatter" defaultIncluded>
                <GlassCard className="p-4 sm:p-6">
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-content-muted">
                    Age vs Minutes
                  </h2>
                  <SquadAgeMinutesScatter
                    points={result.players.map((p) => ({
                      wyscout_id: p.wyscout_id,
                      player: p.player,
                      position: p.position,
                      age: p.age,
                      minutes: p.minutes,
                      matches: p.matches,
                      age_zone: p.age_zone,
                      player_image_url: p.player_image_url,
                    }))}
                    club={result.club}
                    league={result.league ?? null}
                    clubLogoUrl={result.club_logo ?? null}
                    season={result.season}
                    maxLeagueMinutes={result.max_league_minutes}
                  />
                </GlassCard>
              </ExportSection>

              <ExportSection id="bars" label="% of league minutes bars" defaultIncluded>
                <GlassCard className="p-4 sm:p-6">
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-content-muted">
                    % of League Minutes Played
                  </h2>
                  <SquadMinutesShareBars
                    rows={shareRows}
                    season={result.season}
                    maxLeagueMinutes={result.max_league_minutes}
                    maxLeagueGames={result.max_league_games}
                  />
                </GlassCard>
              </ExportSection>
            </div>
          )}
        </main>
      </div>
    </ExportProvider>
  );
}
