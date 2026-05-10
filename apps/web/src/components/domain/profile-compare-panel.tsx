"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Plus, X } from "lucide-react";
import * as React from "react";

import { RadarChart } from "@/components/charts/radar-chart";
import { ExportFilterArea, ExportSection } from "@/components/export";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { Shimmer, SkeletonBlock, SkeletonLine } from "@/components/ui/loading";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { api } from "@/lib/api";
import {
  orderMetricsByPreset,
  presetRoleForPosition,
} from "@/lib/position-metric-presets";
import { COMPARE_PALETTE } from "@/lib/compare-colors";
import { cn } from "@/lib/utils";

import { PlayerSearch } from "./player-search";

interface MetricRow {
  metric: string;
  label: string;
  value: number | null;
  percentile: number | null;
}

interface Props {
  primaryName: string;
  primaryPosition: string | null;
  primaryRadar: MetricRow[];
  primaryTable: MetricRow[];
  season: number;
}

interface CompareSlot {
  wyscoutId: number;
  club: string | null;
}

const MAX_COMPARES = 3;

function seasonShortLabel(year: number): string {
  return `${String(year).slice(2)}-${String(year + 1).slice(2)}`;
}

function maxNumericInRow(values: readonly (number | null | undefined)[]): number | null {
  const nums = values.filter((v): v is number => v != null && !Number.isNaN(v));
  if (nums.length === 0) return null;
  return Math.max(...nums);
}

function isValueAtRowMax(
  value: number | null | undefined,
  rowMax: number | null,
): boolean {
  if (value == null || Number.isNaN(value) || rowMax == null) return false;
  return Math.abs(value - rowMax) <= 1e-6 * Math.max(1, Math.abs(rowMax));
}

