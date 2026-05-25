import { Shimmer, Skeleton, SkeletonLine } from "@/components/ui/loading";

function LaneSkeletonRow({ age }: { age: number }) {
  return (
    <Shimmer className="w-full min-w-0 overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-low/40">
      <div className="flex min-w-0 items-stretch">
        <div className="flex w-24 shrink-0 flex-col items-center justify-center gap-1 border-r border-outline-variant/30 px-2 py-3">
          <div className="data-mono text-3xl font-bold leading-none text-on-surface/70">
            {age}
          </div>
          <div className="w-full text-center text-[9px] uppercase leading-tight tracking-widest text-on-surface-variant/60">
            loading…
          </div>
        </div>
        <div className="relative min-w-0 flex-1 overflow-hidden">
          <div className="flex gap-2 py-3 pl-3 pr-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-[78px] w-44 shrink-0 rounded-md" />
            ))}
          </div>
        </div>
      </div>
    </Shimmer>
  );
}

export default function Loading() {
  return (
    <div className="space-y-4">
      <SkeletonLine width="35%" className="h-3" />
      <div className="space-y-3">
        {[18, 19, 20, 21, 22, 23].map((age) => (
          <LaneSkeletonRow key={age} age={age} />
        ))}
      </div>
    </div>
  );
}
