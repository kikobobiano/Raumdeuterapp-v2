# Profile first load performance — Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/scout/profile/[id]` feel faster on first visit by overlapping catalog + profile HTTP work, deferring similarity work off the hottest window, optionally batching percentile SQL on the profile route, without changing product layout.

**Architecture:** Phase A fixes React Query waterfalls and staggers `POST /replacement` for Similar Big 5 behind profile success + idle/viewport semantics; centralise `/meta/seasons` options (long `staleTime`, shared query definition). Phase B adds a DuckDB percentile batch primitive in `app/core/` and swaps N `_percentile` calls in `routers/profile.py` for fewer round trips. Phase C is gated on measurement only (bundle endpoint—not implemented unless justified).

**Tech stack:** Next.js 16 (`apps/web`), TanStack Query v5, FastAPI + DuckDB (`apps/api`), pytest, `pnpm exec tsc --noEmit`.

**Spec:** `docs/superpowers/specs/2026-05-10-profile-first-load-performance-design.md`

---

### File touch map

| Responsibility | Paths |
|---|---|
| Shared seasons catalog query (`queryKey`, `queryFn`, `staleTime`) | `apps/web/src/lib/catalog-queries.ts` (new) |
| Root seasons fetch + hydration | `apps/web/src/lib/season-sync.tsx` |
| Profile detail waterfalls + deferral prop | `apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx` |
| Similar Big 5 fetch gating | `apps/web/src/components/domain/profile-similar-big5-column.tsx` |
| Other pages using duplicated seasons query (reuse helper) | `apps/web/src/components/shell/top-bar.tsx`, `apps/web/src/components/domain/filter-panel.tsx`, `apps/web/src/app/scout/profile/profile-landing-client.tsx`, `apps/web/src/app/scout/rankings/rankings-index-client.tsx`, `apps/web/src/components/domain/profile-compare-panel.tsx`, `apps/web/src/components/domain/profile-replacement-panel.tsx` |
| Batch percentile core | `apps/api/app/core/profile_percentiles.py` (new) |
| Consume batch helper | `apps/api/app/routers/profile.py` |
| API smoke regression | `apps/api/tests/test_endpoints.py` |

---

### Task A1: Central catalogue query helper (`seasons`)

**Files:**
- Create: `apps/web/src/lib/catalog-queries.ts`
- Modify: `apps/web/src/lib/season-sync.tsx`

Use one exported constant plus options factory so **every** `useQuery(["seasons"], …)` shares the same `queryKey`, `queryFn`, and **`staleTime: 86_400_000` ms** (24h, aligns with `.cursor/rules/performance.mdc` static catalog guidance vs default five minutes).

- [ ] **Step A1a — Create `catalog-queries.ts`**

```typescript
import { api } from "@/lib/api";

export const META_SEASONS_STALE_MS = 86_400_000;

export function metaSeasonsQueryOptions() {
  return {
    queryKey: ["seasons"] as const,
    queryFn: async (): Promise<number[]> =>
      (await api.GET("/meta/seasons")).data ?? [],
    staleTime: META_SEASONS_STALE_MS,
  };
}
```

- [ ] **Step A1b — Wire SeasonSync**

In `season-sync.tsx`, replace inline `queryKey`/`queryFn`/`staleTime` with:

```typescript
useQuery(metaSeasonsQueryOptions());
```

- [ ] **Step A1c — Lint / typecheck snippet**

Run from monorepo root:

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expect: exit code 0.

- [ ] **Step A1d — Commit**

```bash
git add apps/web/src/lib/catalog-queries.ts apps/web/src/lib/season-sync.tsx
git commit -m "Share meta/seasons query options with 24h staleTime"
```

---

### Task A2: Deduplicate all `seasons` consumers onto `metaSeasonsQueryOptions`

**Files:** Modify every file from the table under “Other pages…” plus `profile-detail-client.tsx` (seven total call sites excluding SeasonSync).

- [ ] **Step A2a — Mechanical replace**

Replace each:

```typescript
queryKey: ["seasons"],
queryFn: async () => (await api.GET("/meta/seasons")).data ?? [],
```

(or equivalent spread) with `...metaSeasonsQueryOptions()` merged into existing `useQuery({ … })`.

Example:

```typescript
useQuery({
  ...metaSeasonsQueryOptions(),
  // other fields if any…
});
```

Import from `@/lib/catalog-queries`.

