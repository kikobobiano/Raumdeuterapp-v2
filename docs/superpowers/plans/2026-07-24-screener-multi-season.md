# Screener Multi-Season Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Screener returns one row per (player × season) across up to 8 selected seasons via `UNION ALL`.

**Architecture:** `ScreenerRequest.seasons` → resolve effective list → union season views with literal `season` → criteria/sort/limit. UI: page-local `MultiCombobox` replacing SeasonSelect on Screener.

**Tech Stack:** FastAPI, DuckDB, Next.js, MultiCombobox, OpenAPI → TS types.

**Spec:** `docs/superpowers/specs/2026-07-24-screener-multi-season-design.md`

---

### Task 1: Core helpers + schemas

**Files:**
- Create: `apps/api/app/core/screener_seasons.py`
- Modify: `apps/api/app/schemas.py` (`ScreenerRequest`, `ScreenerRow`)

- [x] `resolve_screener_seasons(seasons, fallback) -> list[int]`
- [x] `validate_screener_seasons(seasons, list_views)` → raise ValueError with season year
- [x] Add `seasons: list[int] = Field(default_factory=list, max_length=8)`
- [x] Add `season: int` to `ScreenerRow`

### Task 2: Non-composite screener path

**Files:**
- Modify: `apps/api/app/routers/screener.py`

- [x] Resolve + validate effective seasons
- [x] Intersect allowed metrics across seasons
- [x] Per-branch SELECT with age/logo/`season` literal + WHERE (`build_where(..., season=y)`) + criteria
- [x] Outer `ORDER BY` / `LIMIT` / `OFFSET` / `COUNT`
- [x] Populate `ScreenerRow.season`

### Task 3: Composite multi-season

**Files:**
- Modify: `apps/api/app/core/screener_composite.py`

- [x] `fetch_screener_candidates` accepts `seasons: list[int]`, unions branches, tags `season`
- [x] `score_candidates` groups by season and builds cohort/team-median per season

### Task 4: Tests + OpenAPI

**Files:**
- Modify: `apps/api/tests/test_endpoints.py`
- Create: `apps/api/tests/test_screener_seasons.py`
- Regen shared-types

- [x] Unit + smoke tests
- [x] OpenAPI / TS regen

### Task 5: Frontend

**Files:**
- Modify: `apps/web/src/app/scout/screener/page.tsx`

- [x] `selectedSeasons` state + MultiCombobox + `FilterPanel hideSeason`
- [x] POST `seasons`, query key, Season column, profile link, export filename
