import { Shimmer, SkeletonLine } from "@/components/ui/loading";

import { PlayerCardGridSkeleton } from "./player-card-skeleton";

export function RankingsTableSkeleton({
  withFilters = false,
  count = 15,
}: {
  withFilters?: boolean;
  count?: number;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1.5">
          <SkeletonLine width={140} className="h-2.5" />
          <SkeletonLine width={210} className="h-3" />
        </div>
        <SkeletonLine width={120} className="h-6 rounded-md" />
      </div>
      <Shimmer className="-m-1 rounded-md p-1">
        <PlayerCardGridSkeleton count={count} withFilters={withFilters} />
      </Shimmer>
    </section>
  );
}