**Do not remove** supplemental options on the same hooks (there are rarely any besides defaults).

- [ ] **Step A2b — Typecheck**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expect: exit code 0.

- [ ] **Step A2c — Commit**

```bash
git add apps/web/src/app/scout/profile/** apps/web/src/components/** apps/web/src/app/scout/rankings/**
git commit -m "Use metaSeasonsQueryOptions for seasons fetch everywhere"
```

---

### Task A3: Remove needless profile block while seasons list loads

**File:** `apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx`

**Observation:** Today `profileQ` uses `enabled: … && (list ?? []).includes(season)`. Before `seasons` resolves `list` is `undefined`; `(undefined ?? []).includes(season)` is always `false`, so **`GET /players/.../profile` does not begin until `/meta/seasons` completes** despite React Query deduplication.

- [ ] **Step A3a — New enable rule**

Define:

```typescript
const list = seasonsQ.data;
const seasonsReadyNotEmpty = seasonsQ.isFetched && (list?.length ?? 0) > 0;
const seasonProbablyValid = list?.includes(season) ?? true;
```

Use for both `profileQ` and `piHistoryQ`:

```typescript
enabled:
  Number.isFinite(wyscoutId) &&
  (!seasonsReadyNotEmpty || seasonProbablyValid),
```

**Semantics:** Allow profile + PI history to run **in parallel with** `/meta/seasons` while the catalogue is unresolved; after fetch, if seasons exist and resolved `season` is not in API list, suspend (prevents querying a parquet that truly does not exist). First render may briefly use unvalidated `season` from URL/store—the existing `resolveSeason` effect already corrects UI when catalogue arrives.

- [ ] **Step A3b — Smoke manually**

Cold refresh profile URL; in DevTools Network, confirm **`/profile` overlaps with `/meta/seasons`** timing (starts before seasons finishes).

- [ ] **Step A3c — Typecheck**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

- [ ] **Step A3d — Commit**

```bash
git add apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx
git commit -m "Start profile queries without waiting on seasons catalogue"
```

---

### Task A4: Defer Similar Big 5 (leagues + replacement) after idle / profile idle

**Files:**
- Modify: `apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx`
- Modify: `apps/web/src/components/domain/profile-similar-big5-column.tsx`

Goals from spec:

1. Secondary work must not contend with **`GET /players/…/profile`** and **`performance-index-history`** at T+0 ms once profile keys enable.
2. Keep skeleton UX; Same response contract.

- [ ] **Step A4a — Add reusable hook**

Create `apps/web/src/hooks/use-idle-ready.ts`:

```typescript
"use client";

import * as React from "react";

/**
 * Waits until the browser reports idle (`requestIdleCallback`) before flipping
 * to true — good for prefetching/heavy secondary requests after painting.
 */
export function useIdleReady(enabled: boolean, idleTimeoutMs = 380): boolean {
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    if (!enabled) {
      setReady(false);
      return;
    }
    let cancelled = false;
    let cancelIdle: number | undefined;

    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      cancelIdle = window.requestIdleCallback(
        () => {
          if (!cancelled) setReady(true);
        },
        { timeout: idleTimeoutMs },
      );
    } else {
      const t = window.setTimeout(() => {
        if (!cancelled) setReady(true);
      }, idleTimeoutMs);
      cancelIdle = t as unknown as number;
    }

    return () => {
      cancelled = true;
      if (typeof window !== "undefined" && cancelIdle !== undefined) {
        if ("cancelIdleCallback" in window) {
          window.cancelIdleCallback(cancelIdle);
        } else {
          window.clearTimeout(cancelIdle);
        }
      }
    };
  }, [enabled, idleTimeoutMs]);

  return ready;
}
```

- [ ] **Step A4b — Prop + consumption**

Extend `ProfileSimilarBig5Column` props with:

```typescript
deferFetch?: boolean;
```

Compute `deferFetch`:

```tsx
const similarDeferParent =
  Number.isFinite(wyscoutId) &&
  profileQ.isSuccess &&
  !profileQ.isFetching;
const idleReadySimilar = useIdleReady(similarDeferParent);
```

Render:

```tsx
<ProfileSimilarBig5Column
  wyscoutId={p.wyscout_id}
  season={season}
  defaultRole={p.role ?? null}
  deferFetch={idleReadySimilar}
/>
```

