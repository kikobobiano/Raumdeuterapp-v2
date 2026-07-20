# Screener Composite Scores — Design

*Date: 2026-07-20*

## 1. Problem

The Screener today only supports **AND filters** (`metric {op} value`) plus a
single-metric sort. Users want to build **custom weighted indexes** that combine
several metrics into one score, e.g.:

- 50% Aerial duels won per 90
- 25% Successful dribbles % — *vs team median*
- 25% Long passes received rate — *vs team median*

…then rank players by that composite. This requires (a) a weighted-composite
scoring layer and (b) a new "vs team median" runtime comparison that does not
exist today.

## 2. Decisions (locked)

| Decision | Choice |
|---|---|
| Normalization | **Z-score** within a cohort |
| Cohort | **Same position group + same league** (`position_league`, with existing fallback cascade) |
| "vs team median" | **Ratio**: `player_value ÷ team_median` (1.0 = median teammate) |
| Team-median population | **Whole team, outfield only** (GK excluded), teammates with `Minutes played ≥ 300` |
| Persistence | **Session-only** (React `useState`); no localStorage, no server storage |
| Scope | **Additive**: composite is an extra sortable column; existing metric filters still apply |
| Per-component breakdown | **No** for MVP — a single composite number per row |
| Weights | Relative; normalized by `Σ|weight|`, so 50/25/25 ≡ 2/1/1 |

## 3. Scoring math

For each player and each component:

1. **Component value**
   - basis `value` → `metric_sql_expr(metric, mode)` (respects raw/p90/as_is).
   - basis `team_median` → `player_value ÷ team_median(metric)`, where
     `team_median` is the median of that metric expression over the player's
     club (GK excluded, `Minutes played ≥ 300`). If the team median is null or
     ≤ 0, the ratio is null for that player.
2. **Z-score** the component value within the cohort (position + league) using
   `shrunk_zscore` (Bayesian shrinkage toward cohort mean for low-minute
   players). Clamped to ±6, consistent with existing behaviour.
   - For basis `value`: cohort mean/sd via existing `cohort_stats`.
   - For basis `team_median`: cohort mean/sd is computed over the **ratio**
     values across the cohort (new helper), because the quantity being z-scored
     is the ratio, not the raw metric.
3. **Composite** = `Σ(weight_i · z_i) / Σ|weight_i|`. Components with a null z
   are skipped (their weight drops out of the denominator for that player),
   matching `scouting_standouts._score_row`. If every component is null, the
   composite is null.

Result is in z units (~ −3…+3). Higher = better.

## 4. Architecture

Reuses the existing composite/cohort machinery (`core/scouting_cohort.py`:
`cohort_stats`, `cohort_where_for_player_set`, `shrunk_zscore`) already powering
`/scouting/discover` and `/scouting/standouts`. The only genuinely new logic is
the team-median ratio basis.

```
routers/screener.py ── (composite present?) ──► core/screener_composite.py
        │  no                                          │
        ▼                                              ├─ team_medians (GROUP BY club)
   existing fast SQL path                              ├─ cohort baselines (value + ratio)
   (unchanged)                                         └─ per-candidate composite
```

### 4.1 Backend

**`schemas.py`**
```python
CompositeBasisLiteral = Literal["value", "team_median"]

class CompositeComponent(BaseModel):
    metric: str
    mode: MetricModeLiteral = "as_is"
    basis: CompositeBasisLiteral = "value"
    weight: float = 1.0

# ScreenerRequest gains:
    composite: list[CompositeComponent] = Field(default_factory=list, max_length=8)
    sort_by_composite: bool = False

# ScreenerRow gains:
    composite: float | None = None
```

**New `core/screener_composite.py`** (no FastAPI imports):
- `team_medians(conn, view, metric, mode) -> dict[str, float]` — one
  `SELECT club, median(expr) ... WHERE <outfield, minutes>=300> GROUP BY club`.
- `compute_composite(conn, *, filters, components, candidates) -> dict[int, float | None]`
  keyed by candidate row index (or wyscout_id). Builds cohort baselines
  (reusing `cohort_stats` for `value` components; a ratio-baseline pass for
  `team_median` components), then scores each candidate.

**`routers/screener.py`**
- Validate composite metric names against `selectable_metric_names` (same as
  criteria today).
- If `composite` is non-empty: apply `build_where` + criteria filters, fetch the
  filtered candidate pool (**capped at 5000 rows**, projecting only the columns
  needed), compute composite via the core module, sort by composite when
  `sort_by_composite` (else by the existing `sort_by` metric), then slice
  `offset:offset+limit`. `total` = number of candidates with a non-null
  composite (or total candidates — see open item resolved in §6).
- If `composite` is empty: **current SQL path is untouched.**

Router stays ≤ 200 lines by pushing scoring into `core/`.

### 4.2 Frontend (`apps/web/src/app/scout/screener/page.tsx`)

- New collapsible **"Composite index"** section in the sidebar:
  - enable toggle,
  - up to 6 component rows: metric combobox (reuse the page's existing combobox +
    `metricOpts`), a basis toggle `Season value / vs Team median`, a numeric
    weight,
  - a "sort by score" toggle (defaults on when composite enabled).
- When enabled, a **Score** column is appended to the results table (right side),
  formatted to 2 dp, and rows sort by it by default.
- State is `useState`, added to the `["screener", …]` React Query key so results
  refetch when the composite changes. No persistence.

### 4.3 Types

Regenerate OpenAPI → TS (`packages/shared-types`) after the schema change, per
AGENTS.md §5.4. No `as any`.

## 5. Testing

- **Backend smoke** (`tests/test_endpoints.py`): a `/screener` POST with one
  `value` component and one `team_median` component returns 200 with a populated
  `composite` on rows and correct ordering when `sort_by_composite=true`.
- **Unit** (`tests/test_screener_composite.py`): tiny synthetic pool exercising
  (a) team-median ratio, (b) weighted-z combination, (c) null-component
  skipping.
- **Typecheck**: `pnpm exec tsc --noEmit` clean. **Lint**: ruff clean.

## 6. Edge cases & resolutions

- **Team of one qualifying player** → team median = that player's value → ratio
  = 1.0 (z ≈ cohort-relative). Acceptable.
- **Null / zero team median** → ratio null → component skipped for that player.
- **Cohort too small** → existing `cohort_stats` fallback cascade
  (`position_league → position_tier → position_global`) applies.
- **Pagination `total`** → count of candidates in the filtered pool (not just
  non-null composite), so paging is stable; rows with null composite sort last
  (NULLS LAST semantics) and are still viewable.
- **Performance** → candidate pool capped at 5000; team-median and cohort
  queries are one pass per metric. Composite path only runs when a composite is
  defined, so the default Screener stays on the fast SQL path.

## 7. Out of scope (YAGNI)

- Saving/naming indexes (persistence) — session-only for now.
- Per-component z-score breakdown / tooltip.
- Filtering *on* the composite (e.g. `composite ≥ 70`) — sort only for MVP.
- Reconciling with `/scouting/discover` (kept separate; this lives in Screener).
