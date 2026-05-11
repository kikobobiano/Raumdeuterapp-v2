"use client";

import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Check, Download, Loader2 } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { useExportContextStrict } from "./export-context";

interface Props {
  className?: string;
  label?: string;
}

export function ExportButton({ className, label = "Export" }: Props) {
  const ctx = useExportContextStrict();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  // Per-section user override. Sections without an entry follow defaultIncluded.
  // Required sections are always selected regardless of override.
  const [overrides, setOverrides] = React.useState<Map<string, boolean>>(
    () => new Map(),
  );

  const selected = React.useMemo(() => {
    const result = new Set<string>();
    ctx.sections.forEach((s) => {
      if (s.disabled) return;
      if (s.required) {
        result.add(s.id);
        return;
      }
      const o = overrides.get(s.id);
      if (o === true) result.add(s.id);
      else if (o === false) {
        // explicitly off
      } else if (s.defaultIncluded) {
        result.add(s.id);
      }
    });
    return result;
  }, [ctx.sections, overrides]);

  const toggle = (id: string, required: boolean, disabled: boolean) => {
    if (required || disabled) return;
    const isOn = selected.has(id);
    setOverrides((prev) => {
      const next = new Map(prev);
      next.set(id, !isOn);
      return next;
    });
  };

  const handleExport = async () => {
    if (busy) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const res = await ctx.exportPng(Array.from(selected));
      if (!res.ok) {
        setErrorMsg("Open at least one of the selected panels to export.");
        return;
      }
      if (res.missing.length > 0) {
        setErrorMsg(
          `Skipped ${res.missing.join(", ")} — open the panel(s) to include them.`,
        );
      } else {
        setOpen(false);
      }
    } catch (err) {
      console.error("Export failed", err);
      setErrorMsg("Export failed. See console for details.");
    } finally {
      setBusy(false);
    }
  };

  const optionalCount = ctx.sections.filter((s) => !s.required).length;

  // Single-button mode: no optional sections, no point in showing a dropdown.
  if (optionalCount === 0) {
    return (
      <span data-export-hide>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn("gap-2", className)}
          onClick={handleExport}
          disabled={busy || selected.size === 0}
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {label}
        </Button>
      </span>
    );
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn("gap-2", className)}
          data-export-hide
        >
          <Download className="h-4 w-4" />
          {label}
        </Button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="end"
          sideOffset={6}
          className="z-50 w-72 rounded-md border border-outline-variant bg-surface-high p-2 shadow-xl shadow-black/50"
        >
          {ctx.sections.length === 0 ? (
            <p className="px-2 py-2 text-sm text-on-surface-variant">No exportable areas.</p>
          ) : (
            <>
              {optionalCount > 0 && (
                <p className="px-2 pt-1 pb-2 text-xs text-on-surface-variant">
                  Choose what to include in the PNG.
                </p>
              )}
              <div className="max-h-72 space-y-0.5 overflow-y-auto">
                {ctx.sections.map((s) => {
                  const isOn = selected.has(s.id);
                  const interactive = !s.required && !s.disabled;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => toggle(s.id, s.required, s.disabled)}
                      disabled={!interactive}
                      aria-pressed={isOn}
                      title={s.disabled ? s.disabledReason : undefined}
                      className={cn(
                        "flex w-full items-center justify-between gap-3 rounded px-2 py-1.5 text-left text-sm",
                        "text-on-surface hover:bg-surface-highest",
                        s.required && "cursor-default opacity-80",
                        s.disabled && "cursor-not-allowed opacity-50 hover:bg-transparent",
                      )}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <span
                          className={cn(
                            "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border",
                            isOn
                              ? "border-primary bg-primary text-primary-fg"
                              : "border-outline-variant",
                          )}
                          aria-hidden
                        >
                          {isOn ? <Check className="h-3 w-3" /> : null}
                        </span>
                        <span className="truncate">{s.label}</span>
                      </span>
                      {s.required ? (
                        <span className="text-[10px] uppercase tracking-wide text-on-surface-variant">
                          Always
                        </span>
                      ) : s.disabled ? (
                        <span className="text-[10px] uppercase tracking-wide text-on-surface-variant">
                          Closed
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
              {errorMsg ? (
                <p className="mt-2 px-2 text-xs text-error">{errorMsg}</p>
              ) : null}
              <div className="mt-2 flex justify-end">
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={handleExport}
                  disabled={busy || selected.size === 0}
                  className="gap-2"
                >
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Export PNG
                </Button>
              </div>
            </>
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
