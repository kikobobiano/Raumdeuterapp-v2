"use client";

import * as React from "react";

/**
 * Flips true after an idle deadline (`requestIdleCallback` or fallback timeout).
 * Keeps heavier secondary queries from competing with the first paint/network slice.
 */
export function useIdleReady(enabled: boolean, idleTimeoutMs = 380): boolean {
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    if (!enabled) {
      setReady(false);
      return;
    }
    setReady(false);
    let cancelled = false;

    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      const id = window.requestIdleCallback(
        () => {
          if (!cancelled) setReady(true);
        },
        { timeout: idleTimeoutMs },
      );
      return () => {
        cancelled = true;
        window.cancelIdleCallback(id);
      };
    }

    const t = window.setTimeout(() => {
      if (!cancelled) setReady(true);
    }, idleTimeoutMs);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [enabled, idleTimeoutMs]);

  return ready;
}
