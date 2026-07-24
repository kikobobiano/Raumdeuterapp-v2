"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { MultiCombobox } from "@/components/ui/multi-combobox";
import { Slider } from "@/components/ui/slider";
import { RoleFilterSection } from "@/components/domain/role-filter-section";
import { SeasonSelect } from "@/components/domain/season-select";
import { BIG_FIVE_LEAGUES } from "@/lib/big-five";
import { api } from "@/lib/api";
import { useGlobalFilters } from "@/lib/store";
import { cn } from "@/lib/utils";

export function FilterPanel({
  hideSeason = false,
  hideLeagues = false,
  hideClubs = false,
  extras = null,
}: {
  hideSeason?: boolean;
  hideLeagues?: boolean;
  hideClubs?: boolean;
  extras?: React.ReactNode;
}) {
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

  const leagueOptions = React.useMemo(() => {
    const fromSeason = leaguesQ.data ?? [];
    if (fromSeason.length > 0) return fromSeason;
    return leaguesKnownQ.data ?? [];
  }, [leaguesQ.data, leaguesKnownQ.data]);

  const bigFiveQ = useQuery({
    queryKey: ["leagues-big-five"],
    queryFn: async () => (await api.GET("/meta/leagues/big-five")).data ?? [],
    staleTime: 24 * 60 * 60 * 1000,
  });

  const bigFiveList = React.useMemo(() => {
    const d = bigFiveQ.data ?? [];
    if (d.length > 0) return d;
    return [...BIG_FIVE_LEAGUES];
  }, [bigFiveQ.data]);

  const bigFiveSet = React.useMemo(() => new Set(bigFiveList), [bigFiveList]);

  const rolesQ = useQuery({
    queryKey: ["roles"],
    queryFn: async () => (await api.GET("/meta/roles")).data ?? [],
  });

  const roleTokensQ = useQuery({
    queryKey: ["role-tokens"],
    queryFn: async () => (await api.GET("/meta/role-tokens")).data ?? {},
  });

  const clubsQ = useQuery({
    queryKey: ["filter-clubs", f.season, f.leagues],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/teams", {
        params: {
          query: {
            season: f.season,
            ...(f.leagues.length ? { leagues: f.leagues } : {}),
          },
        },
      });
      if (error) throw new Error("clubs");
      return data ?? [];
    },
  });

  const clubOptions = React.useMemo(
    () => (clubsQ.data ?? []).map((c) => ({ value: c, label: c })),
    [clubsQ.data],
  );

  // Drop selected clubs that fall outside the current league/season scope so the
  // filter never sends clubs that can't match any row.
  React.useEffect(() => {
    if (!clubsQ.isSuccess) return;
    const valid = new Set(clubsQ.data ?? []);
    const pruned = f.clubs.filter((c) => valid.has(c));
    if (pruned.length !== f.clubs.length) f.setClubs(pruned);
    // Intentionally keyed on the fetched option set, not on f.clubs, to avoid loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clubsQ.isSuccess, clubsQ.data]);

  return (
    <div className="space-y-5">
      {!hideSeason ? (
        <div>
          <p className="label-caps mb-2">Season</p>
          <SeasonSelect />
        </div>
      ) : null}

      {!hideLeagues && (
      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="label-caps">Leagues</p>
          {f.leagues.length > 0 && (
            <button
              type="button"
              className="shrink-0 text-xs text-primary hover:underline"
              onClick={() => f.setLeagues([])}
            >
              Clear
            </button>
          )}
        </div>
        <p className="mb-2 text-xs text-on-surface-variant">
          Multi-select. None = all leagues.
          {leaguesQ.isSuccess && (leaguesQ.data?.length ?? 0) === 0 && leagueOptions.length > 0
            ? " Showing catalog (no values in dataset for this season)."
            : null}
        </p>
        {leaguesQ.isError && (
          <p className="mb-2 text-xs text-error">Could not load leagues for this season.</p>
        )}
        <div className="mb-2 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => {
              const pick = bigFiveList.filter((l) => leagueOptions.includes(l));
              f.setLeagues(pick.length > 0 ? pick : [...bigFiveList]);
            }}
          >
            Big 5
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
            onClick={() => {
              f.setLeagues(leagueOptions.filter((l) => !bigFiveSet.has(l)));
            }}
          >
            Outside Big 5
          </Button>
        </div>
        <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto pr-1">
          {leagueOptions.map((lg) => {
            const selected = f.leagues.includes(lg);
            return (
              <button
                key={lg}
                type="button"
                onClick={() =>
                  f.setLeagues(
                    selected ? f.leagues.filter((x) => x !== lg) : [...f.leagues, lg],
                  )
                }
                className={cn(
                  "rounded-md border px-2.5 py-1.5 text-left text-xs font-medium transition-colors",
                  selected
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-outline-variant/50 bg-surface-low text-on-surface hover:bg-surface-mid",
                )}
              >
                {lg}
              </button>
            );
          })}
        </div>
      </div>
      )}

      {!hideClubs && (
      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="label-caps">Clubs</p>
          {f.clubs.length > 0 && (
            <button
              type="button"
              className="shrink-0 text-xs text-primary hover:underline"
              onClick={() => f.setClubs([])}
            >
              Clear
            </button>
          )}
        </div>
        <p className="mb-2 text-xs text-on-surface-variant">
          Multi-select. None = all clubs{f.leagues.length ? " in the selected leagues" : ""}.
        </p>
        {clubsQ.isError && (
          <p className="mb-2 text-xs text-error">Could not load clubs for this scope.</p>
        )}
        <MultiCombobox
          value={f.clubs}
          onChange={(v) => f.setClubs(v)}
          options={clubOptions}
          placeholder={clubsQ.isPending ? "Loading clubs…" : "Search clubs…"}
        />
      </div>
      )}

      <RoleFilterSection
        value={{ selectedRoles: f.selectedRoles, roleSubTokens: f.roleSubTokens }}
        onChange={(next) => f.setRoleFilter(next)}
        rolesList={rolesQ.data ?? []}
        roleTokensMap={roleTokensQ.data}
        title="Roles"
        helpText="None selected = any outfield position. After choosing a role, pick Wyscout codes (LW, LAMF, …) or leave all active for the whole role."
      />

      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="label-caps">Age range</p>
          <p className="data-mono text-on-surface">
            {f.ageMin} – {f.ageMax}
          </p>
        </div>
        <Slider
          min={15}
          max={42}
          step={1}
          value={[f.ageMin, f.ageMax]}
          onValueChange={([a, b]) => f.setAge(a, b)}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="label-caps">Min. minutes</p>
          <p className="data-mono text-on-surface">{f.minutesMin}</p>
        </div>
        <Slider
          min={0}
          max={3500}
          step={50}
          value={[f.minutesMin]}
          onValueChange={([v]) => f.setMinutesMin(v)}
        />
      </div>

      {extras}
    </div>
  );
}
