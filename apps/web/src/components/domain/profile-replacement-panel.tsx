"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { RoleFilterSection } from "@/components/domain/role-filter-section";
import { ExportFilterArea, ExportSection } from "@/components/export";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { emptyRolesFilter, rolesForApi, type RolesFilterState } from "@/lib/role-filters";
import { BIG_FIVE_LEAGUES } from "@/lib/big-five";
import { cn } from "@/lib/utils";

const CONTRACT_YEAR_MIN = 2023;
const CONTRACT_YEAR_MAX = 2036;

interface Props {
  wyscoutId: number;
  season: number;
  /** Tactical role from profile — pre-selects position filter when present. */
  defaultRole?: string | null;
}

function ReplacementClubCell({
  club,
  logoUrl,
}: {
  club: string | null | undefined;
  logoUrl: string | null | undefined;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <ClubLogoImg logoUrl={logoUrl} className="h-7 w-7" />
      <span className="min-w-0 truncate text-on-surface-variant">{club ?? "—"}</span>
    </div>
  );
}

export function ProfileReplacementPanel({ wyscoutId, season, defaultRole }: Props) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);

  const [candidateSeasons, setCandidateSeasons] = React.useState<number[]>(() => [season]);
  const [leagues, setLeagues] = React.useState<string[]>([]);
  const [roleFilter, setRoleFilter] = React.useState<RolesFilterState>(() =>
    defaultRole ? { selectedRoles: [defaultRole], roleSubTokens: {} } : emptyRolesFilter(),
  );
  const [ageMin, setAgeMin] = React.useState(15);
  const [ageMax, setAgeMax] = React.useState(42);
  const [minutesMin, setMinutesMin] = React.useState(500);
  const [minutesMax, setMinutesMax] = React.useState(4000);
  const [contractYearMin, setContractYearMin] = React.useState<number | null>(null);
  const [contractYearMax, setContractYearMax] = React.useState<number | null>(null);

  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  const rolesQ = useQuery({
    queryKey: ["roles"],
    queryFn: async () => (await api.GET("/meta/roles")).data ?? [],
  });

  const roleTokensQ = useQuery({
    queryKey: ["role-tokens"],
    queryFn: async () => (await api.GET("/meta/role-tokens")).data ?? {},
    enabled: open,
  });

  const leaguesQ = useQuery({
    queryKey: ["replacement-leagues", candidateSeasons],
    queryFn: async () => {
      const seen = new Set<string>();
      const out: string[] = [];
      for (const y of candidateSeasons) {
        const { data } = await api.GET("/meta/leagues", {
          params: { query: { season: y } },
        });
        for (const lg of data ?? []) {
          if (!seen.has(lg)) {
            seen.add(lg);
            out.push(lg);
          }
        }
      }
      return out.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    },
    enabled: open && candidateSeasons.length > 0,
  });

  const leagueOptions = leaguesQ.data ?? [];
  const bigFiveSet = React.useMemo(() => new Set(BIG_FIVE_LEAGUES), []);

  const rolesPayload = React.useMemo(() => rolesForApi(roleFilter), [roleFilter]);

  const rolesList = React.useMemo(() => {
    const fromApi = rolesQ.data ?? [];
    const extra = roleFilter.selectedRoles.filter((r) => !fromApi.includes(r));
    return [...extra, ...fromApi];
  }, [rolesQ.data, roleFilter.selectedRoles]);

  const contractYearOptions = React.useMemo(
    () => [
      { value: "", label: "Any" },
      ...Array.from(
        { length: CONTRACT_YEAR_MAX - CONTRACT_YEAR_MIN + 1 },
        (_, i) => CONTRACT_YEAR_MIN + i,
      ).map((y) => ({ value: String(y), label: String(y) })),
    ],
    [],
  );

  const repQ = useQuery({
    queryKey: [
      "replacement-panel",
      wyscoutId,
      season,
      candidateSeasons,
      leagues,
      rolesPayload,
      ageMin,
      ageMax,
      minutesMin,
      minutesMax,
      contractYearMin,
      contractYearMax,
    ],
    queryFn: async () => {
      const primarySeason = candidateSeasons[0] ?? season;
      const { data, error } = await api.POST("/replacement", {
        body: {
          target_player_id: wyscoutId,
          target_season: season,
          candidate_seasons: candidateSeasons,
          candidate_filters: {
            season: primarySeason,
            leagues: leagues.length > 0 ? leagues : null,
            roles: rolesPayload.length > 0 ? rolesPayload : null,
            age_min: ageMin,
            age_max: ageMax,
            minutes_min: minutesMin,
            minutes_max: minutesMax < 4000 ? minutesMax : null,
            contract_expires_year_min: contractYearMin,
            contract_expires_year_max: contractYearMax,
          },
          limit: 20,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    enabled: open && candidateSeasons.length > 0,
  });

  const toggleSeason = (y: number) => {
    setCandidateSeasons((prev) => {
      const has = prev.includes(y);
      if (has) {
        const next = prev.filter((x) => x !== y);
        return next.length > 0 ? next : prev;
      }
      if (prev.length >= 8) return prev;
      return [...prev, y].sort((a, b) => a - b);
    });
  };

  return (
    <ExportSection
      id="replacement"
      label="Replacement"
      defaultIncluded={false}
      disabled={!open}
      disabledReason="Open the panel to include it in the export."
    >
    <GlassCard>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-on-surface">Replacement Finder</h2>
        </div>
        <span data-export-hide aria-hidden>
          {open ? (
            <ChevronUp className="h-4 w-4 text-on-surface-variant" />
          ) : (
            <ChevronDown className="h-4 w-4 text-on-surface-variant" />
          )}
        </span>
      </button>

      {open && (
        <div className="mt-5 space-y-5">
          <ExportFilterArea className="space-y-5">
          <div>
            <p className="label-caps mb-2">Candidate seasons</p>
            <p className="mb-2 text-xs text-on-surface-variant">
              Pool stats come from these seasons (up to 8). Target player stays on the profile season.
            </p>
            <div className="flex max-h-36 flex-wrap gap-2 overflow-y-auto">
              {(seasonsQ.data ?? []).map((y) => {
                const selected = candidateSeasons.includes(y);
                return (
                  <button
                    key={y}
                    type="button"
                    onClick={() => toggleSeason(y)}
                    className={cn(
                      "rounded-md border px-2.5 py-1.5 text-left text-xs font-medium transition-colors",
                      selected
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-outline-variant/50 bg-surface-low text-on-surface hover:bg-surface-mid",
                    )}
                  >
                    {`${String(y).slice(2)}-${String(y + 1).slice(2)}`}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="label-caps">Leagues</p>
              {leagues.length > 0 && (
                <button
                  type="button"
                  className="shrink-0 text-xs text-primary hover:underline"
                  onClick={() => setLeagues([])}
                >
                  Clear
                </button>
              )}
            </div>
            <p className="mb-2 text-xs text-on-surface-variant">
              None selected = all leagues in the candidate seasons.
            </p>
            <div className="mb-2 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-xs"
                onClick={() => {
                  const pick = BIG_FIVE_LEAGUES.filter((l) => leagueOptions.includes(l));
                  setLeagues(pick.length > 0 ? pick : [...BIG_FIVE_LEAGUES]);
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
                  setLeagues(leagueOptions.filter((l) => !bigFiveSet.has(l)));
                }}
              >
                Outside Big 5
              </Button>
            </div>
            <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto pr-1">
              {leagueOptions.map((lg) => {
                const selected = leagues.includes(lg);
                return (
                  <button
                    key={lg}
                    type="button"
                    onClick={() =>
                      setLeagues(selected ? leagues.filter((x) => x !== lg) : [...leagues, lg])
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

          <RoleFilterSection
            value={roleFilter}
            onChange={setRoleFilter}
            rolesList={rolesList}
            roleTokensMap={roleTokensQ.data}
            title="Position (role)"
            helpText="Default matches this player's tactical role. None selected = any outfield role."
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="label-caps">Age range</p>
                <span className="data-mono text-xs text-on-surface">
                  {ageMin} – {ageMax}
                </span>
              </div>
              <Slider
                min={15}
                max={42}
                step={1}
                value={[ageMin, ageMax]}
                onValueChange={([a, b]) => {
                  setAgeMin(a ?? 15);
                  setAgeMax(b ?? 42);
                }}
              />
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="label-caps">Minutes played</p>
                <span className="data-mono text-xs text-on-surface">
                  {minutesMin}
                  {minutesMax < 4000 ? ` – ${minutesMax}` : "+"}
                </span>
              </div>
              <Slider
                min={0}
                max={4000}
                step={50}
                value={[minutesMin, minutesMax]}
                onValueChange={([a, b]) => {
                  setMinutesMin(a ?? 0);
                  setMinutesMax(b ?? 4000);
                }}
              />
              <p className="mt-1 text-[11px] text-on-surface-variant">
                Upper end at 4000 = no maximum (open-ended).
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <p className="label-caps mb-1">Contract expires (year ≥)</p>
              <Combobox
                value={contractYearMin != null ? String(contractYearMin) : ""}
                onChange={(v) => setContractYearMin(v === "" ? null : Number(v))}
                options={contractYearOptions}
                placeholder="Any"
              />
            </div>
            <div>
              <p className="label-caps mb-1">Contract expires (year ≤)</p>
              <Combobox
                value={contractYearMax != null ? String(contractYearMax) : ""}
                onChange={(v) => setContractYearMax(v === "" ? null : Number(v))}
                options={contractYearOptions}
                placeholder="Any"
              />
            </div>
          </div>
          </ExportFilterArea>

          {repQ.isLoading && <p className="text-on-surface-variant">Computing similarity…</p>}
          {repQ.isError && <p className="text-sm text-error">Error</p>}

          {repQ.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="px-2 py-2 label-caps">#</th>
                    <th className="px-2 py-2 label-caps">Player</th>
                    <th className="px-2 py-2 label-caps">Season</th>
                    <th className="px-2 py-2 label-caps min-w-[10rem]">Club</th>
                    <th className="px-2 py-2 label-caps">League</th>
                    <th className="px-2 py-2 label-caps">Pos</th>
                    <th className="px-2 py-2 label-caps">Age</th>
                    <th className="px-2 py-2 label-caps text-right">Similarity</th>
                  </tr>
                </thead>
                <tbody>
                  {repQ.data.candidates.map((c, i) => (
                    <tr
                      key={`${c.wyscout_id ?? i}-${c.candidate_season ?? ""}`}
                      onClick={() =>
                        c.wyscout_id != null &&
                        router.push(
                          `/scout/profile/${c.wyscout_id}?season=${c.candidate_season ?? season}`,
                        )
                      }
                      className="cursor-pointer border-t border-outline-variant/40 hover:bg-surface-mid/40"
                    >
                      <td className="px-2 py-2 data-mono text-on-surface-variant">{i + 1}</td>
                      <td className="px-2 py-2 text-on-surface">{c.player}</td>
                      <td className="px-2 py-2 data-mono text-on-surface-variant">
                        {c.candidate_season != null
                          ? `${String(c.candidate_season).slice(2)}-${String(c.candidate_season + 1).slice(2)}`
                          : "—"}
                      </td>
                      <td className="px-2 py-2">
                        <ReplacementClubCell club={c.club} logoUrl={c.club_logo} />
                      </td>
                      <td className="px-2 py-2 text-on-surface-variant">{c.league ?? "—"}</td>
                      <td className="px-2 py-2 text-on-surface-variant">{c.position ?? "—"}</td>
                      <td className="px-2 py-2 data-mono text-on-surface">{c.age ?? "—"}</td>
                      <td className="px-2 py-2 text-right data-mono text-primary">
                        {c.similarity.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </GlassCard>
    </ExportSection>
  );
}
