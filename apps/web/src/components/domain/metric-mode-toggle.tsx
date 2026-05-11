"use client";

import type { components } from "shared-types";

import { cn } from "@/lib/utils";

export type MetricMode = "raw" | "p90" | "as_is";

/** Safe mode for API payloads — never undefined (invalid body broke scatter/screener). */
export function modeFromMetricOption(
  o: components["schemas"]["MetricOption"] | undefined,
): MetricMode {
  if (!o?.supports_mode) return "as_is";
  const d = o.default_mode;
  if (d === "raw" || d === "p90" || d === "as_is") return d;
  return "as_is";
}

interface Props {
  supports: boolean;
  value: MetricMode;
  onChange: (mode: MetricMode) => void;
  className?: string;
}

export function MetricModeToggle({ supports, value, onChange, className }: Props) {
  if (!supports) return null;

  const set = (m: "raw" | "p90") => onChange(m);
  const v = value === "raw" || value === "p90" || value === "as_is" ? value : "as_is";

  return (
    <div
      className={cn(
        "flex shrink-0 rounded-md border border-outline-variant/50 p-0.5 text-[11px] font-medium",
        className,
      )}
      role="group"
      aria-label="Metric scale"
    >
      <button
        type="button"
        className={cn(
          "rounded px-2 py-1 transition-colors",
          v === "raw" ? "bg-primary text-on-primary" : "text-on-surface-variant hover:text-on-surface",
        )}
        onClick={() => set("raw")}
      >
        Raw
      </button>
      <button
        type="button"
        className={cn(
          "rounded px-2 py-1 transition-colors",
          v === "p90" ? "bg-primary text-on-primary" : "text-on-surface-variant hover:text-on-surface",
        )}
        onClick={() => set("p90")}
      >
        Per 90
      </button>
    </div>
  );
}
