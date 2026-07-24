"use client";

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { PanelLeft, PanelLeftClose } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import type { components } from "shared-types";

import { ScatterChart, type ScatterPoint } from "@/components/charts/scatter-chart";
import {
  SquadValueHistoryChart,
  type SquadHistoryRow,
} from "@/components/charts/squad-value-history-chart";
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
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { squadValueSelectableLeagues } from "@/lib/squad-value-leagues";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

type LeagueResponse = components["schemas"]["SquadValueLeagueResponse"];
type HistoryResponse = components["schemas"]["SquadValueHistoryResponse"];
type TeamRow = components["schemas"]["SquadValueTeamRow"];

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function slugifyForFilename(s: string): string {
  return (
    s
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase() || "all"
  );
}

function fmtEurCompact(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  if (n >= 1e9) return `€${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) {
    const m = n / 1e6;
    return m >= 10 ? `€${m.toFixed(0)}M` : `€${m.toFixed(1)}M`;
  }
  if (n >= 1e3) return `€${(n / 1e3).toFixed(0)}k`;
  return `€${Math.round(n)}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(0)}%`;
}

function fmtNum(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function KpiCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <GlassCard className="p-4">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-content-muted">
        {label}
      </p>
      <p className="data-mono mt-2 text-2xl font-bold text-on-surface">{value}</p>
      {hint ? <p className="mt-1 text-xs text-on-surface-variant">{hint}</p> : null}
    </GlassCard>
  );
}

export function SquadValueClient() {
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();

  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const league = searchParams.get("league") ?? "";
  const club = searchParams.get("club") ?? "";

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
    updateParams({ league: v || null, club: null });
  };
  const setClub = (v: string) => updateParams({ club: v || null });

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
    enabled: !!league,
    queryKey: ["meta-teams", f.season, league],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/teams", {
        params: {
          query: {
            season: f.season,
            league,
          },
        },
      });
      if (error) throw new Error("clubs");
      return (data ?? []) as string[];
    },
  });

  const clubs = clubsQ.data ?? [];

  const selectableLeagues = React.useMemo(
    () => squadValueSelectableLeagues(leaguesQ.data ?? []),
    [leaguesQ.data],
  );

  // `/meta/leagues` is sorted by power (strongest first); default on first load.
  React.useEffect(() => {
    if (leaguesQ.isPending || selectableLeagues.length === 0) return;
    if (league && selectableLeagues.includes(league)) return;
    updateParams({
      league: selectableLeagues[0],
      club: null,
    });
  }, [league, selectableLeagues, leaguesQ.isPending, updateParams]);

  // Default club to the first team in the league when none is selected.
  React.useEffect(() => {
    if (!league || clubsQ.isPending || clubs.length === 0) return;
    if (club && clubs.includes(club)) return;
    updateParams({ club: clubs[0] });
  }, [league, clubs, club, clubsQ.isPending, updateParams]);

  const leagueQ = useQuery({
    enabled: !!league,
    queryKey: ["squad-value-league", f.season, league],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET("/teams/squad-value/league", {
        params: { query: { season: f.season, league } },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data as LeagueResponse;
    },
  });

  const historyQ = useQuery({
    enabled: !!club,
    queryKey: ["squad-value-history", club],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await api.GET("/teams/squad-value/history", {
        params: { query: { club } },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data as HistoryResponse;
    },
  });

  const selectedTeam: TeamRow | null = React.useMemo(() => {
    if (!leagueQ.data || !club) return null;
    return leagueQ.data.teams.find((t) => t.club === club) ?? null;
  }, [leagueQ.data, club]);

  const xtvSupported = leagueQ.data?.xtv_supported ?? true;

  const scatterPoints: ScatterPoint[] = React.useMemo(() => {
    if (!leagueQ.data) return [];
    return leagueQ.data.teams.map((t) => ({
      wyscout_id: null,
      player: t.club,
      club: t.club,
      league: t.league ?? leagueQ.data!.league,
      position: `${t.n_players} players`,
      age: t.avg_age == null ? null : Math.round(t.avg_age),
      minutes: null,
      x: xtvSupported
        ? (t.total_xtv_eur ?? null)
        : (t.total_market_value_eur ?? null),
      y: t.avg_age ?? null,
    }));
  }, [leagueQ.data, xtvSupported]);

  const qualityScatterPoints: ScatterPoint[] = React.useMemo(() => {
    if (!leagueQ.data || !xtvSupported) return [];
    return leagueQ.data.teams
      .map((t) => ({
        wyscout_id: null,
        player: t.club,
        club: t.club,
        league: t.league ?? leagueQ.data!.league,
        position: `${t.n_players_500 ?? 0} players (500+ min)`,
        age: t.avg_performance_index ?? null,
        minutes: t.n_players_500 ?? null,
        x: t.squad_xtv_zscore ?? null,
        y: t.avg_performance_index ?? null,
      }))
      .filter((p) => p.x != null && p.y != null);
  }, [leagueQ.data, xtvSupported]);

  const historyRows: SquadHistoryRow[] = React.useMemo(() => {
    if (!historyQ.data) return [];
    return historyQ.data.rows.map((r) => ({
      season: r.season,
      total_xtv_eur: r.total_xtv_eur ?? null,
      avg_xtv_eur: r.avg_xtv_eur ?? null,
      total_market_value_eur: r.total_market_value_eur ?? null,
      avg_market_value_eur: r.avg_market_value_eur ?? null,
      avg_age: r.avg_age ?? null,
    }));
  }, [historyQ.data]);

  const showSkeleton = useDelayedLoading(!!league && leagueQ.isPending);
  const filename = `squad-value-${slugifyForFilename(club || "no-club")}-${pad2(f.season % 100)}-${pad2((f.season + 1) % 100)}.png`;

  return (
    <ExportProvider title="Squad Value" filename={filename}>
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
                id="squad-value-filters-panel"
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
                    League <span className="text-primary">*</span>
                  </h3>
                  <Combobox
                    options={selectableLeagues.map((l) => ({
                      value: l,
                      label: l,
                    }))}
                    value={league}
                    onChange={setLeague}
                    placeholder="Pick a league"
                  />
                </div>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-content-muted">
                    Club <span className="text-primary">*</span>
                  </h3>
                  <Combobox
                    options={clubs.map((c) => ({ value: c, label: c }))}
                    value={club}
                    onChange={setClub}
                    placeholder={
                      clubsQ.isPending ? "Loading clubs…" : "Pick a club"
                    }
                  />
                </div>
              </GlassCard>
            </aside>
          </ExportFilterArea>
        ) : null}

        <main className="min-w-0 overflow-auto p-6">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <ExportSection id="header" label="Title + club" required defaultIncluded>
              <div className="flex items-center gap-3">
                {selectedTeam?.club_logo ? (
                  <ClubLogoImg
                    logoUrl={selectedTeam.club_logo}
                    className="h-12 w-12"
                  />
                ) : (
                  <div className="h-12 w-12 rounded-md bg-surface-mid/40" />
                )}
                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-on-surface">
                    Squad Value
                  </h1>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    {selectedTeam
                      ? `${selectedTeam.club} · ${selectedTeam.league ?? league} · ${f.season}/${pad2((f.season + 1) % 100)}`
                      : league
                        ? "Pick a club to see the squad snapshot."
                        : "Pick a league and a club."}
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
                  aria-controls={
                    filtersOpen ? "squad-value-filters-panel" : undefined
                  }
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

          {!league && (
            <div className="flex min-h-[40vh] items-center justify-center text-sm text-content-muted">
              Pick a league from the sidebar.
            </div>
          )}

          {showSkeleton && (
            <div className="space-y-6">
              <GlassCard className="p-6">
                <ChartSkeleton variant="scatter" height={420} />
              </GlassCard>
            </div>
          )}

          {leagueQ.isError && (
            <div className="flex min-h-[40vh] items-center justify-center text-sm text-red-400">
              Error loading league: {String(leagueQ.error)}
            </div>
          )}

          {league && leagueQ.data && (
            <div className="flex flex-col gap-6">
              <ExportSection id="kpis" label="Team KPI cards" defaultIncluded>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <KpiCard
                    label="Avg age"
                    value={fmtNum(selectedTeam?.avg_age ?? null, 1)}
                    hint={`${selectedTeam?.n_players ?? 0} players`}
                  />
                  {xtvSupported ? (
                    <KpiCard
                      label="Total xTV"
                      value={fmtEurCompact(selectedTeam?.total_xtv_eur)}
                      hint={`avg ${fmtEurCompact(selectedTeam?.avg_xtv_eur)}`}
                    />
                  ) : null}
                  <KpiCard
                    label="Avg player value (TM)"
                    value={fmtEurCompact(selectedTeam?.avg_market_value_eur)}
                    hint={`total ${fmtEurCompact(selectedTeam?.total_market_value_eur)}`}
                  />
                  <KpiCard
                    label="Foreign share"
                    value={fmtPct(selectedTeam?.foreign_share)}
                    hint="vs modal squad passport"
                  />
                </div>
              </ExportSection>

              <ExportSection
                id="league-scatter"
                label={
                  xtvSupported
                    ? "League scatter (xTV × age)"
                    : "League scatter (squad value × age)"
                }
                defaultIncluded
              >
                <GlassCard className="p-4 sm:p-6">
                  <div className="mb-3 flex items-baseline justify-between">
                    <h2 className="text-sm font-semibold uppercase tracking-widest text-content-muted">
                      {xtvSupported
                        ? "League comparison — total xTV × avg age"
                        : "League comparison — total squad value (TM) × avg age"}
                    </h2>
                    <span className="text-[11px] text-content-muted">
                      {leagueQ.data.teams.length} teams
                    </span>
                  </div>
                  <ScatterChart
                    points={scatterPoints}
                    xLabel={
                      xtvSupported ? "Total squad xTV (€)" : "Total squad value TM (€)"
                    }
                    yLabel="Avg squad age"
                    height={460}
                    highlightClubs={club ? [club] : []}
                  />
                </GlassCard>
              </ExportSection>

              {xtvSupported ? (
                <ExportSection
                  id="quality-scatter"
                  label="League scatter (avg PI × xTV z-score)"
                  defaultIncluded
                >
                  <GlassCard className="p-4 sm:p-6">
                    <div className="mb-3 flex items-baseline justify-between gap-3">
                      <div>
                        <h2 className="text-sm font-semibold uppercase tracking-widest text-content-muted">
                          League comparison — performance vs value
                        </h2>
                        <p className="mt-1 text-xs text-on-surface-variant">
                          Squad total xTV z-score (500+ min) vs avg performance index; dotted line
                          = linear regression
                        </p>
                      </div>
                      <span className="shrink-0 text-[11px] text-content-muted">
                        {qualityScatterPoints.length} teams
                      </span>
                    </div>
                    {qualityScatterPoints.length === 0 ? (
                      <div className="flex min-h-[20vh] items-center justify-center text-sm text-content-muted">
                        Not enough data for this league (need 500+ min cohorts with xTV).
                      </div>
                    ) : (
                      <ScatterChart
                        points={qualityScatterPoints}
                        xLabel="Squad xTV z-score (vs league)"
                        yLabel="Avg performance index (500+ min)"
                        height={460}
                        highlightClubs={club ? [club] : []}
                        showLinearRegression
                      />
                    )}
                  </GlassCard>
                </ExportSection>
              ) : null}

              <ExportSection
                id="history"
                label="Multi-season club progression"
                defaultIncluded
              >
                <GlassCard className="p-4 sm:p-6">
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-content-muted">
                    {club ? `${club} — multi-season progression` : "Multi-season progression"}
                  </h2>
                  {historyQ.isPending && club ? (
                    <ChartSkeleton variant="scatter" height={320} />
                  ) : historyRows.length === 0 ? (
                    <div className="flex min-h-[20vh] items-center justify-center text-sm text-content-muted">
                      No multi-season history for this club.
                    </div>
                  ) : (
                    <SquadValueHistoryChart rows={historyRows} showXtv={xtvSupported} />
                  )}
                </GlassCard>
              </ExportSection>
            </div>
          )}
        </main>
      </div>
    </ExportProvider>
  );
}
