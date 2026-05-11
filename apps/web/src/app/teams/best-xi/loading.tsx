import { BestXiPitchSkeleton } from "@/components/skeletons/best-xi-pitch-skeleton";
import { FilterChipsSkeleton } from "@/components/skeletons/filter-chips-skeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <FilterChipsSkeleton count={4} />
      <BestXiPitchSkeleton />
    </div>
  );
}
