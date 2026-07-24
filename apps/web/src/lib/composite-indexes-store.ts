"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import {
  exportIndexesPayload,
  mergeImportedIndexes,
  newCompositeIndexId,
  parseImportIndexesJson,
  type CompositeComponentRecipe,
  type SavedCompositeIndex,
} from "@/lib/composite-indexes";

interface CompositeIndexesState {
  indexes: SavedCompositeIndex[];
  saveIndex: (input: {
    id?: string | null;
    name: string;
    components: CompositeComponentRecipe[];
  }) => SavedCompositeIndex;
  renameIndex: (id: string, name: string) => void;
  deleteIndex: (id: string) => void;
  importFromJson: (text: string) => { imported: number; total: number };
  exportJson: () => string;
}

export const useCompositeIndexes = create<CompositeIndexesState>()(
  persist(
    (set, get) => ({
      indexes: [],
      saveIndex: ({ id, name, components }) => {
        const trimmed = name.trim();
        if (!trimmed) throw new Error("Name is required");
        if (!components.length) throw new Error("Add at least one component");
        const now = Date.now();
        const existingId = id || null;
        const next: SavedCompositeIndex = {
          id: existingId ?? newCompositeIndexId(),
          name: trimmed,
          components: components.map((c) => ({ ...c })),
          updatedAt: now,
        };
        set((state) => {
          const others = state.indexes.filter((x) => x.id !== next.id);
          return {
            indexes: [next, ...others].sort((a, b) => b.updatedAt - a.updatedAt),
          };
        });
        return next;
      },
      renameIndex: (id, name) => {
        const trimmed = name.trim();
        if (!trimmed) return;
        set((state) => ({
          indexes: state.indexes.map((x) =>
            x.id === id ? { ...x, name: trimmed, updatedAt: Date.now() } : x,
          ),
        }));
      },
      deleteIndex: (id) => {
        set((state) => ({ indexes: state.indexes.filter((x) => x.id !== id) }));
      },
      importFromJson: (text) => {
        const imported = parseImportIndexesJson(text);
        const merged = mergeImportedIndexes(get().indexes, imported);
        set({ indexes: merged });
        return { imported: imported.length, total: merged.length };
      },
      exportJson: () => exportIndexesPayload(get().indexes),
    }),
    { name: "raumdeuter-composite-indexes" },
  ),
);
