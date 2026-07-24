"use client";

import { Trash2 } from "lucide-react";
import * as React from "react";

import { MetricModeToggle, type MetricMode } from "@/components/domain/metric-mode-toggle";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";

export interface MetricSpec {
  metric: string;
  mode: MetricMode;
  weight: number;
  threshold_z: number | null;
}

interface Props {
  spec: MetricSpec;
  options: { value: string; label: string }[];
  supportsMode: boolean;
  onChange: (patch: Partial<MetricSpec>) => void;
  onRemove: () => void;
}

export function MetricWeightRow({ spec, options, supportsMode, onChange, onRemove }: Props) {
  return (
    <div className="space-y-2 rounded-md bg-surface-low p-3">
      <div className="flex gap-2">
        <Combobox
          value={spec.metric}
          onChange={(v) => onChange({ metric: v })}
          options={options}
          className="min-w-0 flex-1"
        />
        <MetricModeToggle
          supports={supportsMode}
          value={spec.mode}
          onChange={(mode) => onChange({ mode })}
        />
        <Button variant="ghost" size="sm" onClick={onRemove} aria-label="Remove metric">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <span className="label-caps">Weight</span>
            <span className="data-mono text-xs text-on-surface">{spec.weight.toFixed(1)}</span>
          </div>
          <Slider
            min={-2}
            max={3}
            step={0.1}
            value={[spec.weight]}
            onValueChange={([v]) => onChange({ weight: v })}
          />
        </div>
        <div className="w-32">
          <div className="flex items-center justify-between">
            <span className="label-caps">Min z</span>
            <span className="data-mono text-xs text-on-surface-variant">
              {spec.threshold_z != null ? spec.threshold_z.toFixed(1) : "—"}
            </span>
          </div>
          <Input
            type="number"
            step={0.1}
            placeholder="—"
            value={spec.threshold_z ?? ""}
            onChange={(e) =>
              onChange({
                threshold_z: e.target.value === "" ? null : parseFloat(e.target.value),
              })
            }
          />
        </div>
      </div>
    </div>
  );
}
