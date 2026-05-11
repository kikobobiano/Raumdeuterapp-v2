/**
 * Default comparison metrics per role — ported from raumdeuterapp/pages/7_Comparison.py PRESETS_RAW.
 * Used by ProfileComparePanel to scope the side-by-side metric table to the primary player's role.
 */

export const POSITION_PRESETS: Record<string, string[]> = {
  Defender: [
    "Minutes played",
    "Successful defensive actions per 90", "Defensive duels per 90", "Defensive duels won, %",
    "Aerial duels per 90", "Aerial duels won, %", "PAdj Interceptions", "Shots blocked per 90",
    "PAdj Sliding tackles", "Progressive passes per 90", "Passes per 90", "Accurate passes, %",
    "Passes to final third per 90",
  ],
  Fullback: [
    "Minutes played",
    "Dribbles per 90", "Successful dribbles, %", "Progressive runs per 90",
    "Progressive passes per 90", "Passes to penalty area per 90", "Accurate passes, %",
    "Crosses per 90", "Accurate crosses, %", "Successful defensive actions per 90",
    "PAdj Interceptions", "PAdj Sliding tackles",
  ],
  Midfielder: [
    "Minutes played",
    "Goals per 90", "Assists per 90", "xG per 90", "xA per 90",
    "Duels per 90", "Duels won, %", "Aerial duels won, %",
    "Interceptions per 90", "Successful defensive actions per 90",
    "Passes per 90", "Accurate passes, %", "Long passes per 90",
    "Progressive passes per 90", "Progressive runs per 90",
    "Key passes per 90", "Passes to final third per 90",
    "Accelerations per 90", "Dribbles per 90", "Successful dribbles, %",
    "Shots per 90",
  ],
  "Attacking Midfielder": [
    "Minutes played",
    "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
    "Key passes per 90", "Shot assists per 90", "Smart passes per 90",
    "Passes to penalty area per 90", "Through passes per 90",
    "Progressive passes per 90", "Passes per 90", "Accurate passes, %",
    "Passes to final third per 90",
    "Dribbles per 90", "Successful dribbles, %",
    "Progressive runs per 90", "Accelerations per 90",
    "Touches in box per 90", "Successful defensive actions per 90",
    "Shots per 90",
  ],
  Winger: [
    "Minutes played", "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
    "Dribbles per 90", "Successful dribbles, %", "Offensive duels per 90",
    "Progressive runs per 90", "Accelerations per 90", "Shots per 90",
    "Shots on target, %", "Passes to penalty area per 90",
  ],
  Forward: [
    "Minutes played",
    "Goals per 90", "xG per 90", "Shots per 90", "Assists per 90", "xA per 90",
    "Shots on target, %", "Touches in box per 90", "Progressive runs per 90",
    "Deep completions per 90", "Dribbles per 90", "Passes per 90",
    "Second assists per 90", "Offensive duels per 90", "Back passes per 90",
    "Successful dribbles, %",
  ],
  Goalkeeper: [
    "Minutes played",
    "Conceded goals per 90", "Shots against per 90", "Save rate, %",
    "Clean sheets", "Exits per 90", "Aerial duels per 90",
  ],
};

/** Map a Wyscout primary position string → preset role key. */
export function presetRoleForPosition(position: string | null | undefined): string {
  if (!position) return "Midfielder";
  const p = position.toUpperCase();
  if (p.includes("GK")) return "Goalkeeper";
  if (/\bCF|\bST/.test(p)) return "Forward";
  if (/\bRW\b|\bLW\b|\bRWF|\bLWF|RAMF|LAMF/.test(p)) return "Winger";
  if (p.includes("AMF") || p.includes("AMC")) return "Attacking Midfielder";
  if (/\bRB\b|\bLB\b|RWB|LWB|\bWB\b/.test(p)) return "Fullback";
  if (p.includes("CB") || /\bDF\b/.test(p)) return "Defender";
  return "Midfielder";
}

/** Order metrics by preset for the role; preset metrics first, then any extras alphabetically. */
export function orderMetricsByPreset(metrics: string[], role: string): string[] {
  const preset = POSITION_PRESETS[role] ?? POSITION_PRESETS.Midfielder;
  const inPreset = preset.filter((m) => metrics.includes(m));
  const extras = metrics.filter((m) => !preset.includes(m)).sort();
  return [...inPreset, ...extras];
}
