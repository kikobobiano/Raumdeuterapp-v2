"use client";

import { useQuery } from "@tanstack/react-query";
import { PanelLeft, PanelLeftClose, Plus, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { FilterPanel } from "@/components/domain/filter-panel";
import { FiltersSubtitleLine } from "@/components/domain/filters-subtitle-line";
import {
  ExportButton,
  ExportFilterArea,
  ExportProvider,
  ExportSection,
} from "@/components/export";
import { RankingsTableSkeleton } from "@/components/skeletons/rankings-table-skeleton";
import {
  MetricModeToggle,
  modeFromMetricOption,
  type MetricMode,
} from "@/components/domain/metric-mode-toggle";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { MultiCombobox } from "@/components/ui/multi-combobox";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useFiltersSubtitle } from "@/hooks/use-filters-subtitle";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

interface Criterion {
  metric: string;
  mode: MetricMode;
  operator: ">=" | "<=" | ">" | "<" | "=" | "!=";
  value: number;
}

type CompositeBasis = "value" | "team_median";

interface CompositeComponent {
  metric: string;
  mode: MetricMode;
  basis: CompositeBasis;
  weight: number;
}

const DEFAULT_CRITERIA: Criterion[] = [
  { metric: "xG", mode: "p90", operator: ">=", value: 0.3 },
  { metric: "Successful dribbles, %", mode: "as_is", operator: ">=", value: 50 },
];

const DEFAULT_COMPOSITE: CompositeComponent[] = [
  { metric: "Aerial duels per 90", mode: "p90", basis: "value", weight: 2 },
  { metric: "Successful dribbles, %", mode: "as_is", basis: "team_median", weight: 1 },
];

const PAGE_SIZE = 20;
const MAX_SCREENER_SEASONS = 8;

function seasonLabel(y: number): string {
  return `${String(y).slice(2)}-${String(y + 1).slice(2)}`;
}

function screenerExportFilename(selectedSeasons: number[], fallbackSeason: number): string {
  if (selectedSeasons.length === 0) {
    return `screener-${seasonLabel(fallbackSeason)}.png`;
  }
  const min = Math.min(...selectedSeasons);
  const max = Math.max(...selectedSeasons);
  return `screener-${String(min).slice(2)}-${String(max + 1).slice(2)}.png`;
}

function metricHeaderLabel(mode: MetricMode, label: string) {
  if (mode === "p90") return `${label} (/90)`;
  if (mode === "raw") return `${label} (raw)`;
  return label;
}

function criterionHeaderLabel(c: Criterion, label: string) {
  return metricHeaderLabel(c.mode, label);
}

function compositeBasisLabel(basis: CompositeBasis) {
  return basis === "team_median" ? "vs team median" : "season value";
}

function formatCriterionOperator(op: Criterion["operator"]): string {
  if (op === ">=") return "≥";
  if (op === "<=") return "≤";
  return op;
}

function formatCriteriaDescription(
  criteria: Criterion[],
  metricOpts: { value: string; label: string }[],
): string {
  if (criteria.length === 0) return "";
  return criteria
    .map((c) => {
      const lab = metricOpts.find((o) => o.value === c.metric)?.label ?? c.metric;
      const name = criterionHeaderLabel(c, lab);
      return `${name} ${formatCriterionOperator(c.operator)} ${c.value}`;
    })
    .join(" · ");
}

function formatCompositeIndexDescription(
  components: CompositeComponent[],
  metricOpts: { value: string; label: string }[],
): string {
  const weightSum = components.reduce((acc, c) => acc + Math.abs(c.weight), 0) || 1;
  const parts = components.map((comp) => {
    const lab = metricOpts.find((o) => o.value === comp.metric)?.label ?? comp.metric;
    const pct = Math.round((Math.abs(comp.weight) / weightSum) * 100);
    const name = metricHeaderLabel(comp.mode, lab);
    return `${pct}% ${name} (${compositeBasisLabel(comp.basis)})`;
  });
  return `Index · ${parts.join(" · ")}`;
}

/** Club crest + name — logo without frame. */
function ClubWithLogoCell({
  club,
  logoUrl,
}: {
  club: string | null | undefined;
  logoUrl: string | null | undefined;
}) {
  return (
    <div className="flex min-w-0 max-w-[240px] items-center gap-2.5">
      <ClubLogoImg logoUrl={logoUrl} className="h-7 w-7" />
      <span className="min-w-0 truncate text-on-surface">{club ?? "—"}</span>
    </div>
  );
}

