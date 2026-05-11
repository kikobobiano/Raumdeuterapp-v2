"use client";

import { create } from "zustand";

import { BIG_FIVE_LEAGUES } from "@/lib/big-five";

import type { RoleSubTokensState } from "./role-filters";

/** Default season start year (25-26 → 2025). */
export const DEFAULT_SEASON = 2025;

export interface GlobalFilters {
  season: number;
  leagues: string[];
  /** Tactical role parents (e.g. Winger); see roleSubTokens for Wyscout codes. */
  selectedRoles: string[];
  roleSubTokens: RoleSubTokensState;
  ageMin: number;
  ageMax: number;
  minutesMin: number;
  setSeason: (season: number) => void;
  setLeagues: (leagues: string[]) => void;
  setSelectedRoles: (roles: string[]) => void;
  setRoleSubTokens: (subs: RoleSubTokensState) => void;
  setRoleFilter: (next: { selectedRoles: string[]; roleSubTokens: RoleSubTokensState }) => void;
  clearRoleFilters: () => void;
  setAge: (min: number, max: number) => void;
  setMinutesMin: (min: number) => void;
}

export const useGlobalFilters = create<GlobalFilters>((set) => ({
  // Snapped by SeasonSync if missing from GET /meta/seasons
  season: DEFAULT_SEASON,
  leagues: [...BIG_FIVE_LEAGUES],
  selectedRoles: [],
  roleSubTokens: {},
  ageMin: 16,
  ageMax: 40,
  minutesMin: 500,
  setSeason: (season) => set({ season }),
  setLeagues: (leagues) => set({ leagues }),
  setSelectedRoles: (selectedRoles) => set({ selectedRoles }),
  setRoleSubTokens: (roleSubTokens) => set({ roleSubTokens }),
  setRoleFilter: (next) =>
    set({ selectedRoles: next.selectedRoles, roleSubTokens: next.roleSubTokens }),
  clearRoleFilters: () => set({ selectedRoles: [], roleSubTokens: {} }),
  setAge: (ageMin, ageMax) => set({ ageMin, ageMax }),
  setMinutesMin: (minutesMin) => set({ minutesMin }),
}));
