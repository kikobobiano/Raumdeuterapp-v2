"use client";

import * as React from "react";

import { useLeaguesFilterLabel } from "@/hooks/use-leagues-filter-label";
import { useGlobalFilters } from "@/lib/store";

/** Defaults match `useGlobalFilters` initial state — used to skip noop filters. */
const AGE_MAX_DEFAULT = 40;
const AGE_MIN_DEFAULT = 16;

function seasonLabel(year: number): string {
  return `${year}/${String(year + 1).slice(2)}`;
}

interface Options {
  /** Optional leading segment, e.g. "1817 players", "Top 20 by combined…". */
  prefix?: string | null;
}

/**
 * Subtitle string for chart pages (Scatter, Screener, Bar): season, leagues,
 * roles (if selected), max age when capped (`age ≤ N`), minimum minutes.
 *
 * Segments are joined with ` · `. Filter values mirror `useGlobalFilters`.
 */
export function useFiltersSubtitle({ prefix }: Options = {}): string {
  const f = useGlobalFilters();
  const leaguesLabel = useLeaguesFilterLabel();

  return React.useMemo(() => {
    const parts: string[] = [];
    if (prefix && prefix.trim()) parts.push(prefix.trim());
    parts.push(seasonLabel(f.season));
    parts.push(leaguesLabel);
    if (f.selectedRoles.length > 0) {
      parts.push(f.selectedRoles.join(", "));
    }
    if (f.ageMax < AGE_MAX_DEFAULT) {
      parts.push(`age ≤ ${f.ageMax}`);
    } else if (f.ageMin > AGE_MIN_DEFAULT) {
      parts.push(`age ≥ ${f.ageMin}`);
    }
    if (f.minutesMin > 0) {
      parts.push(`> ${f.minutesMin}'`);
    }
    return parts.join(" · ");
  }, [
    prefix,
    f.season,
    leaguesLabel,
    f.selectedRoles,
    f.ageMax,
    f.ageMin,
    f.minutesMin,
  ]);
}
