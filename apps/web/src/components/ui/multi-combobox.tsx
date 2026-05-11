"use client";

import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Check, ChevronsUpDown, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

import type { ComboboxOption } from "./combobox";

interface Props {
  options: ComboboxOption[];
  /** Selected option values (e.g. Wyscout ids as strings). */
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  className?: string;
}

export function MultiCombobox({
  options,
  value,
  onChange,
  placeholder = "Select…",
  className,
}: Props) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const selected = new Set(value);

  const filtered = React.useMemo(
    () => options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())),
    [options, query],
  );

  const toggle = (v: string) => {
    const next = new Set(selected);
    if (next.has(v)) next.delete(v);
    else next.add(v);
    onChange([...next]);
  };

  const labelByValue = React.useMemo(
    () => new Map(options.map((o) => [o.value, o.label])),
    [options],
  );

  return (
    <div className={cn("space-y-2", className)}>
      <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
        <PopoverPrimitive.Trigger asChild>
          <button
            type="button"
            className={cn(
              "flex h-10 w-full items-center justify-between rounded-md border border-outline-variant bg-surface-high px-3 text-sm",
              "text-on-surface hover:bg-surface-highest",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
            )}
          >
            <span className={cn(value.length === 0 && "text-on-surface-variant")}>
              {value.length === 0
                ? placeholder
                : value.length === 1
                  ? (labelByValue.get(value[0]) ?? "1 selected")
                  : `${value.length} selected`}
            </span>
            <ChevronsUpDown className="h-4 w-4 shrink-0 text-on-surface-variant" />
          </button>
        </PopoverPrimitive.Trigger>
        <PopoverPrimitive.Portal>
          <PopoverPrimitive.Content
            align="start"
            sideOffset={4}
            className="z-50 w-[var(--radix-popover-trigger-width)] rounded-md border border-outline-variant bg-surface-high p-1 shadow-xl shadow-black/50"
          >
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search…"
              className="w-full border-0 border-b border-outline-variant/35 bg-transparent px-2 py-1.5 text-sm text-on-surface placeholder:text-on-surface-variant outline-none focus-visible:border-primary/45 focus-visible:ring-0"
            />
            <div className="max-h-60 overflow-y-auto">
              {filtered.length === 0 ? (
                <div className="px-2 py-2 text-sm text-on-surface-variant">No results.</div>
              ) : (
                filtered.map((opt) => {
                  const isOn = selected.has(opt.value);
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => toggle(opt.value)}
                      className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-sm text-on-surface hover:bg-surface-highest"
                    >
                      <span className="min-w-0 truncate">{opt.label}</span>
                      {isOn ? <Check className="h-4 w-4 shrink-0 text-primary" /> : null}
                    </button>
                  );
                })
              )}
            </div>
          </PopoverPrimitive.Content>
        </PopoverPrimitive.Portal>
      </PopoverPrimitive.Root>

      {value.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {value.map((v) => (
            <span
              key={v}
              className="inline-flex max-w-full items-center gap-1 rounded-md border border-primary/35 bg-primary/10 px-2 py-0.5 text-xs text-primary"
            >
              <span className="truncate">{labelByValue.get(v) ?? v}</span>
              <button
                type="button"
                className="shrink-0 rounded p-0.5 hover:bg-primary/20"
                aria-label={`Remove ${labelByValue.get(v) ?? v}`}
                onClick={() => onChange(value.filter((x) => x !== v))}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
