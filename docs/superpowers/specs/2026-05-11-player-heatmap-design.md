# Player heatmap — design

**Status:** Draft (2026-05-11)
**Scope:** Add Wyscout `playerHeatmap` to the data pipeline, expose via API, render as a base layer on the Profile position pitch (zones stay on top). Current season only.

## Problem

Profile detail shows position zones on a small pitch SVG, but no spatial signal of where the player actually plays. Wyscout exposes a `playerHeatmap` GraphQL query that returns per-cell touch counts for the current season. We want this data ingested, cached, and rendered under the existing zone circles.

## Current behaviour (reference)

- `scripts/download_data.py` walks `ALLOWED_LEAGUE_WYSCOUT_IDS`, fetches per-league season search results from `https://searchapi.wyscout.com/api/v1/search/results.json`, writes one CSV per league/season under `data/players/wyscout/`. Notebook `scripts/data_gathering_and_cleaning.ipynb` consolidates these into per-season parquets under `data/players/all/{year}_all_leagues.parquet`.
- API exposes `GET /players/{wyscout_id}/profile` (radar, percentiles, traits) and `GET /players/{wyscout_id}/performance-index-history`. No spatial endpoint.
- `components/domain/player-position-pitch.tsx` renders a 100×100 SVG pitch with primary + secondary position zones as inscribed circles. No heatmap layer.

## Goals

- One-time-per-season Wyscout heatmap fetch with safe re-runs (skip already-cached pairs).
- Server-side cache on parquet, read through DuckDB pool like other season views.
- Single new lazy endpoint, no impact on existing `/profile` latency.
- Heatmap rendered as a soft glow base layer in the existing pitch SVG, zones unchanged on top.
- Module direction respected: `routers/` → `core/`, `core/` has no FastAPI imports, schemas in `schemas.py`.

## Non-goals

