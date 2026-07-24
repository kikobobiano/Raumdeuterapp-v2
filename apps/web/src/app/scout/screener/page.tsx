"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  PanelLeft,
  PanelLeftClose,
  SlidersHorizontal,
} from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { FilterPanel } from "@/components/domain/filter-panel";
import { FiltersSubtitleLine } from "@/components/domain/filters-subtitle-line";
import {
  ScreenerBuilderDialog,
  type ScreenerBuilderState,
  type ScreenerCriterionDraft,
} from "@/components/domain/screener-builder-dialog";
import {
  ExportButton,
  ExportFilterArea,
  ExportProvider,
  ExportSection,
} from "@/components/export";
import { RankingsTableSkeleton } from "@/components/skeletons/rankings-table-skeleton";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { MultiCombobox } from "@/components/ui/multi-combobox";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useFiltersSubtitle } from "@/hooks/use-filters-subtitle";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import {
  compositeMetricId,
  isCompositeMetricId,
  parseCompositeMetricId,
  type CompositeComponentRecipe,
  type MetricMode,
} from "@/lib/composite-indexes";
import { useCompositeIndexes } from "@/lib/composite-indexes-store";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

const DEFAULT_CRITERIA: ScreenerCriterionDraft[] = [
  { metric: "xG", mode: "p90", operator: ">=", value: 0.3 },
  { metric: "Successful dribbles, %", mode: "as_is", operator: ">=", value: 50 },
];

