"use client";

import * as React from "react";

/**
 * Flips true after an idle deadline (`requestIdleCallback` or fallback timeout).
 * Keeps heavier secondary queries from competing with the first paint/network slice.
 */
export function useIdleReady(enabled: boolean, idleTimeoutMs = 380): boolean {
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;

    if (!enabled) {
      setReady(false);
      return;
    }
    setReady(false);
    let cancelled = false;

    const w = window;
    if ("requestIdleCallback" in w && typeof w.requestIdleCallback === "function") {
      const id = w.requestIdleCallback(
        () => {
          if (!cancelled) setReady(true);
        },
        { timeout: idleTimeoutMs },
      );
      return () => {
        cancelled = true;
        w.cancelIdleCallback(id);
      };
    }

    const t = w.setTimeout(() => {
      if (!cancelled) setReady(true);
    }, idleTimeoutMs);
    return () => {
      cancelled = true;
      w.clearTimeout(t);
    };
  }, [enabled, idleTimeoutMs]);

  return ready;
}
