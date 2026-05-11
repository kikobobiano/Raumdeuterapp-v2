/**
 * Global scout filters: parent tactical roles + optional Wyscout sub-position tokens.
 * API `roles` accepts either parent names (expanded server-side) or raw tokens (LW, CMF, …).
 */

export type RoleSubTokensState = Record<string, string[]>;

export interface RolesFilterState {
  selectedRoles: string[];
  roleSubTokens: RoleSubTokensState;
}

export function rolesForApi(s: RolesFilterState): string[] {
  const out: string[] = [];
  for (const parent of s.selectedRoles) {
    const subs = s.roleSubTokens[parent];
    if (subs && subs.length > 0) out.push(...subs);
    else out.push(parent);
  }
  return [...new Set(out)];
}

export function emptyRolesFilter(): RolesFilterState {
  return { selectedRoles: [], roleSubTokens: {} };
}
