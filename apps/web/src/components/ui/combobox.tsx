"use client";

import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Check, ChevronsUpDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export interface ComboboxOption {
  value: string;
  label: string;
}

interface Props {
  options: ComboboxOption[];
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  /** Pill style aligned with top-bar `PlayerSearch` minimal variant. */
  variant?: "default" | "minimal";
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder,
  className,
  variant = "default",
}: Props) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const filtered = React.useMemo(
    () =>
      options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())),
    [options, query],
  );
  const selected = options.find((o) => o.value === value);

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          className={cn(
            "flex w-full items-center justify-between text-sm text-on-surface",
            variant === "minimal"
              ? cn(
                  "h-9 gap-2 rounded-full border border-transparent bg-surface-low px-4",
                  "hover:bg-surface-mid/80",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35",
                )
              : cn(
                  "h-10 rounded-md border border-outline-variant bg-surface-high px-3",
                  "hover:bg-surface-highest",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                ),
            className,
          )}
        >
          <span
            suppressHydrationWarning
            className={cn(
              "min-w-0 truncate text-left",
              !selected && "text-on-surface-variant",
            )}
          >
            {selected?.label ?? placeholder ?? "Select..."}
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-on-surface-variant" strokeWidth={1.5} />
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align={variant === "minimal" ? "end" : "start"}
          sideOffset={4}
          className="z-50 w-[var(--radix-popover-trigger-width)] rounded-md border border-outline-variant bg-surface-high p-1 shadow-xl shadow-black/50"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search..."
            className="w-full border-0 border-b border-outline-variant/35 bg-transparent px-2 py-1.5 text-sm text-on-surface placeholder:text-on-surface-variant outline-none focus-visible:border-primary/45 focus-visible:ring-0"
          />
          <div className="max-h-60 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-2 py-2 text-sm text-on-surface-variant">No results.</div>
            ) : (
              filtered.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                    setQuery("");
                  }}
                  className="flex w-full items-center justify-between rounded px-2 py-1.5 text-sm text-on-surface hover:bg-surface-highest"
                >
                  {opt.label}
                  {opt.value === value && <Check className="h-4 w-4 text-primary" />}
                </button>
              ))
            )}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
