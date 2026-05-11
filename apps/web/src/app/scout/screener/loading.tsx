import { FilterChipsSkeleton } from "@/components/skeletons/filter-chips-skeleton";
import { RankingsTableSkeleton } from "@/components/skeletons/rankings-table-skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <FilterChipsSkeleton count={6} />
      <RankingsTableSkeleton count={20} />
    </div>
  );
}
