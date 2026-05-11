import { SkeletonBlock, SkeletonLine } from "@/components/ui/loading";

export default function Loading() {
  return (
    <div className="space-y-6">
      <SkeletonLine width="40%" className="h-5" />
      <SkeletonBlock className="h-64" />
    </div>
  );
}
