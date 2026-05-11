"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, PanelLeft, PanelLeftClose, X } from "lucide-react";
import * as React from "react";

import { HorizontalBarRanking } from "@/components/charts/horizontal-bar-ranking";
import { FilterPanel } from "@/components/domain/filter-panel";
import { FiltersSubtitleLine } from "@/components/domain/filters-subtitle-line";
import {
  ExportButton,
  ExportFilterArea,
  ExportProvider,
  ExportSection,
} from "@/components/export";
import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import {
  MetricModeToggle,
  modeFromMetricOption,
  type MetricMode,
} from "@/components/domain/metric-mode-toggle";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useFiltersSubtitle } from "@/hooks/use-filters-subtitle";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

interface PickedMetric {
  metric: string;
  mode: MetricMode;
}

const DEFAULT_METRICS: PickedMetric[] = [
  { metric: "xG", mode: "p90" },
  { metric: "xA", mode: "p90" },
  { metric: "Goals", mode: "p90" },
];

export default function BarPage() {
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();
  const [picked, setPicked] = React.useState<PickedMetric[]>(DEFAULT_METRICS);
  const [sortDesc, setSortDesc] = React.useState(true);
  const [pickerValue, setPickerValue] = React.useState<string>("");

  const metricsListQ = useQuery({
    queryKey: ["metrics", f.season],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/metrics", {
        params: { query: { season: f.season } },
      });
      if (error) throw new Error("metrics");
      return data ?? [];
    },
  });

  const metricByName = React.useMemo(() => {
    const m = metricsListQ.data ?? [];
    return Object.fromEntries(m.map((row) => [row.name, row]));
  }, [metricsListQ.data]);

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const barQ = useQuery({
    queryKey: [
      "bar-ranking",
      f.season,
      f.leagues,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      picked,
      sortDesc,
    ],
    queryFn: async () => {
      const { data, error } = await api.POST("/bar/ranking", {
        body: {
          filters: {
            season: f.season,
            leagues: f.leagues.length ? f.leagues : null,
            roles: rolesPayload.length ? rolesPayload : null,
            age_min: f.ageMin,
            age_max: f.ageMax,
            minutes_min: f.minutesMin,
          },
          metrics: picked.map((p) => p.metric),
          modes: picked.map((p) => p.mode),
          sort_combined: true,
          sort_by: "",
          sort_mode: "as_is",
          sort_desc: sortDesc,
          limit: 20,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    enabled: picked.length > 0,
  });

  const showBarSkeleton = useDelayedLoading(
    picked.length > 0 && barQ.isFetching,
    { delay: 80 },
  );

  const metricOpts = (metricsListQ.data ?? [])
    .filter((m) => !picked.find((p) => p.metric === m.name))
    .map((m) => ({ value: m.name, label: m.label }));

  const addMetric = (name: string) => {
    if (!name || picked.find((p) => p.metric === name) || picked.length >= 3) return;
    const meta = metricByName[name];
    setPicked([...picked, { metric: name, mode: modeFromMetricOption(meta) }]);
    setPickerValue("");
  };

  const removeMetric = (name: string) => {
    setPicked((prev) => prev.filter((p) => p.metric !== name));
  };

  const updateMode = (i: number, mode: MetricMode) =>
    setPicked(picked.map((p, idx) => (idx === i ? { ...p, mode } : p)));

  const subtitle = useFiltersSubtitle({
    prefix: `Top 20 by combined normalized score (${picked.length} metric${
      picked.length === 1 ? "" : "s"
    })`,
  });

  return (
    <ExportProvider title="Bar Chart" filename={`bar-chart-${String(f.season).slice(2)}-${String(f.season + 1).slice(2)}.png`}>
    <div className={cn("grid gap-6", filtersOpen ? "grid-cols-[280px_minmax(0,1fr)]" : "grid-cols-1")}>
      {filtersOpen ? (
        <ExportFilterArea>
        <GlassCard id="bar-filters-panel">
          <p className="label-caps mb-3">Metrics ({picked.length}/3)</p>
          <div className="space-y-2 mb-3">
            {picked.map((p, i) => {
              const meta = metricByName[p.metric];
              return (
                <div
                  key={p.metric}
                  className="flex items-center gap-2 rounded-md bg-surface-low p-2"
                >
                  <span className="flex-1 truncate text-sm text-on-surface">
                    {meta?.label ?? p.metric}
                  </span>
                  <MetricModeToggle
                    supports={!!meta?.supports_mode}
                    value={p.mode}
                    onChange={(m) => updateMode(i, m)}
                  />
                  <button
                    type="button"
                    onClick={() => removeMetric(p.metric)}
                    className="text-on-surface-variant hover:text-on-surface"
                    aria-label="Remove"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              );
            })}
          </div>

          {picked.length < 3 && (
            <Combobox
              value={pickerValue}
              onChange={addMetric}
              options={metricOpts}
              placeholder="Add metric…"
              className="mb-4"
            />
          )}

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="mb-6 w-full gap-1.5"
            onClick={() => setSortDesc(!sortDesc)}
          >
            {sortDesc ? <ArrowDown className="h-4 w-4" /> : <ArrowUp className="h-4 w-4" />}
            {sortDesc ? "Ranking: highest combined first" : "Ranking: lowest combined first"}
          </Button>

          <p className="label-caps mb-3">Population</p>
          <FilterPanel />
        </GlassCard>
        </ExportFilterArea>
      ) : null}

      <ExportSection id="chart" label="Bar chart" required defaultIncluded>
      <GlassCard>
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">Bar Chart</h1>
            <FiltersSubtitleLine>{subtitle}</FiltersSubtitleLine>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <ExportFilterArea>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={() => setFiltersOpen(!filtersOpen)}
                aria-expanded={filtersOpen}
                aria-controls={filtersOpen ? "bar-filters-panel" : undefined}
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

        {picked.length === 0 ? (
          <p className="text-on-surface-variant">Pick at least one metric to start.</p>
        ) : showBarSkeleton ? (
          <ChartSkeleton variant="bar" height={420} />
        ) : barQ.error ? (
          <p className="text-error text-sm">Error</p>
        ) : barQ.data ? (
          barQ.data.rows.length === 0 ? (
            <p className="text-on-surface-variant">No players match the current filters.</p>
          ) : (
            <HorizontalBarRanking
              rows={barQ.data.rows}
              metrics={barQ.data.metrics}
              labels={barQ.data.labels}
              metricMaxAbs={barQ.data.metric_max_abs ?? null}
            />
          )
        ) : null}
      </GlassCard>
      </ExportSection>
    </div>
    </ExportProvider>
  );
}
