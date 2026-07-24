/** Saved composite index ids, import/export helpers (no React). */

export type CompositeBasis = "value" | "team_median";

export type MetricMode = "raw" | "p90" | "as_is";

export interface CompositeComponentRecipe {
  metric: string;
  mode: MetricMode;
  basis: CompositeBasis;
  weight: number;
}

export interface SavedCompositeIndex {
  id: string;
  name: string;
  components: CompositeComponentRecipe[];
  updatedAt: number;
}

export const COMPOSITE_METRIC_PREFIX = "ci:";
export const COMPOSITE_INDEXES_EXPORT_VERSION = 1;

export function compositeMetricId(id: string): string {
  return `${COMPOSITE_METRIC_PREFIX}${id}`;
}

export function isCompositeMetricId(name: string): boolean {
  return name.startsWith(COMPOSITE_METRIC_PREFIX) && name.length > COMPOSITE_METRIC_PREFIX.length;
}

export function parseCompositeMetricId(name: string): string | null {
  if (!isCompositeMetricId(name)) return null;
  return name.slice(COMPOSITE_METRIC_PREFIX.length);
}

function isMode(v: unknown): v is MetricMode {
  return v === "raw" || v === "p90" || v === "as_is";
}

function isBasis(v: unknown): v is CompositeBasis {
  return v === "value" || v === "team_median";
}

function parseComponent(raw: unknown): CompositeComponentRecipe | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.metric !== "string" || !o.metric) return null;
  if (!isMode(o.mode)) return null;
  if (!isBasis(o.basis)) return null;
  const weight = typeof o.weight === "number" ? o.weight : Number(o.weight);
  if (!Number.isFinite(weight)) return null;
  return { metric: o.metric, mode: o.mode, basis: o.basis, weight };
}

function parseIndex(raw: unknown): SavedCompositeIndex | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.id !== "string" || !o.id) return null;
  if (typeof o.name !== "string" || !o.name.trim()) return null;
  if (!Array.isArray(o.components) || o.components.length === 0 || o.components.length > 8) {
    return null;
  }
  const components: CompositeComponentRecipe[] = [];
  for (const c of o.components) {
    const parsed = parseComponent(c);
    if (!parsed) return null;
    components.push(parsed);
  }
  const updatedAt =
    typeof o.updatedAt === "number" && Number.isFinite(o.updatedAt)
      ? o.updatedAt
      : Date.now();
  return { id: o.id, name: o.name.trim(), components, updatedAt };
}

export function parseImportIndexesJson(text: string): SavedCompositeIndex[] {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("Invalid JSON");
  }
  if (!data || typeof data !== "object") throw new Error("Invalid export shape");
  const root = data as Record<string, unknown>;
  if (root.version !== COMPOSITE_INDEXES_EXPORT_VERSION) {
    throw new Error("Unsupported export version");
  }
  if (!Array.isArray(root.indexes)) throw new Error("Missing indexes array");
  const out: SavedCompositeIndex[] = [];
  for (const item of root.indexes) {
    const parsed = parseIndex(item);
    if (parsed) out.push(parsed);
  }
  return out;
}

export function exportIndexesPayload(indexes: SavedCompositeIndex[]): string {
  return JSON.stringify(
    { version: COMPOSITE_INDEXES_EXPORT_VERSION, indexes },
    null,
    2,
  );
}

export function mergeImportedIndexes(
  existing: SavedCompositeIndex[],
  imported: SavedCompositeIndex[],
): SavedCompositeIndex[] {
  const byId = new Map(existing.map((x) => [x.id, x]));
  for (const item of imported) {
    byId.set(item.id, item);
  }
  return [...byId.values()].sort((a, b) => b.updatedAt - a.updatedAt);
}

export function newCompositeIndexId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `ci-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
