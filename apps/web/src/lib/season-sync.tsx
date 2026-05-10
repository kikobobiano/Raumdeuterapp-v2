"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { DEFAULT_SEASON, useGlobalFilters } from "@/lib/store";

/** If store season has no parquet, snap to latest season from API (same order as /meta/seasons). */
export function SeasonSync({ children }: { children: React.ReactNode }) {
  const season = useGlobalFilters((s) => s.season);
  const setSeason = useGlobalFilters((s) => s.setSeason);

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  React.useEffect(() => {
    const list = seasonsQ.data ?? [];
    if (list.length === 0) return;
    if (!list.includes(season)) {
      const fallback = list.includes(DEFAULT_SEASON) ? DEFAULT_SEASON : list[0];
      setSeason(fallback);
    }
  }, [seasonsQ.data, season, setSeason]);

  return <>{children}</>;
}
