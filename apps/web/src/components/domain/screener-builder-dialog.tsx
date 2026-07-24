"use client";

import { Download, Plus, Trash2, Upload } from "lucide-react";
import * as React from "react";

import {
  MetricModeToggle,
  modeFromMetricOption,
  type MetricMode,
} from "@/components/domain/metric-mode-toggle";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  compositeMetricId,
  type CompositeBasis,
  type CompositeComponentRecipe,
} from "@/lib/composite-indexes";
import { useCompositeIndexes } from "@/lib/composite-indexes-store";
import type { components } from "shared-types";

export interface ScreenerCriterionDraft {
  metric: string;
  mode: MetricMode;
  operator: ">=" | "<=" | ">" | "<" | "=" | "!=";
  value: number;
}

export interface ScreenerBuilderState {
  criteria: ScreenerCriterionDraft[];
  compositeEnabled: boolean;
  compositeComponents: CompositeComponentRecipe[];
  sortByComposite: boolean;
  sortBy: string;
  sortMode: MetricMode;
  editingIndexId: string | null;
}

interface MetricOpt {
  value: string;
  label: string;
}

type MetricOption = components["schemas"]["MetricOption"];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: ScreenerBuilderState;
  onChange: (patch: Partial<ScreenerBuilderState>) => void;
  onApply: () => void;
  metricOpts: MetricOpt[];
  metricByName: Record<string, MetricOption | undefined>;
  /** Includes API metrics + saved ci:* options */
  criterionMetricOpts: MetricOpt[];
  sortMetricOpts: MetricOpt[];
}

function compositeBasisLabel(basis: CompositeBasis) {
  return basis === "team_median" ? "vs team median" : "season value";
}

