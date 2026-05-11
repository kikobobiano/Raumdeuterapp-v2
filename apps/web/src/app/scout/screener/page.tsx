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
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { useFiltersSubtitle } from "@/hooks/use-filters-subtitle";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

interface Criterion {
  metric: string;
  mode: MetricMode;
  operator: ">=" | "<=" | ">" | "<" | "=" | "!=";
  value: number;
}

const DEFAULT_CRITERIA: Criterion[] = [
  { metric: "xG", mode: "p90", operator: ">=", value: 0.3 },
  { metric: "Successful dribbles, %", mode: "as_is", operator: ">=", value: 50 },
];

const PAGE_SIZE = 20;

function criterionHeaderLabel(c: Criterion, label: string) {
  if (c.mode === "p90") return `${label} (/90)`;
  if (c.mode === "raw") return `${label} (raw)`;
  return label;
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
  const [criteria, setCriteria] = React.useState<Criterion[]>(DEFAULT_CRITERIA);
  const [sortBy, setSortBy] = React.useState("xG");
  const [sortMode, setSortMode] = React.useState<MetricMode>("p90");
  const [page, setPage] = React.useState(1);

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
        f.leagues,
        rolesPayload,
        f.ageMin,
        f.ageMax,
        f.minutesMin,
        criteria,
        sortBy,
        sortMode,
      ]),
    [f.season, f.leagues, rolesPayload, f.ageMin, f.ageMax, f.minutesMin, criteria, sortBy, sortMode],
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
      f.leagues,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
      criteria,
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
            roles: rolesPayload.length ? rolesPayload : null,
            age_min: f.ageMin,
            age_max: f.ageMax,
            minutes_min: f.minutesMin,
          },
          criteria,
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

  const update = (i: number, patch: Partial<Criterion>) =>
    setCriteria(criteria.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));

  const onCriterionMetric = (i: number, name: string) => {
    const meta = metricByName[name];
    update(i, {
      metric: name,
      mode: modeFromMetricOption(meta),
    });
  };

  const onSortMetric = (name: string) => {
    setSortBy(name);
    setSortMode(modeFromMetricOption(metricByName[name]));
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

  return (
    <ExportProvider title="Screener" filename={`screener-${String(f.season).slice(2)}-${String(f.season + 1).slice(2)}.png`}>
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
        <div className="flex gap-2">
          <Combobox
            value={sortBy}
            onChange={onSortMetric}
            options={metricOpts}
            className="min-w-0 flex-1"
          />
          <MetricModeToggle
            supports={!!sortMeta?.supports_mode}
            value={sortMode}
            onChange={setSortMode}
          />
        </div>

        <div className="mt-6">
          <p className="label-caps mb-3">Population</p>
          <FilterPanel />
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
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={`${r.wyscout_id}-${i}`}
                    onClick={() =>
                      r.wyscout_id != null &&
                      router.push(`/scout/profile/${r.wyscout_id}?season=${f.season}`)
                    }
                    className={cn(
                      "border-t border-outline-variant/40 hover:bg-surface-mid/40",
                      r.wyscout_id != null && "cursor-pointer",
                    )}
                  >
                    <td className="px-2 py-2 font-medium text-on-surface">{r.player}</td>
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
