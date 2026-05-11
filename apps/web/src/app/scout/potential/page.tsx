"use client";

import { Info, PanelLeft, PanelLeftClose } from "lucide-react";
import * as React from "react";

import {
  AgeCohortLanes,
  chipKey,
  type CohortFilters,
  type CohortPlayer,
} from "@/components/charts/age-cohort-lanes";
import { FilterPanel } from "@/components/domain/filter-panel";
import {
  ExportButton,
  ExportFilterArea,
  ExportProvider,
  ExportSection,
} from "@/components/export";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { useLeaguesFilterLabel } from "@/hooks/use-leagues-filter-label";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { rolesForApi } from "@/lib/role-filters";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

const COHORT_AGES = [16, 17, 18, 19, 20, 21, 22, 23, 24, 25];

export default function PotentialPage() {
  const f = useGlobalFilters();
  const [selectedKey, setSelectedKey] = React.useState<string | null>(null);
  const leaguesLabel = useLeaguesFilterLabel();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const filters = React.useMemo<CohortFilters>(
    () => ({
      season: f.season,
      leagues: f.leagues.length ? f.leagues : null,
      roles: rolesPayload.length ? rolesPayload : null,
      age_min: f.ageMin,
      age_max: f.ageMax,
      minutes_min: f.minutesMin,
    }),
    [f.season, f.leagues, rolesPayload, f.ageMin, f.ageMax, f.minutesMin],
  );

  const visibleAges = React.useMemo(() => {
    const lo = f.ageMin ?? COHORT_AGES[0]!;
    const hi = f.ageMax ?? COHORT_AGES[COHORT_AGES.length - 1]!;
    return COHORT_AGES.filter((a) => a >= lo && a <= hi);
  }, [f.ageMin, f.ageMax]);

  const onCardClick = React.useCallback((p: CohortPlayer) => {
    const k = chipKey(p);
    setSelectedKey((prev) => (prev === k ? null : k));
  }, []);

  return (
    <ExportProvider title="Potential" filename={`potential-${String(f.season).slice(2)}-${String(f.season + 1).slice(2)}.png`}>
    <div
      className={cn(
        "grid gap-6",
        filtersOpen ? "grid-cols-[280px_minmax(0,1fr)]" : "grid-cols-1",
      )}
    >
      {filtersOpen ? (
        <ExportFilterArea>
        <GlassCard id="potential-filters-panel">
          <p className="label-caps mb-4">Population Filter</p>
          <FilterPanel />
        </GlassCard>
        </ExportFilterArea>
      ) : null}

      <ExportSection id="lanes" label="Potential lanes" required defaultIncluded>
      <div className="flex min-w-0 flex-col gap-6">
        <GlassCard className="flex flex-col">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-on-surface">
                Potential
              </h1>
              <p className="mt-1 text-sm text-on-surface-variant">
                {leaguesLabel} · Season {String(f.season).slice(2)}-{String(f.season + 1).slice(2)}{" "}
                · Top 20 per age
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <ExportFilterArea>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => setFiltersOpen(!filtersOpen)}
                  aria-expanded={filtersOpen}
                  aria-controls={filtersOpen ? "potential-filters-panel" : undefined}
                  aria-label={filtersOpen ? "Hide filters" : "Show filters"}
                >
                  {filtersOpen ? (
                    <>
                      <PanelLeftClose className="h-4 w-4 shrink-0" />
                      <span>Hide filters</span>
                    </>
                  ) : (
                    <>
                      <PanelLeft className="h-4 w-4 shrink-0" />
                      <span>Show filters</span>
                    </>
                  )}
                </Button>
              </ExportFilterArea>
              <ExportButton />
            </div>
          </div>

          <div className="mt-3 flex items-start gap-2 rounded-md border border-outline-variant/40 bg-surface-mid/40 px-3 py-2 text-xs text-on-surface-variant">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" strokeWidth={1.5} />
            <p>
              <span className="text-on-surface">Potential Score</span> is a model-derived probability
              (0–100) that the player will reach elite performance in elite tier within 3 seasons.
              Each row groups players by age (16→25), sorted by potential.
            </p>
          </div>
        </GlassCard>

        <GlassCard>
          {visibleAges.length === 0 ? (
            <p className="py-12 text-center text-sm text-on-surface-variant">
              Adjust the age filter to include some of the 16–25 cohort.
            </p>
          ) : (
            <AgeCohortLanes
              ages={visibleAges}
              filters={filters}
              pageSize={20}
              onSelect={onCardClick}
              selectedKey={selectedKey}
            />
          )}
        </GlassCard>
      </div>
      </ExportSection>
    </div>
    </ExportProvider>
  );
}
