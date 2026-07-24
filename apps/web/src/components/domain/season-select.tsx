"use client";

import { useQuery } from "@tanstack/react-query";

import { Combobox } from "@/components/ui/combobox";
import { metaSeasonsQueryOptions } from "@/lib/catalog-queries";
import { useGlobalFilters } from "@/lib/store";

/** Global season picker — same options/labels as ``FilterPanel`` / Best XI. */
export function SeasonSelect() {
  const f = useGlobalFilters();
  const seasonsQ = useQuery(metaSeasonsQueryOptions());

  return (
    <Combobox
      value={String(f.season)}
      onChange={(v) => f.setSeason(Number(v))}
      options={(seasonsQ.data ?? []).map((y) => ({
        value: String(y),
        label: `${String(y).slice(2)}-${String(y + 1).slice(2)}`,
      }))}
    />
  );
}
