import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import { GlassCard } from "@/components/ui/glass-card";
import { Skeleton, SkeletonLine } from "@/components/ui/loading";

export default function Loading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-2">
          <SkeletonLine width={200} className="h-4" />
          <SkeletonLine width={140} className="h-3" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <GlassCard key={i} className="p-4">
            <SkeletonLine width={100} className="h-3" />
            <Skeleton className="mt-3 h-6 w-24 rounded" />
          </GlassCard>
        ))}
      </div>
      <GlassCard className="p-6">
        <ChartSkeleton variant="scatter" height={420} />
      </GlassCard>
      <GlassCard className="p-6">
        <ChartSkeleton variant="scatter" height={320} />
      </GlassCard>
    </div>
  );
}
