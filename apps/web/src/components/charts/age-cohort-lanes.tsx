"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import * as React from "react";

import { potentialDotColor } from "@/components/charts/quadrant-chart";
import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { Shimmer } from "@/components/ui/loading";
import { api } from "@/lib/api";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";
import { cn } from "@/lib/utils";

export interface CohortPlayer {
  wyscoutId: number | null;
  player: string;
  club: string | null;
  clubLogo: string | null;
  league: string | null;
  position: string | null;
  age: number;
  minutes: number | null;
  currentPi: number | null;
  potentialScore: number;
  playerImageUrl: string | null;
}

/** Filter set sent to ``POST /potential/cohort``; matches API ``PlayerFilters`` shape. */
export interface CohortFilters {
  season: number;
  leagues: string[] | null;
  teams?: string[] | null;
  roles: string[] | null;
  age_min?: number | null;
  age_max?: number | null;
  minutes_min?: number | null;
}

export function chipKey(p: CohortPlayer): string {
  return `${p.wyscoutId ?? "x"}-${p.club ?? ""}`;
}

interface Props {
  /** Age range to render (e.g. ``[16, 17, …, 25]``). */
  ages: number[];
  filters: CohortFilters;
  /** Page size per fetch (default 20). */
  pageSize?: number;
  onSelect?: (p: CohortPlayer) => void;
  /** Highlight the chip whose ``chipKey`` matches. */
  selectedKey?: string | null;
}

const DEFAULT_PAGE_SIZE = 20;

/**
 * Server-paginated big board: one row (Lane) per age, fetching on demand
 * (``useInfiniteQuery`` per age) — initial page = ``pageSize``, scroll near the
 * right edge fetches the next page.
 */
export function AgeCohortLanes({
  ages,
  filters,
  pageSize = DEFAULT_PAGE_SIZE,
  onSelect,
  selectedKey,
}: Props) {
  return (
    <div className="flex w-full min-w-0 flex-col gap-3">
      {ages.map((age) => (
        <LaneQuery
          key={age}
          age={age}
          filters={filters}
          pageSize={pageSize}
          onSelect={onSelect}
          selectedKey={selectedKey}
        />
      ))}
    </div>
  );
}

// ── Per-age data wrapper ──────────────────────────────────────────────────────

const filterSig = (f: CohortFilters): string =>
  [
    f.season,
    (f.leagues ?? []).join(","),
    (f.teams ?? []).join(","),
    (f.roles ?? []).join(","),
    f.age_min ?? "",
    f.age_max ?? "",
    f.minutes_min ?? "",
  ].join("|");

function LaneQuery({
  age,
  filters,
  pageSize,
  onSelect,
  selectedKey,
}: {
  age: number;
  filters: CohortFilters;
  pageSize: number;
  onSelect?: (p: CohortPlayer) => void;
  selectedKey?: string | null;
}) {
  const sig = filterSig(filters);

  const q = useInfiniteQuery({
    queryKey: ["potential-cohort", age, sig, pageSize],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.POST("/potential/cohort", {
        body: {
          filters: filters as CohortFilters,
          age,
          limit: pageSize,
          offset: pageParam as number,
        },
      });
      if (error) throw new Error(JSON.stringify(error));
      return data!;
    },
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce(
        (acc, p) => acc + (p.players?.length ?? 0),
        0,
      );
      return loaded < (lastPage.total ?? 0) ? loaded : undefined;
    },
    staleTime: 60_000,
  });

  const apiPlayers = React.useMemo(
    () => q.data?.pages.flatMap((p) => p.players) ?? [],
    [q.data],
  );
  const total = q.data?.pages[0]?.total ?? 0;

  const players = React.useMemo<CohortPlayer[]>(
    () =>
      apiPlayers
        .filter((p) => p.age != null && p.potential_score != null)
        .map((p) => ({
          wyscoutId: p.wyscout_id ?? null,
          player: p.player,
          club: p.club ?? null,
          clubLogo: p.club_logo ?? null,
          league: p.league ?? null,
          position: p.position ?? null,
          age: p.age!,
          minutes: p.minutes ?? null,
          currentPi: p.current_pi ?? null,
          potentialScore: p.potential_score,
          playerImageUrl: p.player_image_url ?? null,
        })),
    [apiPlayers],
  );

  const fetchNextPage = q.fetchNextPage;
  const hasNextPage = q.hasNextPage;
  const isFetchingNextPage = q.isFetchingNextPage;
  const onLoadMore = React.useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  if (q.isPending) {
    return <LaneSkeleton age={age} />;
  }

  if (q.isError) {
    return (
      <div className="rounded-lg border border-error/30 bg-surface-low/40 px-3 py-2 text-xs text-error">
        Age {age}: failed to load.
      </div>
    );
  }

  if (players.length === 0) return null;

  return (
    <Lane
      age={age}
      players={players}
      total={total}
      hasMore={Boolean(hasNextPage)}
      isFetchingMore={isFetchingNextPage}
      onLoadMore={onLoadMore}
      onSelect={onSelect}
      selectedKey={selectedKey}
    />
  );
}

