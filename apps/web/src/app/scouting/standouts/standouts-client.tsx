"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, Sparkles } from "lucide-react";
import * as React from "react";

import { FilterPanel } from "@/components/domain/filter-panel";
import { type MetricMode, modeFromMetricOption } from "@/components/domain/metric-mode-toggle";
import { HorizontalBarRanking } from "@/components/charts/horizontal-bar-ranking";
import { ExportButton, ExportProvider, ExportSection } from "@/components/export";
import { MetricWeightRow, type MetricSpec } from "@/components/scouting/metric-weight-row";
import { StandoutsTable } from "@/components/scouting/standouts-table";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";

import type { components } from "shared-types";

type StandoutResponse = components["schemas"]["StandoutResponse"];
type Signal = "overall" | "metrics";

const BAR_TOP_N = 15;
const PAGE_SIZE = 15;

const DEFAULT_METRICS: MetricSpec[] = [
  { metric: "Goals", mode: "p90", weight: 1.0, threshold_z: null },
  { metric: "Assists", mode: "p90", weight: 1.0, threshold_z: null },
];

const MODE_SUFFIX: Record<MetricMode, string> = { p90: " /90", raw: " (raw)", as_is: "" };

interface RunMeta {
  signal: Signal;
  metrics: MetricSpec[];
}

