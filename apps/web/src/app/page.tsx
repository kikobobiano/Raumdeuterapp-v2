import { ArrowUpRight, TrendingUp, Users, Trophy, Activity } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
} from "@/components/ui/glass-card";

const KPIS = [
  { label: "Players Tracked", value: "12,847", trend: "+8.2%", icon: Users },
  { label: "Active Leagues", value: "5", trend: "Top 5 EU", icon: Trophy },
  { label: "Seasons Indexed", value: "12", trend: "2015 → 2026", icon: Activity },
  { label: "Elite Performers", value: "324", trend: "+12% YoY", icon: TrendingUp },
];

const QUICK_TOOLS = [
  {
    title: "Performance rankings",
    desc: "Leaderboard, top index, player cards.",
    href: "/scout/rankings",
  },
  {
    title: "Scatter Analysis",
    desc: "Compare metrics across populations.",
    href: "/scout/scatter",
  },
  {
    title: "Screener",
    desc: "Filter the universe by criteria.",
    href: "/scout/screener",
  },
  {
    title: "Best XI",
    desc: "Build optimal lineup from filters.",
    href: "/teams/best-xi",
  },
];

export default function Dashboard() {
  return (
    <div className="mx-auto max-w-[1440px] space-y-8">
      <header className="flex items-end justify-between">
        <div>
          <p className="label-caps mb-2">Overview</p>
          <h1 className="text-4xl font-bold tracking-tight text-on-surface">
            RaumdeuterApp
          </h1>
          <p className="mt-2 text-on-surface-variant">
            Premium scouting intelligence across Europe&apos;s top 5 leagues.
          </p>
        </div>
        <Badge variant="primary">Season 25-26 — Live</Badge>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {KPIS.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <GlassCard key={kpi.label}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="label-caps">{kpi.label}</p>
                  <p className="mt-3 text-3xl font-bold text-on-surface tracking-tight">
                    {kpi.value}
                  </p>
                  <p className="mt-2 data-mono text-primary">{kpi.trend}</p>
                </div>
                <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" strokeWidth={1.5} />
                </div>
              </div>
            </GlassCard>
          );
        })}
      </section>

      <section>
        <h2 className="text-xl font-semibold text-on-surface mb-4">Quick Tools</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {QUICK_TOOLS.map((tool) => (
            <GlassCard key={tool.href} className="group cursor-pointer hover:glow-primary">
              <GlassCardHeader>
                <GlassCardTitle>{tool.title}</GlassCardTitle>
                <ArrowUpRight className="h-4 w-4 text-on-surface-variant group-hover:text-primary transition-colors" />
              </GlassCardHeader>
              <p className="text-sm text-on-surface-variant">{tool.desc}</p>
            </GlassCard>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <GlassCard className="lg:col-span-2">
          <GlassCardHeader>
            <GlassCardTitle>Recent Activity</GlassCardTitle>
            <Button variant="ghost" size="sm">
              View all
            </Button>
          </GlassCardHeader>
          <ul className="space-y-3 text-sm">
            {[
              "F. Wirtz scouted — Leverkusen",
              "M. Ødegaard report saved",
              "Best XI generated for U23 attacking mids",
            ].map((line) => (
              <li
                key={line}
                className="flex items-center justify-between rounded-md bg-surface-low/60 px-3 py-2 text-on-surface-variant"
              >
                <span>{line}</span>
                <span className="data-mono text-on-surface-variant/70">2h ago</span>
              </li>
            ))}
          </ul>
        </GlassCard>

        <GlassCard>
          <GlassCardHeader>
            <GlassCardTitle>Backend Status</GlassCardTitle>
            <Badge variant="primary">Online</Badge>
          </GlassCardHeader>
          <div className="space-y-2 text-sm text-on-surface-variant">
            <div className="flex justify-between">
              <span>API</span>
              <span className="data-mono text-primary">/health 200</span>
            </div>
            <div className="flex justify-between">
              <span>DuckDB views</span>
              <span className="data-mono text-on-surface">12 seasons</span>
            </div>
            <div className="flex justify-between">
              <span>Latency p95</span>
              <span className="data-mono text-on-surface">— ms</span>
            </div>
          </div>
        </GlassCard>
      </section>
    </div>
  );
}
