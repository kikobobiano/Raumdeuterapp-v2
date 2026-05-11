"use client";

import { useQuery } from "@tanstack/react-query";
import { PanelLeft, PanelLeftClose } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { FilterPanel } from "@/components/domain/filter-panel";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { GlassCard } from "@/components/ui/glass-card";
import { useScoutFiltersSidebar } from "@/hooks/use-scout-filters-sidebar";
import { api } from "@/lib/api";
import { useGlobalFilters } from "@/lib/store";
import { wyscoutClubLogoSrc, wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { scoutProfileIndexColor } from "@/lib/translation-band-color";
import { cn } from "@/lib/utils";
import { useDelayedLoading } from "@/hooks/use-delayed-loading";
import { BestXiPitchSkeleton } from "@/components/skeletons/best-xi-pitch-skeleton";
import { FilterChipsSkeleton } from "@/components/skeletons/filter-chips-skeleton";

const FORMATIONS = [
  "4-3-3", "4-2-3-1", "4-4-2", "4-1-4-1",
  "3-4-3", "3-5-2", "3-4-2-1", "5-3-2", "5-4-1",
];

/** Fallbacks for empty slots; PI / ring colours use ``scoutProfileIndexColor`` (rankings + profile). */
const PITCH = {
  textMuted: "#7eb8d4",
  textName: "#d2e2f2",
  emptyStroke: "#374557",
} as const;

/** ViewBox units — smaller than before; portrait tiles use `meet` so faces are not cropped. */
const AVATAR_R = 3.35;
const AVATAR_D = AVATAR_R * 2;
const AVATAR_CLIP_ID = "bxi-avatar-clip";

type Mode = "by_league" | "by_club" | "two_teams";

interface BestXIPlayer {
  slot: string;
  player: string;
  wyscout_id?: number | null;
  club?: string | null;
  club_logo?: string | null;
  league?: string | null;
  position?: string | null;
  age?: number | null;
  minutes?: number | null;
  goals?: number | null;
  assists?: number | null;
  performance_index?: number | null;
  position_type: string;
  player_image_url?: string | null;
}

interface BestXITop3Row {
  slot: string;
  rank: number;
  player: string;
  wyscout_id?: number | null;
  club?: string | null;
  club_logo?: string | null;
  age?: number | null;
  minutes?: number | null;
  performance_index?: number | null;
  position_type: string;
  player_image_url?: string | null;
}

interface BestXIResponse {
  formation: string;
  context: string;
  slots: BestXIPlayer[];
  top3: BestXITop3Row[];
  coords: Record<string, [number, number]>;
}

/** Mirror across the vertical centre line so LB draws on the right, RB on the left, etc. */
function mirrorPitchCoords(
  coords: Record<string, [number, number]>,
): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  for (const [k, [x, y]] of Object.entries(coords)) {
    out[k] = [100 - x, y];
  }
  return out;
}

// ---------------------------------------------------------------------------
// Pitch SVG
// ---------------------------------------------------------------------------

