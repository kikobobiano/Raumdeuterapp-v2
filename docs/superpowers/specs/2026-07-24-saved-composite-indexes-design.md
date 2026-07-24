# Saved Composite Indexes — Design (Phase 1)

*Date: 2026-07-24*

## 1. Problem

Screener composite indexes are built in the left sidebar and live only in React
state. Users want to **name**, **persist**, and **reuse** composite recipes —
including picking them from metric-style selects — without rebuilding weights
each session. Longer term they also want them on Scatter / Bar; that is Phase 2.

## 2. Decisions (locked)

| Decision | Choice |
|---|---|
| Phase 1 scope | **Screener only** (sort + criteria on composite score) |
| Phase 2 (later) | Scatter X/Y + Bar metric picks |
| What is saved | **Composite recipe only** (name + components). Criteria stay session-only |
| Persistence | **localStorage** (Zustand persist) **+** JSON Export/Import |
| Popup layout | **Tabs**: Criteria \| Composite \| Saved |
| Sidebar | Population filters only; builder moves to a Dialog |
| Approach | Client library + virtual ids `ci:<uuid>`; API scores as today |
| Criteria on index | New optional `composite_criteria` on `/screener` |

## 3. Product behaviour (Phase 1)

1. Screener sidebar shows **Population** only (seasons + `FilterPanel`).
2. **Builder…** opens a modal with three tabs:
   - **Criteria** — same controls as today (max 8 metric filters).
   - **Composite** — enable components (metric / mode / basis / weight), max 8;
     “Sort by composite score”.
   - **Saved** — list saved indexes: Load, Rename, Delete; Export / Import JSON.
3. **Save index…** prompts for a name and stores the current composite
   `components` (not criteria). Same `id` overwrite when re-saving a loaded
   index; “Save as…” can create a new id.
4. Sort Combobox and criteria metric Combobox include API metrics **plus**
   saved indexes (`ci:<id>`, label = name).
5. **Apply** closes the dialog and runs the screener with the current builder
   state.

## 4. Data model

```ts
type CompositeComponent = {
  metric: string;
  mode: "raw" | "p90" | "as_is";
  basis: "value" | "team_median";
  weight: number;
};

type SavedCompositeIndex = {
  id: string;       // uuid
  name: string;
  components: CompositeComponent[];
  updatedAt: number; // epoch ms
};
```

**Virtual metric id:** `ci:${id}`  
Treat as mode-less in the UI (`supports_mode: false`). The value is the
weighted z-score composite already used by Screener.

**Export file**

```json
{
  "version": 1,
  "indexes": [ /* SavedCompositeIndex[] */ ]
}
```

Import: validate `version` + shape; merge by `id` (imported wins); skip invalid
entries; show a short count toast/message.

**Storage key:** `raumdeuter-composite-indexes` via Zustand `persist`.

## 5. Architecture

```
ScreenerBuilderDialog
  ├─ Criteria tab ──► page state (session)
  ├─ Composite tab ─► page state + Save → composite-indexes-store
  └─ Saved tab ────► load / rename / delete / export / import

Screener page
  resolve ci:* → components
       │
       ▼
POST /screener {
  criteria,           // real metrics only
  composite,          // resolved components (if any)
  composite_criteria, // optional { operator, value } on score
  sort_by_composite,
  …filters / seasons
}
```

### 5.1 Backend

**`schemas.py`**

```python
class CompositeScoreCriterion(BaseModel):
    operator: str = Field(..., pattern=r"^(>=|<=|>|<|=|!=)$")
    value: float

class ScreenerRequest(BaseModel):
    # …existing…
    composite_criteria: CompositeScoreCriterion | None = None
```

**Router / `screener_composite`**

After `score_candidates`, if `composite_criteria` is set:

1. Keep only candidates whose composite score satisfies the operator/value
   (null scores fail the filter).
2. Recompute `total` as the filtered count.
3. Then sort + paginate as today.

If `composite` is empty, `composite_criteria` → `400`.

No change to Scatter / Bar / `/meta/metrics` in Phase 1.

### 5.2 Frontend

| Piece | Location |
|---|---|
| Dialog primitive | `apps/web/src/components/ui/dialog.tsx` (Radix Dialog) |
| Builder modal | `apps/web/src/components/domain/screener-builder-dialog.tsx` |
| Persist store | `apps/web/src/lib/composite-indexes-store.ts` |
| Screener page | slim sidebar; wire dialog; merge `ci:*` into Combobox options |

Helpers (pure, testable):

- `isCompositeMetricId(name: string): boolean`
- `compositeMetricId(id: string): string`
- `parseCompositeMetricId(name: string): string | null`
- `exportIndexesJson(indexes): Blob`
- `parseImportIndexesJson(text): SavedCompositeIndex[]`

When the user selects `ci:*` as a **criteria** metric, the UI does **not** send
it inside `criteria[]` (unknown column). It maps to `composite_criteria` and
ensures `composite` is that recipe.

**Single-recipe rule:** one request uses at most one composite recipe. If sort is
`ci:A` and a criterion is `ci:B` with `A ≠ B`, **block Apply** with a clear
message. If only one of sort/criteria is `ci:*`, that recipe becomes `composite`.
If the Composite tab has an unsaved recipe and the user also picks a different
`ci:*`, Apply prefers the explicit `ci:*` selection(s) and warns, or blocks —
**lock: block Apply on conflict**.

When sort is `ci:*` (and no conflict), set `sort_by_composite: true` and
`composite` to that recipe.

### 5.3 OpenAPI

Regen shared-types after adding `composite_criteria`.

## 6. Errors

| Case | Behaviour |
|---|---|
| `composite_criteria` without `composite` | 400 |
| Empty name on save | Client blocks |
| Import invalid JSON | Client message; no store change |
| Metric in recipe missing for season | Existing 400 from screener metric allowlist |
| Duplicate display names | Allowed (ids differ); Combobox shows name only |

## 7. Testing

- Unit: id helpers; import merge/validation.
- API smoke: composite + `composite_criteria` (≥) reduces `total` vs unfiltered.
- Manual: save → reload page → index still in Combobox; export/import round-trip.

## 8. Out of scope (Phase 1)

- Scatter / Bar virtual metrics
- Saving criteria / full screener presets
- Server-side or shared team library
- Showing composite score breakdown per component
- Editing `/meta/metrics` catalog

## 9. Phase 2 sketch (not implemented)

Reuse the same store. Scatter/Bar POST bodies accept optional `composite`
(or `x_composite` / `y_composite`) and compute the score per returned point
with the same cohort z-score path (likely shared core helper). Metric Combobox
merges `ci:*` the same way.
