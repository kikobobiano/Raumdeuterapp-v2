"use client";

import { usePathname, useSearchParams } from "next/navigation";
import * as React from "react";

const TICK_MS = 100;
const FINISH_FADE_MS = 200;

export function RouteProgress() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [progress, setProgress] = React.useState(0);
  const [visible, setVisible] = React.useState(false);
  const tickRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const fadeRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevKeyRef = React.useRef<string>(`${pathname}?${searchParams.toString()}`);

  const clearTick = React.useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const start = React.useCallback(() => {
    if (fadeRef.current) {
      clearTimeout(fadeRef.current);
      fadeRef.current = null;
    }
    setVisible(true);
    setProgress(8);
    clearTick();
    tickRef.current = setInterval(() => {
      setProgress((p) => (p < 80 ? p + (90 - p) * 0.08 : p));
    }, TICK_MS);
  }, [clearTick]);

  const finish = React.useCallback(() => {
    clearTick();
    setProgress(100);
    if (fadeRef.current) clearTimeout(fadeRef.current);
    fadeRef.current = setTimeout(() => {
      setVisible(false);
      setProgress(0);
      fadeRef.current = null;
    }, FINISH_FADE_MS);
  }, [clearTick]);

  React.useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented) return;
      if (e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      const link = target?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link) return;
      if (link.target && link.target !== "_self") return;
      const href = link.getAttribute("href") ?? "";
      if (
        !href ||
        href.startsWith("#") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:")
      ) {
        return;
      }
      try {
        const url = new URL(link.href, window.location.href);
        if (url.origin !== window.location.origin) return;
        const sameRoute =
          url.pathname === window.location.pathname &&
          url.search === window.location.search;
        if (sameRoute) return;
      } catch {
        return;
      }
      start();
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [start]);

  React.useEffect(() => {
    const key = `${pathname}?${searchParams.toString()}`;
    if (prevKeyRef.current !== key) {
      prevKeyRef.current = key;
      finish();
    }
  }, [pathname, searchParams, finish]);

  React.useEffect(() => {
    return () => {
      clearTick();
      if (fadeRef.current) clearTimeout(fadeRef.current);
    };
  }, [clearTick]);

  if (!visible) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed left-0 top-0 z-[100] h-[2px] transition-[width,opacity] duration-200 ease-out"
      style={{
        width: `${progress}%`,
        opacity: progress >= 100 ? 0 : 1,
        background: "linear-gradient(90deg, #14d1ff, #00ff41)",
        boxShadow: "0 0 8px #14d1ff, 0 0 4px #14d1ff",
      }}
    />
  );
}
