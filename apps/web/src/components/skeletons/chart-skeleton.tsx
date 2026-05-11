import {
  Shimmer,
  Skeleton,
  SkeletonBlock,
  SkeletonCircle,
  SkeletonLine,
} from "@/components/ui/loading";

type Variant = "bar" | "scatter" | "radial" | "progression" | "generic";

export function ChartSkeleton({
  variant = "generic",
  height = 280,
  label,
}: {
  variant?: Variant;
  height?: number;
  label?: string;
}) {
  return (
    <div className="space-y-3">
      {label != null && (
        <SkeletonLine width={Math.max(80, label.length * 7)} className="h-2.5" />
      )}
      <Shimmer
        className="rounded-lg border border-outline-variant/30 bg-surface-low/40"
        style={{ height }}
      >
        <ChartBody variant={variant} />
      </Shimmer>
    </div>
  );
}

function ChartBody({ variant }: { variant: Variant }) {
  if (variant === "bar") return <BarChartBody />;
  if (variant === "scatter") return <ScatterChartBody />;
  if (variant === "radial") return <RadialChartBody />;
  if (variant === "progression") return <ProgressionChartBody />;
  return <GenericChartBody />;
}

function ChartFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full w-full">
      <div className="flex w-10 flex-col justify-between py-3 pr-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <SkeletonLine key={i} width={20} className="h-2" />
        ))}
      </div>
      <div className="relative flex-1 overflow-hidden border-l border-outline-variant/20 px-3 py-3">
        {children}
        <div className="absolute inset-x-3 bottom-2 flex justify-between">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <SkeletonLine key={i} width={18} className="h-2" />
          ))}
        </div>
      </div>
    </div>
  );
}

function BarChartBody() {
  const heights = [42, 65, 28, 82, 48, 72, 38, 58, 26, 70];
  return (
    <ChartFrame>
      <div className="flex h-full items-end gap-2 pb-6 pt-2">
        {heights.map((h, i) => (
          <Skeleton key={i} className="flex-1 rounded-sm" style={{ height: `${h}%` }} />
        ))}
      </div>
    </ChartFrame>
  );
}

function ScatterChartBody() {
  const dots = [
    [12, 70], [22, 55], [30, 38], [38, 60], [44, 22], [52, 48],
    [58, 68], [64, 30], [72, 52], [78, 18], [84, 64], [90, 40],
    [18, 28], [42, 80], [62, 12],
  ];
  return (
    <ChartFrame>
      <div className="relative h-full pb-6">
        {dots.map(([x, y], i) => (
          <SkeletonCircle
            key={i}
            size={10}
            className="absolute"
            style={{ left: `${x}%`, top: `${y}%` }}
          />
        ))}
      </div>
    </ChartFrame>
  );
}

function RadialChartBody() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="relative">
        <SkeletonCircle size={180} />
        <div className="absolute inset-6">
          <SkeletonCircle size={132} />
        </div>
        <div className="absolute inset-12">
          <SkeletonCircle size={84} />
        </div>
      </div>
    </div>
  );
}

function ProgressionChartBody() {
  const points = [70, 55, 60, 42, 48, 38, 30, 36, 28];
  return (
    <ChartFrame>
      <div className="relative h-full pb-6">
        <svg
          aria-hidden
          className="h-full w-full"
          viewBox={`0 0 ${(points.length - 1) * 100} 100`}
          preserveAspectRatio="none"
        >
          <polyline
            fill="none"
            stroke="rgba(255,255,255,0.18)"
            strokeWidth="2"
            points={points.map((y, i) => `${i * 100},${y}`).join(" ")}
          />
        </svg>
        {points.map((y, i) => (
          <SkeletonCircle
            key={i}
            size={8}
            className="absolute"
            style={{ left: `${(i / (points.length - 1)) * 100}%`, top: `${y}%` }}
          />
        ))}
      </div>
    </ChartFrame>
  );
}

function GenericChartBody() {
  return (
    <div className="flex h-full items-center justify-center p-4">
      <SkeletonBlock className="h-full" />
    </div>
  );
}
