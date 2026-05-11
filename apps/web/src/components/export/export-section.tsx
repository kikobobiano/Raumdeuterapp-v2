"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

import { useExportContext } from "./export-context";

interface SectionProps {
  id: string;
  label: string;
  required?: boolean;
  defaultIncluded?: boolean;
  /** When true the section appears in the dropdown but cannot be selected. */
  disabled?: boolean;
  /** Tooltip / help text shown next to the disabled row. */
  disabledReason?: string;
  className?: string;
  children: React.ReactNode;
}

export function ExportSection({
  id,
  label,
  required = false,
  defaultIncluded = true,
  disabled = false,
  disabledReason,
  className,
  children,
}: SectionProps) {
  const ctx = useExportContext();
  const register = ctx?.register;
  const unregister = ctx?.unregister;
  const ref = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!register || !unregister) return;
    register({ id, label, required, defaultIncluded, disabled, disabledReason, ref });
    return () => unregister(id);
  }, [register, unregister, id, label, required, defaultIncluded, disabled, disabledReason]);

  return (
    <div ref={ref} data-export-section={id} className={className}>
      {children}
    </div>
  );
}

interface FilterAreaProps {
  children: React.ReactNode;
  className?: string;
}

export function ExportFilterArea({ children, className }: FilterAreaProps) {
  return (
    <div data-export-hide className={cn(className)}>
      {children}
    </div>
  );
}
