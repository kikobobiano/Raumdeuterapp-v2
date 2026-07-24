"use client";

import { useQuery } from "@tanstack/react-query";
import { PanelLeft, PanelLeftClose } from "lucide-react";
import * as React from "react";

import { ScatterChart } from "@/components/charts/scatter-chart";
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
import { MultiCombobox } from "@/components/ui/multi-combobox";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useFiltersSubtitle } from "@/hooks/use-filters-subtitle";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import {
  compositeMetricId,
  isCompositeMetricId,
  parseCompositeMetricId,
} from "@/lib/composite-indexes";
import { useCompositeIndexes } from "@/lib/composite-indexes-store";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

export default function ScatterPage() {
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();
  const savedIndexes = useCompositeIndexes((s) => s.indexes);
  const [xMetric, setXMetric] = React.useState<string | null>(null);
  const [yMetric, setYMetric] = React.useState<string | null>(null);
  const [xMode, setXMode] = React.useState<MetricMode>("as_is");
  const [yMode, setYMode] = React.useState<MetricMode>("as_is");
  const [highlightWyscoutIds, setHighlightWyscoutIds] = React.useState<number[]>([]);
  const [emphasiseTop, setEmphasiseTop] = React.useState(false);

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

  const metricByName = React.useMemo(() => {
    const m = metricsQ.data ?? [];
    return Object.fromEntries(m.map((row) => [row.name, row]));
  }, [metricsQ.data]);

  const savedById = React.useMemo(
    () => new Map(savedIndexes.map((x) => [x.id, x])),
    [savedIndexes],
  );

  const savedMetricOpts = React.useMemo(
    () =>
      savedIndexes.map((idx) => ({
        value: compositeMetricId(idx.id),
        label: `★ ${idx.name}`,
      })),
    [savedIndexes],
  );

  const lastSeasonRef = React.useRef(f.season);
  React.useEffect(() => {
    const list = metricsQ.data ?? [];
    if (!list.length) return;

    const names = new Set(list.map((r) => r.name));
    for (const opt of savedMetricOpts) names.add(opt.value);
    const seasonChanged = lastSeasonRef.current !== f.season;
    if (seasonChanged) lastSeasonRef.current = f.season;

    const needInit =
      seasonChanged ||
      xMetric === null ||
      yMetric === null ||
      (xMetric !== null && !names.has(xMetric)) ||
      (yMetric !== null && !names.has(yMetric));
    if (!needInit) return;

    const x = list.find((r) => r.name === "xG") ?? list[0];
    const y = list.find((r) => r.name === "xA") ?? list[0];
    setXMetric(x.name);
    setYMetric(y.name);
    setXMode(modeFromMetricOption(x));
    setYMode(modeFromMetricOption(y));
  }, [metricsQ.data, f.season, xMetric, yMetric, savedMetricOpts]);

  const pickX = (name: string) => {
    setXMetric(name);
    if (isCompositeMetricId(name)) {
      setXMode("as_is");
      return;
    }
    setXMode(modeFromMetricOption(metricByName[name]));
  };

  const pickY = (name: string) => {
    setYMetric(name);
    if (isCompositeMetricId(name)) {
      setYMode("as_is");
      return;
    }
    setYMode(modeFromMetricOption(metricByName[name]));
  };

  const axesReady = xMetric != null && yMetric != null;

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const resolveComposite = (metric: string | null) => {
    const id = metric ? parseCompositeMetricId(metric) : null;
    if (!id) return [];
    return savedById.get(id)?.components ?? [];
  };

  const scatterQ = useQuery({
    enabled: axesReady,
    queryKey: [
      "scatter",
      f.season,
      f.leagues,
      f.clubs,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      xMetric,
      yMetric,
      xMode,
      yMode,
      savedIndexes,
    ],
    queryFn: async () => {
      const xComposite = resolveComposite(xMetric);
      const yComposite = resolveComposite(yMetric);
      const xLabel = isCompositeMetricId(xMetric!)
        ? savedById.get(parseCompositeMetricId(xMetric!)!)?.name
        : undefined;
      const yLabel = isCompositeMetricId(yMetric!)
        ? savedById.get(parseCompositeMetricId(yMetric!)!)?.name
        : undefined;
      const { data, error } = await api.POST("/scatter", {
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
          x_metric: xMetric!,
          y_metric: yMetric!,
          x_mode: xMode,
          y_mode: yMode,
          x_composite: xComposite,
          y_composite: yComposite,
          x_label: xLabel ?? null,
          y_label: yLabel ?? null,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
  });

  const showScatterSkeleton = useDelayedLoading(
    !axesReady || scatterQ.isFetching,
    { delay: 80 },
  );

  const highlightOptions = React.useMemo(() => {
    const pts = scatterQ.data?.points ?? [];
    const seen = new Map<number, string>();
    for (const p of pts) {
      const raw = p.wyscout_id;
      if (raw == null || Number.isNaN(Number(raw))) continue;
      const id = Number(raw);
      if (!seen.has(id)) seen.set(id, p.player);
    }
    return [...seen.entries()]
      .sort((a, b) => a[1].localeCompare(b[1], undefined, { sensitivity: "base" }))
      .map(([id, player]) => ({ value: String(id), label: player }));
  }, [scatterQ.data?.points]);

  const validHighlightIds = React.useMemo(() => {
    const pts = scatterQ.data?.points ?? [];
    const valid = new Set(
      pts
        .map((p) => p.wyscout_id)
        .filter((id): id is number => id != null && Number.isFinite(Number(id)))
        .map((id) => Number(id)),
    );
    return highlightWyscoutIds.filter((id) => valid.has(id));
  }, [scatterQ.data?.points, highlightWyscoutIds]);

  const metricOpts = [
    ...savedMetricOpts,
    ...(metricsQ.data ?? []).map((m) => ({ value: m.name, label: m.label })),
  ];

  const xMeta = xMetric && !isCompositeMetricId(xMetric) ? metricByName[xMetric] : undefined;
  const yMeta = yMetric && !isCompositeMetricId(yMetric) ? metricByName[yMetric] : undefined;

  const subtitle = useFiltersSubtitle({
    prefix: scatterQ.data ? `${scatterQ.data.n} players` : null,
  });

  return (
    <ExportProvider title="Scatter Analysis" filename={`scatter-${String(f.season).slice(2)}-${String(f.season + 1).slice(2)}.png`}>
    <div
      className={cn("grid gap-6", filtersOpen ? "grid-cols-[280px_1fr]" : "grid-cols-1")}
    >
      {filtersOpen ? (
        <ExportFilterArea>
        <GlassCard id="scatter-filters-panel">
          <p className="label-caps mb-4">Axes</p>
          <div className="mb-6 space-y-3">
            <div>
              <p className="label-caps mb-1">X-Axis Metric</p>
              <div className="flex gap-2">
                <Combobox
                  value={xMetric ?? ""}
                  onChange={pickX}
                  options={metricOpts}
                  className="min-w-0 flex-1"
                />
                {!isCompositeMetricId(xMetric ?? "") ? (
                  <MetricModeToggle
                    supports={!!xMeta?.supports_mode}
                    value={xMode}
                    onChange={setXMode}
                  />
                ) : null}
              </div>
            </div>
            <div>
              <p className="label-caps mb-1">Y-Axis Metric</p>
              <div className="flex gap-2">
                <Combobox
                  value={yMetric ?? ""}
                  onChange={pickY}
                  options={metricOpts}
                  className="min-w-0 flex-1"
                />
                {!isCompositeMetricId(yMetric ?? "") ? (
                  <MetricModeToggle
                    supports={!!yMeta?.supports_mode}
                    value={yMode}
                    onChange={setYMode}
                  />
                ) : null}
              </div>
            </div>
          </div>

          <p className="label-caps mb-2">Highlight players</p>
          <div className="mb-6 flex flex-col gap-2">
            <MultiCombobox
              value={highlightWyscoutIds.map(String)}
              onChange={(ids) => setHighlightWyscoutIds(ids.map(Number).filter(Number.isFinite))}
              options={highlightOptions}
              placeholder="Search players…"
              className="w-full"
            />
            {highlightWyscoutIds.length > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="self-start text-xs text-primary hover:underline"
                onClick={() => setHighlightWyscoutIds([])}
              >
                Clear highlights
              </Button>
            ) : null}
          </div>

          <p className="label-caps mb-3">Chart emphasis</p>
          <div className="mb-6">
            <label className="flex cursor-pointer items-start gap-3 text-sm text-on-surface">
              <input
                type="checkbox"
                checked={emphasiseTop}
                onChange={(e) => setEmphasiseTop(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-outline-variant bg-surface-mid text-primary focus-visible:ring-2 focus-visible:ring-primary/40"
              />
              <span>
                <span className="font-medium">Emphasise top performers</span>
                <span className="mt-0.5 block text-xs text-on-surface-variant">
                  Highlights top 15 per axis + top 15 dual; others are dimmed.
                </span>
              </span>
            </label>
          </div>

          <p className="label-caps mb-4">Population Filter</p>
          <FilterPanel />
        </GlassCard>
        </ExportFilterArea>
      ) : null}

      <ExportSection id="chart" label="Scatter chart" required defaultIncluded>
      <GlassCard className="flex flex-col">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">Scatter Analysis</h1>
            <FiltersSubtitleLine>{subtitle}</FiltersSubtitleLine>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <ExportFilterArea>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="gap-1.5"
                onClick={() => setFiltersOpen(!filtersOpen)}
                aria-expanded={filtersOpen}
                aria-controls={filtersOpen ? "scatter-filters-panel" : undefined}
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
        {metricsQ.isError ? (
          <div className="text-sm text-error">Could not load metrics for this season.</div>
        ) : showScatterSkeleton ? (
          <ChartSkeleton variant="scatter" height={520} />
        ) : scatterQ.error ? (
          <div className="text-sm text-error">Error: {String(scatterQ.error)}</div>
        ) : (
          <div className="mx-auto w-[90%] max-w-full min-w-0">
            <ScatterChart
              key={filtersOpen ? "filters-open" : "filters-closed"}
              points={scatterQ.data?.points ?? []}
              xLabel={scatterQ.data?.x_label ?? xMetric ?? ""}
              yLabel={scatterQ.data?.y_label ?? yMetric ?? ""}
              highlightWyscoutIds={validHighlightIds}
              emphasiseTop={emphasiseTop}
            />
          </div>
        )}
      </GlassCard>
      </ExportSection>
    </div>
    </ExportProvider>
  );
}
