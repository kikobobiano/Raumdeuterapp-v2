# Screener Multi-Season — Design

*Date: 2026-07-24*

## 1. Problem

The Screener is single-season only (`PlayerFilters.season` → view
`players_{YYYY}`). Scouts often want the same criteria applied across several
seasons and to see **each (player × season) hit as its own row** — e.g. who
cleared xG ≥ 0.3 in any of the last few seasons, with season visible on the
row.

## 2. Decisions (locked)

| Decision | Choice |
|---|---|
| Row grain | **One row per (player × season)** — not aggregated |
| Season picker UX | **`MultiCombobox`** (same pattern as Clubs in `FilterPanel`) |
| Empty selection | **None = current global season** (`filters.season` / store) |
| Control placement | **Screener-only**: replace page `SeasonSelect` with multi; `hideSeason` on `FilterPanel` |
| State | **Page-local** `selectedSeasons: number[]`; not Zustand |
| Backend strategy | **`UNION ALL`** of `players_{y}` with literal `y AS season` |
| Cap | **Max 8** seasons (same ceiling as Replacement `candidate_seasons`) |
| Season column in table | **Always** show (label `YY-(YY+1)`) |
| Profile navigation | Link uses **`?season=` from the row** |
| Metrics / clubs catalog | Still anchored on **global** `f.season` for this slice |
| Composite scores | Still scored **per row / per season** (no cross-season aggregate) |

## 3. Product behaviour

1. User opens Screener. Season multi is empty → API behaves like today (one
   season = global store season).
2. User picks 2–8 seasons in the multi-select → table returns matching rows
   across those views; same player may appear multiple times.
3. Clicking a player opens profile for that row’s season.
4. Clearing the multi-select returns to single-season fallback.

Hint copy (near control):  
`Multi-select. None = current season (global).`

## 4. Architecture

```
UI (screener page)
  selectedSeasons[] ──► POST /screener { filters, seasons, criteria, … }
                              │
                              ▼
                     resolve effective seasons
                     (seasons or [filters.season])
                              │
                              ▼
                     UNION ALL players_{y} + y AS season
                              │
                    criteria / sort / LIMIT / OFFSET
                              │
                              ▼
                     ScreenerRow (+ season: int)
```

### 4.1 Backend

**`schemas.py`**

```python
class ScreenerRequest(BaseModel):
    filters: PlayerFilters
    seasons: list[int] = Field(default_factory=list, max_length=8)
    # … existing fields unchanged …

class ScreenerRow(BaseModel):
    season: int
    # … existing fields …
```

**Resolution**

```text
effective = request.seasons if request.seasons else [request.filters.season]
```

Validate each `view_name(y)` ∈ `list_views()`; else HTTP 404.

**SQL shape (non-composite path)**

Build a derived source:

```sql
SELECT …, 2024 AS season FROM players_2024
UNION ALL
SELECT …, 2025 AS season FROM players_2025
-- …
```

- Project only needed columns (no `SELECT *`).
- Age expression and club-logo SQL use **that branch’s season**.
- Apply `build_where` + criterion predicates on the union (params shared where
  filter fragments are season-agnostic; age filter parts must be applied
  **per branch** when age depends on season, matching Replacement’s pattern).
- `ORDER BY` / `LIMIT` / `OFFSET` / `COUNT(*)` over the union result.
- Keep existing LIMIT caps (`le=2000`).

**Composite path**

Extend `screener_composite.fetch_screener_candidates` to accept multiple
seasons: candidates tagged with `season`, cohort / team-median baselines
computed **within each season**, then score + sort + paginate in memory as
today. Candidate cap `MAX_CANDIDATES` applies to the **combined** pool
(multi-season can hit the cap sooner than single-season).

**Backward compatibility**

Omitting `seasons` or sending `[]` preserves current single-season behaviour.

### 4.2 Frontend

**`apps/web/src/app/scout/screener/page.tsx`**

- `const [selectedSeasons, setSelectedSeasons] = useState<number[]>([])`.
- `<FilterPanel hideSeason />`.
- Season block: `MultiCombobox` over `/meta/seasons`, Clear when non-empty.
- POST body: `seasons: selectedSeasons`.
- Query key includes `selectedSeasons` and `f.season`.
- Table: Season column; row click →
  `/scout/profile/${id}?season=${row.season}`.
- Export filename: single → `screener-{YY}-{YY+1}`; multi →
  `screener-{minYY}-{maxYY+1}` (min/max of selected seasons).

Do **not** change global `SeasonSelect` / Zustand `season` to a list.

### 4.3 OpenAPI / types

After schema change: regen `packages/shared-types` per `AGENTS.md` §5.4.

## 5. Errors

| Case | Response |
|---|---|
| Season not loaded | 404 `"season {y} not loaded"` |
| `seasons` length > 8 | 422 (Pydantic) |
| Unknown metric | 400 (existing) |
| Internal SQL failure | 500 generic (no SQL leak) |

## 6. Testing

- Smoke: `seasons: []` → 200, rows lack surprises vs current season.
- Smoke: two loaded seasons → 200, every row has `season` in the requested set;
  `total` ≥ page length.
- Optional unit: effective-season resolution helper.

Skip gracefully when `/meta/seasons` is empty (CI without data).

## 7. Out of scope

- Multi-season Scatter / Rankings / Bar / other pages
- Cross-season metric aggregation (avg / sum / “must pass every season”)
- Making `PlayerFilters.season` or the global store a list
- Injecting a `season` column into the DuckDB `players_all` view
- Per-selected-season metrics catalog intersection

## 8. Implementation notes

- Prefer a small helper in `core/` (e.g. `resolve_screener_seasons`,
  `screener_union_sql`) so the router stays thin.
- Whitelist seasons against `list_views()` only — never interpolate untrusted
  view names beyond `players_{int}` after validation.
- When pruning invalid seasons on the client is needed, drop values not in
  `/meta/seasons` (same idea as club option pruning).
