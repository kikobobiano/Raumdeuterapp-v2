"use client";

import * as React from "react";

import { GlassCard } from "@/components/ui/glass-card";
import { cn } from "@/lib/utils";

/** Left accent = `@theme` vars from `globals.css` (reliable with `border-l-2`). */
const TRAIT_AREA_BORDER: Record<string, string> = {
  Distribution: "border-l-[var(--color-primary)]",
  Assistance: "border-l-[var(--color-secondary)]",
  "Take Ons": "border-l-[var(--color-primary-soft)]",
  Finishing: "border-l-[var(--color-tertiary)]",
  "Ground Defense": "border-l-[var(--color-outline)]",
  "Aerial Play": "border-l-[var(--color-secondary-soft)]",
};

export type PlayerTraitItem = {
  positive: boolean;
  label: string;
  game_area: string;
};

function TraitRows({ items }: { items: PlayerTraitItem[] }) {
  return (
    <ul className="grid grid-cols-1 gap-2 md:grid-cols-3">
      {items.map((t, i) => (
        <li
          key={`${t.label}-${t.game_area}-${i}`}
          className={cn(
            "min-w-0 rounded-r-md border-l-2 bg-surface-low/40 py-2.5 pl-3 pr-2",
            TRAIT_AREA_BORDER[t.game_area] ?? "border-l-[var(--color-on-surface-variant)]",
          )}
        >
          <p className="break-words text-sm font-medium leading-snug text-on-surface">{t.label}</p>
          <p className="label-caps mt-1.5 text-[0.65rem] text-on-surface-variant">{t.game_area}</p>
        </li>
      ))}
    </ul>
  );
}

export function PlayerTraitsBlock({ traits }: { traits: PlayerTraitItem[] }) {
  const strengths = React.useMemo(() => traits.filter((t) => t.positive), [traits]);
  const watchouts = React.useMemo(() => traits.filter((t) => !t.positive), [traits]);

  if (traits.length === 0) {
    return null;
  }

  return (
    <GlassCard>
      <h2 className="mb-1 text-xl font-semibold text-on-surface">Player traits</h2>
      <p className="mb-6 text-sm text-on-surface-variant">
        Derived from percentile rules vs. players in the same tactical role (all leagues).
      </p>

      <div
        className={cn(
          "grid gap-8",
          strengths.length > 0 && watchouts.length > 0 && "md:grid-cols-2",
        )}
      >
        {strengths.length > 0 ? (
          <div>
            <h3 className="label-caps mb-3 text-on-surface">Strengths</h3>
            <TraitRows items={strengths} />
          </div>
        ) : null}
        {watchouts.length > 0 ? (
          <div>
            <h3 className="label-caps mb-3 text-on-surface">Watchouts</h3>
            <TraitRows items={watchouts} />
          </div>
        ) : null}
      </div>
    </GlassCard>
  );
}