// ── Pure-UI lane renderer ─────────────────────────────────────────────────────

function Lane({
  age,
  players,
  total,
  hasMore,
  isFetchingMore,
  onLoadMore,
  onSelect,
  selectedKey,
}: {
  age: number;
  players: CohortPlayer[];
  total: number;
  hasMore: boolean;
  isFetchingMore: boolean;
  onLoadMore: () => void;
  onSelect?: (p: CohortPlayer) => void;
  selectedKey?: string | null;
}) {
  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const sentinelRef = React.useRef<HTMLDivElement | null>(null);
  const [canLeft, setCanLeft] = React.useState(false);
  const [canRight, setCanRight] = React.useState(false);

  const updateScrollState = React.useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 4);
    setCanRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  React.useEffect(() => {
    updateScrollState();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", updateScrollState, { passive: true });
    const ro = new ResizeObserver(updateScrollState);
    ro.observe(el);
    return () => {
      el.removeEventListener("scroll", updateScrollState);
      ro.disconnect();
    };
  }, [updateScrollState, players.length]);

  // Auto-load next page when sentinel scrolls into view inside the lane.
  React.useEffect(() => {
    const root = scrollRef.current;
    const target = sentinelRef.current;
    if (!root || !target || !hasMore) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) onLoadMore();
        }
      },
      { root, rootMargin: "0px 240px 0px 0px", threshold: 0.01 },
    );
    io.observe(target);
    return () => io.disconnect();
  }, [hasMore, onLoadMore, players.length]);

  const scrollBy = (dx: number) => {
    scrollRef.current?.scrollBy({ left: dx, behavior: "smooth" });
  };

  const top = players[0];
  const topColor = top ? potentialDotColor(top.potentialScore) : "#666";

  return (
    <div className="w-full min-w-0 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-low/40">
      <div className="flex min-w-0 items-stretch">
        {/* Lane header */}
        <div
          className="flex w-24 shrink-0 flex-col items-center justify-center gap-1 border-r border-outline-variant/30 px-2 py-3"
          style={{ background: `linear-gradient(180deg, ${topColor}10, transparent)` }}
        >
          <div className="data-mono text-3xl font-bold leading-none text-on-surface">
            {age}
          </div>
          <div className="w-full text-center text-[9px] uppercase leading-tight text-on-surface-variant">
            <span className="block font-medium tabular-nums tracking-tight">{total}</span>
            <span className="mt-0.5 block tracking-widest">
              {total === 1 ? "player" : "players"}
            </span>
          </div>
        </div>

        {/* Scroll area */}
        <div className="relative min-w-0 flex-1">
          {canLeft && (
            <button
              type="button"
              onClick={() => scrollBy(-300)}
              aria-label="Scroll left"
              data-export-hide
              className="absolute left-1 top-1/2 z-10 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-full border border-outline-variant/60 bg-surface-high/95 text-on-surface shadow-md backdrop-blur-sm hover:bg-surface-highest"
            >
              <ChevronLeft className="h-4 w-4" strokeWidth={1.5} />
            </button>
          )}
          {canRight && (
            <button
              type="button"
              onClick={() => scrollBy(300)}
              aria-label="Scroll right"
              data-export-hide
              className="absolute right-1 top-1/2 z-10 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-full border border-outline-variant/60 bg-surface-high/95 text-on-surface shadow-md backdrop-blur-sm hover:bg-surface-highest"
            >
              <ChevronRight className="h-4 w-4" strokeWidth={1.5} />
            </button>
          )}
          {canLeft && (
            <div data-export-hide className="pointer-events-none absolute left-0 top-0 z-[1] h-full w-10 bg-gradient-to-r from-surface-low/90 to-transparent" />
          )}
          {canRight && (
            <div data-export-hide className="pointer-events-none absolute right-0 top-0 z-[1] h-full w-10 bg-gradient-to-l from-surface-low/90 to-transparent" />
          )}

          <div
            ref={scrollRef}
            className="flex gap-2 overflow-x-auto overflow-y-hidden scroll-smooth py-3 pl-3 pr-3 export-no-scrollbar"
            style={{ scrollbarWidth: "thin" }}
          >
            {players.map((p, i) => (
              <Chip
                key={`${p.wyscoutId}-${p.club ?? ""}-${i}`}
                p={p}
                rankInAge={i + 1}
                onClick={() => onSelect?.(p)}
                selected={selectedKey != null && chipKey(p) === selectedKey}
              />
            ))}

            {/* Sentinel + spinner / load-more handle */}
            {hasMore ? (
              <div
                ref={sentinelRef}
                className={cn(
                  "flex w-44 shrink-0 snap-start flex-col items-center justify-center gap-2 rounded-md border border-dashed border-outline-variant/40 bg-surface-mid/30 p-2 text-[10px] text-on-surface-variant",
                )}
              >
                {isFetchingMore ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Loading more…</span>
                  </>
                ) : (
                  <>
                    <ChevronRight className="h-4 w-4" />
                    <button
                      type="button"
                      className="hover:text-on-surface"
                      onClick={onLoadMore}
                    >
                      Load more
                    </button>
                  </>
                )}
                <span className="text-[9px] opacity-70">
                  {players.length} / {total}
                </span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Skeleton (during first load) ──────────────────────────────────────────────

function LaneSkeleton({ age }: { age: number }) {
  return (
    <Shimmer className="w-full min-w-0 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-low/40">
      <div className="flex min-w-0 items-stretch">
        <div className="flex w-24 shrink-0 flex-col items-center justify-center gap-1 border-r border-outline-variant/30 px-2 py-3">
          <div className="data-mono text-3xl font-bold leading-none text-on-surface/70">
            {age}
          </div>
          <div className="w-full text-center text-[9px] uppercase leading-tight tracking-widest text-on-surface-variant/60">
            loading…
          </div>
        </div>
        <div className="relative min-w-0 flex-1 overflow-hidden">
          <div className="flex gap-2 py-3 pl-3 pr-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-[78px] w-44 shrink-0 animate-pulse rounded-md border border-outline-variant/30 bg-surface-mid/40"
              />
            ))}
          </div>
        </div>
      </div>
    </Shimmer>
  );
}

