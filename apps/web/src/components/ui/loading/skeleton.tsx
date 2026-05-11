import * as React from "react";

import { cn } from "@/lib/utils";

type DivProps = React.HTMLAttributes<HTMLDivElement>;

export function Skeleton({ className, ...rest }: DivProps) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse rounded-md border border-outline-variant/20 bg-surface-mid/40",
        className,
      )}
      {...rest}
    />
  );
}

export function SkeletonLine({
  width,
  className,
  style,
  ...rest
}: DivProps & { width?: number | string }) {
  return (
    <Skeleton
      className={cn("h-3 rounded", className)}
      style={{ width: typeof width === "number" ? `${width}px` : width, ...style }}
      {...rest}
    />
  );
}

export function SkeletonBlock({ className, ...rest }: DivProps) {
  return <Skeleton className={cn("w-full rounded-md", className)} {...rest} />;
}

export function SkeletonCircle({
  size = 32,
  className,
  style,
  ...rest
}: DivProps & { size?: number }) {
  return (
    <Skeleton
      className={cn("shrink-0 rounded-full", className)}
      style={{ width: size, height: size, ...style }}
      {...rest}
    />
  );
}
