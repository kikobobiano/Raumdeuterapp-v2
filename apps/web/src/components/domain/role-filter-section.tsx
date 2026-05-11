"use client";

import * as React from "react";

import type { RolesFilterState } from "@/lib/role-filters";
import { cn } from "@/lib/utils";

interface Props {
  value: RolesFilterState;
  onChange: (next: RolesFilterState) => void;
  /** From GET /meta/roles */
  rolesList: string[];
  /** From GET /meta/role-tokens */
  roleTokensMap: Record<string, string[]> | undefined;
  /** Section title (e.g. "Roles" vs "Position (role)") */
  title?: string;
  helpText?: string;
}

export function RoleFilterSection({
  value,
  onChange,
  rolesList,
  roleTokensMap,
  title = "Roles",
  helpText = "Multi-select. None = any outfield position. Pick a role, then narrow by Wyscout codes.",
}: Props) {
  const toggleParent = (role: string) => {
    const has = value.selectedRoles.includes(role);
    const selectedRoles = has
      ? value.selectedRoles.filter((r) => r !== role)
      : [...value.selectedRoles, role];
    const roleSubTokens = { ...value.roleSubTokens };
    if (has) delete roleSubTokens[role];
    onChange({ selectedRoles, roleSubTokens });
  };

  const toggleSub = (role: string, token: string) => {
    if (!value.selectedRoles.includes(role)) return;
    const all = roleTokensMap?.[role] ?? [];
    const cur = value.roleSubTokens[role];
    const roleSubTokens = { ...value.roleSubTokens };

    if (!cur || cur.length === 0) {
      roleSubTokens[role] = [token];
      onChange({ selectedRoles: value.selectedRoles, roleSubTokens });
      return;
    }

    const set = new Set(cur);
    if (set.has(token)) set.delete(token);
    else set.add(token);

    if (set.size === 0 || (all.length > 0 && set.size === all.length)) {
      delete roleSubTokens[role];
    } else {
      roleSubTokens[role] = [...set].sort((a, b) => a.localeCompare(b));
    }
    onChange({ selectedRoles: value.selectedRoles, roleSubTokens });
  };

  const clear = () => onChange({ selectedRoles: [], roleSubTokens: {} });

  const hasSelection = value.selectedRoles.length > 0;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="label-caps">{title}</p>
        {hasSelection && (
          <button type="button" className="shrink-0 text-xs text-primary hover:underline" onClick={clear}>
            Clear
          </button>
        )}
      </div>
      <p className="mb-2 text-xs text-on-surface-variant">{helpText}</p>

      <div className="space-y-3">
        {rolesList.map((role) => {
          const selected = value.selectedRoles.includes(role);
          const subs = roleTokensMap?.[role] ?? [];
          const activeSubs = value.roleSubTokens[role];
          const narrowed = Boolean(activeSubs && activeSubs.length > 0);

          return (
            <div key={role}>
              <button
                type="button"
                onClick={() => toggleParent(role)}
                className={cn(
                  "rounded-md border px-2.5 py-1.5 text-left text-xs font-medium transition-colors",
                  selected
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-outline-variant/50 bg-surface-low text-on-surface hover:bg-surface-mid",
                )}
              >
                {role}
                {selected && subs.length > 0 && narrowed ? (
                  <span className="ml-1.5 font-normal text-on-surface-variant">
                    ({activeSubs!.length}/{subs.length} codes)
                  </span>
                ) : null}
              </button>

              {selected && subs.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5 pl-0.5">
                  {subs.map((tok) => {
                    const on =
                      !narrowed ||
                      (activeSubs != null && activeSubs.includes(tok));
                    return (
                      <button
                        key={`${role}-${tok}`}
                        type="button"
                        onClick={() => toggleSub(role, tok)}
                        className={cn(
                          "rounded border px-2 py-0.5 font-mono text-[0.65rem] font-medium transition-colors",
                          on
                            ? "border-primary/50 bg-primary/10 text-primary"
                            : "border-outline-variant/40 bg-surface-mid/80 text-on-surface-variant line-through opacity-70",
                        )}
                      >
                        {tok}
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
