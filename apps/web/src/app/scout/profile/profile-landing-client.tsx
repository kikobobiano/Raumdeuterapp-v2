"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { RankingsTableSkeleton } from "@/components/skeletons/rankings-table-skeleton";
import { GlassCard } from "@/components/ui/glass-card";
import { api } from "@/lib/api";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { useProfilePrefs } from "@/lib/profile-prefs";
import { rolesForApi } from "@/lib/role-filters";
import { DEFAULT_SEASON, useGlobalFilters } from "@/lib/store";

function resolveSeason(
  urlSeason: string | null,
  globalSeason: number,
  list: number[] | undefined,
): number {
  let y =
    urlSeason != null && urlSeason !== ""
      ? Number(urlSeason)
      : globalSeason;
  if (Number.isNaN(y)) y = globalSeason;
  if (list && list.length > 0 && !list.includes(y)) {
    y = list.includes(DEFAULT_SEASON) ? DEFAULT_SEASON : list[0];
  }
  return y;
}

/** `/scout/profile` → last viewed player, or #1 under current filters (same pool as rankings page 1). */
export function ProfileLandingClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const f = useGlobalFilters();
  const urlSeason = searchParams.get("season");
  const lastWyscoutId = useProfilePrefs((s) => s.lastWyscoutId);

  const [hydrated, setHydrated] = React.useState(() => useProfilePrefs.persist.hasHydrated());
  React.useEffect(() => {
    return useProfilePrefs.persist.onFinishHydration(() => setHydrated(true));
  }, []);

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  const list = seasonsQ.data;
  const season = React.useMemo(
    () => resolveSeason(urlSeason, f.season, list),
    [urlSeason, f.season, list],
  );

  const rolesPayload = React.useMemo(
    () => rolesForApi({ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }),
    [f.selectedRoles, f.roleSubTokens],
  );

  const hasStoredProfile =
    hydrated && lastWyscoutId != null && Number.isFinite(lastWyscoutId);

  const topQ = useQuery({
    queryKey: [
      "profile-landing-top",
      season,
      f.leagues,
      rolesPayload,
      f.ageMin,
      f.ageMax,
      f.minutesMin,
    ],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/players/top-performance", {
        params: {
          query: {
            season,
            minutes_min: f.minutesMin,
            limit: 1,
            offset: 0,
            leagues: f.leagues.length ? f.leagues : undefined,
            roles: rolesPayload.length ? rolesPayload : undefined,
            age_min: f.ageMin,
            age_max: f.ageMax,
          },
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data ?? { items: [], total: 0 };
    },
    enabled: hydrated && !hasStoredProfile && (list ?? []).includes(season),
  });

  const didRedirect = React.useRef(false);

  React.useEffect(() => {
    if (didRedirect.current || !hydrated || !(list ?? []).includes(season)) return;

    if (lastWyscoutId != null && Number.isFinite(lastWyscoutId)) {
      didRedirect.current = true;
      router.replace(`/scout/profile/${lastWyscoutId}?season=${season}`);
      return;
    }

    if (!topQ.isSuccess) return;
    const id = topQ.data?.items?.[0]?.wyscout_id;
    if (id != null && Number.isFinite(id)) {
      didRedirect.current = true;
      router.replace(`/scout/profile/${id}?season=${season}`);
    }
  }, [hydrated, season, list, lastWyscoutId, topQ.isSuccess, topQ.data, router]);

  if (!hydrated || !(list ?? []).includes(season)) {
    return <RankingsTableSkeleton withFilters={false} count={6} />;
  }

  if (hasStoredProfile) {
    return <RankingsTableSkeleton withFilters={false} count={6} />;
  }

  if (topQ.isPending) {
    return <RankingsTableSkeleton withFilters={false} count={6} />;
  }

  if (topQ.isError) {
    return (
      <GlassCard>
        <p className="text-sm text-error">Could not resolve a default profile.</p>
        <Link
          href={`/scout/rankings?season=${season}`}
          className="mt-3 inline-block text-sm text-primary hover:underline"
        >
          Open rankings
        </Link>
      </GlassCard>
    );
  }

  const firstId = topQ.data?.items?.[0]?.wyscout_id;
  const empty =
    firstId == null || !Number.isFinite(firstId);

  if (empty) {
    return (
      <GlassCard className="flex flex-col gap-3 py-10">
        <p className="text-base font-medium text-on-surface">No default player yet</p>
        <p className="text-sm text-on-surface-variant">
          Nothing matched your filters for rank #1. Open rankings to pick a player or widen leagues /
          roles / age / minutes.
        </p>
        <Link
          href={`/scout/rankings?season=${season}`}
          className="text-sm font-medium text-primary hover:underline"
        >
          Go to rankings
        </Link>
      </GlassCard>
    );
  }

  return <RankingsTableSkeleton withFilters={false} count={6} />;
}