export function ScreenerBuilderDialog({
  open,
  onOpenChange,
  state,
  onChange,
  onApply,
  metricOpts,
  metricByName,
  criterionMetricOpts,
  sortMetricOpts,
}: Props) {
  const indexes = useCompositeIndexes((s) => s.indexes);
  const saveIndex = useCompositeIndexes((s) => s.saveIndex);
  const renameIndex = useCompositeIndexes((s) => s.renameIndex);
  const deleteIndex = useCompositeIndexes((s) => s.deleteIndex);
  const importFromJson = useCompositeIndexes((s) => s.importFromJson);
  const exportJson = useCompositeIndexes((s) => s.exportJson);

  const [saveName, setSaveName] = React.useState("");
  const [statusMsg, setStatusMsg] = React.useState<string | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (!open) {
      setStatusMsg(null);
      return;
    }
    if (state.editingIndexId) {
      const found = indexes.find((x) => x.id === state.editingIndexId);
      setSaveName(found?.name ?? "");
    } else {
      setSaveName("");
    }
  }, [open, state.editingIndexId, indexes]);

  const updateCriterion = (i: number, patch: Partial<ScreenerCriterionDraft>) => {
    onChange({
      criteria: state.criteria.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
    });
  };

  const updateComposite = (i: number, patch: Partial<CompositeComponentRecipe>) => {
    onChange({
      compositeComponents: state.compositeComponents.map((c, idx) =>
        idx === i ? { ...c, ...patch } : c,
      ),
    });
  };

  const onSave = (asNew: boolean) => {
    try {
      const saved = saveIndex({
        id: asNew ? null : state.editingIndexId,
        name: saveName || "Untitled index",
        components: state.compositeComponents,
      });
      onChange({
        editingIndexId: saved.id,
        compositeEnabled: true,
        compositeComponents: saved.components,
        sortByComposite: true,
        sortBy: compositeMetricId(saved.id),
      });
      setSaveName(saved.name);
      setStatusMsg(`Saved “${saved.name}”.`);
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Could not save");
    }
  };

  const onExport = () => {
    const blob = new Blob([exportJson()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "raumdeuter-composite-indexes.json";
    a.click();
    URL.revokeObjectURL(url);
    setStatusMsg("Exported JSON.");
  };

  const onImportFile = async (file: File) => {
    try {
      const text = await file.text();
      const { imported, total } = importFromJson(text);
      setStatusMsg(`Imported ${imported} index(es). Library size: ${total}.`);
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Import failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Screener builder</DialogTitle>
          <DialogDescription>
            Set criteria and composite indexes. Save recipes to reuse in metric selects.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <Tabs defaultValue="criteria">
            <TabsList className="mb-4">
              <TabsTrigger value="criteria">Criteria</TabsTrigger>
              <TabsTrigger value="composite">Composite</TabsTrigger>
              <TabsTrigger value="saved">Saved</TabsTrigger>
            </TabsList>

            <TabsContent value="criteria" className="space-y-3 outline-none">
              {state.criteria.map((c, i) => {
                const meta = metricByName[c.metric];
                const isCi = c.metric.startsWith("ci:");
                return (
                  <div key={`crit-${i}`} className="space-y-2 rounded-md bg-surface-low p-3">
                    <div className="flex gap-2">
                      <Combobox
                        value={c.metric}
                        onChange={(v) => {
                          if (v.startsWith("ci:")) {
                            updateCriterion(i, { metric: v, mode: "as_is" });
                            return;
                          }
                          const m = metricByName[v];
                          updateCriterion(i, {
                            metric: v,
                            mode: modeFromMetricOption(m),
                          });
                        }}
                        options={criterionMetricOpts}
                        className="min-w-0 flex-1"
                      />
                      {!isCi ? (
                        <MetricModeToggle
                          supports={!!meta?.supports_mode}
                          value={c.mode}
                          onChange={(mode) => updateCriterion(i, { mode })}
                        />
                      ) : null}
                    </div>
                    <div className="flex gap-2">
                      <select
                        value={c.operator}
                        onChange={(e) =>
                          updateCriterion(i, {
                            operator: e.target.value as ScreenerCriterionDraft["operator"],
                          })
                        }
                        className="rounded-md bg-surface-mid px-2 py-1 text-sm text-on-surface"
                      >
                        {[">=", "<=", ">", "<", "=", "!="].map((op) => (
                          <option key={op} value={op}>
                            {op}
                          </option>
                        ))}
                      </select>
                      <Input
                        type="number"
                        value={c.value}
                        onChange={(e) =>
                          updateCriterion(i, { value: parseFloat(e.target.value) })
                        }
                        className="flex-1"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          onChange({
                            criteria: state.criteria.filter((_, idx) => idx !== i),
                          })
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    {isCi ? (
                      <p className="text-xs text-on-surface-variant">
                        Filters on the composite score (z units, typically −3…+3).
                      </p>
                    ) : null}
                  </div>
                );
              })}
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                disabled={state.criteria.length >= 8}
                onClick={() => {
                  const first = criterionMetricOpts[0];
                  if (!first) return;
                  const meta = metricByName[first.value];
                  onChange({
                    criteria: [
                      ...state.criteria,
                      {
                        metric: first.value,
                        mode: first.value.startsWith("ci:")
                          ? "as_is"
                          : modeFromMetricOption(meta),
                        operator: ">=",
                        value: 0,
                      },
                    ],
                  });
                }}
              >
                <Plus className="h-4 w-4" />
                {state.criteria.length >= 8 ? "Max 8 criteria" : "Add criterion"}
              </Button>

              <div className="mt-4 border-t border-outline-variant/40 pt-4">
                <p className="label-caps mb-2">Sort by</p>
                <div
                  className={
                    state.compositeEnabled && state.sortByComposite
                      ? "flex gap-2 opacity-50"
                      : "flex gap-2"
                  }
                >
                  <Combobox
                    value={state.sortBy}
                    onChange={(name) => {
                      if (name.startsWith("ci:")) {
                        onChange({
                          sortBy: name,
                          sortByComposite: true,
                          sortMode: "as_is",
                          compositeEnabled: true,
                        });
                        return;
                      }
                      const meta = metricByName[name];
                      onChange({
                        sortBy: name,
                        sortByComposite: false,
                        sortMode: modeFromMetricOption(meta),
                      });
                    }}
                    options={sortMetricOpts}
                    className="min-w-0 flex-1"
                  />
                  {!state.sortBy.startsWith("ci:") ? (
                    <MetricModeToggle
                      supports={!!metricByName[state.sortBy]?.supports_mode}
                      value={state.sortMode}
                      onChange={(mode) =>
                        onChange({ sortMode: mode, sortByComposite: false })
                      }
                    />
                  ) : null}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="composite" className="space-y-3 outline-none">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="label-caps">Composite index</p>
                <label className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <input
                    type="checkbox"
                    checked={state.compositeEnabled}
                    onChange={(e) => {
                      const on = e.target.checked;
                      onChange({
                        compositeEnabled: on,
                        sortByComposite: on ? true : state.sortByComposite,
                      });
                    }}
                    className="rounded border-outline-variant"
                  />
                  Enable
                </label>
              </div>

              {state.compositeEnabled ? (
                <>
                  {state.compositeComponents.map((comp, i) => {
                    const meta = metricByName[comp.metric];
                    const lab =
                      metricOpts.find((o) => o.value === comp.metric)?.label ??
                      comp.metric;
                    return (
                      <div key={`comp-${i}`} className="space-y-2 rounded-md bg-surface-low p-3">
                        <div className="flex gap-2">
                          <Combobox
                            value={comp.metric}
                            onChange={(v) => {
                              const m = metricByName[v];
                              updateComposite(i, {
                                metric: v,
                                mode: modeFromMetricOption(m),
                              });
                            }}
                            options={metricOpts}
                            className="min-w-0 flex-1"
                          />
                          <MetricModeToggle
                            supports={!!meta?.supports_mode}
                            value={comp.mode}
                            onChange={(mode) => updateComposite(i, { mode })}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              onChange({
                                compositeComponents: state.compositeComponents.filter(
                                  (_, idx) => idx !== i,
                                ),
                              })
                            }
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            value={comp.basis}
                            onChange={(e) =>
                              updateComposite(i, {
                                basis: e.target.value as CompositeBasis,
                              })
                            }
                            className="rounded-md bg-surface-mid px-2 py-1 text-sm text-on-surface"
                          >
                            <option value="value">Season value</option>
                            <option value="team_median">vs team median</option>
                          </select>
                          <div className="flex min-w-0 flex-1 items-center gap-2">
                            <span className="label-caps shrink-0">Weight</span>
                            <Input
                              type="number"
                              step={0.1}
                              min={0}
                              value={comp.weight}
                              onChange={(e) =>
                                updateComposite(i, {
                                  weight: parseFloat(e.target.value) || 0,
                                })
                              }
                              className="w-20"
                            />
                          </div>
                        </div>
                        <p className="text-xs text-on-surface-variant">
                          {lab} · {compositeBasisLabel(comp.basis)}
                        </p>
                      </div>
                    );
                  })}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full"
                    disabled={state.compositeComponents.length >= 8}
                    onClick={() => {
                      const first = metricOpts[0];
                      if (!first) return;
                      const meta = metricByName[first.value];
                      onChange({
                        compositeComponents: [
                          ...state.compositeComponents,
                          {
                            metric: first.value,
                            mode: modeFromMetricOption(meta),
                            basis: "value",
                            weight: 1,
                          },
                        ],
                      });
                    }}
                  >
                    <Plus className="h-4 w-4" />
                    {state.compositeComponents.length >= 8
                      ? "Max 8 components"
                      : "Add component"}
                  </Button>

                  <label className="mt-3 flex items-center gap-2 text-sm text-on-surface">
                    <input
                      type="checkbox"
                      checked={state.sortByComposite}
                      onChange={(e) => onChange({ sortByComposite: e.target.checked })}
                      className="rounded border-outline-variant"
                    />
                    Sort by composite score
                  </label>

                  <div className="mt-4 space-y-2 rounded-md border border-outline-variant/40 p-3">
                    <p className="label-caps">Save index</p>
                    <Input
                      value={saveName}
                      onChange={(e) => setSaveName(e.target.value)}
                      placeholder="Name (e.g. Aerial + dribble)"
                    />
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => onSave(false)}
                        disabled={!state.compositeComponents.length}
                      >
                        {state.editingIndexId ? "Save" : "Save index"}
                      </Button>
                      {state.editingIndexId ? (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onSave(true)}
                          disabled={!state.compositeComponents.length}
                        >
                          Save as…
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-xs text-on-surface-variant">
                  Enable to build a weighted z-score index from metrics.
                </p>
              )}
            </TabsContent>

            <TabsContent value="saved" className="space-y-3 outline-none">
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="secondary" size="sm" onClick={onExport}>
                  <Download className="h-4 w-4" />
                  Export
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="h-4 w-4" />
                  Import
                </Button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) void onImportFile(file);
                  }}
                />
              </div>

              {indexes.length === 0 ? (
                <p className="text-sm text-on-surface-variant">No saved indexes yet.</p>
              ) : (
                <ul className="space-y-2">
                  {indexes.map((idx) => (
                    <li
                      key={idx.id}
                      className="flex flex-wrap items-center gap-2 rounded-md bg-surface-low p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-on-surface">{idx.name}</p>
                        <p className="text-xs text-on-surface-variant">
                          {idx.components.length} component
                          {idx.components.length === 1 ? "" : "s"}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          onChange({
                            editingIndexId: idx.id,
                            compositeEnabled: true,
                            compositeComponents: idx.components.map((c) => ({ ...c })),
                            sortByComposite: true,
                            sortBy: compositeMetricId(idx.id),
                          });
                          setSaveName(idx.name);
                          setStatusMsg(`Loaded “${idx.name}”.`);
                        }}
                      >
                        Load
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          const next = window.prompt("Rename index", idx.name);
                          if (next != null) renameIndex(idx.id, next);
                        }}
                      >
                        Rename
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          if (window.confirm(`Delete “${idx.name}”?`)) {
                            deleteIndex(idx.id);
                            if (state.editingIndexId === idx.id) {
                              onChange({ editingIndexId: null });
                            }
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          </Tabs>

          {statusMsg ? (
            <p className="mt-4 text-xs text-secondary">{statusMsg}</p>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={onApply}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
