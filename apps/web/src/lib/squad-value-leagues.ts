/** Must match `LEAGUES_EXCLUDED_FROM_SQUAD_VALUE` in apps/api `core/config.py`. */
export const SQUAD_VALUE_EXCLUDED_LEAGUES: ReadonlySet<string> = new Set([
  "Campeonato de Portugal",
]);

export function squadValueSelectableLeagues(leagues: readonly string[]): string[] {
  return leagues.filter((l) => !SQUAD_VALUE_EXCLUDED_LEAGUES.has(l));
}
