import { FilterChipsSkeleton } from "@/components/skeletons/filter-chips-skeleton";
import { RankingsTableSkeleton } from "@/components/skeletons/rankings-table-skeleton";
import { Skeleton, SkeletonLine } from "@/components/ui/loading";

export default function Loading() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
        <div className="min-w-0 flex-1 space-y-2">
          <SkeletonLine width={88} className="h-2.5" />
          <Skeleton className="h-10 rounded-md" />
        </div>
        <div className="w-full shrink-0 space-y-2 lg:w-48">
          <SkeletonLine width={56} className="h-2.5" />
          <Skeleton className="h-10 rounded-md" />
        </div>
        <Skeleton className="h-8 w-32 shrink-0 rounded-md" />
      </div>
      <FilterChipsSkeleton count={4} />
      <RankingsTableSkeleton count={20} />
    </div>
  );
}