export function ProfileComparePanel({
  primaryName,
  primaryPosition,
  primaryRadar,
  primaryTable,
  season,
}: Props) {
  const [open, setOpen] = React.useState(false);
  const [slots, setSlots] = React.useState<CompareSlot[]>([]);
  const [compareSeason, setCompareSeason] = React.useState(season);
  const colors = [...COMPARE_PALETTE];

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  const seasonOpts = (seasonsQ.data ?? []).map((y) => ({
    value: String(y),
    label: seasonShortLabel(y),
  }));

  const [prevSeason, setPrevSeason] = React.useState(season);
  if (prevSeason !== season) {
    setPrevSeason(season);
    setCompareSeason(season);
  }

  const skipCompareSeasonClear = React.useRef(true);
  React.useEffect(() => {
    if (skipCompareSeasonClear.current) {
      skipCompareSeasonClear.current = false;
      return;
    }
    setSlots([]);
  }, [compareSeason]);

  const presetRole = React.useMemo(
    () => presetRoleForPosition(primaryPosition),
    [primaryPosition],
  );

  const orderedTable = React.useMemo(() => {
    const order = orderMetricsByPreset(
      primaryTable.map((r) => r.metric),
      presetRole,
    );
    const indexOf = new Map(order.map((m, i) => [m, i]));
    return [...primaryTable].sort(
      (a, b) => (indexOf.get(a.metric) ?? 1e9) - (indexOf.get(b.metric) ?? 1e9),
    );
  }, [primaryTable, presetRole]);

  const queries = useQueries({
    queries: slots.map((s) => ({
      queryKey: ["profile", s.wyscoutId, s.club, compareSeason],
      queryFn: async () => {
        const { data, error } = await api.GET("/players/{wyscout_id}/profile", {
          params: {
            path: { wyscout_id: s.wyscoutId },
            query: { season: compareSeason, club: s.club ?? undefined },
          },
        });
        if (error) throw new Error(JSON.stringify(error));
        return data!;
      },
    })),
  });

  const others = queries.map((q) => q.data).filter(Boolean) as NonNullable<typeof queries[number]["data"]>[];

  const addSlot = (wyscoutId: number, _player: string, club?: string | null) => {
    if (slots.length >= MAX_COMPARES) return;
    if (slots.some((s) => s.wyscoutId === wyscoutId && (s.club ?? null) === (club ?? null))) return;
    setSlots([...slots, { wyscoutId, club: club ?? null }]);
  };

  const removeSlot = (i: number) => {
    setSlots(slots.filter((_, idx) => idx !== i));
  };

  const primaryColor = colors[0] ?? "#14d1ff";

  const cmpSeasonSuffix =
    compareSeason !== season ? ` · ${seasonShortLabel(compareSeason)}` : "";

  const primarySeasonSuffix =
    compareSeason !== season ? ` · ${seasonShortLabel(season)}` : "";

  return (
    <ExportSection
      id="compare"
      label="Compare"
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
          <h2 className="text-lg font-semibold text-on-surface">Compare with…</h2>
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
          {/* Picker + active chips */}
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {slots.map((s, i) => {
                const data = queries[i].data;
                const color = colors[i + 1] ?? "#fff";
                return (
                  <span
                    key={`${s.wyscoutId}-${s.club ?? ""}`}
                    className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs"
                    style={{
                      borderColor: color + "60",
                      backgroundColor: color + "12",
                      color,
                    }}
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    {data?.player ?? `Player ${s.wyscoutId}`}
                    {s.club ? ` · ${s.club}` : ""}
                    {cmpSeasonSuffix}
                    <button
                      onClick={() => removeSlot(i)}
                      className="ml-1 opacity-70 hover:opacity-100"
                      aria-label="Remove"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                );
              })}
              {slots.length < MAX_COMPARES && (
                <span className="inline-flex items-center gap-1.5 text-xs text-on-surface-variant">
                  <Plus className="h-3 w-3" />
                  Add up to {MAX_COMPARES} players
                </span>
              )}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end sm:gap-4">
              <div className="w-full shrink-0 sm:w-52">
                <p className="label-caps mb-1.5">Comparison season</p>
                <Combobox
                  value={String(compareSeason)}
                  onChange={(v) => setCompareSeason(Number(v))}
                  options={seasonOpts}
                  placeholder="Season"
                />
              </div>
              {slots.length < MAX_COMPARES && (
                <div className="min-w-0 flex-1 sm:max-w-md">
                  <p className="label-caps mb-1.5">Add player</p>
                  <PlayerSearch
                    season={compareSeason}
                    onSelect={addSlot}
                    className="w-full"
                    placeholder="Search a comparison player..."
                  />
                </div>
              )}
            </div>
          </div>
          </ExportFilterArea>

          {queries.some((q) => q.isLoading) && (
            <Shimmer className="space-y-2 rounded-md p-2">
              <SkeletonLine width="40%" />
              <SkeletonBlock className="h-32" />
            </Shimmer>
          )}

          {others.length > 0 && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
              {/* Radar overlay */}
              <div>
                <p className="label-caps mb-3">Radar overlay</p>
                <div className="relative flex items-center justify-center" style={{ minHeight: 380 }}>
                  {/* Primary (with labels, on top of nothing — gets axis labels) */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <RadarChart
                      metrics={primaryRadar.map((m) => ({
                        label: m.label,
                        percentile: m.percentile,
                        value: m.value,
                      }))}
                      size={360}
                      colorOverride={primaryColor}
                    />
                  </div>
                  {/* Secondary radars stacked, no labels */}
                  {others.map((o, i) => {
                    const color = colors[i + 1] ?? "#ff4d9d";
                    return (
                      <div
                        key={`${slots[i]?.wyscoutId}-${slots[i]?.club ?? ""}`}
                        className="absolute inset-0 flex items-center justify-center"
                        style={{ opacity: 0.85 }}
                      >
                        <RadarChart
                          metrics={o.radar.map((m) => ({
                            label: m.label,
                            percentile: m.percentile,
                            value: m.value,
                          }))}
                          size={360}
                          colorOverride={color}
                          hideLabels
                        />
                      </div>
                    );
                  })}
                </div>
                {/* Legend */}
                <div className="mt-3 flex flex-wrap justify-center gap-4 text-xs">
                  <span
                    className="flex items-center gap-1.5"
                    style={{ color: primaryColor }}
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: primaryColor }}
                    />
                    {primaryName}
                    {primarySeasonSuffix}
                  </span>
                  {others.map((o, i) => {
                    const color = colors[i + 1] ?? "#fff";
                    return (
                      <span
                        key={`legend-${i}`}
                        className="flex items-center gap-1.5"
                        style={{ color }}
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: color }}
                        />
                        {o.player}
                        {slots[i]?.club ? ` · ${slots[i]?.club}` : ""}
                        {cmpSeasonSuffix}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Side-by-side metrics */}
              <div>
                <p className="label-caps mb-3">
                  Side-by-side metrics
                  <span className="ml-2 text-on-surface-variant normal-case font-normal">
                    · {presetRole} preset
                  </span>
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left">
                        <th className="px-2 py-1.5 label-caps">Metric</th>
                        <th
                          className="px-2 py-1.5 label-caps text-right"
                          style={{ color: primaryColor }}
                        >
                          {primaryName}
                          {primarySeasonSuffix}
                        </th>
                        {others.map((o, i) => (
                          <th
                            key={`h-${i}`}
                            className="px-2 py-1.5 label-caps text-right"
                            style={{ color: colors[i + 1] }}
                          >
                            {o.player}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {orderedTable.map((row) => {
                        const otherVals = others.map(
                          (o) =>
                            o.table.find((t) => t.metric === row.metric)?.value ?? null,
                        );
                        const rowMax = maxNumericInRow([row.value, ...otherVals]);

                        const primaryMax = isValueAtRowMax(row.value, rowMax);

                        return (
                          <tr
                            key={row.metric}
                            className="border-t border-outline-variant/40"
                          >
                            <td className="px-2 py-1.5 text-on-surface">{row.label}</td>
                            <td
                              className={cn(
                                "px-2 py-1.5 text-right data-mono",
                                !primaryMax && "text-on-surface",
                              )}
                              style={
                                primaryMax ? { color: primaryColor } : undefined
                              }
                            >
                              {row.value == null ? "—" : row.value.toFixed(2)}
                            </td>
                            {others.map((o, i) => {
                              const otherRow = o.table.find((t) => t.metric === row.metric);
                              const v = otherRow?.value;
                              const cmpColor = colors[i + 1] ?? "#ffffff";
                              const otherMax = isValueAtRowMax(v, rowMax);

                              return (
                                <td
                                  key={`v-${i}`}
                                  className={cn(
                                    "px-2 py-1.5 text-right data-mono",
                                    !otherMax && "text-on-surface",
                                  )}
                                  style={
                                    otherMax ? { color: cmpColor } : undefined
                                  }
                                >
                                  {otherRow?.value == null ? "—" : otherRow.value.toFixed(2)}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </GlassCard>
    </ExportSection>
  );
}
