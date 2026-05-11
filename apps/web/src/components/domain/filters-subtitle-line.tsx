import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Size = "sm" | "xs";

/** Single-line filter summary; nowrap + horizontal scroll if overflow (export-safe). */
export function FiltersSubtitleLine({
  children,
  size = "sm",
  className,
}: {
  children: ReactNode;
  size?: Size;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "max-w-full whitespace-nowrap overflow-x-auto text-on-surface-variant",
        "[scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        size === "xs" ? "mt-0.5 text-xs" : "mt-1 text-sm",
        className,
      )}
    >
      {children}
    </p>
  );
}