export function StandoutsClient() {
  const f = useGlobalFilters();
  const [signal, setSignal] = React.useState<Signal>("overall");
  const [metrics, setMetrics] = React.useState<MetricSpec[]>(DEFAULT_METRICS);
  const [minStandoutZ, setMinStandoutZ] = React.useState(1.0);
  const [page, setPage] = React.useState(0);
  const [runMeta, setRunMeta] = React.useState<RunMeta | null>(null);

  const metricsQ = useQuery({
    queryKey: ["metrics", f.season],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/metrics", {
        params: { query: { season: f.season } },
      });
      if (error) throw new Error("metrics");
      return data ?? [];
    },
  });
  const metricByName = React.useMemo(
    () => Object.fromEntries((metricsQ.data ?? []).map((m) => [m.name, m])),
    [metricsQ.data],
  );
  const metricOpts = React.useMemo(
    () => (metricsQ.data ?? []).map((m) => ({ value: m.name, label: m.label })),
    [metricsQ.data],
  );

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const standoutMu = useMutation({
    mutationFn: async (): Promise<StandoutResponse> => {
      const { data, error } = await api.POST("/scouting/standouts", {
        body: {
          filters: {
            season: f.season,
            leagues: f.leagues.length ? f.leagues : null,
            teams: f.clubs.length ? f.clubs : null,
            roles: rolesPayload.length ? rolesPayload : null,
            age_min: f.ageMin,
            age_max: f.ageMax,
            minutes_min: f.minutesMin,
          },
          signal,
          metrics:
            signal === "metrics"
              ? metrics.map((m) => ({
                  metric: m.metric,
                  mode: m.mode,
                  weight: m.weight,
                  threshold_z: m.threshold_z,
                }))
              : [],
          min_standout_z: minStandoutZ,
          limit: 100,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
  });

  const result = standoutMu.data;
  const rows = result?.rows ?? [];

  const barRows = React.useMemo(
    () =>
      rows.slice(0, BAR_TOP_N).map((r, i) => ({
        rank: i + 1,
        player: r.player,
        wyscout_id: r.wyscout_id,
        player_image_url: r.player_image_url,
        club: r.club,
        club_logo: r.club_logo,
        position: r.position,
        age: r.age,
        minutes: r.minutes,
        values: { standout_score: r.standout_score },
      })),
    [rows],
  );

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pagedRows = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const canRun = !standoutMu.isPending && (signal === "overall" || metrics.length > 0);

  const runSignal = runMeta?.signal ?? signal;
  const exportSignalLabel =
    runSignal === "metrics" ? "Metrics" : "Overall Performance Index";
  const exportMetricSubtitle = React.useMemo(() => {
    if (runMeta?.signal !== "metrics") return "";
    return runMeta.metrics
      .map((m) => (metricByName[m.metric]?.label ?? m.metric) + MODE_SUFFIX[m.mode])
      .join(" · ");
  }, [runMeta, metricByName]);

  const seasonLabel = `${String(f.season).slice(2)}-${String(f.season + 1).slice(2)}`;

  const handleRun = () => {
    setPage(0);
    setRunMeta({ signal, metrics });
    standoutMu.mutate();
  };

  return (
    <ExportProvider title="Standouts" filename={`standouts-${seasonLabel}.png`}>
    <div className="grid gap-6 grid-cols-[300px_1fr]">
      <GlassCard className="self-start sticky top-4">
        <p className="label-caps mb-3">Population</p>
        <FilterPanel />
      </GlassCard>

      <div className="space-y-6 min-w-0">
        <GlassCard>
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-on-surface">Scouting · Standouts</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Players performing furthest above the selected leagues&apos; average, in σ. Overall
                uses the per-league Performance Index; By metrics uses a weighted set you choose.
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
            {result && <ExportButton />}
            <Button
              variant="primary"
              size="md"
              onClick={handleRun}
              disabled={!canRun}
              className="gap-1.5"
            >
              <Sparkles className="h-4 w-4" />
              {standoutMu.isPending ? "Finding…" : "Find standouts"}
            </Button>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              <div>
                <p className="label-caps mb-2">Signal</p>
                <div className="flex gap-2">
                  {(
                    [
                      ["overall", "Overall (PI)"],
                      ["metrics", "By metrics"],
                    ] as const
                  ).map(([key, label]) => (
                    <Button
                      key={key}
                      variant={signal === key ? "primary" : "secondary"}
                      size="sm"
                      onClick={() => setSignal(key)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="label-caps">Min σ above average</p>
                  <p className="data-mono text-on-surface">{minStandoutZ.toFixed(1)}</p>
                </div>
                <Slider
                  min={0}
                  max={3}
                  step={0.1}
                  value={[minStandoutZ]}
                  onValueChange={([v]) => setMinStandoutZ(v)}
                />
              </div>
            </div>

            {signal === "metrics" && (
              <div>
                <p className="label-caps mb-2">Metrics + weights</p>
                <div className="space-y-2">
                  {metrics.map((spec, i) => {
                    const meta = metricByName[spec.metric];
                    return (
                      <MetricWeightRow
                        key={`m-${i}`}
                        spec={spec}
                        options={metricOpts}
                        supportsMode={!!meta?.supports_mode}
                        onChange={(patch) =>
                          setMetrics((arr) =>
                            arr.map((m, idx) => {
                              if (idx !== i) return m;
                              const next = { ...m, ...patch };
                              if (patch.metric) {
                                const newMeta = metricByName[patch.metric];
                                next.mode = modeFromMetricOption(newMeta) as MetricMode;
                              }
                              return next;
                            }),
                          )
                        }
                        onRemove={() => setMetrics((arr) => arr.filter((_, idx) => idx !== i))}
                      />
                    );
                  })}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full"
                    disabled={metrics.length >= 20 || metricOpts.length === 0}
                    onClick={() => {
                      const first = metricOpts[0];
                      if (!first) return;
                      const meta = metricByName[first.value];
                      setMetrics([
                        ...metrics,
                        {
                          metric: first.value,
                          mode: modeFromMetricOption(meta) as MetricMode,
                          weight: 1.0,
                          threshold_z: null,
                        },
                      ]);
                    }}
                  >
                    <Plus className="h-4 w-4" />
                    Add metric
                  </Button>
                </div>
              </div>
            )}
          </div>
        </GlassCard>

        {standoutMu.isError && (
          <GlassCard>
            <p className="text-sm text-error">Error: {String(standoutMu.error)}</p>
          </GlassCard>
        )}

        {result && (
          <>
            <ExportSection id="summary" label="Description" required>
              <GlassCard>
                <div className="mb-4">
                  <p className="label-caps mb-1">Standout signal</p>
                  <h2 className="text-xl font-bold text-on-surface">{exportSignalLabel}</h2>
                  {runSignal === "metrics" && exportMetricSubtitle && (
                    <p className="mt-1 text-sm text-on-surface-variant">{exportMetricSubtitle}</p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-4 text-xs text-on-surface-variant">
                  <span>
                    Leagues{" "}
                    <span className="text-on-surface">
                      {f.leagues.length === 0
                        ? "All"
                        : result.league ?? `${f.leagues.length} selected`}
                    </span>
                  </span>
                  <span>
                    Cohort N=
                    <span className="data-mono text-on-surface">{result.cohort_n}</span>
                  </span>
                  <span>
                    Min minutes{" "}
                    <span className="data-mono text-on-surface">{result.min_minutes}</span>
                  </span>
                  <span>
                    Standouts <span className="data-mono text-on-surface">{result.total}</span>
                  </span>
                  {result.cohort_n < 30 && (
                    <span className="text-warning">Cohort small — σ unstable.</span>
                  )}
                </div>
              </GlassCard>
            </ExportSection>

            {rows.length === 0 ? (
              <GlassCard>
                <p className="text-sm text-on-surface-variant">
                  No players clear +{minStandoutZ.toFixed(1)}σ with the current filters. Lower the
                  threshold or widen the population.
                </p>
              </GlassCard>
            ) : (
              <>
                <ExportSection id="chart" label="Chart" required>
                  <GlassCard>
                    <p className="label-caps mb-2">Top standouts · σ above league average</p>
                    <HorizontalBarRanking
                      rows={barRows}
                      metrics={["standout_score"]}
                      labels={{ standout_score: "Standout σ" }}
                      height={Math.max(280, barRows.length * 34)}
                    />
                  </GlassCard>
                </ExportSection>

                <ExportSection id="table" label="Table" required>
                  <GlassCard>
                    <div className="mb-2 flex items-center justify-between">
                      <p className="label-caps">Standouts</p>
                      {pageCount > 1 && (
                        <div className="flex items-center gap-1" data-export-hide>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={page === 0}
                            onClick={() => setPage((p) => Math.max(0, p - 1))}
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </Button>
                          <span className="data-mono text-xs text-on-surface-variant">
                            {page + 1} / {pageCount}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={page + 1 >= pageCount}
                            onClick={() => setPage((p) => p + 1)}
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                    <StandoutsTable
                      rows={pagedRows}
                      season={f.season}
                      startIndex={page * PAGE_SIZE}
                      showPerformanceIndex={signal === "overall"}
                    />
                  </GlassCard>
                </ExportSection>
              </>
            )}
          </>
        )}
      </div>
    </div>
    </ExportProvider>
  );
}
