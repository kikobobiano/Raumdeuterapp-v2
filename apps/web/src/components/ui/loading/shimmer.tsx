import * as React from "react";

import { cn } from "@/lib/utils";

type Props = React.HTMLAttributes<HTMLDivElement> & {
  children: React.ReactNode;
};

export function Shimmer({ className, children, ...rest }: Props) {
  return (
    <div
      className={cn(
        "relative overflow-hidden",
        "after:pointer-events-none after:absolute after:inset-0 after:content-['']",
        "after:bg-[linear-gradient(90deg,transparent_0%,rgba(20,209,255,0.18)_50%,transparent_100%)]",
        "after:animate-[shimmerSweep_1.6s_linear_infinite]",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
