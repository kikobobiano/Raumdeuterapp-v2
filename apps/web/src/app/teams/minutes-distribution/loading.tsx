import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import { GlassCard } from "@/components/ui/glass-card";
import { Skeleton, SkeletonLine } from "@/components/ui/loading";

export default function Loading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-2">
          <SkeletonLine width={180} className="h-4" />
          <SkeletonLine width={120} className="h-3" />
        </div>
      </div>
      <GlassCard className="p-6">
        <ChartSkeleton variant="scatter" height={420} />
      </GlassCard>
      <GlassCard className="p-6">
        <div className="space-y-2">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-md" />
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