- Historical season heatmaps (Wyscout only exposes current).
- Per-competition picker in the UI when a player has two leagues (use the profile's resolved `Competition`).
- Heatmap on Compare panel.
- Match-level heatmaps.

---

## Approach

### 1. Data gathering — `scripts/download_heatmaps.py`

New script, separate from `download_data.py` to keep responsibilities narrow.

**Inputs / config (top of file):**

```python
CURRENT_SEASON_YEAR = 2025   # update manually on season roll
GRAPHQL_URL = "https://searchapi.wyscout.com/graphql"
MAX_WORKERS = 5
REQUEST_TIMEOUT_SEC = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 6
```

Auth: same `WYSCOUT_SEARCH_TOKEN`, `WYSCOUT_GROUP_ID`, `WYSCOUT_SUBGROUP_ID` env vars as `download_data.py`, passed as query string on the GraphQL URL (matches the existing API surface — no new env vars).

**Flow:**

1. Resolve source parquet: `data/players/all/{CURRENT_SEASON_YEAR}_all_leagues.parquet`. Fail fast if missing.
2. Project `["Wyscout id", "Competition"]` (drop duplicates on the pair).
3. Map `Competition` → `competition_id` via `ALLOWED_LEAGUE_WYSCOUT_IDS` imported from `download_data` (single source of truth). Unknown competitions → log warning, skip.
4. Resolve output parquet `data/players/heatmaps/heatmaps_{CURRENT_SEASON_YEAR}.parquet`. If it exists, read it, build the set of already-cached `(wyscout_id, competition_id)` pairs. Diff against the work list → todo.
5. `concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)`. Per task:
   - POST JSON body to `GRAPHQL_URL?token=…&groupId=…&subgroupId=…` with the operationName `Player` and variables `{playerId, timeframeYouthMode:false, timeframeCompetitionId}` and the heatmap-only query string (verbatim from the user's curl).
   - On HTTP 429 / 5xx → retry up to `MAX_RETRIES` with `RETRY_BACKOFF_SEC` linear backoff.
   - On success: parse `data.playerHeatmap.points` (list of `{x, y, count}`, drop `__typename`). If `playerHeatmap` is `null` → `points = []` (still write a row so we don't re-fetch every time).
6. Successful rows are appended to a thread-safe list. Every 500 successes (and once at the end), flush: read the existing parquet (if any), concat the new rows, write a temp file, atomic rename to the final path. PyArrow used directly (avoids pandas list-of-struct round-trip pain).
7. Failures: log to stderr, do not write a row. Next run picks them up.

**Output parquet schema (PyArrow):**

```
wyscout_id      int64        # negatives allowed (existing Wyscout quirk)
competition_id  int32
competition     string       # league display name (same as players parquet)
season_year     int32        # == CURRENT_SEASON_YEAR
points          list<struct<x: float, y: float, count: int>>
n_points        int32        # convenience for COUNT-style queries
fetched_at      timestamp    # UTC, when the row was written
```

Primary key by convention: `(wyscout_id, competition_id, season_year)`.

**Operational notes:**

- 5 workers, no per-task sleep. ~18k requests expected; should land 5–15 min.
- If 429s appear in practice, fall back to a `threading.Semaphore` + exponential backoff. Start optimistic, watch first run.
- Output dir created if missing.

### 2. Backend — schema, core, router

**`apps/api/app/schemas.py`** (additions):

```python
class HeatmapPoint(BaseModel):
    x: float
    y: float
    count: int

class HeatmapResponse(BaseModel):
    wyscout_id: int
    competition_id: int
    competition: str
    season: int
    points: list[HeatmapPoint]
    n_points: int
    max_count: int
```

**`apps/api/app/core/duckdb_pool.py`** (register):

For each `data/players/heatmaps/heatmaps_*.parquet`:

```python
year = int(path.stem.split("_")[1])
conn.execute(
    f"CREATE OR REPLACE VIEW heatmaps_{year} AS SELECT * FROM read_parquet(?)",
    [str(path)],
)
```

Missing directory → skip silently (dev / CI without data still boots).

**`apps/api/app/core/player_heatmap.py`** (new, no FastAPI imports):

- `def fetch_heatmap(conn, wyscout_id: int, season: int, competition_id: int | None) -> HeatmapData | None`
- Validate view exists via `list_views(conn)` → return `None` on missing.
- Query: `SELECT wyscout_id, competition_id, competition, points FROM "heatmaps_{season}" WHERE wyscout_id = ? [AND competition_id = ?] LIMIT 1`.
- Unpack `points` (DuckDB returns list of tuples) into `[{x, y, count}, …]`.
- Return a dataclass / TypedDict consumed by the router.

**`apps/api/app/routers/heatmap.py`** (new, thin, ≤80 lines):

```
GET /players/{wyscout_id}/heatmap?season=YYYY&competition_id=N
  200 → HeatmapResponse
  404 → no row
```

`competition_id` optional; if omitted and the player has multiple rows, returns the first match (deterministic by `competition_id ASC`). Profile page will pass the explicit id it already knows.

Wire in `apps/api/app/main.py` via `app.include_router(heatmap.router)`.

**Test:** `apps/api/tests/test_endpoints.py` — smoke test calling `/players/{id}/heatmap?season=2025` for a known id present in the parquet, assert `200` + non-empty points. Skip cleanly if parquet absent (CI without data).

**OpenAPI + TS types:** regen per `AGENTS.md §5.4`.

### 3. Frontend — render heatmap base layer

**Extend** `apps/web/src/components/domain/player-position-pitch.tsx` (do not fork — adds an optional `heatmap` prop, default `null`, preserves zones-only behaviour for non-current seasons).

```ts
interface HeatmapInput {
  points: { x: number; y: number; count: number }[];
  maxCount: number;
}

interface Props {
  primaryTokens: string[];
  secondaryTokens?: string[];
  heatmap?: HeatmapInput | null;
  className?: string;
}
```

**Coordinate mapping** (Wyscout `x ∈ [0,100]` is pitch length own → opponent, `y ∈ [0,100]` is width; existing SVG viewBox is `0 0 100 100` with attacking direction up i.e. `y=2` is opponent goal, `y=98` is own goal):

```ts
const svgX = wy.y;            // width → x
const svgY = 100 - wy.x;       // length flipped → y
```

Verify orientation on first render with a known CF (cluster should be top half). Flip the mapping if mirrored.

**SVG render order** inside the same `<svg>`:

1. Pitch rect + sheen *(unchanged)*
2. Pitch lines *(unchanged)*
3. `<g class="heatmap" style="mix-blend-mode: screen">` *(NEW base layer)*
   - `<defs>` radial gradient: center `var(--color-primary)` (#14d1ff) at α≈0.55 → fade to transparent at 100%.
   - Optional `<filter><feGaussianBlur stdDeviation="0.6"/></filter>` on the group for soft blobs.
   - One `<circle>` per point: `cx, cy` from mapping above; `r = R_BASE + R_SCALE * sqrt(count/maxCount)` (e.g. `R_BASE=0.5`, `R_SCALE=2.3`); `opacity = 0.25 + 0.6 * (count/maxCount)`.
4. Secondary zone circles *(unchanged)*
5. Primary zone circles *(unchanged)*

Caption beneath the SVG, only when `heatmap` is non-null:
`Heatmap · {points.length} zones · {season label}`.

Falls back to existing zones-only behaviour when `heatmap == null` (older seasons, missing data, fetch error).

**Data fetching** (Profile detail client — `apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx`, the only consumer of `PlayerPositionPitch`):

```ts
const { data: heatmap } = useQuery({
  queryKey: ["heatmap", wyscoutId, season, competitionId],
  queryFn: async () => {
    const { data, error } = await api.GET("/players/{wyscout_id}/heatmap", {
      params: {
        path: { wyscout_id: wyscoutId },
        query: { season, competition_id: competitionId },
      },
    });
    if (error) throw error;
    return data;
  },
  enabled: !!wyscoutId && !!season,
  staleTime: 1000 * 60 * 60,            // 1h
});

const heatmapProp = heatmap
  ? { points: heatmap.points, maxCount: heatmap.max_count }
  : null;
```

404 → `data === undefined` → component receives `heatmap={null}` → zones-only. No error toast.

---

## Risks / trade-offs

| Item | Risk | Mitigation |
|------|------|-------------|
| Coord orientation guess | Heatmap mirrored / rotated vs zones | Verify on first render with a known position (CF top half, GK around y=98). Flip mapping if needed. |
| Rate limits on GraphQL | Wyscout 429s mid-run | Start at 5 workers + no sleep; on 429 add exponential backoff + semaphore. MAX_RETRIES=3 already handles transient. |
| Player in two competitions | Wrong league's heatmap shown if `competition_id` omitted | Profile already knows the player's `Competition`; pass `competition_id` from the profile payload explicitly. Endpoint deterministic fallback (`ORDER BY competition_id ASC`). |
| Season rolls over | Old parquet stops being current | `CURRENT_SEASON_YEAR` constant is explicit + documented; new season just bumps the constant and reruns. Both season parquets coexist; DuckDB pool registers all. |
| Empty points | Player with no minutes in current season | Write empty row (`points=[]`) so we don't re-fetch. Endpoint returns `200` with `points=[]`; frontend shows zones-only path. |
| Negative `Wyscout id` | Existing Wyscout quirk for some leagues | Stored as `int64`, no special handling. |

---

## Verification

- **Manual:**
  - Run script on a single league first (e.g. Primeira Liga): inspect parquet via DuckDB, confirm row count and `points` structure.
  - Open a Profile in the browser, confirm heatmap renders under the zone circles, blends correctly, and falls back when the parquet is removed.
  - Switch season filter to a non-current year, confirm heatmap disappears cleanly.
- **Automated:**
  - `pytest -q` — new smoke test for `/players/{id}/heatmap`.
  - `pnpm exec tsc --noEmit` clean after types regen.
  - No new lint errors in script (`ruff`) or web (`eslint`).

---

## Implementation note

Implementation plan produced separately via the writing-plans workflow. This document is specification only.