function PitchPlayerMarker({
  slot,
  p,
  x,
  y,
  onSelect,
}: {
  slot: string;
  p: BestXIPlayer;
  x: number;
  y: number;
  onSelect?: () => void;
}) {
  const empty = p.player === "—";
  const piLabel = p.performance_index != null ? p.performance_index.toFixed(1) : "";
  const wid = p.wyscout_id != null && Number.isFinite(Number(p.wyscout_id))
    ? Number(p.wyscout_id)
    : null;
  const [faceFailed, setFaceFailed] = React.useState(false);
  const directImg = p.player_image_url?.trim();
  const imgHref = directImg && !faceFailed ? wyscoutPlayerImageSrc(directImg) : null;

  const interactive = Boolean(onSelect && !empty && wid != null);
  const badgeR = AVATAR_R * 0.38;
  const badgeOff = AVATAR_R * 0.62;
  const pi = p.performance_index;
  const accent =
    !empty && pi != null && !Number.isNaN(Number(pi))
      ? scoutProfileIndexColor(pi, "text")
      : null;

  return (
    <g
      transform={`translate(${x}, ${y})`}
      style={{ cursor: interactive ? "pointer" : "default" }}
      onClick={interactive ? onSelect : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect?.();
              }
            }
          : undefined
      }
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? `Open profile: ${p.player}` : undefined}
    >
      <title>
        {empty ? `${slot} (empty)` : `${p.player} (${slot})`}
      </title>

      {!empty && pi != null && pi > 75 && accent && (
        <circle
          cx="0"
          cy="0"
          r={AVATAR_R + 1.05}
          fill="none"
          stroke={accent}
          strokeWidth="0.18"
          opacity={0.42}
        />
      )}

      {/* Avatar: fill + photo + ring on top */}
      <circle
        cx="0"
        cy="0"
        r={AVATAR_R}
        fill={empty ? "#121a26" : "#152a38"}
        opacity={empty ? 0.45 : 1}
      />

      {imgHref ? (
        <image
          href={imgHref}
          x={-AVATAR_R}
          y={-AVATAR_R}
          width={AVATAR_D}
          height={AVATAR_D}
          preserveAspectRatio="xMidYMid slice"
          clipPath={`url(#${AVATAR_CLIP_ID})`}
          onError={() => setFaceFailed(true)}
        />
      ) : null}
      <circle
        cx="0"
        cy="0"
        r={AVATAR_R}
        fill="none"
        stroke={empty ? PITCH.emptyStroke : accent ?? PITCH.emptyStroke}
        strokeWidth={empty ? 0.3 : 0.42}
        opacity={empty ? 0.45 : 1}
      />

      {!empty && !imgHref && (
        <text
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={AVATAR_R * 0.95}
          fill={accent ?? PITCH.emptyStroke}
          fontWeight="bold"
        >
          {p.player.split(" ").pop()?.slice(0, 2).toUpperCase() ?? "??"}
        </text>
      )}

      {/* Club badge — bottom-right of avatar */}
      {!empty && p.club_logo ? (
        <>
          <circle
            cx={badgeOff}
            cy={badgeOff}
            r={badgeR}
            fill="#0a1018"
            stroke={accent ?? PITCH.emptyStroke}
            strokeWidth="0.28"
          />
          <image
            href={wyscoutClubLogoSrc(p.club_logo)}
            x={badgeOff - badgeR}
            y={badgeOff - badgeR}
            width={badgeR * 2}
            height={badgeR * 2}
            preserveAspectRatio="xMidYMid meet"
          />
        </>
      ) : null}

      <rect
        x={-(AVATAR_R + 0.6)}
        y={AVATAR_R + 0.55}
        width={(AVATAR_R + 0.6) * 2}
        height="2.75"
        fill="#000000a0"
        rx="0.45"
      />
      <text
        x="0"
        y={AVATAR_R + 2}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize="1.85"
        fill={PITCH.textMuted}
        fontWeight="600"
      >
        {slot}
      </text>

      {!empty && (
        <>
          <text
            x="0"
            y={AVATAR_R + 5.1}
            textAnchor="middle"
            fontSize="2.05"
            fill={PITCH.textName}
            fontWeight="700"
            style={{ textShadow: "0 1px 3px #000c" }}
          >
            {p.player.split(" ").slice(-1)[0]}
          </text>
          {piLabel ? (
            <text
              x="0"
              y={AVATAR_R + 7.35}
              textAnchor="middle"
              fontSize="1.85"
              fill={accent ?? "#b2c4d8"}
              opacity={0.95}
            >
              {piLabel}
            </text>
          ) : null}
        </>
      )}
    </g>
  );
}