Inside `profile-similar-big5-column.tsx`, thread `deferFetch` into both queries:

```typescript
const leaguesQ = useQuery({
  ...existing,
  enabled: deferFetch === true && existingEnabled,
});

const repQ = useQuery({
  ...existing,
  enabled: deferFetch === true && leaguesQ.isFetched && Number.isFinite(wyscoutId),
});
```

If `deferFetch` is optional for test/story usage, default `deferFetch = true` or `false` — **default `true` for production column** to preserve new behaviour; parent always passes explicitly from profile page.

- [ ] **Step A4c — Typecheck**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

- [ ] **Step A4d — Commit**

```bash
git add apps/web/src/hooks/use-idle-ready.ts \
  apps/web/src/components/domain/profile-similar-big5-column.tsx \
  apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx
git commit -m "Defer Similar Big 5 fetch until profile idle + requestIdleCallback"
```

---

### Task B1: Batch cohort percentiles in core

**Files:**
- Modify (prerequisite): `apps/api/app/core/sql_ident.py` (new, holds `_q`)
- Modify: `apps/api/app/routers/scatter.py` (+ any importer of `_q` from scatter)
- Create: `apps/api/app/core/profile_percentiles.py`
- Modify: `apps/api/app/routers/profile.py`

**Semantic requirement:** Old `_percentile` used `WHERE {cohort}` AND `{metric} IS NOT NULL` and divided by `COUNT(*)`. For each metric `m` and player value `v`, the cohort percentile is:

`100 * (count of rows with m non-null and m <= v) / (count of rows with m non-null)`

among rows matching `cohort_where` / `cohort_params`. That is equivalent to:

```sql
100.0 * SUM(CASE WHEN {_q(m)} IS NOT NULL AND {_q(m)} <= ? THEN 1 ELSE 0 END)
  / NULLIF(SUM(CASE WHEN {_q(m)} IS NOT NULL THEN 1 ELSE 0 END), 0)
```

Use this form so **one** `SELECT` can return many columns with **one** table scan per profile request.

```python
from __future__ import annotations

from typing import Sequence

import duckdb

from app.core.sql_ident import _q


def batch_percentiles(
    conn: duckdb.DuckDBPyConnection,
    view: str,
    items: Sequence[tuple[str, float | None]],
    cohort_where_sql: str,
    cohort_params: list,
) -> dict[str, float | None]:
    """Return metric name -> cohort percentile (same semantics as repeated SUM/CASE queries).

    Skips None/NaN values (returns None for those metrics). ``items`` order is preserved
    in output keys; duplicate metric names last write wins.
    """
    out: dict[str, float | None] = {}
    selects: list[str] = []
    params: list[object] = []

    for idx, (metric, value) in enumerate(items):
        if value is None or value != value:
            out[metric] = None
            continue
        qm = _q(metric)
        alias = f"__p{idx}"
        selects.append(
            f"100.0 * SUM(CASE WHEN {qm} IS NOT NULL AND {qm} <= ? THEN 1 ELSE 0 END) "
            f"/ NULLIF(SUM(CASE WHEN {qm} IS NOT NULL THEN 1 ELSE 0 END), 0) AS {alias}"
        )
        params.append(value)
        out[metric] = None  # placeholder; filled from row

    if not selects:
        return {m: None for m, _ in items}

    where_sql = cohort_where_sql.strip() if cohort_where_sql else "TRUE"
    sql = f"SELECT {', '.join(selects)} FROM {view} WHERE {where_sql}"
    row = conn.execute(sql, [*params, *cohort_params]).fetchone()
    if row is None:
        return out

    j = 0
    for idx, (metric, value) in enumerate(items):
        if value is None or value != value:
            continue
        cell = row[j]
        j += 1
        out[metric] = float(cell) if cell is not None else None
    return out
```

**Note:** `core/` must not import routers. **Step B1a’ completes before B1a.**

- [ ] **Step B1a’ — Move `_q` to core**

1. Create `apps/api/app/core/sql_ident.py` with `_q` copied from `routers/scatter.py`.
2. In `routers/scatter.py`, replace definition with `from app.core.sql_ident import _q` (or keep thin wrapper).
3. Grep `from app.routers.scatter import _q` across `apps/api` and point imports to `app.core.sql_ident`.
4. Run `cd apps/api && uv run pytest -q` — expect all pass.
5. Commit: `git add apps/api/app/core/sql_ident.py apps/api/app/routers/scatter.py … && git commit -m "Move _q column guard to core for reuse"`

