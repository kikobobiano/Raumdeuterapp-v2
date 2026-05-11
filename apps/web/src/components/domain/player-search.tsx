"use client";

import * as PopoverPrimitive from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import * as React from "react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  season: number;
  onSelect: (wyscoutId: number, player: string, club?: string | null) => void;
  className?: string;
  placeholder?: string;
  /** Compact pill (top bar); default is bordered inline field. */
  variant?: "default" | "minimal";
}

export function PlayerSearch({
  season,
  onSelect,
  className,
  placeholder,
  variant = "default",
}: Props) {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState("");

  const search = useQuery({
    queryKey: ["search", season, q],
    queryFn: async () => {
      const { data } = await api.GET("/players/search", {
        params: { query: { season, q, limit: 10 } },
      });
      return data ?? [];
    },
    enabled: q.length >= 2,
  });

  return (
    <PopoverPrimitive.Root open={open && q.length >= 2} onOpenChange={setOpen}>
      <PopoverPrimitive.Anchor asChild>
        <div
          className={cn(
            variant === "minimal"
              ? "relative flex h-9 max-w-full items-center rounded-full border border-transparent bg-surface-low focus-within:bg-surface-low focus-within:ring-2 focus-within:ring-primary/35"
              : "flex h-10 items-center gap-2 rounded-md border border-outline-variant bg-surface-high px-3 focus-within:ring-2 focus-within:ring-primary/40",
            variant === "minimal" ? "pr-4" : "",
            className,
          )}
        >
          <Search
            className={cn(
              "h-4 w-4 shrink-0 text-on-surface-variant",
              variant === "minimal" &&
                "pointer-events-none absolute left-3 top-1/2 -translate-y-1/2",
            )}
            strokeWidth={1.5}
          />
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder={placeholder ?? "Search players..."}
            className={cn(
              "min-w-0 flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant outline-none",
              variant === "minimal" ? "h-9 rounded-full py-1 pl-10 pr-0" : "py-1 pl-0",
            )}
          />
        </div>
      </PopoverPrimitive.Anchor>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align={variant === "minimal" ? "end" : "start"}
          sideOffset={4}
          className="z-50 w-[var(--radix-popover-trigger-width)] rounded-md border border-outline-variant bg-surface-high p-1 shadow-xl shadow-black/50"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          {(search.data ?? []).length === 0 ? (
            <div className="px-3 py-2 text-sm text-on-surface-variant">
              {search.isLoading ? "Searching..." : "No matches."}
            </div>
          ) : (
            (search.data ?? []).map((p) => (
              <button
                key={`${p.wyscout_id ?? p.player}-${p.club ?? ""}`}
                onClick={() => {
                  if (p.wyscout_id != null) {
                    onSelect(p.wyscout_id, p.player, p.club ?? null);
                    setOpen(false);
                    setQ("");
                  }
                }}
                className="flex w-full items-start justify-between rounded px-3 py-2 text-left hover:bg-surface-highest"
              >
                <div>
                  <div className="text-sm text-on-surface">{p.player}</div>
                  <div className="text-xs text-on-surface-variant">
                    {p.club ?? "—"} · {p.position ?? "—"} · age {p.age ?? "—"}
                  </div>
                </div>
                <span className="data-mono text-xs text-on-surface-variant">
                  {p.minutes ?? 0}&apos;
                </span>
              </button>
            ))
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
