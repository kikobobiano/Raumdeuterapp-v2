"use client";

import dynamic from "next/dynamic";
import * as React from "react";

import { GlassCard } from "@/components/ui/glass-card";
import { PLOTLY_APP_CONFIG } from "@/lib/plotly-config";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface SamplePoint {
  player: string;
  club: string;
  league: string;
  position: string;
  age: number;
  pi: number;
  x: number;
  y: number;
  color: string;
  clubLogo?: string;
  imageUrl?: string;
}

const POINTS: SamplePoint[] = [
  { player: "K. Mbappé", club: "Real Madrid", league: "La Liga", position: "CF", age: 27, pi: 87.2, x: 23.4, y: 7.8, color: "#fb7185", clubLogo: "https://cdn5.wyscout.com/photos/team/public/g676_120x120.png" },
  { player: "Lamine Yamal", club: "Barcelona", league: "La Liga", position: "RAMF", age: 18, pi: 86.0, x: 12.1, y: 9.4, color: "#fb7185", clubLogo: "https://cdn5.wyscout.com/photos/team/public/g672_120x120.png" },
  { player: "M. Olise", club: "Bayern München", league: "Bundesliga", position: "RAMF", age: 23, pi: 87.4, x: 9.8, y: 12.0, color: "#14d1ff", clubLogo: "https://cdn5.wyscout.com/photos/team/public/g31_120x120.png" },
  { player: "H. Kane", club: "Bayern München", league: "Bundesliga", position: "CF", age: 32, pi: 85.5, x: 24.5, y: 4.2, color: "#14d1ff", clubLogo: "https://cdn5.wyscout.com/photos/team/public/g31_120x120.png" },
  { player: "Bruno Fernandes", club: "Manchester United", league: "Premier League", position: "AMF", age: 31, pi: 84.0, x: 11.8, y: 11.6, color: "#00ff41" },
  { player: "F. Thiaw", club: "Newcastle", league: "Premier League", position: "CB", age: 24, pi: 79.0, x: 8.6, y: 8.1, color: "#00ff41" },
  { player: "F. Dimarco", club: "Inter", league: "Serie A", position: "LB", age: 28, pi: 81.8, x: 5.2, y: 12.1, color: "#facc15" },
  { player: "Vitinha", club: "PSG", league: "Ligue 1", position: "CMF", age: 26, pi: 84.8, x: 10.9, y: 6.8, color: "#c084fc" },
  { player: "I. Thiago", club: "PSG", league: "Ligue 1", position: "CF", age: 26, pi: 80.5, x: 19.5, y: 2.4, color: "#c084fc" },
  { player: "M. Salah", club: "Liverpool", league: "Premier League", position: "RW", age: 33, pi: 82.0, x: 18.0, y: 8.6, color: "#00ff41" },
];

const BAR_DATA = [...POINTS].sort((a, b) => b.pi - a.pi).slice(0, 7);

/* ============================================================
   A — Glass Card hover (native, restyled)
   ============================================================ */
function ScatterGlass({ pts }: { pts: SamplePoint[] }) {
  const data = [
    {
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      type: "scatter" as const,
      mode: "markers" as const,
      marker: { size: 12, color: pts.map((p) => p.color), line: { width: 0.5, color: "rgba(255,255,255,0.15)" } },
      customdata: pts.map((p) => [p.player, p.club, p.league, p.position, p.age, p.pi.toFixed(1)]),
      hovertemplate:
        "<b style='font-size:13px'>%{customdata[0]}</b><br>" +
        "<span style='color:#9fb3c8'>%{customdata[1]} · %{customdata[2]}</span><br>" +
        "<span style='color:#9fb3c8'>%{customdata[3]} · %{customdata[4]} y/o</span><br>" +
        "<span style='color:#14d1ff;font-weight:600'>Scout idx %{customdata[5]}</span>" +
        "<extra></extra>",
    },
  ];
  return (
    <Plot
      data={data as Plotly.Data[]}
      layout={{
        autosize: true,
        height: 320,
        margin: { l: 36, r: 12, t: 8, b: 36 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: "Inter", color: "#d2e2f2", size: 11 },
        xaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "xG (raw)" } },
        yaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "xA (raw)" } },
        hoverlabel: {
          bgcolor: "rgba(8,14,22,0.94)",
          bordercolor: "#14d1ff",
          font: { family: "Inter, sans-serif", color: "#d2e2f2", size: 12 },
          align: "left",
        },
        showlegend: false,
      }}
      config={PLOTLY_APP_CONFIG}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}

