"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ProfilePrefsState {
  lastWyscoutId: number | null;
  setLastWyscoutId: (id: number | null) => void;
}

export const useProfilePrefs = create<ProfilePrefsState>()(
  persist(
    (set) => ({
      lastWyscoutId: null,
      setLastWyscoutId: (id) => set({ lastWyscoutId: id }),
    }),
    { name: "raumdeuter-profile-prefs" },
  ),
);