export default function ScreenerPage() {
  const router = useRouter();
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();
  const [selectedSeasons, setSelectedSeasons] = React.useState<number[]>([]);
  const [criteria, setCriteria] = React.useState<Criterion[]>(DEFAULT_CRITERIA);
  const [compositeEnabled, setCompositeEnabled] = React.useState(false);
  const [compositeComponents, setCompositeComponents] =
    React.useState<CompositeComponent[]>(DEFAULT_COMPOSITE);
  const [sortByComposite, setSortByComposite] = React.useState(true);
  const [sortBy, setSortBy] = React.useState("xG");
  const [sortMode, setSortMode] = React.useState<MetricMode>("p90");
  const [page, setPage] = React.useState(1);

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  React.useEffect(() => {
    if (!seasonsQ.isSuccess) return;
    const valid = new Set(seasonsQ.data ?? []);
    const pruned = selectedSeasons.filter((y) => valid.has(y));
    if (pruned.length !== selectedSeasons.length) setSelectedSeasons(pruned);
    // Intentionally keyed on the fetched option set, not on selectedSeasons.
  }, [seasonsQ.isSuccess, seasonsQ.data]);

  const seasonOptions = React.useMemo(
    () =>
      (seasonsQ.data ?? []).map((y) => ({
        value: String(y),
        label: seasonLabel(y),
      })),
    [seasonsQ.data],
  );

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

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const filterSig = React.useMemo(
    () =>
      JSON.stringify([
        f.season,
        selectedSeasons,
        f.leagues,
        rolesPayload,
        f.ageMin,
        f.ageMax,
        f.minutesMin,
        criteria,
        compositeEnabled,
        compositeComponents,
        sortByComposite,
        sortBy,
        sortMode,
      ]),
    [
      f.season,
      selectedSeasons,
      f.leagues,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      criteria,
      compositeEnabled,
      compositeComponents,
      sortByComposite,
      sortBy,
      sortMode,
    ],
  );
  const [prevFilterSig, setPrevFilterSig] = React.useState(filterSig);
  if (prevFilterSig !== filterSig) {
    setPrevFilterSig(filterSig);
    setPage(1);
  }

  const offset = (page - 1) * PAGE_SIZE;

  const screenQ = useQuery({
    queryKey: [
      "screener",
      f.season,
      selectedSeasons,
      f.leagues,
      f.clubs,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      criteria,
      compositeEnabled,
      compositeComponents,
      sortByComposite,
      sortBy,
      sortMode,
      page,
    ],
    queryFn: async () => {
      const { data, error } = await api.POST("/screener", {
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
          seasons: selectedSeasons,
          criteria,
          composite: compositeEnabled ? compositeComponents : [],
          sort_by_composite: compositeEnabled && sortByComposite,
          sort_by: sortBy,
          sort_mode: sortMode,
          sort_desc: true,
          limit: PAGE_SIZE,
          offset,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    placeholderData: (previousData) => previousData,
  });

  const showScreenerSkeleton = useDelayedLoading(screenQ.isPending);
  const total = screenQ.data?.total ?? 0;
  const rows = screenQ.data?.rows ?? [];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (screenQ.isSuccess && total > 0 && page > totalPages) {
    setPage(totalPages);
  }

  const metricOpts = (metricsQ.data ?? []).map((m) => ({ value: m.name, label: m.label }));

  const allowedSortMetrics = React.useMemo(() => {
    const names = new Set<string>();
    for (const c of criteria) names.add(c.metric);
    if (compositeEnabled) {
      for (const comp of compositeComponents) names.add(comp.metric);
    }
    return names;
  }, [criteria, compositeEnabled, compositeComponents]);

  const sortMetricOpts = React.useMemo(
    () => metricOpts.filter((o) => allowedSortMetrics.has(o.value)),
    [metricOpts, allowedSortMetrics],
  );

  const modeForSortMetric = React.useCallback(
    (name: string): MetricMode => {
      const crit = criteria.find((c) => c.metric === name);
      if (crit) return crit.mode;
      if (compositeEnabled) {
        const comp = compositeComponents.find((c) => c.metric === name);
        if (comp) return comp.mode;
      }
      return modeFromMetricOption(metricByName[name]);
    },
    [criteria, compositeEnabled, compositeComponents, metricByName],
  );

  React.useEffect(() => {
    if (sortByComposite || allowedSortMetrics.has(sortBy)) return;
    const fallback =
      criteria[0]?.metric ??
      (compositeEnabled ? compositeComponents[0]?.metric : undefined);
    if (!fallback) return;
    setSortBy(fallback);
    setSortMode(modeForSortMetric(fallback));
  }, [allowedSortMetrics, sortBy, sortByComposite, criteria, compositeEnabled, compositeComponents, modeForSortMetric]);

  const update = (i: number, patch: Partial<Criterion>) =>
    setCriteria(criteria.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));

  const updateComposite = (i: number, patch: Partial<CompositeComponent>) =>
    setCompositeComponents(
      compositeComponents.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
    );

  const onCriterionMetric = (i: number, name: string) => {
    const meta = metricByName[name];
    update(i, {
      metric: name,
      mode: modeFromMetricOption(meta),
    });
  };

  const onSortMetric = (name: string) => {
    setSortBy(name);
    setSortMode(modeForSortMetric(name));
    setSortByComposite(false);
  };

  const onCompositeMetric = (i: number, name: string) => {
    const meta = metricByName[name];
    updateComposite(i, {
      metric: name,
      mode: modeFromMetricOption(meta),
    });
  };

  const sortMeta = metricByName[sortBy];

  const subtitlePrefix = screenQ.isError
    ? ""
    : total === 0 && !screenQ.isPending
      ? "0 results"
      : total > 0
        ? `${offset + 1}–${offset + rows.length} of ${total}${
            total > PAGE_SIZE ? ` · Page ${Math.min(page, totalPages)} of ${totalPages}` : ""
          }`
        : "";
  const subtitle = useFiltersSubtitle({ prefix: subtitlePrefix || null });

  const criteriaDescription = React.useMemo(
    () => formatCriteriaDescription(criteria, metricOpts),
    [criteria, metricOpts],
  );

  const compositeIndexDescription = React.useMemo(() => {
    if (!compositeEnabled || compositeComponents.length === 0) return null;
    return formatCompositeIndexDescription(compositeComponents, metricOpts);
  }, [compositeEnabled, compositeComponents, metricOpts]);

  return (
    <ExportProvider title="Screener" filename={screenerExportFilename(selectedSeasons, f.season)}>
    <div className={cn("grid gap-6", filtersOpen ? "grid-cols-[280px_1fr]" : "grid-cols-1")}>
      {filtersOpen ? (
      <ExportFilterArea>
      <GlassCard id="screener-filters-panel">
        <p className="label-caps mb-4">Criteria</p>
        <div className="space-y-3 mb-4">
          {criteria.map((c, i) => {
            const meta = metricByName[c.metric];
            return (
              <div key={`crit-${i}`} className="space-y-2 rounded-md bg-surface-low p-3">
                <div className="flex gap-2">
                  <Combobox
                    value={c.metric}
                    onChange={(v) => onCriterionMetric(i, v)}
                    options={metricOpts}
                    className="min-w-0 flex-1"
                  />
                  <MetricModeToggle
                    supports={!!meta?.supports_mode}
                    value={c.mode}
                    onChange={(mode) => update(i, { mode })}
                  />
                </div>
                <div className="flex gap-2">
                  <select
                    value={c.operator}
                    onChange={(e) => update(i, { operator: e.target.value as Criterion["operator"] })}
                    className="rounded-md bg-surface-mid px-2 py-1 text-sm text-on-surface"
                  >
                    {[">=", "<=", ">", "<", "=", "!="].map((op) => (
                      <option key={op} value={op}>{op}</option>
                    ))}
                  </select>
                  <Input
                    type="number"
                    value={c.value}
                    onChange={(e) => update(i, { value: parseFloat(e.target.value) })}
                    className="flex-1"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCriteria(criteria.filter((_, idx) => idx !== i))}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full mb-6"
          disabled={criteria.length >= 8}
          onClick={() => {
            if (criteria.length >= 8) return;
            const first = metricOpts[0];
            if (!first) return;
            const meta = metricByName[first.value];
            setCriteria([
              ...criteria,
              {
                metric: first.value,
                mode: modeFromMetricOption(meta),
                operator: ">=",
                value: 0,
              },
            ]);
          }}
        >
          <Plus className="h-4 w-4" />
          {criteria.length >= 8 ? "Max 8 criteria" : "Add criterion"}
        </Button>

        <p className="label-caps mb-2">Sort by</p>
        <div className={cn("flex gap-2", compositeEnabled && sortByComposite && "opacity-50")}>
          <Combobox
            value={sortBy}
            onChange={onSortMetric}
            options={sortMetricOpts}
            className="min-w-0 flex-1"
          />
          <MetricModeToggle
            supports={!!sortMeta?.supports_mode}
            value={sortMode}
            onChange={(mode) => {
              setSortMode(mode);
              setSortByComposite(false);
            }}
          />
        </div>
        {sortMetricOpts.length === 0 ? (
          <p className="mt-1 text-xs text-on-surface-variant">
            Add criteria or composite components to choose a sort metric.
          </p>
        ) : null}

        <div className="mt-6 border-t border-outline-variant/40 pt-6">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="label-caps">Composite index</p>
            <label className="flex items-center gap-2 text-xs text-on-surface-variant">
              <input
                type="checkbox"
                checked={compositeEnabled}
                onChange={(e) => {
                  setCompositeEnabled(e.target.checked);
                  if (e.target.checked) setSortByComposite(true);
                }}
                className="rounded border-outline-variant"
              />
              Enable
            </label>
          </div>
          {compositeEnabled ? (
            <>
              <div className="space-y-3">
                {compositeComponents.map((comp, i) => {
                  const meta = metricByName[comp.metric];
                  const lab =
                    metricOpts.find((o) => o.value === comp.metric)?.label ?? comp.metric;
                  return (
                    <div key={`comp-${i}`} className="space-y-2 rounded-md bg-surface-low p-3">
                      <div className="flex gap-2">
                        <Combobox
                          value={comp.metric}
                          onChange={(v) => onCompositeMetric(i, v)}
                          options={metricOpts}
                          className="min-w-0 flex-1"
                        />
                        <MetricModeToggle
                          supports={!!meta?.supports_mode}
                          value={comp.mode}
                          onChange={(mode) => updateComposite(i, { mode })}
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setCompositeComponents(
                              compositeComponents.filter((_, idx) => idx !== i),
                            )
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          value={comp.basis}
                          onChange={(e) =>
                            updateComposite(i, {
                              basis: e.target.value as CompositeBasis,
                            })
                          }
                          className="rounded-md bg-surface-mid px-2 py-1 text-sm text-on-surface"
                        >
                          <option value="value">Season value</option>
                          <option value="team_median">vs team median</option>
                        </select>
                        <div className="flex min-w-0 flex-1 items-center gap-2">
                          <span className="label-caps shrink-0">Weight</span>
                          <Input
                            type="number"
                            step={0.1}
                            min={0}
                            value={comp.weight}
                            onChange={(e) =>
                              updateComposite(i, {
                                weight: parseFloat(e.target.value) || 0,
                              })
                            }
                            className="w-20"
                          />
                        </div>
                      </div>
                      <p className="text-xs text-on-surface-variant">
                        {metricHeaderLabel(comp.mode, lab)} · {compositeBasisLabel(comp.basis)}
                      </p>
                    </div>
                  );
                })}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="mt-3 w-full"
                disabled={compositeComponents.length >= 8}
                onClick={() => {
                  const first = metricOpts[0];
                  if (!first) return;
                  const meta = metricByName[first.value];
                  setCompositeComponents([
                    ...compositeComponents,
                    {
                      metric: first.value,
                      mode: modeFromMetricOption(meta),
                      basis: "value",
                      weight: 1,
                    },
                  ]);
                }}
              >
                <Plus className="h-4 w-4" />
                {compositeComponents.length >= 8 ? "Max 8 components" : "Add component"}
              </Button>
              <label className="mt-4 flex items-center gap-2 text-sm text-on-surface">
                <input
                  type="checkbox"
                  checked={sortByComposite}
                  onChange={(e) => setSortByComposite(e.target.checked)}
                  className="rounded border-outline-variant"
                />
                Sort by composite score
              </label>
              <p className="mt-2 text-xs text-on-surface-variant">
                Weighted z-score within position + league cohort. Team-median components use
                player value ÷ team median (1.0 = average teammate).
              </p>
            </>
          ) : (
            <p className="text-xs text-on-surface-variant">
              Combine metrics into a custom index with weights and optional team-relative
              comparisons.
            </p>
          )}
        </div>

        <div className="mt-6">
          <p className="label-caps mb-3">Population</p>
          <div className="mb-5">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="label-caps">Seasons</p>
              {selectedSeasons.length > 0 && (
                <button
                  type="button"
                  className="shrink-0 text-xs text-primary hover:underline"
                  onClick={() => setSelectedSeasons([])}
                >
                  Clear
                </button>
              )}
            </div>
            <p className="mb-2 text-xs text-on-surface-variant">
              Multi-select. None = current season (global). Max {MAX_SCREENER_SEASONS}.
            </p>
            <MultiCombobox
              value={selectedSeasons.map(String)}
              onChange={(vals) => {
                if (vals.length > MAX_SCREENER_SEASONS) return;
                const next = vals.map(Number).filter((y) => Number.isFinite(y));
                setSelectedSeasons(next);
              }}
              options={seasonOptions}
              placeholder={seasonsQ.isPending ? "Loading seasons…" : "Search seasons…"}
            />
          </div>
          <FilterPanel hideSeason />
        </div>
      </GlassCard>
      </ExportFilterArea>
      ) : null}

      <ExportSection id="table" label="Screener table" required defaultIncluded>
      <GlassCard>
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold text-on-surface">Screener</h1>
            <FiltersSubtitleLine className="mt-0">{subtitle}</FiltersSubtitleLine>
            {criteriaDescription ? (
              <FiltersSubtitleLine size="xs" className="mt-0.5">
                {criteriaDescription}
              </FiltersSubtitleLine>
            ) : null}
            {compositeIndexDescription ? (
              <FiltersSubtitleLine size="xs" className="mt-0.5 text-secondary">
                {compositeIndexDescription}
              </FiltersSubtitleLine>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <ExportFilterArea className="flex flex-wrap items-center gap-2">
              {total > PAGE_SIZE && (
                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2"
                    disabled={page <= 1 || screenQ.isFetching}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
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
                    disabled={page >= totalPages || screenQ.isFetching}
                    onClick={() => setPage((p) => p + 1)}
                    aria-label="Next page"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={() => setFiltersOpen(!filtersOpen)}
                aria-expanded={filtersOpen}
                aria-controls={filtersOpen ? "screener-filters-panel" : undefined}
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

        {showScreenerSkeleton ? (
          <RankingsTableSkeleton count={PAGE_SIZE} />
        ) : screenQ.error ? (
          <div className="text-sm text-error">Error</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="px-2 py-2 label-caps">Player</th>
                  <th className="px-2 py-2 label-caps">Season</th>
                  <th className="px-2 py-2 label-caps">Club</th>
                  <th className="px-2 py-2 label-caps">Age</th>
                  <th className="px-2 py-2 label-caps">Min</th>
                  {criteria.map((c, ci) => {
                    const lab = metricOpts.find((o) => o.value === c.metric)?.label ?? c.metric;
                    return (
                      <th key={`h-${ci}-${c.metric}`} className="px-2 py-2 label-caps text-right">
                        {criterionHeaderLabel(c, lab)}
                      </th>
                    );
                  })}
                  {compositeEnabled ? (
                    <th className="px-2 py-2 label-caps text-right">Score</th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={`${r.wyscout_id}-${r.season}-${i}`}
                    onClick={() =>
                      r.wyscout_id != null &&
                      router.push(`/scout/profile/${r.wyscout_id}?season=${r.season}`)
                    }
                    className={cn(
                      "border-t border-outline-variant/40 hover:bg-surface-mid/40",
                      r.wyscout_id != null && "cursor-pointer",
                    )}
                  >
                    <td className="px-2 py-2 font-medium text-on-surface">{r.player}</td>
                    <td className="px-2 py-2 data-mono text-on-surface">
                      {seasonLabel(r.season)}
                    </td>
                    <td className="px-2 py-2 align-middle">
                      <ClubWithLogoCell club={r.club} logoUrl={r.club_logo} />
                    </td>
                    <td className="px-2 py-2 data-mono text-on-surface">{r.age ?? "—"}</td>
                    <td className="px-2 py-2 data-mono text-on-surface">{r.minutes ?? "—"}</td>
                    {criteria.map((c, ci) => (
                      <td
                        key={`c-${ci}-${c.metric}`}
                        className="px-2 py-2 text-right data-mono text-primary"
                      >
                        {r.metrics[c.metric] != null ? r.metrics[c.metric]!.toFixed(2) : "—"}
                      </td>
                    ))}
                    {compositeEnabled ? (
                      <td className="px-2 py-2 text-right data-mono font-semibold text-secondary">
                        {r.composite != null ? r.composite.toFixed(2) : "—"}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
      </ExportSection>
    </div>
    </ExportProvider>
  );
}