function BarGlass({ rows }: { rows: SamplePoint[] }) {
  return (
    <Plot
      data={[
        {
          type: "bar" as const,
          orientation: "h" as const,
          y: rows.map((r) => r.player),
          x: rows.map((r) => r.pi),
          marker: { color: rows.map((r) => r.color) },
          customdata: rows.map((r) => [r.club, r.league, r.position, r.pi.toFixed(1)]),
          hovertemplate:
            "<b style='font-size:13px'>%{y}</b><br>" +
            "<span style='color:#9fb3c8'>%{customdata[0]} · %{customdata[1]}</span><br>" +
            "<span style='color:#9fb3c8'>%{customdata[2]}</span><br>" +
            "<span style='color:#14d1ff;font-weight:600'>Scout idx %{customdata[3]}</span>" +
            "<extra></extra>",
        },
      ]}
      layout={{
        autosize: true,
        height: 320,
        margin: { l: 130, r: 12, t: 8, b: 36 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: "Inter", color: "#d2e2f2", size: 11 },
        xaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "Scout idx" } },
        yaxis: { fixedrange: true, automargin: true },
        hoverlabel: {
          bgcolor: "rgba(8,14,22,0.94)",
          bordercolor: "#14d1ff",
          font: { family: "Inter, sans-serif", color: "#d2e2f2", size: 12 },
          align: "left",
        },
        showlegend: false,
      }}
      config={PLOTLY_APP_CONFIG}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}

/* ============================================================
   B — Custom React Overlay (face + crest + chips)
   ============================================================ */
interface PlotlyDiv extends HTMLElement {
  on?: (ev: string, cb: (e: { points?: { pointIndex?: number }[] }) => void) => void;
  removeListener?: (ev: string, cb: (e: { points?: { pointIndex?: number }[] }) => void) => void;
}

function useOverlayHover(pts: SamplePoint[]) {
  const [state, setState] = React.useState<{ idx: number; x: number; y: number } | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  const onInitialized = React.useCallback(
    (_fig: unknown, gd: HTMLElement) => {
      const div = gd as PlotlyDiv;
      const root = containerRef.current;
      if (!root) return;
      let lastIdx: number | null = null;
      const onHover = (e: { points?: { pointIndex?: number }[] }) => {
        const i = e.points?.[0]?.pointIndex;
        if (i != null) lastIdx = i;
      };
      const onUnhover = () => {
        lastIdx = null;
        setState(null);
      };
      const onMove = (ev: MouseEvent) => {
        if (lastIdx == null) return;
        const rect = root.getBoundingClientRect();
        setState({ idx: lastIdx, x: ev.clientX - rect.left, y: ev.clientY - rect.top });
      };
      div.on?.("plotly_hover", onHover);
      div.on?.("plotly_unhover", onUnhover);
      root.addEventListener("mousemove", onMove);
    },
    [],
  );

  const point = state ? pts[state.idx] ?? null : null;
  return { point, cursor: state, onInitialized, containerRef };
}