const DEFAULT_COMPOSITE: CompositeComponentRecipe[] = [
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

function criterionHeaderLabel(c: ScreenerCriterionDraft, label: string) {
  if (isCompositeMetricId(c.metric)) return label;
  return metricHeaderLabel(c.mode, label);
}

function formatCriterionOperator(op: ScreenerCriterionDraft["operator"]): string {
  if (op === ">=") return "≥";
  if (op === "<=") return "≤";
  return op;
}

function formatCriteriaDescription(
  criteria: ScreenerCriterionDraft[],
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
  components: CompositeComponentRecipe[],
  metricOpts: { value: string; label: string }[],
): string {
  const weightSum = components.reduce((acc, c) => acc + Math.abs(c.weight), 0) || 1;
  const parts = components.map((comp) => {
    const lab = metricOpts.find((o) => o.value === comp.metric)?.label ?? comp.metric;
    const pct = Math.round((Math.abs(comp.weight) / weightSum) * 100);
    const name = metricHeaderLabel(comp.mode, lab);
    const basis = comp.basis === "team_median" ? "vs team median" : "season value";
    return `${pct}% ${name} (${basis})`;
  });
  return `Index · ${parts.join(" · ")}`;
}

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

type ResolveOk = {
  ok: true;
  realCriteria: ScreenerCriterionDraft[];
  composite: CompositeComponentRecipe[];
  compositeCriteria: { operator: ScreenerCriterionDraft["operator"]; value: number } | null;
  sortByComposite: boolean;
  sortBy: string | null;
  sortMode: MetricMode;
};

type ResolveErr = { ok: false; error: string };

function resolveScreenerRequest(
  builder: ScreenerBuilderState,
  indexes: { id: string; components: CompositeComponentRecipe[] }[],
): ResolveOk | ResolveErr {
  const byId = new Map(indexes.map((x) => [x.id, x]));
  const recipeIds = new Set<string>();

  const realCriteria: ScreenerCriterionDraft[] = [];
  let compositeCriteria: ResolveOk["compositeCriteria"] = null;

  for (const c of builder.criteria) {
    const cid = parseCompositeMetricId(c.metric);
    if (cid) {
      if (compositeCriteria) {
        return { ok: false, error: "Only one composite-score criterion is allowed." };
      }
      if (!byId.has(cid)) {
        return { ok: false, error: "Saved index for criterion not found." };
      }
      recipeIds.add(cid);
      compositeCriteria = { operator: c.operator, value: c.value };
    } else {
      realCriteria.push(c);
    }
  }

  let sortByComposite = builder.sortByComposite;
  let sortBy: string | null = builder.sortBy;
  let sortMode = builder.sortMode;
  const sortCid = parseCompositeMetricId(builder.sortBy);
  if (sortCid) {
    if (!byId.has(sortCid)) {
      return { ok: false, error: "Saved index for sort not found." };
    }
    recipeIds.add(sortCid);
    sortByComposite = true;
    sortBy = null;
    sortMode = "as_is";
  }

  if (recipeIds.size > 1) {
    return {
      ok: false,
      error: "Sort and criteria must use the same saved composite index.",
    };
  }

  let composite: CompositeComponentRecipe[] = [];
  if (recipeIds.size === 1) {
    const id = [...recipeIds][0]!;
    composite = byId.get(id)!.components.map((c) => ({ ...c }));
    sortByComposite = sortByComposite || !!sortCid;
  } else if (builder.compositeEnabled && builder.compositeComponents.length > 0) {
    composite = builder.compositeComponents.map((c) => ({ ...c }));
  }

  if (compositeCriteria && composite.length === 0) {
    return { ok: false, error: "Composite criterion requires a composite recipe." };
  }

  if (sortByComposite && composite.length === 0) {
    return { ok: false, error: "Sort by composite requires composite components." };
  }

  if (sortBy && isCompositeMetricId(sortBy)) {
    sortBy = null;
  }

  return {
    ok: true,
    realCriteria,
    composite,
    compositeCriteria,
    sortByComposite: sortByComposite && composite.length > 0,
    sortBy: sortByComposite ? null : sortBy,
    sortMode,
  };
}

export default function ScreenerPage() {
  const router = useRouter();
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();
  const savedIndexes = useCompositeIndexes((s) => s.indexes);

  const [selectedSeasons, setSelectedSeasons] = React.useState<number[]>([]);
  const [builderOpen, setBuilderOpen] = React.useState(false);
  const [builder, setBuilder] = React.useState<ScreenerBuilderState>({
    criteria: DEFAULT_CRITERIA,
    compositeEnabled: false,
    compositeComponents: DEFAULT_COMPOSITE,
    sortByComposite: true,
    sortBy: "xG",
    sortMode: "p90",
    editingIndexId: null,
  });
  const [page, setPage] = React.useState(1);
  const [resolveError, setResolveError] = React.useState<string | null>(null);

  const patchBuilder = (patch: Partial<ScreenerBuilderState>) => {
    setBuilder((prev) => ({ ...prev, ...patch }));
  };

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  React.useEffect(() => {
    if (!seasonsQ.isSuccess) return;
    const valid = new Set(seasonsQ.data ?? []);
    const pruned = selectedSeasons.filter((y) => valid.has(y));
    if (pruned.length !== selectedSeasons.length) setSelectedSeasons(pruned);
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

  const metricOpts = (metricsQ.data ?? []).map((m) => ({ value: m.name, label: m.label }));

  const savedMetricOpts = React.useMemo(
    () =>
      savedIndexes.map((idx) => ({
        value: compositeMetricId(idx.id),
        label: `★ ${idx.name}`,
      })),
    [savedIndexes],
  );

  const criterionMetricOpts = React.useMemo(
    () => [...savedMetricOpts, ...metricOpts],
    [savedMetricOpts, metricOpts],
  );

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const resolved = React.useMemo(
    () => resolveScreenerRequest(builder, savedIndexes),
    [builder, savedIndexes],
  );

  React.useEffect(() => {
    if (resolved.ok) setResolveError(null);
  }, [resolved]);

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
        builder,
        resolved,
      ]),
    [
      f.season,
      selectedSeasons,
      f.leagues,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      builder,
      resolved,
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
      resolved,
      page,
    ],
    enabled: resolved.ok,
    queryFn: async () => {
      if (!resolved.ok) throw new Error(resolved.error);
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
          criteria: resolved.realCriteria,
          composite: resolved.composite,
          composite_criteria: resolved.compositeCriteria,
          sort_by_composite: resolved.sortByComposite,
          sort_by: resolved.sortBy,
          sort_mode: resolved.sortMode,
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

  const showScreenerSkeleton = useDelayedLoading(screenQ.isPending && resolved.ok);
  const total = screenQ.data?.total ?? 0;
  const rows = screenQ.data?.rows ?? [];
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (screenQ.isSuccess && total > 0 && page > totalPages) {
    setPage(totalPages);
  }

  const allowedSortMetrics = React.useMemo(() => {
    const names = new Set<string>();
    for (const c of builder.criteria) {
      if (!isCompositeMetricId(c.metric)) names.add(c.metric);
    }
    if (builder.compositeEnabled) {
      for (const comp of builder.compositeComponents) names.add(comp.metric);
    }
    for (const opt of savedMetricOpts) names.add(opt.value);
    return names;
  }, [builder.criteria, builder.compositeEnabled, builder.compositeComponents, savedMetricOpts]);

  const sortMetricOpts = React.useMemo(() => {
    const fromMetrics = metricOpts.filter((o) => allowedSortMetrics.has(o.value));
    const fromSaved = savedMetricOpts.filter((o) => allowedSortMetrics.has(o.value));
    // Always allow sorting by any saved index + metrics used in builder
    return [...fromSaved, ...fromMetrics.length ? fromMetrics : metricOpts.slice(0, 20)];
  }, [metricOpts, savedMetricOpts, allowedSortMetrics]);

  const allLabelOpts = React.useMemo(
    () => [...savedMetricOpts, ...metricOpts],
    [savedMetricOpts, metricOpts],
  );

  const subtitlePrefix = !resolved.ok
    ? ""
    : screenQ.isError
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
    () => formatCriteriaDescription(builder.criteria, allLabelOpts),
    [builder.criteria, allLabelOpts],
  );

  const compositeIndexDescription = React.useMemo(() => {
    if (!resolved.ok || resolved.composite.length === 0) return null;
    return formatCompositeIndexDescription(resolved.composite, metricOpts);
  }, [resolved, metricOpts]);

  const showCompositeColumn = resolved.ok && resolved.composite.length > 0;

  return (
    <ExportProvider title="Screener" filename={screenerExportFilename(selectedSeasons, f.season)}>
      <ScreenerBuilderDialog
        open={builderOpen}
        onOpenChange={setBuilderOpen}
        state={builder}
        onChange={patchBuilder}
        onApply={() => {
          const next = resolveScreenerRequest(builder, savedIndexes);
          if (!next.ok) {
            setResolveError(next.error);
            return;
          }
          setResolveError(null);
          setBuilderOpen(false);
        }}
        metricOpts={metricOpts}
        metricByName={metricByName}
        criterionMetricOpts={criterionMetricOpts}
        sortMetricOpts={sortMetricOpts}
      />

      <div className={cn("grid gap-6", filtersOpen ? "grid-cols-[280px_1fr]" : "grid-cols-1")}>
        {filtersOpen ? (
          <ExportFilterArea>
            <GlassCard id="screener-filters-panel">
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
                {resolveError || (!resolved.ok ? resolved.error : null) ? (
                  <p className="mt-1 text-xs text-error">
                    {resolveError ?? (!resolved.ok ? resolved.error : null)}
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <ExportFilterArea className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="gap-1.5"
                    onClick={() => setBuilderOpen(true)}
                  >
                    <SlidersHorizontal className="h-4 w-4 shrink-0" />
                    Builder…
                  </Button>
                  {total > PAGE_SIZE && resolved.ok && (
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
            ) : !resolved.ok ? (
              <div className="text-sm text-on-surface-variant">
                Fix builder conflicts to run the screener.
              </div>
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
                      {builder.criteria.map((c, ci) => {
                        const lab =
                          allLabelOpts.find((o) => o.value === c.metric)?.label ?? c.metric;
                        return (
                          <th
                            key={`h-${ci}-${c.metric}`}
                            className="px-2 py-2 label-caps text-right"
                          >
                            {criterionHeaderLabel(c, lab)}
                          </th>
                        );
                      })}
                      {showCompositeColumn ? (
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
                        <td className="px-2 py-2 data-mono text-on-surface">
                          {r.minutes ?? "—"}
                        </td>
                        {builder.criteria.map((c, ci) => {
                          const isCi = isCompositeMetricId(c.metric);
                          const display = isCi
                            ? r.composite
                            : r.metrics[c.metric];
                          return (
                            <td
                              key={`c-${ci}-${c.metric}`}
                              className="px-2 py-2 text-right data-mono text-primary"
                            >
                              {display != null ? display.toFixed(2) : "—"}
                            </td>
                          );
                        })}
                        {showCompositeColumn ? (
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
