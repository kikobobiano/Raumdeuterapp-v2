import { GlassCard } from "@/components/ui/glass-card";

type Metric = string;
type Category = {
  name: string;
  color: string;
  accent: string;
  metrics: Metric[];
  note?: string;
};

const CATEGORIES: Category[] = [
  {
    name: "Finishing",
    color: "border-orange-500/30",
    accent: "bg-orange-500/10 text-orange-300",
    metrics: [
      "Goals", "Goals per 90", "Non-penalty goals", "Non-penalty goals per 90",
      "xG", "xG per 90", "Head goals", "Head goals per 90",
      "Shots", "Shots per 90", "Shots on target %",
      "Goal conversion %", "Touches in box per 90",
      "xG per shot per 90", "Touches in box per shot per 90",
    ],
  },
  {
    name: "Assistance",
    color: "border-yellow-500/30",
    accent: "bg-yellow-500/10 text-yellow-300",
    metrics: [
      "Assists per 90", "xA per 90",
      "Second assists per 90", "Third assists per 90",
      "Shot assists per 90", "Key passes per 90",
      "Smart passes per 90", "Accurate smart passes %",
      "Through passes per 90", "Accurate through passes %",
      "Passes to penalty area per 90", "Accurate passes to penalty area %",
      "Deep completions per 90", "Deep completed crosses per 90",
    ],
  },
  {
    name: "Take Ons & Carries",
    color: "border-lime-500/30",
    accent: "bg-lime-500/10 text-lime-300",
    metrics: [
      "Dribbles per 90", "Successful dribbles %",
      "Offensive duels per 90", "Offensive duels won %",
      "Progressive runs per 90", "Accelerations per 90",
      "Fouls suffered per 90", "Received passes per 90",
      "Received long passes per 90",
    ],
  },
  {
    name: "Distribution",
    color: "border-cyan-500/30",
    accent: "bg-cyan-500/10 text-cyan-300",
    metrics: [
      "Passes per 90", "Accurate passes %",
      "Forward passes per 90", "Accurate forward passes %",
      "Back passes per 90", "Accurate back passes %",
      "Short/medium passes per 90", "Accurate short/medium passes %",
      "Long passes per 90", "Accurate long passes %",
      "Progressive passes per 90", "Accurate progressive passes %",
      "Vertical passes per 90", "Accurate vertical passes %",
      "Passes to final third per 90", "Accurate passes to final third %",
      "Crosses per 90", "Accurate crosses %",
      "Crosses from left flank per 90", "Accurate crosses from left flank %",
      "Crosses from right flank per 90", "Accurate crosses from right flank %",
      "Crosses to goalie box per 90",
      "Average pass length (m)", "Average long pass length (m)",
    ],
  },
  {
    name: "Ground Defense",
    color: "border-blue-500/30",
    accent: "bg-blue-500/10 text-blue-300",
    metrics: [
      "Successful defensive actions per 90",
      "Defensive duels per 90", "Defensive duels won %",
      "Sliding tackles per 90", "PAdj Sliding tackles",
      "Interceptions per 90", "PAdj Interceptions",
      "Shots blocked per 90", "Fouls per 90",
      "Yellow cards", "Yellow cards per 90", "Red cards", "Red cards per 90",
    ],
  },
  {
    name: "Aerial Play",
    color: "border-indigo-500/30",
    accent: "bg-indigo-500/10 text-indigo-300",
    metrics: ["Aerial duels per 90", "Aerial duels won %"],
  },
  {
    name: "Duels",
    color: "border-violet-500/30",
    accent: "bg-violet-500/10 text-violet-300",
    metrics: [
      "Duels per 90", "Duels won %", "Successful attacking actions per 90",
    ],
  },
  {
    name: "Goalkeeping",
    color: "border-purple-500/30",
    accent: "bg-purple-500/10 text-purple-300",
    metrics: [
      "Conceded goals", "Conceded goals per 90",
      "Shots against", "Shots against per 90",
      "Clean sheets", "Save rate %",
      "xG against", "xG against per 90",
      "Prevented goals", "Prevented goals per 90",
      "Back passes received as GK per 90", "Exits per 90",
    ],
  },
  {
    name: "Set Pieces",
    color: "border-pink-500/30",
    accent: "bg-pink-500/10 text-pink-300",
    metrics: [
      "Free kicks per 90", "Direct free kicks per 90", "Direct free kicks on target %",
      "Corners per 90", "Penalties taken", "Penalty conversion %",
    ],
  },
];

