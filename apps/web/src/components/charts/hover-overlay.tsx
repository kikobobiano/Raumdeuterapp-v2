"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";

export interface OverlayHoverState {
  idx: number;
  x: number;
  y: number;
}

interface PlotlyDiv extends HTMLElement {
  on?: (ev: string, cb: (e: { points?: { pointIndex?: number; curveNumber?: number }[] }) => void) => void;
  removeListener?: (
    ev: string,
    cb: (e: { points?: { pointIndex?: number; curveNumber?: number }[] }) => void,
  ) => void;
}

/**
 * Listens to plotly_hover via gd.on() (most reliable across react-plotly versions),
 * and tracks cursor via mousemove on a container div for absolute overlay positioning.
 */
export function useOverlayHover<T>(items: T[], opts?: { trace?: number }) {
  const resolver = React.useCallback(
    (curve: number, idx: number) => {
      if (opts?.trace != null && curve !== opts.trace) return null;
      return items[idx] ?? null;
    },
    [items, opts?.trace],
  );
  return useOverlayHoverByCurve<T>(resolver);
}

/**
 * Variant that resolves the hovered item by (curveNumber, pointIndex) — use for charts
 * with multiple traces where a single index isn't enough.
 */
export function useOverlayHoverByCurve<T>(
  resolve: (curveNumber: number, pointIndex: number) => T | null,
) {
  const [state, setState] = React.useState<{ x: number; y: number; item: T } | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const resolveRef = React.useRef(resolve);
  resolveRef.current = resolve;

  const onInitialized = React.useCallback((_fig: unknown, gd: HTMLElement) => {
    const div = gd as PlotlyDiv;
    const root = containerRef.current;
    if (!root) return;
    let lastItem: T | null = null;
    const onHover = (e: { points?: { pointIndex?: number; curveNumber?: number }[] }) => {
      const p = e.points?.[0];
      if (!p) return;
      const ci = p.curveNumber;
      const pi = p.pointIndex;
      if (ci == null || pi == null) return;
      const r = resolveRef.current(ci, pi);
      if (r != null) lastItem = r;
    };
    const onUnhover = () => {
      lastItem = null;
      setState(null);
    };
    const onMove = (ev: MouseEvent) => {
      if (lastItem == null) return;
      const rect = root.getBoundingClientRect();
      setState({ item: lastItem, x: ev.clientX - rect.left, y: ev.clientY - rect.top });
    };
    div.on?.("plotly_hover", onHover);
    div.on?.("plotly_unhover", onUnhover);
    root.addEventListener("mousemove", onMove);
  }, []);

  return { item: state?.item ?? null, state, onInitialized, containerRef };
}

export interface OverlayCardData {
  name: string;
  club?: string | null;
  league?: string | null;
  position?: string | null;
  age?: number | null;
  value?: string | null;
  valueLabel?: string | null;
  /** Extra metric lines shown below identity (e.g. metric: value pairs). */
  rows?: { label: string; value: string }[];
  color?: string | null;
  clubLogoUrl?: string | null;
  imageUrl?: string | null;
  /** Fallback portrait via Wyscout public portrait when imageUrl missing. */
  wyscoutId?: number | null;
}

/** Floating tooltip card — face thumb, club crest, name, identity, value pill. */
export function OverlayCard({ data }: { data: OverlayCardData }) {
  const accent = data.color ?? "#14d1ff";
  const [faceFailed, setFaceFailed] = React.useState(false);
  const portraitSrc = (() => {
    if (faceFailed) return null;
    const direct = data.imageUrl?.trim();
    if (direct) return wyscoutPlayerImageSrc(direct);
    return null;
  })();
  return (
    <div
      className="pointer-events-none flex w-[260px] gap-2.5 rounded-lg border bg-surface-high/95 p-2.5 shadow-2xl backdrop-blur-md"
      style={{
        borderColor: accent,
        boxShadow: `0 6px 24px ${accent}30, 0 0 0 1px ${accent}40 inset`,
      }}
    >
      <div className="relative h-[44px] w-[44px] shrink-0 overflow-hidden rounded-md bg-surface-mid">
        {portraitSrc ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={portraitSrc}
            alt=""
            className="h-full w-full object-cover object-[center_22%]"
            onError={() => setFaceFailed(true)}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs font-bold text-on-surface-variant/60">
            {data.name
              .split(" ")
              .map((s) => s[0])
              .slice(0, 2)
              .join("")}
          </div>
        )}
        {data.clubLogoUrl && (
          <div className="absolute -bottom-0.5 -right-0.5 rounded-sm bg-surface-high p-0.5 ring-1 ring-outline-variant/40">
            <ClubLogoImg logoUrl={data.clubLogoUrl} className="h-4 w-4" />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-on-surface">{data.name}</p>
        {(data.club || data.league) && (
          <p className="mt-0.5 truncate text-[10px] text-on-surface-variant">
            {[data.club, data.league].filter(Boolean).join(" · ")}
          </p>
        )}
        <div className="mt-1.5 flex items-center gap-1.5">
          {data.position && (
            <span className="rounded bg-surface-low/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-on-surface-variant">
              {data.position}
            </span>
          )}
          {data.age != null && <span className="text-[10px] text-on-surface-variant">{data.age}y</span>}
          {data.value && (
            <span
              className="ml-auto data-mono rounded px-1.5 py-0.5 text-[11px] font-bold"
              style={{ background: `${accent}20`, color: accent }}
              title={data.valueLabel ?? undefined}
            >
              {data.value}
            </span>
          )}
        </div>
        {data.rows && data.rows.length > 0 && (
          <ul className="mt-1.5 space-y-0.5 border-t border-outline-variant/30 pt-1.5">
            {data.rows.map((r) => (
              <li key={r.label} className="flex items-center justify-between gap-2 text-[10px]">
                <span className="truncate text-on-surface-variant">{r.label}</span>
                <span className="data-mono shrink-0 tabular-nums text-on-surface">{r.value}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** Flat hoverlabel that hides plotly's native tooltip while keeping hover events. */
export const TRANSPARENT_HOVERLABEL = {
  bgcolor: "rgba(0,0,0,0)",
  bordercolor: "rgba(0,0,0,0)",
  font: { color: "rgba(0,0,0,0)", size: 1 },
} as const;
