import { api } from "@/lib/api";

/** Static catalog cache (matches performance rules for leagues/season lists). */
export const META_SEASONS_STALE_MS = 86_400_000;

export function metaSeasonsQueryOptions() {
  return {
    queryKey: ["seasons"] as const,
    queryFn: async (): Promise<number[]> =>
      (await api.GET("/meta/seasons")).data ?? [],
    staleTime: META_SEASONS_STALE_MS,
  };
}
