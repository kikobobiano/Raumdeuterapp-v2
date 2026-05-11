import { Shimmer, Skeleton, SkeletonCircle, SkeletonLine } from "@/components/ui/loading";

const POSITIONS: Array<[number, number]> = [
  [50, 88],          // GK
  [12, 70], [37, 72], [63, 72], [88, 70], // back four
  [25, 50], [50, 52], [75, 50],           // mids
  [22, 25], [50, 18], [78, 25],           // forwards
];

export function BestXiPitchSkeleton() {
  return (
    <div className="space-y-4">
      <SkeletonLine width={180} className="h-3" />
      <Shimmer
        className="relative overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-low/40"
        style={{ aspectRatio: "16/11" }}
      >
        <svg
          aria-hidden
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 70"
          preserveAspectRatio="none"
        >
          <rect x="2" y="2" width="96" height="66" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="0.4" />
          <line x1="50" y1="2" x2="50" y2="68" stroke="rgba(255,255,255,0.1)" strokeWidth="0.3" />
          <circle cx="50" cy="35" r="9" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="0.3" />
          <rect x="20" y="2" width="60" height="14" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="0.3" />
          <rect x="20" y="54" width="60" height="14" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="0.3" />
        </svg>
        {POSITIONS.map(([x, y], i) => (
          <div
            key={i}
            className="absolute"
            style={{ left: `${x}%`, top: `${y}%`, transform: "translate(-50%,-50%)" }}
          >
            <SkeletonCircle size={36} />
          </div>
        ))}
      </Shimmer>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 rounded-md" />
        ))}
      </div>
    </div>
  );
}
