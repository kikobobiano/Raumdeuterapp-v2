import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import { ProfileHeaderSkeleton } from "@/components/skeletons/profile-header-skeleton";
import { Skeleton, SkeletonLine } from "@/components/ui/loading";

export default function Loading() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-4 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1 space-y-2 sm:max-w-xl">
            <SkeletonLine width={56} className="h-2.5" />
            <Skeleton className="h-10 rounded-md" />
          </div>
          <div className="w-full shrink-0 space-y-2 sm:w-48">
            <SkeletonLine width={56} className="h-2.5" />
            <Skeleton className="h-10 rounded-md" />
          </div>
        </div>
        <SkeletonLine width={140} className="h-3" />
      </div>

      <ProfileHeaderSkeleton />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <ChartSkeleton variant="radial" height={320} />
        <ChartSkeleton variant="generic" height={320} label="Positions" />
        <ChartSkeleton variant="bar" height={320} label="Similar (Big 5)" />
      </div>

      <ChartSkeleton variant="progression" height={260} label="Performance progression" />
    </div>
  );
}
