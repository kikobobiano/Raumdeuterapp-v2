import {
  Skeleton,
  SkeletonBlock,
  SkeletonLine,
} from "@/components/ui/loading";

export function PlayerCardSkeleton() {
  return (
    <div className="flex w-full overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-low/40">
      <SkeletonBlock className="h-[140px] w-[100px] shrink-0 rounded-none" />
      <div className="flex min-w-0 flex-1 flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1 space-y-1.5">
            <SkeletonLine width="70%" className="h-3.5" />
            <SkeletonLine width="55%" className="h-2.5" />
            <SkeletonLine width="40%" className="h-2.5" />
          </div>
          <Skeleton className="h-9 w-12 shrink-0 rounded-md" />
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="flex flex-col gap-1.5">
            <SkeletonBlock className="h-3" />
            <SkeletonBlock className="h-3" />
            <SkeletonBlock className="h-3" />
          </div>
          <div className="flex flex-col gap-1.5 border-l border-outline-variant/30 pl-3">
            <SkeletonBlock className="h-3" />
            <SkeletonBlock className="h-3" />
            <SkeletonBlock className="h-3" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function PlayerCardGridSkeleton({
  count = 8,
}: {
  count?: number;
  /** Retained for call-site compatibility; grid matches rankings (3 cols at lg). */
  withFilters?: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <PlayerCardSkeleton key={i} />
      ))}
    </div>
  );
}