const DERIVED: Category[] = [
  {
    name: "Performance Indices",
    color: "border-teal-400/40",
    accent: "bg-teal-400/10 text-teal-300",
    metrics: [
      "Finishing Index", "Assistance Index", "Distribution Index",
      "Take Ons Index", "Ground Defense Index", "Aerial Play Index",
      "Performance Index",
    ],
    note: "Composite scores (0–100) aggregating weighted metrics per game area. The overall Performance Index combines all area indices, weighted by position role.",
  },
  {
    name: "Quality Scores",
    color: "border-teal-400/40",
    accent: "bg-teal-400/10 text-teal-300",
    metrics: [
      "Link-Up Play Quality", "Finishing Quality", "Dribbling Quality",
      "Distribution Quality", "Aerial Play Quality", "Ground Defense Quality",
      "Creativity Quality",
    ],
    note: "Relative quality scores comparing a player's output against positional peers in the same league. Highlights over- or under-performance versus expected output.",
  },
  {
    name: "Composite Outputs",
    color: "border-teal-400/40",
    accent: "bg-teal-400/10 text-teal-300",
    metrics: [
      "Expected Offensive Output per 90", "Offensive Output per 90",
      "Ball Progression per 90", "Ball Winning Actions per 90",
    ],
    note: "Aggregated action counts combining multiple raw metrics into single summaries for cross-position comparison.",
  },
];

const APP_CONCEPTS = [
  {
    term: "Performance Translation",
    definition:
      "Estimated performance band when a player moves between leagues of different calibre. Applies a league difficulty coefficient to project likely output in the target league.",
  },
  {
    term: "League Style Fit",
    definition:
      "Score measuring how closely a player's profile matches the average style of play in a given league, based on distribution and carry metrics.",
  },
  {
    term: "Per 90 vs Raw toggle",
    definition:
      "Per 90 normalises volume metrics by minutes played (value / minutes × 90). Raw shows cumulative totals. Percentage and rate metrics are unaffected.",
  },
  {
    term: "Wyscout ID",
    definition:
      "Unique identifier in the Wyscout data provider. Used for player image resolution and cross-referencing across seasons.",
  },
];

export const metadata = { title: "Glossary" };

function MetricChip({ label, accent }: { label: string; accent: string }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${accent}`}>
      {label}
    </span>
  );
}

function CategoryCard({ cat }: { cat: Category }) {
  return (
    <GlassCard className={`border ${cat.color} space-y-3`}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-content">{cat.name}</h3>
        <span className="text-xs text-content-muted">{cat.metrics.length} metrics</span>
      </div>
      {cat.note && <p className="text-xs text-content-muted leading-relaxed">{cat.note}</p>}
      <div className="flex flex-wrap gap-1.5">
        {cat.metrics.map((m) => (
          <MetricChip key={m} label={m} accent={cat.accent} />
        ))}
      </div>
    </GlassCard>
  );
}

export default function GlossaryPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10 space-y-10">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-content">Glossary</h1>
        <p className="text-sm text-content-muted">
          Metrics and concepts used across Raumdeuter. Raw data sourced from Wyscout; derived metrics are custom-built.
        </p>
      </div>

      {/* Raw metrics by game area */}
      <section className="space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-content-muted">
          Raw Metrics — by Game Area
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CATEGORIES.map((cat) => (
            <CategoryCard key={cat.name} cat={cat} />
          ))}
        </div>
      </section>

      {/* Derived metrics */}
      <section className="space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-content-muted">
          Derived Metrics
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DERIVED.map((cat) => (
            <CategoryCard key={cat.name} cat={cat} />
          ))}
        </div>
      </section>

      {/* App concepts */}
      <section className="space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-content-muted">
          App Concepts
        </h2>
        <GlassCard className="divide-y divide-outline-variant/20">
          {APP_CONCEPTS.map(({ term, definition }) => (
            <div key={term} className="px-6 py-4 flex flex-col gap-1 sm:flex-row sm:gap-6">
              <dt className="w-full shrink-0 text-sm font-semibold text-content sm:w-56">{term}</dt>
              <dd className="text-sm text-content-muted leading-relaxed">{definition}</dd>
            </div>
          ))}
        </GlassCard>
      </section>
    </main>
  );
}
