import * as React from "react";

import { cn } from "@/lib/utils";

export const GlassCard = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "glass rounded-lg p-6 relative overflow-hidden",
      "before:absolute before:inset-0 before:rounded-lg before:pointer-events-none",
      "before:bg-[linear-gradient(135deg,rgba(255,255,255,0.06)_0%,transparent_40%)]",
      className,
    )}
    {...props}
  />
));
GlassCard.displayName = "GlassCard";

export const GlassCardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex items-center justify-between pb-3 border-b border-outline-variant/50 mb-4",
      className,
    )}
    {...props}
  />
));
GlassCardHeader.displayName = "GlassCardHeader";

export const GlassCardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-lg font-semibold tracking-tight text-on-surface", className)}
    {...props}
  />
));
GlassCardTitle.displayName = "GlassCardTitle";
