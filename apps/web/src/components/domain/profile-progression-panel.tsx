"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import * as React from "react";

import { ProgressionChart } from "@/components/charts/progression-chart";
import { ExportFilterArea, ExportSection } from "@/components/export";
import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { Slider } from "@/components/ui/slider";
import {
  MetricModeToggle,
  modeFromMetricOption,
  type MetricMode,
} from "@/components/domain/metric-mode-toggle";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { api } from "@/lib/api";

interface Props {
  wyscoutId: number;
  targetSeason: number;
  playerImageUrl?: string | null;
  initialMetrics?: string[];
}

const DEFAULT_METRICS = ["xG", "xA", "Goals"];

/** Always fetch this many seasons; narrower window is client-side slice (no extra API calls). */
const PROGRESSION_FETCH_SEASONS = 10;

export function ProfileProgressionPanel({
  wyscoutId,
  targetSeason,
  playerImageUrl,
  initialMetrics = DEFAULT_METRICS,
}: Props) {
  const [open, setOpen] = React.useState(false);
  const [seasonsCount, setSeasonsCount] = React.useState(10);
  const [metrics, setMetrics] = React.useState<string[]>(initialMetrics);
  const [mode, setMode] = React.useState<MetricMode>("p90");
  const [pickerValue, setPickerValue] = React.useState<string>("");

  const metricsListQ = useQuery({
    queryKey: ["metrics", targetSeason],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/metrics", {
        params: { query: { season: targetSeason } },
      });
      if (error) throw new Error("metrics");
      return data ?? [];
    },
    enabled: open,
  });

  const metricByName = React.useMemo(() => {
    const m = metricsListQ.data ?? [];
    return Object.fromEntries(m.map((row) => [row.name, row]));
  }, [metricsListQ.data]);

  const progQ = useQuery({
    queryKey: ["progression", wyscoutId, metrics, targetSeason, mode],
    queryFn: async () => {
      const { data, error } = await api.POST("/players/{wyscout_id}/progression", {
        params: { path: { wyscout_id: wyscoutId } },
        body: {
          metrics,
          target_season: targetSeason,
          seasons_count: PROGRESSION_FETCH_SEASONS,
          mode,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    enabled: metrics.length > 0,
  });

  const showProgressionSkeleton = useDelayedLoading(progQ.isPending);

  const progressionVisible = React.useMemo(() => {
    const data = progQ.data;
    if (!data?.metrics.length || !data.seasons.length) return null;
    const n = Math.min(seasonsCount, data.seasons.length);
    const visibleSeasons = data.seasons.slice(-n);
    const visibleMetrics = data.metrics.map((s) => ({
      ...s,
      points: s.points.filter((p) => visibleSeasons.includes(p.season)),
    }));

    const seasonHasNumericMetric = (season: number) =>
      visibleMetrics.some((ser) => {
        const p = ser.points.find((pt) => pt.season === season);
        return typeof p?.value === "number" && !Number.isNaN(p.value);
      });

    const compactSeasons = visibleSeasons.filter(seasonHasNumericMetric);
    const shouldCompact =
      compactSeasons.length > 0 && compactSeasons.length < visibleSeasons.length;
    const seasonsOut = shouldCompact ? compactSeasons : visibleSeasons;
    const seriesOut = shouldCompact
      ? visibleMetrics.map((s) => ({
          ...s,
          points: s.points.filter((p) => seasonsOut.includes(p.season)),
        }))
      : visibleMetrics;

    return { series: seriesOut, seasons: seasonsOut };
  }, [progQ.data, seasonsCount]);

  const metricOpts = (metricsListQ.data ?? [])
    .filter((m) => !metrics.includes(m.name))
    .map((m) => ({ value: m.name, label: m.label }));

  const addMetric = (name: string) => {
    if (!name || metrics.includes(name) || metrics.length >= 10) return;
    setMetrics([...metrics, name]);
    setPickerValue("");
    const meta = metricByName[name];
    if (meta && metrics.length === 0) {
      setMode(modeFromMetricOption(meta));
    }
  };

  const removeMetric = (name: string) =>
    setMetrics(metrics.filter((m) => m !== name));

  const supportsMode = metrics.some((m) => metricByName[m]?.supports_mode);

  return (
    <ExportSection
      id="metric-progression"
      label="Progression"
      defaultIncluded={false}
      disabled={!open}
      disabledReason="Open the panel to include it in the export."
    >
    <GlassCard>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-on-surface">Progression</h2>
        </div>
        <span data-export-hide aria-hidden>
          {open ? (
            <ChevronUp className="h-4 w-4 text-on-surface-variant" />
          ) : (
            <ChevronDown className="h-4 w-4 text-on-surface-variant" />
          )}
        </span>
      </button>

      {open && (
        <div className="mt-5 space-y-5">
          <ExportFilterArea>
          <div className="space-y-4">
            <div>
              <div
                className={
                  supportsMode
                    ? "mb-2 grid gap-x-3 gap-y-2 [grid-template-columns:minmax(0,1fr)_auto]"
                    : "mb-2 grid gap-y-2"
                }
              >
                <p className="label-caps">Metrics ({metrics.length}/10)</p>
                {supportsMode ? <p className="label-caps">Mode</p> : null}
                <Combobox
                  value={pickerValue}
                  onChange={addMetric}
                  options={metricOpts}
                  placeholder="Add metric…"
                  className="min-w-0 w-full"
                />
                {supportsMode ? (
                  <div className="flex items-center">
                    <MetricModeToggle
                      supports={supportsMode}
                      value={mode}
                      onChange={setMode}
                    />
                  </div>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {metrics.map((m) => {
                  const label = metricByName[m]?.label ?? m;
                  return (
                    <span
                      key={m}
                      className="inline-flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary/15 px-2 py-1 text-xs text-primary"
                    >
                      {label}
                      <button
                        type="button"
                        onClick={() => removeMetric(m)}
                        className="hover:text-on-surface"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="label-caps">Seasons</p>
                <span className="data-mono text-xs text-on-surface">{seasonsCount}</span>
              </div>
              <Slider
                min={2}
                max={10}
                step={1}
                value={[seasonsCount]}
                onValueChange={(v) => setSeasonsCount(v[0] ?? 10)}
              />
            </div>
          </div>
          </ExportFilterArea>

          {showProgressionSkeleton && (
            <ChartSkeleton variant="progression" height={220} />
          )}
          {progQ.isError && (
            <p className="text-sm text-error">Error loading progression.</p>
          )}
          {progressionVisible && (
            <ProgressionChart
              series={progressionVisible.series}
              seasons={progressionVisible.seasons}
              playerWyscoutId={wyscoutId}
              playerImageUrl={playerImageUrl ?? null}
            />
          )}
        </div>
      )}
    </GlassCard>
    </ExportSection>
  );
}