- [ ] **Step B1a — Implement `batch_percentiles` (uses `sql_ident._q`)**  
        Use the snippet above inside `apps/api/app/core/profile_percentiles.py`; adjust implementation details if QA finds aggregate edge cases (e.g. all-null cohort).

- [ ] **Step B1b — Build `items` list in `profile()`**

After `cohort_where` / `cohort_params` are known, collect `(metric, value)` tuples in the same order you currently call `_percentile`:

1. Every `AREA_INDEX_COLS` entry with a numeric `v`
2. Every `table_metrics` entry except `"Minutes played"`
3. Every `GAME_AREA_METRIC_GROUPS` nested metric except `"Minutes played"`
4. `"performance_index"` when `pi` is finite

Call `batch_percentiles(conn, view, items, cohort_where, cohort_params)` once (or twice if SQL length ever exceeded—YAGNI single call first).

Map results back into `radar`, `table`, `game_areas`, and `pi_pct` construction **without changing response schema**.

- [ ] **Step B1c — Delete or keep `_percentile`**

Remove dead `_percentile` if unused; otherwise leave for other routers (grep first).

- [ ] **Step B1d — Run pytest**

```bash
cd apps/api && PATH="$HOME/.local/bin:$PATH" uv run pytest -q
```

Expect: exit code 0.

- [ ] **Step B1e — Manual parity sampling (mandatory)**

Pick one outfield `wid` via `/players/search` and dump profile JSON:

```bash
curl -s "http://127.0.0.1:8000/players/<WID>/profile?season=<S>" | jq '.radar,.table[0],.performance_index_percentile'
```

Run against commit before B1 vs after batching; percentile floats should match within floating tolerance (`abs(a-b)<1e-6`) for non-null metrics.

- [ ] **Step B1f — Commit**

```bash
git add apps/api/app/core/profile_percentiles.py apps/api/app/routers/profile.py apps/api/app/core/sql_ident.py
git commit -m "Batch DuckDB percentile scan for GET /players/{id}/profile"
```

---

### Task B2: Smoke test GET profile endpoint

**File:** `apps/api/tests/test_endpoints.py`

- [ ] **Step B2a — Append test**

```python
def test_player_profile_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.get(f"/players/{wid}/profile", params={"season": seasons[0]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("wyscout_id") == wid
        assert "radar" in d and isinstance(d["radar"], list)
```

- [ ] **Step B2b — Run pytest**

```bash
cd apps/api && uv run pytest tests/test_endpoints.py::test_player_profile_smoke -v
```

- [ ] **Step B2c — Commit**

```bash
git add apps/api/tests/test_endpoints.py
git commit -m "Smoke test GET /players/{id}/profile"
```

---

### Phase C gate (documentation only — no coding until thresholds met)

- [ ] **Step C-doc — Measurement checklist**

Capture before/after in Chrome Performance + Network waterfall or `curl -w "%{time_total}\n"` for:

| Call | SLA note |
|---|---|
| `/meta/seasons` | should warm cache 24h |
| `/players/{id}/profile` | target per `AGENTS.md` hot path commentary |
| `/players/{id}/performance-index-history` | watch overlap |
| `POST /replacement` (Similar widget) | should start after idle boundary |

Promote Phase C (**bundle endpoint** from spec §Phase C) only if **combined** perceived “full settle” still unacceptable after Tasks A+B; then follow normal OpenAPI regen workflow.

---

### Plan self-review (completed)

**Spec coverage:** Phase A parallels §Approach Phase A (`staleTime`, defer Similar); §blocking seasons waterfall addressed explicitly (`enabled` predicate); Phase B parallels §Approach Phase B (`batch percentile queries`); Phase C captured as gated doc only.

**Placeholder scan:** Numeric threshold for Phase C left intentionally as measurement artefacts (no fictional ms numbers).

**Type consistency:** `metaSeasonsQueryOptions` returns `{ queryKey, queryFn, staleTime }`; compatible with TanStack Query v5 inference.

---

**Plan complete.** Two execution modes:

**1. Subagent-Driven** — Dispatch a fresh subagent per checkbox task cluster; pause for human review between A / B phases.

**2. Inline Execution** — Run tasks sequentially in Cursor with manual checkpoints between commits.

Say which execution mode you want when starting implementation.
