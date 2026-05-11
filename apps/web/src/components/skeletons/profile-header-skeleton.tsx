import {
  Shimmer,
  Skeleton,
  SkeletonBlock,
  SkeletonCircle,
  SkeletonLine,
} from "@/components/ui/loading";

export function ProfileHeaderSkeleton() {
  return (
    <Shimmer className="rounded-xl border border-outline-variant/30 bg-surface-low/40 p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center">
        <SkeletonCircle size={96} />
        <div className="min-w-0 flex-1 space-y-3">
          <SkeletonLine width="55%" className="h-5" />
          <div className="flex flex-wrap gap-2">
            <Skeleton className="h-5 w-24 rounded-full" />
            <Skeleton className="h-5 w-32 rounded-full" />
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-1.5">
                <SkeletonLine width="60%" className="h-2" />
                <SkeletonBlock className="h-6" />
              </div>
            ))}
          </div>
        </div>
        <SkeletonBlock className="hidden h-32 w-32 shrink-0 rounded-lg lg:block" />
      </div>
    </Shimmer>
  );
}
