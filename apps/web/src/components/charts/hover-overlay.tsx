"use client";

import * as React from "react";

import { ClubLogoImg } from "@/components/domain/club-logo-img";
import { wyscoutPlayerImageSrc } from "@/lib/wyscout-image";

export interface OverlayHoverState {
  idx: number;
  x: number;
  y: number;
}

type PlotHoverPayload = Readonly<{
  points?: ReadonlyArray<{
    pointIndex?: number;
    curveNumber?: number;
  }>;
  event?: MouseEvent;
}>;

interface PlotlyDiv extends HTMLElement {
  on?: (ev: string, cb: (e: PlotHoverPayload) => void) => void;
  removeListener?: (ev: string, cb: (e: PlotHoverPayload) => void) => void;
}

/**
 * Custom overlay hover for Plotly charts.
 * Wires both react-plotly ``onHover`` and ``gd.on('plotly_hover')`` — scattergl
 * often only fires the latter.
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

export function useOverlayHoverByCurve<T>(
  resolve: (curveNumber: number, pointIndex: number) => T | null,
) {
  const [state, setState] = React.useState<{ x: number; y: number; item: T } | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const resolveRef = React.useRef(resolve);
  resolveRef.current = resolve;
  const lastItemRef = React.useRef<T | null>(null);
  const cleanupRef = React.useRef<(() => void) | null>(null);

  const positionFromEvent = React.useCallback((ev: MouseEvent | undefined) => {
    const root = containerRef.current;
    if (!root) return { x: 0, y: 0 };
    const rect = root.getBoundingClientRect();
    if (ev) {
      return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    }
    return { x: rect.width / 2, y: rect.height / 2 };
  }, []);

  const applyHover = React.useCallback(
    (ev: PlotHoverPayload) => {
      const p = ev.points?.[0];
      if (!p) return;
      const ci = p.curveNumber;
      const pi = p.pointIndex;
      if (ci == null || pi == null) return;
      const r = resolveRef.current(ci, pi);
      if (r == null) return;
      lastItemRef.current = r;
      const { x, y } = positionFromEvent(ev.event);
      setState({ item: r, x, y });
    },
    [positionFromEvent],
  );

  const onHover = React.useCallback(
    (ev: PlotHoverPayload) => applyHover(ev),
    [applyHover],
  );

  const onUnhover = React.useCallback(() => {
    lastItemRef.current = null;
    setState(null);
  }, []);

  const onMouseMove = React.useCallback((ev: React.MouseEvent<HTMLDivElement>) => {
    if (lastItemRef.current == null) return;
    const root = containerRef.current;
    if (!root) return;
    const rect = root.getBoundingClientRect();
    setState({
      item: lastItemRef.current,
      x: ev.clientX - rect.left,
      y: ev.clientY - rect.top,
    });
  }, []);

  const onInitialized = React.useCallback(
    (_fig: unknown, gd: HTMLElement) => {
      cleanupRef.current?.();
      const div = gd as PlotlyDiv;
      div.on?.("plotly_hover", applyHover);
      div.on?.("plotly_unhover", onUnhover);
      cleanupRef.current = () => {
        div.removeListener?.("plotly_hover", applyHover);
        div.removeListener?.("plotly_unhover", onUnhover);
      };
    },
    [applyHover, onUnhover],
  );

  React.useEffect(() => () => cleanupRef.current?.(), []);

  return {
    item: state?.item ?? null,
    state,
    containerRef,
    onHover,
    onUnhover,
    onMouseMove,
    onInitialized,
  };
}

export interface OverlayCardData {
  name: string;
  club?: string | null;
  league?: string | null;
  position?: string | null;
  age?: number | null;
  value?: string | null;
  valueLabel?: string | null;
  rows?: { label: string; value: string }[];
  color?: string | null;
  clubLogoUrl?: string | null;
  imageUrl?: string | null;
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

export const TRANSPARENT_HOVERLABEL = {
  bgcolor: "rgba(0,0,0,0)",
  bordercolor: "rgba(0,0,0,0)",
  font: { color: "rgba(0,0,0,0)", size: 1 },
} as const;