function OverlayCard({ point }: { point: SamplePoint }) {
  return (
    <div
      className="pointer-events-none flex w-[240px] gap-2.5 rounded-lg border bg-surface-high/95 p-2.5 shadow-2xl backdrop-blur-md"
      style={{ borderColor: point.color, boxShadow: `0 6px 24px ${point.color}30, 0 0 0 1px ${point.color}40 inset` }}
    >
      <div className="relative h-[44px] w-[44px] shrink-0 overflow-hidden rounded-md bg-surface-mid">
        <div className="flex h-full w-full items-center justify-center text-xs font-bold text-on-surface-variant/60">
          {point.player.split(" ").map((s) => s[0]).slice(0, 2).join("")}
        </div>
        {point.clubLogo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`/api/club-logo?url=${encodeURIComponent(point.clubLogo)}`}
            alt=""
            className="absolute -bottom-0.5 -right-0.5 h-5 w-5 rounded-sm bg-surface-high p-0.5 ring-1 ring-outline-variant/40"
          />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-on-surface">{point.player}</p>
        <p className="mt-0.5 truncate text-[10px] text-on-surface-variant">
          {point.club} · {point.league}
        </p>
        <div className="mt-1.5 flex items-center gap-1.5">
          <span className="rounded bg-surface-low/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-on-surface-variant">
            {point.position}
          </span>
          <span className="text-[10px] text-on-surface-variant">{point.age}y</span>
          <span
            className="ml-auto data-mono rounded px-1.5 py-0.5 text-[11px] font-bold"
            style={{ background: `${point.color}20`, color: point.color }}
          >
            {point.pi.toFixed(1)}
          </span>
        </div>
      </div>
    </div>
  );
}

function ScatterOverlay({ pts }: { pts: SamplePoint[] }) {
  const { point, cursor, onInitialized, containerRef } = useOverlayHover(pts);
  return (
    <div ref={containerRef} className="relative w-full">
      <Plot
        data={[
          {
            x: pts.map((p) => p.x),
            y: pts.map((p) => p.y),
            type: "scatter" as const,
            mode: "markers" as const,
            marker: { size: 12, color: pts.map((p) => p.color), line: { width: 0.5, color: "rgba(255,255,255,0.15)" } },
          },
        ] as Plotly.Data[]}
        layout={{
          autosize: true,
          height: 320,
          margin: { l: 36, r: 12, t: 8, b: 36 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: "Inter", color: "#d2e2f2", size: 11 },
          xaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "xG (raw)" } },
          yaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "xA (raw)" } },
          hoverlabel: {
            bgcolor: "rgba(0,0,0,0)",
            bordercolor: "rgba(0,0,0,0)",
            font: { color: "rgba(0,0,0,0)", size: 1 },
          },
          showlegend: false,
        }}
        config={PLOTLY_APP_CONFIG}
        style={{ width: "100%" }}
        useResizeHandler
        onInitialized={onInitialized}
      />
      {point && cursor && (
        <div
          className="pointer-events-none absolute z-50"
          style={{ left: Math.min(cursor.x + 14, 540), top: Math.max(cursor.y - 64, 4) }}
        >
          <OverlayCard point={point} />
        </div>
      )}
    </div>
  );
}

function BarOverlay({ rows }: { rows: SamplePoint[] }) {
  const { point, cursor, onInitialized, containerRef } = useOverlayHover(rows);
  return (
    <div ref={containerRef} className="relative w-full">
      <Plot
        data={[
          {
            type: "bar" as const,
            orientation: "h" as const,
            y: rows.map((r) => r.player),
            x: rows.map((r) => r.pi),
            marker: { color: rows.map((r) => r.color) },
          },
        ]}
        layout={{
          autosize: true,
          height: 320,
          margin: { l: 130, r: 12, t: 8, b: 36 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: "Inter", color: "#d2e2f2", size: 11 },
          xaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "Scout idx" } },
          yaxis: { fixedrange: true, automargin: true },
          hoverlabel: {
            bgcolor: "rgba(0,0,0,0)",
            bordercolor: "rgba(0,0,0,0)",
            font: { color: "rgba(0,0,0,0)", size: 1 },
          },
          showlegend: false,
        }}
        config={PLOTLY_APP_CONFIG}
        style={{ width: "100%" }}
        useResizeHandler
        onInitialized={onInitialized}
      />
      {point && cursor && (
        <div
          className="pointer-events-none absolute z-50"
          style={{ left: Math.min(cursor.x + 14, 540), top: Math.max(cursor.y - 64, 4) }}
        >
          <OverlayCard point={point} />
        </div>
      )}
    </div>
  );
}

/* ============================================================
   C — Pill Tag hover (native, minimal one-liner)
   ============================================================ */
