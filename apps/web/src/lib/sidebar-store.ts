"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SidebarState {
  collapsed: boolean;
  toggle: () => void;
  setCollapsed: (v: boolean) => void;
}

export const useSidebar = create<SidebarState>()(
  persist(
    (set, get) => ({
      collapsed: true,
      toggle: () => set({ collapsed: !get().collapsed }),
      setCollapsed: (collapsed) => set({ collapsed }),
    }),
    { name: "raumdeuter-sidebar" },
  ),
);
