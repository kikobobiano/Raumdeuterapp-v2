const MAX_LEAGUES_IN_SUBTITLE = 5;

function normSortUnique(arr: readonly string[]): string[] {
  return [...new Set(arr)].sort((a, b) => a.localeCompare(b));
}

/** Comma list, capped at ``MAX_LEAGUES_IN_SUBTITLE`` then ``+ N leagues``. */
function formatLeagueNameList(leagues: readonly string[]): string {
  const sorted = normSortUnique(leagues);
  if (sorted.length <= MAX_LEAGUES_IN_SUBTITLE) {
    return sorted.join(", ");
  }
  const visible = sorted.slice(0, MAX_LEAGUES_IN_SUBTITLE);
  const rest = sorted.length - MAX_LEAGUES_IN_SUBTITLE;
  const suffix = rest === 1 ? "league" : "leagues";
  return `${visible.join(", ")} + ${rest} ${suffix}`;
}

function sameSortedSet(a: readonly string[], b: readonly string[]): boolean {
  const sa = normSortUnique(a);
  const sb = normSortUnique(b);
  if (sa.length !== sb.length) return false;
  return sa.every((v, i) => v === sb[i]);
}

/**
 * Human-readable league filter for chart headers: ``Big 5``, ``Outside Big 5``,
 * ``Big 5, Primeira Liga``, or a sorted comma list.
 *
 * @param selectedLeagues Empty = all leagues (handled by caller → "All leagues").
 * @param leagueOptions Season catalog (same fallback order as ``FilterPanel``).
 * @param bigFiveCanon API order or ``BIG_FIVE_LEAGUES``.
 */
export function formatLeaguesFilterLabel(
  selectedLeagues: readonly string[],
  leagueOptions: readonly string[],
  bigFiveCanon: readonly string[],
): string {
  if (selectedLeagues.length === 0) return "All leagues";

  const bigFiveSet = new Set(bigFiveCanon);
  const bigInScope = bigFiveCanon.filter((l) => leagueOptions.includes(l));
  const outsideScope = leagueOptions.filter((l) => !bigFiveSet.has(l));

  if (bigInScope.length > 0 && sameSortedSet(selectedLeagues, bigInScope)) {
    return "Big 5";
  }

  if (outsideScope.length > 0 && sameSortedSet(selectedLeagues, outsideScope)) {
    return "Outside Big 5";
  }

  const selBig = selectedLeagues.filter((l) => bigFiveSet.has(l));
  const selNonBig = selectedLeagues.filter((l) => !bigFiveSet.has(l));

  if (
    bigInScope.length > 0 &&
    sameSortedSet(selBig, bigInScope) &&
    selNonBig.length > 0
  ) {
    return `Big 5, ${formatLeagueNameList(selNonBig)}`;
  }

  return formatLeagueNameList(selectedLeagues);
}