function ScatterPill({ pts }: { pts: SamplePoint[] }) {
  return (
    <Plot
      data={[
        {
          x: pts.map((p) => p.x),
          y: pts.map((p) => p.y),
          type: "scatter" as const,
          mode: "markers" as const,
          marker: { size: 12, color: pts.map((p) => p.color), line: { width: 0.5, color: "rgba(255,255,255,0.15)" } },
          customdata: pts.map((p) => [p.player, p.pi.toFixed(1), p.position]),
          hovertemplate:
            "<b>%{customdata[0]}</b>  ·  %{customdata[2]}  ·  <span style='color:#14d1ff;font-weight:700'>%{customdata[1]}</span>" +
            "<extra></extra>",
        },
      ] as Plotly.Data[]}
      layout={{
        autosize: true,
        height: 320,
        margin: { l: 36, r: 12, t: 8, b: 36 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: "Inter", color: "#d2e2f2", size: 11 },
        xaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "xG (raw)" } },
        yaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "xA (raw)" } },
        hoverlabel: {
          bgcolor: "rgba(20,209,255,0.12)",
          bordercolor: "rgba(20,209,255,0.55)",
          font: { family: "Inter, sans-serif", color: "#e6f3ff", size: 11 },
          align: "left",
        },
        showlegend: false,
      }}
      config={PLOTLY_APP_CONFIG}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}

function BarPill({ rows }: { rows: SamplePoint[] }) {
  return (
    <Plot
      data={[
        {
          type: "bar" as const,
          orientation: "h" as const,
          y: rows.map((r) => r.player),
          x: rows.map((r) => r.pi),
          marker: { color: rows.map((r) => r.color) },
          customdata: rows.map((r) => [r.pi.toFixed(1), r.position]),
          hovertemplate:
            "<b>%{y}</b>  ·  %{customdata[1]}  ·  <span style='color:#14d1ff;font-weight:700'>%{customdata[0]}</span>" +
            "<extra></extra>",
        },
      ]}
      layout={{
        autosize: true,
        height: 320,
        margin: { l: 130, r: 12, t: 8, b: 36 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: "Inter", color: "#d2e2f2", size: 11 },
        xaxis: { gridcolor: "rgba(255,255,255,0.05)", fixedrange: true, title: { text: "Scout idx" } },
        yaxis: { fixedrange: true, automargin: true },
        hoverlabel: {
          bgcolor: "rgba(20,209,255,0.12)",
          bordercolor: "rgba(20,209,255,0.55)",
          font: { family: "Inter, sans-serif", color: "#e6f3ff", size: 11 },
          align: "left",
        },
        showlegend: false,
      }}
      config={PLOTLY_APP_CONFIG}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}

function Section({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-content">{title}</h2>
        <p className="text-xs text-content-muted">{desc}</p>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}

export default function HoverPreviewPage() {
  return (
    <main className="mx-auto max-w-6xl space-y-10 px-4 py-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-content">Hover Tooltip Variants</h1>
        <p className="text-sm text-content-muted">
          Hover any dot or bar to compare. Choose one and it gets wired into all charts.
        </p>
      </header>

      <Section
        title="A — Glass Card"
        desc="Native plotly hover, restyled. Multi-line: bold name, club·league, position·age, Scout idx accent. Brand cyan border."
      >
        <GlassCard><ScatterGlass pts={POINTS} /></GlassCard>
        <GlassCard><BarGlass rows={BAR_DATA} /></GlassCard>
      </Section>

      <Section
        title="B — Custom React Overlay"
        desc="Disables native hover. React-rendered floating card with player initials thumb, club crest, league color, position chip, age, Scout idx pill. Richest, brand-aligned."
      >
        <GlassCard><ScatterOverlay pts={POINTS} /></GlassCard>
        <GlassCard><BarOverlay rows={BAR_DATA} /></GlassCard>
      </Section>

      <Section
        title="C — Pill Tag"
        desc="Native hover, minimal one-liner: name · position · Scout idx. Translucent cyan pill, low chrome, fast read."
      >
        <GlassCard><ScatterPill pts={POINTS} /></GlassCard>
        <GlassCard><BarPill rows={BAR_DATA} /></GlassCard>
      </Section>
    </main>
  );
}
