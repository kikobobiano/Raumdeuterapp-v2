"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { api } from "@/lib/api";
import { BIG_FIVE_LEAGUES } from "@/lib/big-five";
import { formatLeaguesFilterLabel } from "@/lib/leagues-subtitle";
import { useGlobalFilters } from "@/lib/store";

/**
 * Label for headers matching ``FilterPanel`` Big 5 / Outside Big 5 semantics
 * (season league list + ``/meta/leagues/big-five``).
 */
export function useLeaguesFilterLabel(): string {
  const f = useGlobalFilters();

  const leaguesQ = useQuery({
    queryKey: ["leagues", f.season],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/leagues", {
        params: { query: { season: f.season } },
      });
      if (error) throw new Error("leagues");
      return data ?? [];
    },
  });

  const leaguesKnownQ = useQuery({
    queryKey: ["leagues-known"],
    queryFn: async () => (await api.GET("/meta/leagues/known")).data ?? [],
    staleTime: 24 * 60 * 60 * 1000,
  });

  const bigFiveQ = useQuery({
    queryKey: ["leagues-big-five"],
    queryFn: async () => (await api.GET("/meta/leagues/big-five")).data ?? [],
    staleTime: 24 * 60 * 60 * 1000,
  });

  const leagueOptions = React.useMemo(() => {
    const fromSeason = leaguesQ.data ?? [];
    if (fromSeason.length > 0) return fromSeason;
    return leaguesKnownQ.data ?? [];
  }, [leaguesQ.data, leaguesKnownQ.data]);

  const bigFiveList = React.useMemo(() => {
    const d = bigFiveQ.data ?? [];
    if (d.length > 0) return d;
    return [...BIG_FIVE_LEAGUES];
  }, [bigFiveQ.data]);

  return React.useMemo(
    () => formatLeaguesFilterLabel(f.leagues, leagueOptions, bigFiveList),
    [f.leagues, leagueOptions, bigFiveList],
  );
}
