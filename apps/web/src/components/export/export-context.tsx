"use client";

import * as React from "react";

import { runExportPng } from "./use-export-png";

export interface ExportSectionMeta {
  id: string;
  label: string;
  required: boolean;
  defaultIncluded: boolean;
  disabled: boolean;
  disabledReason?: string;
  ref: React.RefObject<HTMLDivElement | null>;
}

export interface ExportRunResult {
  ok: boolean;
  missing: string[];
}

interface ExportContextValue {
  title: string;
  filename: string;
  sections: ExportSectionMeta[];
  register: (meta: ExportSectionMeta) => void;
  unregister: (id: string) => void;
  exportPng: (selectedIds: string[]) => Promise<ExportRunResult>;
}

const ExportContext = React.createContext<ExportContextValue | null>(null);

export function useExportContext(): ExportContextValue | null {
  return React.useContext(ExportContext);
}

export function useExportContextStrict(): ExportContextValue {
  const ctx = React.useContext(ExportContext);
  if (!ctx) throw new Error("Export components must be used inside <ExportProvider>.");
  return ctx;
}

interface ProviderProps {
  title: string;
  filename: string;
  children: React.ReactNode;
}

export function ExportProvider({ title, filename, children }: ProviderProps) {
  const [sections, setSections] = React.useState<ExportSectionMeta[]>([]);

  const register = React.useCallback((meta: ExportSectionMeta) => {
    setSections((prev) => {
      const existing = prev.find((s) => s.id === meta.id);
      if (!existing) return [...prev, meta];
      // Shallow-equal check — only re-render if something material changed.
      if (
        existing.label === meta.label &&
        existing.required === meta.required &&
        existing.defaultIncluded === meta.defaultIncluded &&
        existing.disabled === meta.disabled &&
        existing.disabledReason === meta.disabledReason &&
        existing.ref === meta.ref
      ) {
        return prev;
      }
      return prev.map((s) => (s.id === meta.id ? meta : s));
    });
  }, []);

  const unregister = React.useCallback((id: string) => {
    setSections((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const exportPng = React.useCallback(
    async (selectedIds: string[]): Promise<ExportRunResult> => {
      const ordered = orderSectionsByDom(sections);
      const chosen = ordered.filter(
        (s) => selectedIds.includes(s.id) && !s.disabled,
      );
      const live: ExportSectionMeta[] = [];
      const missing: string[] = [];
      for (const s of chosen) {
        if (s.ref.current) live.push(s);
        else missing.push(s.id);
      }
      if (live.length === 0) return { ok: false, missing };
      await runExportPng(
        live.map((s) => s.ref.current as HTMLElement),
        filename,
      );
      return { ok: true, missing };
    },
    [sections, filename],
  );

  const value = React.useMemo<ExportContextValue>(
    () => ({ title, filename, sections, register, unregister, exportPng }),
    [title, filename, sections, register, unregister, exportPng],
  );

  return <ExportContext.Provider value={value}>{children}</ExportContext.Provider>;
}

function orderSectionsByDom(sections: ExportSectionMeta[]): ExportSectionMeta[] {
  const withNodes = sections.filter((s) => s.ref.current);
  const sorted = [...withNodes].sort((a, b) => {
    const an = a.ref.current!;
    const bn = b.ref.current!;
    const pos = an.compareDocumentPosition(bn);
    if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
    if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
    return 0;
  });
  const seen = new Set(sorted.map((s) => s.id));
  const tail = sections.filter((s) => !seen.has(s.id));
  return [...sorted, ...tail];
}
