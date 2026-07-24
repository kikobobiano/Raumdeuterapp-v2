# Saved Composite Indexes (Phase 1) Implementation Plan

> **For agentic workers:** Execute task-by-task.

**Goal:** Persist named screener composite recipes (localStorage + export/import) and use them via `ci:<id>` in Screener sort/criteria; builder moves to a tabbed Dialog.

**Architecture:** Zustand persist store + Dialog builder; API `composite_criteria` filters scored rows.

**Spec:** `docs/superpowers/specs/2026-07-24-saved-composite-indexes-design.md`

---

### Task 1: API `composite_criteria`

- [x] Modify: `schemas.py`, `routers/screener.py`
- [x] Test: `test_endpoints.py` + unit

### Task 2: Store + helpers

- [x] Create: `lib/composite-indexes.ts`
- [x] Create: `lib/composite-indexes-store.ts`

### Task 3: Dialog + Builder UI

- [x] Create: `components/ui/dialog.tsx`
- [x] Create: `components/domain/screener-builder-dialog.tsx`
- [x] Modify: `app/scout/screener/page.tsx`

### Task 4: OpenAPI regen + verify

- [x] Regen shared-types; tsc clean for touched files
