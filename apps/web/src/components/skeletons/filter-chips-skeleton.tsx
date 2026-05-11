import { Skeleton } from "@/components/ui/loading";

export function FilterChipsSkeleton({ count = 5 }: { count?: number }) {
  const widths = [72, 96, 84, 110, 64, 88];
  return (
    <div className="flex flex-wrap items-center gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-7 rounded-full"
          style={{ width: widths[i % widths.length] }}
        />
      ))}
    </div>
  );
}
