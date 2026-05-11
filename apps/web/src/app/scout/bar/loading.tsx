import { ChartSkeleton } from "@/components/skeletons/chart-skeleton";
import { FilterChipsSkeleton } from "@/components/skeletons/filter-chips-skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <FilterChipsSkeleton count={5} />
      <ChartSkeleton variant="bar" height={520} label="Bar chart" />
    </div>
  );
}