// ── Chip (single player) ──────────────────────────────────────────────────────

function Chip({
  p,
  rankInAge,
  onClick,
  selected = false,
}: {
  p: CohortPlayer;
  rankInAge: number;
  onClick?: () => void;
  selected?: boolean;
}) {
  const [imgFailed, setImgFailed] = React.useState(false);

  const portrait = (() => {
    if (imgFailed) return null;
    if (p.playerImageUrl) return wyscoutPlayerImageSrc(p.playerImageUrl);
    return null;
  })();

  const potColor = potentialDotColor(p.potentialScore);

  const isTop = rankInAge === 1;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "group flex w-44 shrink-0 snap-start flex-col rounded-md border p-2 text-left transition-all",
        "hover:scale-[1.02] hover:border-primary/50 hover:bg-surface-mid",
        selected
          ? "border-sky-400 bg-sky-500/15 ring-2 ring-sky-400/60"
          : isTop
            ? "border-primary/40 bg-surface-mid/50"
            : "border-outline-variant/30 bg-surface-mid/50",
      )}
      style={
        selected
          ? { boxShadow: "0 0 0 1px rgba(56,189,248,0.5), 0 4px 18px rgba(56,189,248,0.35)" }
          : isTop
            ? { boxShadow: `0 0 0 1px ${potColor}30, 0 4px 12px ${potColor}15` }
            : undefined
      }
    >
      {/* Header row */}
      <div className="flex items-center gap-2">
        <div className="grid h-4 w-4 shrink-0 place-items-center rounded-sm bg-surface-low text-[9px] font-bold tabular-nums text-on-surface-variant">
          {rankInAge}
        </div>
        <div className="relative h-8 w-8 shrink-0 overflow-hidden rounded bg-surface-low">
          {portrait ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={portrait}
              alt=""
              className="h-full w-full object-cover"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <div className="grid h-full w-full place-items-center text-[8px] text-on-surface-variant">
              {p.player.split(" ").map((s) => s[0]).slice(0, 2).join("")}
            </div>
          )}
        </div>
        <div className="ml-auto data-mono text-base font-bold leading-none" style={{ color: potColor }}>
          {p.potentialScore.toFixed(1)}
        </div>
      </div>

      {/* Name */}
      <div className="mt-1.5 min-w-0">
        <div className="truncate text-xs font-semibold text-on-surface">{p.player}</div>
        <div className="mt-0.5 flex items-center gap-1 text-[10px] text-on-surface-variant">
          <ClubLogoImg logoUrl={p.clubLogo} className="h-3 w-3" />
          <span className="truncate">{p.club ?? "—"}</span>
        </div>
      </div>

      {/* Footer: minutes (left) + position (right) */}
      <div className="mt-1.5 flex items-center justify-between gap-2 text-[10px] data-mono text-on-surface-variant">
        <span>{p.minutes ?? 0}&apos;</span>
        {p.position ? (
          <span className="rounded-sm bg-surface-low px-1 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-on-surface">
            {p.position}
          </span>
        ) : null}
      </div>
    </button>
  );
}
