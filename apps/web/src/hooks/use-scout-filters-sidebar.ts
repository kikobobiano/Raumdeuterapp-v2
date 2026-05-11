"use client";

import * as React from "react";

const LS_KEY = "scout-filters-sidebar-open";

export function useScoutFiltersSidebar() {
  const [filtersOpen, setFiltersOpenState] = React.useState(true);

  React.useEffect(() => {
    try {
      if (localStorage.getItem(LS_KEY) === "0") {
        // One-time restore after mount; reading localStorage during SSR would mismatch hydration.
        // eslint-disable-next-line react-hooks/set-state-in-effect -- persisted sidebar preference
        setFiltersOpenState(false);
      }
    } catch {
      /* private mode / blocked */
    }
  }, []);

  const setFiltersOpen = React.useCallback((open: boolean) => {
    setFiltersOpenState(open);
    try {
      localStorage.setItem(LS_KEY, open ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, []);

  return { filtersOpen, setFiltersOpen };
}