function PitchSVG({
  slots,
  coords,
  onPlayerSelect,
}: {
  slots: BestXIPlayer[];
  coords: Record<string, [number, number]>;
  onPlayerSelect?: (wyscoutId: number) => void;
}) {
  const bySlot = Object.fromEntries(slots.map((s) => [s.slot, s]));
  const mirrored = React.useMemo(() => mirrorPitchCoords(coords), [coords]);

  return (
    <svg
      viewBox="0 0 100 118"
      className="h-auto w-full max-w-none"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      <rect x="0" y="0" width="100" height="118" fill="#081018" rx="3" />

      <g stroke="#ffffff" strokeWidth="0.3" fill="none" opacity="0.22">
        <rect x="5" y="2" width="90" height="106" rx="1" />
        <line x1="5" y1="55" x2="95" y2="55" />
        <circle cx="50" cy="55" r="9.15" />
        <circle cx="50" cy="55" r="0.45" fill="#ffffff" opacity="0.45" />
        <rect x="21.1" y="2" width="57.8" height="16.5" />
        <rect x="21.1" y="91.5" width="57.8" height="16.5" />
        <rect x="33" y="2" width="34" height="5.5" />
        <rect x="33" y="102.5" width="34" height="5.5" />
        <circle cx="50" cy="13.85" r="0.45" fill="#ffffff" opacity="0.38" />
        <circle cx="50" cy="96.15" r="0.45" fill="#ffffff" opacity="0.38" />
      </g>

      <defs>
        {/* objectBoundingBox: (0-1) relative to the <image> box — avoids clipping in root 0-100 coords */}
        <clipPath id={AVATAR_CLIP_ID} clipPathUnits="objectBoundingBox">
          <circle cx="0.5" cy="0.5" r="0.5" />
        </clipPath>
      </defs>

      {Object.entries(mirrored).map(([slot, [x, y]]) => {
        const p = bySlot[slot];
        if (!p) return null;
        const wid = p.wyscout_id != null ? Number(p.wyscout_id) : null;
        return (
          <PitchPlayerMarker
            key={slot}
            slot={slot}
            p={p}
            x={x}
            y={y}
            onSelect={
              wid != null && Number.isFinite(wid) && p.player !== "—"
                ? () => onPlayerSelect?.(wid)
                : undefined
            }
          />
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Top 3 table
// ---------------------------------------------------------------------------

function ClubLogo({ url }: { url?: string | null }) {
  return <ClubLogoImg logoUrl={url} className="h-5 w-5" />;
}

function Top3Table({
  top3,
  season,
}: {
  top3: BestXITop3Row[];
  season: number;
}) {
  const bySlot = top3.reduce<Record<string, BestXITop3Row[]>>((acc, r) => {
    (acc[r.slot] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="overflow-auto">
      <table className="w-full text-xs text-content">
        <thead>
          <tr className="border-b border-outline-variant/30">
            <th className="py-2 px-3 text-left text-content-muted font-medium w-14">Slot</th>
            <th className="py-2 px-3 text-left text-content-muted font-medium">Player</th>
            <th className="py-2 px-3 text-left text-content-muted font-medium">Club</th>
            <th className="py-2 px-3 text-right text-content-muted font-medium">Age</th>
            <th className="py-2 px-3 text-right text-content-muted font-medium">Min</th>
            <th className="py-2 px-3 text-right text-content-muted font-medium">PI</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(bySlot).map(([slot, rows], gi) =>
            rows.map((r, i) => {
              const profileId = r.wyscout_id != null && Number.isFinite(Number(r.wyscout_id))
                ? Number(r.wyscout_id)
                : null;
              const playerCell = (
                <div className="flex min-w-0 items-center gap-2">
                  {profileId != null ? (
                    <Link
                      href={`/scout/profile/${profileId}?season=${season}`}
                      className="truncate font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded-sm"
                    >
                      {r.player}
                    </Link>
                  ) : (
                    <span className="truncate">{r.player}</span>
                  )}
                </div>
              );
              return (
                <tr
                  key={`${slot}-${r.rank}`}
                  className={cn(
                    "border-b border-outline-variant/10 transition-colors hover:bg-surface-mid/30",
                    gi % 2 === 0 ? "bg-surface/5" : "",
                    i === 0 ? "font-semibold" : "opacity-75",
                    profileId != null ? "cursor-pointer" : "",
                  )}
                >
                  <td className="py-1.5 px-3">
                    {i === 0 ? (
                      <span className="inline-flex items-center rounded-sm bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary font-bold">
                        {slot}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-1.5 px-3">{playerCell}</td>
                  <td className="py-1.5 px-3">
                    <div className="flex items-center gap-1.5">
                      <ClubLogo url={r.club_logo} />
                      <span className="truncate max-w-[120px]">{r.club ?? "—"}</span>
                    </div>
                  </td>
                  <td className="py-1.5 px-3 text-right tabular-nums">{r.age ?? "—"}</td>
                  <td className="py-1.5 px-3 text-right tabular-nums">
                    {r.minutes != null ? r.minutes.toLocaleString() : "—"}
                  </td>
                  <td
                    className="py-1.5 px-3 text-right tabular-nums"
                    style={
                      r.performance_index != null
                        ? { color: scoutProfileIndexColor(r.performance_index, "text") }
                        : undefined
                    }
                  >
                    {r.performance_index != null ? r.performance_index.toFixed(1) : "—"}
                  </td>
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BestXIPage() {
  const router = useRouter();
  const f = useGlobalFilters();
  const { filtersOpen, setFiltersOpen } = useScoutFiltersSidebar();
  const [formation, setFormation] = React.useState("4-3-3");
  const [mode, setMode] = React.useState<Mode>("by_league");
  const [club, setClub] = React.useState<string | null>(null);
  const [team2, setTeam2] = React.useState<string | null>(null);
  /** Start true so “By league” loads immediately on first visit. */
  const [submitted, setSubmitted] = React.useState(true);

  const clubsQ = useQuery({
    queryKey: ["meta-teams", f.season, f.leagues],
    queryFn: async () => {
      const { data, error } = await api.GET("/meta/teams", {
        params: {
          query: {
            season: f.season,
          },
        },
      });
      if (error) throw new Error("clubs");
      return (data ?? []) as string[];
    },
  });

  const clubs: string[] = clubsQ.data ?? [];

  const requestBody = React.useMemo(() => ({
    filters: {
      season: f.season,
      leagues: f.leagues.length ? f.leagues : null,
      age_min: f.ageMin,
      age_max: f.ageMax,
      minutes_min: f.minutesMin,
    },
    formation,
    mode,
    club: club ?? undefined,
    team2: team2 ?? undefined,
  }), [f.season, f.leagues, f.ageMin, f.ageMax, f.minutesMin, formation, mode, club, team2]);

  const canSubmit =
    mode === "by_league" ||
    (mode === "by_club" && club != null) ||
    (mode === "two_teams" && club != null && team2 != null);

  const bxiQ = useQuery({
    enabled: submitted && canSubmit,
    queryKey: ["best-xi", requestBody],
    queryFn: async () => {
      const { data, error } = await api.POST("/teams/best-xi", {
        body: requestBody,
      });
      if (error) throw new Error(JSON.stringify(error));
      return data as BestXIResponse;
    },
  });

  const result = bxiQ.data;
  const showBxiSkeleton = useDelayedLoading(submitted && canSubmit && bxiQ.isPending);

  const pitchMeasureRef = React.useRef<HTMLDivElement>(null);
  const [pitchCardHeightPx, setPitchCardHeightPx] = React.useState<number | null>(null);
  const [viewportLg, setViewportLg] = React.useState(false);

  React.useLayoutEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const sync = () => setViewportLg(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  React.useLayoutEffect(() => {
    if (!result) {
      setPitchCardHeightPx(null);
      return;
    }
    const el = pitchMeasureRef.current;
    if (!el) return;

    const measure = () => {
      setPitchCardHeightPx(Math.round(el.getBoundingClientRect().height));
    };
    measure();

    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [result]);

  const goProfile = React.useCallback(
    (id: number) => {
      router.push(`/scout/profile/${id}?season=${f.season}`);
    },
    [router, f.season],
  );

  return (
    <div
      className={cn("grid gap-6", filtersOpen ? "grid-cols-[280px_1fr]" : "grid-cols-1")}
    >
      {filtersOpen ? (
        <aside className="flex min-w-0 flex-col gap-4">
          <GlassCard id="best-xi-filters-panel" className="flex flex-col gap-4 p-4">
            <p className="label-caps">Population & formation</p>
            <FilterPanel />

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-content-muted">
                Formation
              </h3>
              <Combobox
                options={FORMATIONS.map((form) => ({ value: form, label: form }))}
                value={formation}
                onChange={(v) => {
                  setFormation(v);
                  setSubmitted(false);
                }}
                placeholder="Formation"
              />
            </div>

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-widest text-content-muted">
                Mode
              </h3>
              <div className="flex flex-col gap-1.5">
                {(
                  [
                    { value: "by_league" as const, label: "By league" },
                    { value: "by_club" as const, label: "By club" },
                    { value: "two_teams" as const, label: "Two teams combined" },
                  ]
                ).map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => {
                      setMode(value);
                      setSubmitted(false);
                    }}
                    className={cn(
                      "rounded px-3 py-2 text-left text-sm transition-colors",
                      mode === value
                        ? "border border-primary/40 bg-primary/20 text-primary"
                        : "border border-transparent text-content-muted hover:bg-surface-mid/40",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {mode !== "by_league" && (
                <div className="mt-3 flex flex-col gap-2">
                  <Combobox
                    options={clubs.map((c) => ({ value: c, label: c }))}
                    value={club ?? ""}
                    onChange={(v) => {
                      setClub(v || null);
                      setSubmitted(false);
                    }}
                    placeholder="Team 1"
                  />
                  {mode === "two_teams" && (
                    <Combobox
                      options={clubs.filter((c) => c !== club).map((c) => ({ value: c, label: c }))}
                      value={team2 ?? ""}
                      onChange={(v) => {
                        setTeam2(v || null);
                        setSubmitted(false);
                      }}
                      placeholder="Team 2"
                    />
                  )}
                </div>
              )}
            </div>

            <Button
              disabled={!canSubmit}
              onClick={() => setSubmitted(true)}
              className="w-full"
            >
              Build Best XI
            </Button>
          </GlassCard>
        </aside>
      ) : null}

      <main className="min-w-0 overflow-auto p-6">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">Best XI</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              {result
                ? `${result.formation} · ${result.context} · Season ${f.season}/${(f.season + 1) % 100}`
                : "Pick formation, filters, and build — or load by league automatically."}
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="gap-1.5"
            onClick={() => setFiltersOpen(!filtersOpen)}
            aria-expanded={filtersOpen}
            aria-controls={filtersOpen ? "best-xi-filters-panel" : undefined}
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
        </div>

        {!submitted && (
          <div className="flex min-h-[40vh] items-center justify-center text-sm text-content-muted">
            Select filters and click &ldquo;Build Best XI&rdquo;
          </div>
        )}

        {submitted && !canSubmit && (
          <div className="flex min-h-[40vh] items-center justify-center text-center text-sm text-content-muted px-4">
            Complete the team selection for this mode, then click &ldquo;Build Best XI&rdquo;.
          </div>
        )}

        {showBxiSkeleton && (
          <div className="space-y-6">
            <FilterChipsSkeleton count={4} />
            <BestXiPitchSkeleton />
          </div>
        )}

        {submitted && canSubmit && bxiQ.isError && (
          <div className="flex min-h-[40vh] items-center justify-center text-sm text-red-400">
            Error: {String(bxiQ.error)}
          </div>
        )}

        {result && (
          <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 lg:grid lg:grid-cols-[3fr_2fr] lg:items-start">
            <div ref={pitchMeasureRef} className="min-w-0">
              <GlassCard className="min-w-0 w-full p-4 sm:p-6">
                <PitchSVG
                  slots={result.slots}
                  coords={result.coords as Record<string, [number, number]>}
                  onPlayerSelect={goProfile}
                />
              </GlassCard>
            </div>

            <GlassCard
              className="min-w-0 w-full p-4 sm:p-6 lg:flex lg:min-h-0 lg:flex-col lg:overflow-hidden"
              style={
                pitchCardHeightPx != null && viewportLg
                  ? { maxHeight: pitchCardHeightPx }
                  : undefined
              }
            >
              <h2 className="mb-4 shrink-0 text-sm font-semibold text-content">
                Top 3 per position
              </h2>
              <div className="min-h-0 flex-1 overflow-y-auto lg:min-h-0">
                <Top3Table top3={result.top3} season={f.season} />
              </div>
            </GlassCard>
          </div>
        )}
      </main>
    </div>
  );
}
