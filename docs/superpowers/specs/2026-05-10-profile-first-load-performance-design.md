# Profile first load — performance design

**Status:** Approved (2026-05-10)  
**Scope:** `/scout/profile/[wyscoutId]` first visit — perceived latency for both above-fold content and full page settling (including “Similar Big 5”).

## Problem

Opening a player profile triggers multiple API calls and server work; first paint can feel slow, and total time until all visible regions are steady (including similarity column) compounds the effect.

## Current behaviour (reference)

Rough network order after client mount:

1. `GET /meta/seasons` — profile-heavy requests stay `enabled: false` until season list includes the resolved season.
2. In parallel once valid:  
   - `GET /players/{id}/profile` — many cohort percentile lookups server-side.  
   - `GET /players/{id}/performance-index-history` (mini PI chart in header).
3. Immediately when profile data renders — “Similar Big 5” fires:  
   - `GET /meta/leagues?season=…`  
   - Then `POST /replacement` — expensive vector similarity workload.

Panels that start collapsed (`Progression`, `Replacement`, `Translation`) correctly gate on `open`; Compare only fetches when slots exist.

## Goals

- **Above-fold:** reduce time until header + KPIs + radar/block content is reliably rendered (fewer waterfalls; less contention on the browser connection and DuckDB/sklearn simultaneously).
- **Full page:** reduce time until “Similar Big 5” resolves or cleanly finishes loading — without regressing correctness of filters Big 5 + role-derived pool.
- Maintain existing security boundaries (whitelist metrics, parameterized SQL), response shapes unless an explicit aggregation endpoint is added later.

## Non-goals

- Changing product placement of Similar Big 5 in the grid.
- Auth, CDN for Wyscout imagery, or general Next.js routing refactors unrelated to profile data fetch.

---

## Approach (phased)

### Phase A — Client (low risk)

- **Seasons catalogue:** minimise blocking before first useful fetch — reuse long-lived TanStack Query cache for `["seasons"]` consistent with catalog guidance (`staleTime` where appropriate); consider prefetch from shell/layout if cold navigation still staggers (`enabled` dependency on `(list ?? []).includes(season)` amplifies waterfalls).
- **Similar Big 5:** defer `/meta/leagues` + `POST /replacement` so they do not compete with `/profile` and PI history during the earliest critical slice — strategies to combine or choose among: viewport (`IntersectionObserver`), `requestIdleCallback` (fallback timeout), or `enabled: profileQ.isSuccess && !profileQ.isFetching` plus a micro-delay / idle deferral explicitly documented in implementation.
- UX: skeletons already present for Similar loading; preserve error copy on failure — must not block rest of profile.

### Phase B — Server profile efficiency (medium risk)

- **Batch or consolidate percentile cohort queries** in `apps/api` profile path — replace repeated small `SUM(CASE WHEN …)` passes with fewer DuckDB executions over the same league + minutes cohort for the radar + game-area metrics, respecting existing filter semantics (GK vs outfield behaviour unchanged).
- Optional: collapse PI history into profile response or tighten the second endpoint only if profiling shows duplicated work; default is to keep two routes unless measurement proves benefit.

### Phase C — Optional bundle endpoint (conditional)

Only if profiling after A+B shows **`/profile` + `POST /replacement`** still dominate first meaningful “full settle” latency:

- Add a narrowly scoped aggregated contract (e.g. `GET /players/{id}/profile` extended query flag or sibling route `…/profile-with-similar`) returning profile payload plus top-N similarity for Big 5 preset — regenerate OpenAPI + shared types, smoke tests — **defer until measurements justify complexity.**

---

## Risks / trade-offs

| Item | Risk | Mitigation |
|------|------|-------------|
| Defer Similar | Short empty/skeleton gap after radar | Skeleton + optional min-height unchanged |
| Batch percentiles | SQL regression or wrong cohort | Preserve same WHERE/cohort semantics; parity tests vs current outputs on sample IDs |
| Bundle endpoint | API surface creep | Gate behind Phase C metric threshold |

---

## Verification

- **Manual:** Browser Network waterfall — seasons no longer needless blocker; Similar starts after defer rule; `/profile` duration trend down post Phase B if implemented.
- **Automated:** Existing `pytest` smoke for profile and endpoints touched; TS `pnpm exec tsc --noEmit` unchanged after client-only Phase A unless types regen (Phase C only).

---

## Implementation note

Implementation plan is produced separately (Writing-plans workflow) — this document is specification only until an implementation slice is prioritised.
