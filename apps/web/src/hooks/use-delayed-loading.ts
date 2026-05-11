"use client";

import * as React from "react";

type Options = {
  delay?: number;
  minHold?: number;
};

export function useDelayedLoading(
  isLoading: boolean,
  { delay = 200, minHold = 400 }: Options = {},
): boolean {
  const [visible, setVisible] = React.useState(false);
  const showTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const hideTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const shownAtRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    const clearShow = () => {
      if (showTimerRef.current) {
        clearTimeout(showTimerRef.current);
        showTimerRef.current = null;
      }
    };
    const clearHide = () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
    };

    if (isLoading) {
      clearHide();
      if (visible) return;
      if (showTimerRef.current) return;
      showTimerRef.current = setTimeout(() => {
        showTimerRef.current = null;
        shownAtRef.current = Date.now();
        setVisible(true);
      }, delay);
      return clearShow;
    }

    clearShow();
    if (!visible) return;
    const elapsed = shownAtRef.current ? Date.now() - shownAtRef.current : minHold;
    const remaining = Math.max(0, minHold - elapsed);
    if (remaining === 0) {
      shownAtRef.current = null;
      setVisible(false);
      return;
    }
    if (hideTimerRef.current) return;
    hideTimerRef.current = setTimeout(() => {
      hideTimerRef.current = null;
      shownAtRef.current = null;
      setVisible(false);
    }, remaining);
    return clearHide;
  }, [isLoading, visible, delay, minHold]);

  React.useEffect(() => {
    return () => {
      if (showTimerRef.current) clearTimeout(showTimerRef.current);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, []);

  return visible;
}
