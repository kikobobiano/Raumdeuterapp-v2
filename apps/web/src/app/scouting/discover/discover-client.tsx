"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, Sparkles } from "lucide-react";
import * as React from "react";

import { ScatterChart, type ScatterPoint } from "@/components/charts/scatter-chart";
import { FilterPanel } from "@/components/domain/filter-panel";
import { type MetricMode, modeFromMetricOption } from "@/components/domain/metric-mode-toggle";
import { MetricWeightRow, type MetricSpec } from "@/components/scouting/metric-weight-row";
import { ShortlistTable } from "@/components/scouting/shortlist-table";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

import type { components } from "shared-types";

type DiscoverResponse = components["schemas"]["DiscoverResponse"];

const PAGE_SIZE = 25;

const DEFAULT_METRICS: MetricSpec[] = [
  { metric: "Progressive passes per 90", mode: "p90", weight: 1.0, threshold_z: null },
  { metric: "Progressive runs per 90", mode: "p90", weight: 1.0, threshold_z: null },
  { metric: "Key passes per 90", mode: "p90", weight: 1.0, threshold_z: null },
  { metric: "Defensive duels per 90", mode: "p90", weight: 0.5, threshold_z: null },
];

type CohortTier = "position_tier" | "position_league" | "position_global";

export function DiscoverClient() {
  const f = useGlobalFilters();
  const [metrics, setMetrics] = React.useState<MetricSpec[]>(DEFAULT_METRICS);
  const [normalization, setNormalization] = React.useState<"zscore" | "percentile">("zscore");
  const [cohortTier, setCohortTier] = React.useState<CohortTier>("position_tier");
  const [kClusters, setKClusters] = React.useState(4);
  const [clubFitTeam, setClubFitTeam] = React.useState("");
  const [clubFitWeight, setClubFitWeight] = React.useState(0.3);
  // Local extras (kept outside Zustand).
  const [xtvMin, setXtvMin] = React.useState<number | null>(null);
  const [xtvMax, setXtvMax] = React.useState<number | null>(null);
  const [heightMin, setHeightMin] = React.useState<number | null>(null);
  const [heightMax, setHeightMax] = React.useState<number | null>(null);
  const [foot, setFoot] = React.useState<string>("");
  const [contractMaxYear, setContractMaxYear] = React.useState<number | null>(null);
  const [passportCsv, setPassportCsv] = React.useState("");
  const [customXMetric, setCustomXMetric] = React.useState<string>("");
  const [customYMetric, setCustomYMetric] = React.useState<string>("");
  const [page, setPage] = React.useState(0);

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

  const discoverMu = useMutation({
    mutationFn: async (): Promise<DiscoverResponse> => {
      const passport_countries =
        passportCsv
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean) || null;
      const { data, error } = await api.POST("/scouting/discover", {
        body: {
          filters: {
            season: f.season,
            leagues: f.leagues.length ? f.leagues : null,
            teams: f.clubs.length ? f.clubs : null,
            roles: rolesPayload.length ? rolesPayload : null,
            age_min: f.ageMin,
            age_max: f.ageMax,
            minutes_min: f.minutesMin,
            foot: foot || null,
            contract_expires_year_max: contractMaxYear,
            xtv_min_eur: xtvMin,
            xtv_max_eur: xtvMax,
            height_min: heightMin,
            height_max: heightMax,
            passport_countries: passport_countries.length ? passport_countries : null,
          },
          metrics: metrics.map((m) => ({
            metric: m.metric,
            mode: m.mode,
            weight: m.weight,
            threshold_z: m.threshold_z,
          })),
          normalization,
          cohort_tier: cohortTier,
          archetype: "pca_kmeans",
          k_clusters: kClusters,
          club_fit_team: clubFitTeam || null,
          club_fit_weight: clubFitWeight,
          limit: 500,
          offset: 0,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
  });

  const result = discoverMu.data;
  const allRows = result?.rows ?? [];
  const totalKept = result?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(allRows.length / PAGE_SIZE));
  const sliced = allRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const pcaPoints: ScatterPoint[] = (result?.rows ?? []).map((r) => ({
    wyscout_id: r.wyscout_id,
    player: r.player,
    club: r.club ?? null,
    league: r.league ?? null,
    position: r.position ?? null,
    age: r.age ?? null,
    minutes: r.minutes ?? null,
    x: r.pca_x ?? null,
    y: r.pca_y ?? null,
    player_image_url: r.player_image_url ?? null,
  }));

  const pcaPointsPC13: ScatterPoint[] = (result?.rows ?? []).map((r) => ({
    wyscout_id: r.wyscout_id,
    player: r.player,
    club: r.club ?? null,
    league: r.league ?? null,
    position: r.position ?? null,
    age: r.age ?? null,
    minutes: r.minutes ?? null,
    x: r.pca_x ?? null,
    y: r.pca_z ?? null,
    player_image_url: r.player_image_url ?? null,
  }));

  const customPoints: ScatterPoint[] = (result?.rows ?? []).map((r) => {
    const xz = r.metric_values.find((m) => m.metric === customXMetric)?.z ?? null;
    const yz = r.metric_values.find((m) => m.metric === customYMetric)?.z ?? null;
    return {
      wyscout_id: r.wyscout_id,
      player: r.player,
      club: r.club ?? null,
      league: r.league ?? null,
      position: r.position ?? null,
      age: r.age ?? null,
      minutes: r.minutes ?? null,
      x: xz,
      y: yz,
      player_image_url: r.player_image_url ?? null,
    };
  });

  React.useEffect(() => {
    if (!customXMetric && metrics[0]) setCustomXMetric(metrics[0].metric);
    if (!customYMetric && metrics[1]) setCustomYMetric(metrics[1].metric);
  }, [metrics, customXMetric, customYMetric]);

  const explained = result?.pca?.explained_variance ?? [];
  const pcaWarn = explained.length >= 2 && explained[0] + explained[1] < 0.6;

  const extras = (
    <div className="space-y-4">
      <div>
        <p className="label-caps mb-2">xTV range (EUR)</p>
        <div className="flex gap-2">
          <Input
            type="number"
            placeholder="min"
            value={xtvMin ?? ""}
            onChange={(e) => setXtvMin(e.target.value === "" ? null : parseFloat(e.target.value))}
          />
          <Input
            type="number"
            placeholder="max"
            value={xtvMax ?? ""}
            onChange={(e) => setXtvMax(e.target.value === "" ? null : parseFloat(e.target.value))}
          />
        </div>
      </div>
      <div>
        <p className="label-caps mb-2">Height (cm)</p>
        <div className="flex gap-2">
          <Input
            type="number"
            placeholder="min"
            value={heightMin ?? ""}
            onChange={(e) => setHeightMin(e.target.value === "" ? null : parseInt(e.target.value, 10))}
          />
          <Input
            type="number"
            placeholder="max"
            value={heightMax ?? ""}
            onChange={(e) => setHeightMax(e.target.value === "" ? null : parseInt(e.target.value, 10))}
          />
        </div>
      </div>
      <div>
        <p className="label-caps mb-2">Foot</p>
        <select
          value={foot}
          onChange={(e) => setFoot(e.target.value)}
          className="w-full rounded-md bg-surface-mid px-2 py-1.5 text-sm text-on-surface"
        >
          <option value="">Any</option>
          <option value="right">Right</option>
          <option value="left">Left</option>
          <option value="both">Both</option>
        </select>
      </div>
      <div>
        <p className="label-caps mb-2">Contract expires ≤</p>
        <Input
          type="number"
          placeholder="year"
          value={contractMaxYear ?? ""}
          onChange={(e) =>
            setContractMaxYear(e.target.value === "" ? null : parseInt(e.target.value, 10))
          }
        />
      </div>
      <div>
        <p className="label-caps mb-2">Passport (comma-sep)</p>
        <Input
          type="text"
          placeholder="Portugal, Brazil…"
          value={passportCsv}
          onChange={(e) => setPassportCsv(e.target.value)}
        />
      </div>
    </div>
  );

  return (
    <div className="grid gap-6 grid-cols-[300px_1fr]">
      <GlassCard className="self-start sticky top-4">
        <p className="label-caps mb-3">Population</p>
        <FilterPanel extras={extras} />
      </GlassCard>

      <div className="space-y-6 min-w-0">
        <GlassCard>
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-on-surface">Scouting · Discover</h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                Cohort-normalized shortlist + archetype scatters. Cohort tier widens normalization
                pool when a single league is small.
              </p>
            </div>
            <Button
              variant="primary"
              size="md"
              onClick={() => {
                setPage(0);
                discoverMu.mutate();
              }}
              disabled={discoverMu.isPending || metrics.length === 0}
              className="gap-1.5"
            >
              <Sparkles className="h-4 w-4" />
              {discoverMu.isPending ? "Running…" : "Run discovery"}
            </Button>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
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

            <div className="space-y-4">
              <div>
                <p className="label-caps mb-2">Normalization</p>
                <div className="flex gap-2">
                  {(["zscore", "percentile"] as const).map((mode) => (
                    <Button
                      key={mode}
                      variant={normalization === mode ? "primary" : "secondary"}
                      size="sm"
                      onClick={() => setNormalization(mode)}
                    >
                      {mode === "zscore" ? "Z-score" : "Percentile"}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <p className="label-caps mb-2">Cohort tier</p>
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      ["position_tier", "Position + tier"],
                      ["position_league", "Position + league"],
                      ["position_global", "Position global"],
                    ] as const
                  ).map(([key, label]) => (
                    <Button
                      key={key}
                      variant={cohortTier === key ? "primary" : "secondary"}
                      size="sm"
                      onClick={() => setCohortTier(key)}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="label-caps">Clusters (k)</p>
                  <p className="data-mono text-on-surface">{kClusters}</p>
                </div>
                <Slider
                  min={2}
                  max={8}
                  step={1}
                  value={[kClusters]}
                  onValueChange={([v]) => setKClusters(v)}
                />
              </div>
              <div>
                <p className="label-caps mb-2">Club-fit (optional)</p>
                <Input
                  type="text"
                  placeholder="e.g. Bayer Leverkusen"
                  value={clubFitTeam}
                  onChange={(e) => setClubFitTeam(e.target.value)}
                />
                {clubFitTeam && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between">
                      <span className="label-caps">Fit weight</span>
                      <span className="data-mono text-xs text-on-surface">
                        {clubFitWeight.toFixed(2)}
                      </span>
                    </div>
                    <Slider
                      min={0}
                      max={1}
                      step={0.05}
                      value={[clubFitWeight]}
                      onValueChange={([v]) => setClubFitWeight(v)}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </GlassCard>

        {discoverMu.isError && (
          <GlassCard>
            <p className="text-sm text-error">Error: {String(discoverMu.error)}</p>
          </GlassCard>
        )}

        {result && (
          <>
            <GlassCard>
              <div className="flex flex-wrap items-center gap-4 text-xs text-on-surface-variant">
                <span>
                  Cohort N=<span className="text-on-surface data-mono">{result.cohort.n}</span> ·
                  tier <span className="text-on-surface">{result.cohort.tier_used}</span>
                  {result.cohort.fallback_applied && (
                    <span className="ml-1 text-warning">(widened)</span>
                  )}
                </span>
                <span>
                  Min minutes <span className="data-mono text-on-surface">{result.cohort.min_minutes}</span>
                </span>
                <span>
                  Shortlist <span className="data-mono text-on-surface">{totalKept}</span>
                </span>
                {result.silhouette != null && (
                  <span>
                    Silhouette{" "}
                    <span className="data-mono text-on-surface">{result.silhouette.toFixed(2)}</span>
                  </span>
                )}
                {explained.length > 0 && (
                  <span>
                    PCA var{" "}
                    <span className="data-mono text-on-surface">
                      {explained.map((v) => `${(v * 100).toFixed(0)}%`).join(" / ")}
                    </span>
                  </span>
                )}
                {pcaWarn && (
                  <span className="text-warning">
                    PC1+PC2 explain &lt;60% — interpret scatters with caution.
                  </span>
                )}
                {result.cohort.n < 30 && (
                  <span className="text-warning">Cohort small — z-scores unstable.</span>
                )}
              </div>
            </GlassCard>

            <div className="grid gap-4 lg:grid-cols-3">
              <GlassCard>
                <p className="label-caps mb-2">Archetype · PC1 vs PC2</p>
                <ScatterChart
                  points={pcaPoints}
                  xLabel="PC1"
                  yLabel="PC2"
                  height={360}
                  emphasiseTop
                />
              </GlassCard>
              <GlassCard>
                <p className="label-caps mb-2">Archetype · PC1 vs PC3</p>
                <ScatterChart
                  points={pcaPointsPC13}
                  xLabel="PC1"
                  yLabel="PC3"
                  height={360}
                  emphasiseTop
                />
              </GlassCard>
              <GlassCard>
                <p className="label-caps mb-2">Custom z×z</p>
                <div className="mb-2 flex gap-2">
                  <Combobox
                    value={customXMetric}
                    onChange={setCustomXMetric}
                    options={metrics.map((m) => ({
                      value: m.metric,
                      label: metricByName[m.metric]?.label ?? m.metric,
                    }))}
                    className="min-w-0 flex-1"
                  />
                  <Combobox
                    value={customYMetric}
                    onChange={setCustomYMetric}
                    options={metrics.map((m) => ({
                      value: m.metric,
                      label: metricByName[m.metric]?.label ?? m.metric,
                    }))}
                    className="min-w-0 flex-1"
                  />
                </div>
                <ScatterChart
                  points={customPoints}
                  xLabel={`${customXMetric} z`}
                  yLabel={`${customYMetric} z`}
                  height={300}
                  emphasiseTop
                />
              </GlassCard>
            </div>

            {(result.clusters ?? []).length > 0 && (
              <GlassCard>
                <p className="label-caps mb-2">Clusters</p>
                <div className="flex flex-wrap gap-2">
                  {(result.clusters ?? []).map((c) => (
                    <div
                      key={c.cluster_id}
                      className={cn(
                        "rounded-md border border-outline-variant/50 bg-surface-low px-2.5 py-1.5 text-xs",
                      )}
                    >
                      <span className="data-mono text-primary">#{c.cluster_id}</span>
                      <span className="ml-2 text-on-surface">{c.label}</span>
                      <span className="ml-2 text-on-surface-variant">({c.n_members})</span>
                    </div>
                  ))}
                </div>
              </GlassCard>
            )}

            <GlassCard>
              <div className="mb-2 flex items-center justify-between">
                <p className="label-caps">Shortlist · top by composite</p>
                {pageCount > 1 && (
                  <div className="flex items-center gap-1">
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
              <ShortlistTable
                rows={sliced}
                season={f.season}
                showStyleFit={!!clubFitTeam}
                metricLabels={result.metric_labels ?? {}}
              />
            </GlassCard>
          </>
        )}
      </div>
    </div>
  );
}
