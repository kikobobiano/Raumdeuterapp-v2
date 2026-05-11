"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import * as React from "react";

import { TranslationGrid, TRANSLATION_GRID_MARGIN_PX } from "@/components/charts/translation-grid";
import { ExportFilterArea, ExportSection } from "@/components/export";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { api } from "@/lib/api";
import { translationBandColor } from "@/lib/translation-band-color";

interface Props {
  wyscoutId: number;
  season: number;
  playerImageUrl?: string | null;
}

export function ProfileTranslationPanel({ wyscoutId, season, playerImageUrl }: Props) {
  const [open, setOpen] = React.useState(false);
  const [targetLeagues, setTargetLeagues] = React.useState<string[]>([]);
  const [pickerValue, setPickerValue] = React.useState("");

  const [prevSeason, setPrevSeason] = React.useState(season);
  if (prevSeason !== season) {
    setPrevSeason(season);
    setTargetLeagues([]);
  }

  const leaguesInSeasonQ = useQuery({
    queryKey: ["leagues", season],
    queryFn: async () => {
      const { data } = await api.GET("/meta/leagues", {
        params: { query: { season } },
      });
      return data ?? [];
    },
    enabled: open,
  });

  const transQ = useQuery({
    queryKey: ["translation", wyscoutId, season, targetLeagues],
    queryFn: async () => {
      const { data, error } = await api.POST("/translation", {
        body: {
          player_id: wyscoutId,
          season,
          target_leagues: targetLeagues.length ? targetLeagues : null,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    enabled: open,
  });

  const leagueOpts = (leaguesInSeasonQ.data ?? [])
    .filter((l) => !targetLeagues.includes(l))
    .map((l) => ({ value: l, label: l }));

  return (
    <ExportSection
      id="translation"
      label="Translation"
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
          <h2 className="text-lg font-semibold text-on-surface">Performance Translation</h2>
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
          <ExportFilterArea>
          <div>
            <p className="label-caps mb-2">Target leagues</p>
            <p className="mb-2 text-xs text-on-surface-variant">
              Pools use the same season as this profile ({String(season).slice(2)}-
              {String(season + 1).slice(2)}). Empty = default by power proximity (up to 6; source
              league included first for current PI vs peers).
            </p>
            <Combobox
              value={pickerValue}
              onChange={(v) => {
                if (!v || targetLeagues.includes(v) || targetLeagues.length >= 6) return;
                setTargetLeagues([...targetLeagues, v]);
                setPickerValue("");
              }}
              options={leagueOpts}
              placeholder="Add league…"
              className="mb-2 max-w-sm"
            />
            <div className="flex flex-wrap gap-2">
              {targetLeagues.map((lg) => (
                <span
                  key={lg}
                  className="inline-flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary/15 px-2 py-1 text-xs text-primary"
                >
                  {lg}
                  <button
                    type="button"
                    onClick={() =>
                      setTargetLeagues(targetLeagues.filter((x) => x !== lg))
                    }
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
          </ExportFilterArea>

          {transQ.isLoading && (
            <p className="text-on-surface-variant">Computing translation…</p>
          )}
          {transQ.isError && <p className="text-sm text-error">Error</p>}

          {transQ.data && (
            <>
              {/* Source summary */}
              <div className="rounded-md border border-outline-variant/50 bg-surface-low p-4">
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className="label-caps">Source</span>
                  <span className="text-sm text-on-surface">
                    {transQ.data.club ?? "—"} · {transQ.data.source_league}
                    {transQ.data.player_age != null
                      ? ` · age ${transQ.data.player_age}`
                      : null}
                  </span>
                  <span
                    className="data-mono ml-auto text-2xl"
                    style={{ color: translationBandColor(transQ.data.source_perf_index, "text") }}
                  >
                    {transQ.data.source_perf_index.toFixed(1)}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                  <Stat
                    label="Strength adj"
                    value={`×${transQ.data.source_strength_adj.value.toFixed(3)}`}
                  />
                  <Stat
                    label="xG factor"
                    value={`×${transQ.data.source_strength_adj.xg_factor.toFixed(3)}`}
                  />
                  <Stat
                    label="Tier (dom z)"
                    value={`×${transQ.data.source_strength_adj.tier_factor.toFixed(3)}`}
                  />
                  <Stat
                    label="League band"
                    value={`×${transQ.data.source_strength_adj.league_factor.toFixed(3)}`}
                  />
                </div>
                {!transQ.data.source_strength_adj.available && (
                  <p className="mt-2 text-xs text-on-surface-variant">
                    No team profile data — using league-average team (1.0).
                  </p>
                )}
              </div>

              {transQ.data.pools.length > 0 ? (
                <div className="mx-auto w-[90%] max-w-full min-w-0">
                  <TranslationGrid
                    pools={transQ.data.pools}
                    playerName={transQ.data.player}
                    playerAge={transQ.data.player_age}
                    playerWyscoutId={wyscoutId}
                    playerImageUrl={playerImageUrl ?? null}
                  />
                </div>
              ) : (
                <p className="text-sm text-on-surface-variant">
                  No target leagues to project. Pick one or more above.
                </p>
              )}

              {(transQ.data.league_style_fit ?? []).length > 0 ? (
                <div>
                  <div
                    className="overflow-x-auto"
                    style={{
                      paddingInline: TRANSLATION_GRID_MARGIN_PX.left,
                    }}
                  >
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left">
                          <th className="px-2 py-2 label-caps">League</th>
                          <th className="px-2 py-2 label-caps text-right">Teams</th>
                          <th className="px-2 py-2 label-caps text-right">Style fit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(transQ.data.league_style_fit ?? []).map((row) => (
                          <tr
                            key={row.league}
                            className="border-t border-outline-variant/40"
                          >
                            <td className="px-2 py-2 text-on-surface">{row.league}</td>
                            <td className="px-2 py-2 text-right data-mono text-on-surface-variant">
                              {row.n_teams}
                            </td>
                            <td className="px-2 py-2 text-right data-mono text-on-surface">
                              {row.style_fit.toFixed(3)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : transQ.data.pools.length > 0 ? (
                <p className="text-xs text-on-surface-variant">
                  Style fit is unavailable: no team profile rows for these leagues and the target
                  season, or player style inputs are missing. Build{" "}
                  <code className="rounded bg-surface-mid px-1 py-0.5 text-[10px]">team_profiles</code>{" "}
                  for that season or choose leagues that have profiles.
                </p>
              ) : null}
            </>
          )}
        </div>
      )}
    </GlassCard>
    </ExportSection>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label-caps">{label}</p>
      <p className="data-mono text-on-surface">{value}</p>
    </div>
  );
}
