"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { PlayerSearch } from "@/components/domain/player-search";
import { Combobox } from "@/components/ui/combobox";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
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

function profileWyscoutIdFromPath(pathname: string): number | null {
  const m = pathname.match(/^\/scout\/profile\/(\d+)$/);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}

function scoutProfileRankingsHeader(pathname: string): boolean {
  return pathname === "/scout/rankings" || pathname.startsWith("/scout/profile");
}

export function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const globalSeason = useGlobalFilters((s) => s.season);
  const setSeason = useGlobalFilters((s) => s.setSeason);

  const showScoutControls = scoutProfileRankingsHeader(pathname);

  const seasonsQ = useQuery({
    ...metaSeasonsQueryOptions(),
    enabled: showScoutControls,
  });

  const list = seasonsQ.data;
  const urlSeason = searchParams.get("season");
  const season = React.useMemo(
    () => resolveSeason(urlSeason, globalSeason, list),
    [urlSeason, globalSeason, list],
  );

  React.useEffect(() => {
    if (!showScoutControls || list == null || list.length === 0) return;
    const raw = searchParams.get("season");
    if (raw == null || raw === "") return;
    const y = Number(raw);
    if (!list.includes(y) || globalSeason === y) return;
    setSeason(y);
  }, [showScoutControls, list, searchParams, globalSeason, setSeason]);

  const seasonOpts = (list ?? []).map((y) => ({
    value: String(y),
    label: `${String(y).slice(2)}-${String(y + 1).slice(2)}`,
  }));

  const onSeasonChange = React.useCallback(
    (v: string) => {
      setSeason(Number(v));
      const sp = new URLSearchParams(searchParams.toString());
      sp.set("season", v);

      if (pathname === "/scout/rankings") {
        sp.delete("page");
        router.replace(`/scout/rankings?${sp.toString()}`);
        return;
      }

      if (pathname.startsWith("/scout/profile")) {
        const pid = profileWyscoutIdFromPath(pathname);
        if (pid != null) {
          sp.delete("club");
          router.replace(`/scout/profile/${pid}?${sp.toString()}`);
        } else {
          router.replace(`/scout/profile?${sp.toString()}`);
        }
      }
    },
    [pathname, router, searchParams, setSeason],
  );

  const onPlayerSelect = React.useCallback(
    (id: number, _player: string, club?: string | null) => {
      const qp = new URLSearchParams();
      qp.set("season", String(season));
      if (club) qp.set("club", club);
      router.push(`/scout/profile/${id}?${qp.toString()}`);
    },
    [router, season],
  );

  return (
    <header className="flex h-16 min-w-0 items-center justify-end gap-4 border-b border-outline-variant bg-surface px-8">
      {showScoutControls ? (
        <div className="flex min-w-0 max-w-full items-center justify-end gap-3 sm:gap-4">
          <PlayerSearch
            variant="minimal"
            season={season}
            onSelect={onPlayerSelect}
            className="w-72 shrink-0 sm:w-80"
            placeholder="Search Players"
          />
          <div className="w-[10.5rem] shrink-0 sm:w-44">
            <Combobox
              variant="minimal"
              value={String(season)}
              onChange={onSeasonChange}
              options={seasonOpts}
              placeholder="Season"
            />
          </div>
        </div>
      ) : null}
    </header>
  );
}
