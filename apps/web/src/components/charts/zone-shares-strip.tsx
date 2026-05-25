"use client";

import * as React from "react";

import {
  ZONE_COLOR,
  ZONE_LABEL,
  ZONE_ORDER,
  type AgeZone,
} from "./squad-age-minutes-scatter";

export interface ZoneShareValues {
  youth: number;
  peak: number;
  experienced: number;
  veteran: number;
}

interface Props {
  shares: ZoneShareValues;
  /** Optional context label shown above the bar (e.g. club name). */
  caption?: string;
}

export function ZoneSharesStrip({ shares, caption }: Props) {
  const total =
    shares.youth + shares.peak + shares.experienced + shares.veteran;
  const safe = total > 0 ? total : 1;

  return (
    <div className="flex flex-col gap-1.5">
      {caption && (
        <p className="text-[10px] font-semibold uppercase tracking-widest text-content-muted">
          {caption}
        </p>
      )}
      <div className="flex h-6 w-full overflow-hidden rounded-full ring-1 ring-inset ring-outline-variant/30">
        {ZONE_ORDER.map((zone: AgeZone) => {
          const v = shares[zone];
          if (v <= 0) return null;
          const w = (100 * v) / safe;
          return (
            <div
              key={zone}
              title={`${ZONE_LABEL[zone]} ${v.toFixed(1)}%`}
              className="h-full"
              style={{
                width: `${w}%`,
                background: `linear-gradient(180deg, ${ZONE_COLOR[zone]}dd 0%, ${ZONE_COLOR[zone]} 100%)`,
              }}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-content-muted">
        {ZONE_ORDER.map((zone) => (
          <span key={zone} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: ZONE_COLOR[zone] }}
            />
            <span className="text-on-surface-variant">{ZONE_LABEL[zone]}</span>
            <span
              className="font-semibold tabular-nums"
              style={{ color: ZONE_COLOR[zone] }}
            >
              {shares[zone].toFixed(1)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
