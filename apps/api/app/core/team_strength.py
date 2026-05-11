"""Team-level strength adjustment for performance translation.

Port of legacy `utils/team_profile_scoring.compute_strength_adjustment` and
`utils/transforms.get_league_power_multiplier`. Reads from the
``team_profiles`` parquet (data/teams/profiles/team_profiles.parquet) via
DuckDB.
"""
from __future__ import annotations

import math

import numpy as np

from app.core.config import (
    LEAGUE_POWER_BASE,
    LEAGUE_POWER_MAX_ADJUSTED,
    LEAGUE_POWER_MIN_ADJUSTED,
)
from app.core.duckdb_pool import fetch_all_dicts

# xG context clamps + conservative shrink (match legacy values)
STRENGTH_ADJ_MIN = 0.90
STRENGTH_ADJ_MAX = 1.10
STRENGTH_ADJ_CONSERVATIVE_FRACTION = 0.45

TIER_DOMINANCE_Z_CLIP = 2.0
TIER_WITHIN_LEAGUE_COEF = 0.03

STRENGTH_LEAGUE_ADJ_MIN = 0.85
STRENGTH_LEAGUE_ADJ_MAX = 1.15

STRENGTH_ADJ_OUTPUT_MIN = 0.72
STRENGTH_ADJ_OUTPUT_MAX = 1.28


def donut_color(pct: float) -> str:
    """Match legacy `utils/plotting._donut_color` thresholds (used for translation peer dots)."""
    if pct < 40:
        return "#DC0C00"
    if pct < 55:
        return "#ED7E07"
    if pct < 65:
        return "#D9AF00"
    if pct < 80:
        return "#00C424"
    if pct < 90:
        return "#00ADC4"
    return "#374DF5"


def default_target_leagues_by_power(
    *,
    source_league: str,
    leagues_in_target_season: list[str],
    max_leagues: int = 6,
) -> list[str]:
    """Match legacy `utils/transforms.default_target_leagues_by_power`."""
    cap = max(1, int(max_leagues))
    pool = {str(lg).strip() for lg in leagues_in_target_season if str(lg).strip()}
    if not pool:
        return []

    pairs: list[tuple[str, float]] = [
        (lg, float(LEAGUE_POWER_BASE[lg]))
        for lg in pool
        if lg in LEAGUE_POWER_BASE
    ]
    pw = LEAGUE_POWER_BASE.get(str(source_league or "").strip())
    if pw is None:
        return sorted(pool)[:cap]

    pvf = float(pw)
    above = [lg for lg, _ in sorted((x for x in pairs if x[1] > pvf), key=lambda x: (x[1], x[0]))]
    below = [lg for lg, _ in sorted((x for x in pairs if x[1] < pvf), key=lambda x: (-x[1], x[0]))]

    out: list[str] = []
    seen: set[str] = set()
    src = str(source_league or "").strip()
    if src and src in pool:
        out.append(src)
        seen.add(src)

    for lg in above + below:
        if len(out) >= cap:
            break
        if lg not in seen:
            out.append(lg)
            seen.add(lg)

    if len(out) < cap:
        for lg in sorted(pool):
            if len(out) >= cap:
                break
            if lg not in seen:
                out.append(lg)
                seen.add(lg)

    return out


def get_league_power_multiplier(league: str) -> float:
    if league not in LEAGUE_POWER_BASE:
        return 1.0
    lp = LEAGUE_POWER_BASE[league]
    lo = min(LEAGUE_POWER_BASE.values())
    hi = max(LEAGUE_POWER_BASE.values())
    if hi == lo:
        return 1.0
    norm = (lp - lo) / (hi - lo)
    return LEAGUE_POWER_MIN_ADJUSTED + norm * (
        LEAGUE_POWER_MAX_ADJUSTED - LEAGUE_POWER_MIN_ADJUSTED
    )


def _clamp(v: float, lo: float, hi: float) -> float:
    if not np.isfinite(v):
        return 1.0
    return max(lo, min(hi, v))


def compute_strength_adjustment(
    conn, team: str | None, league: str | None, season: int
) -> tuple[float, dict]:
    """Return ``(adj, meta)`` where meta has the three component factors.

    ``adj`` defaults to 1.0 (league-average team) when team/league missing or
    the team_profiles view is not registered. The ``meta`` dict surfaces the
    three components for transparent display in the UI.
    """
    meta = {
        "xg_factor": 1.0,
        "tier_factor": 1.0,
        "league_factor": 1.0,
        "raw_team_xg_p90": None,
        "raw_league_avg_xg_p90": None,
        "dominance_z": 0.0,
        "available": False,
    }
    if not team or not league:
        return 1.0, meta

    try:
        league_rows = fetch_all_dicts(
            conn,
            "SELECT xg_p90, dominance_index_z, team FROM team_profiles "
            "WHERE league = ? AND season = ?",
            [league, int(season)],
        )
    except Exception:
        return 1.0, meta

    if not league_rows:
        return 1.0, meta

    league_xgs = [
        r["xg_p90"] for r in league_rows
        if r.get("xg_p90") is not None and r["xg_p90"] == r["xg_p90"]
    ]
    if not league_xgs:
        return 1.0, meta
    league_avg = float(np.mean(league_xgs))

    team_row = next((r for r in league_rows if r.get("team") == team), None)
    if team_row is None:
        return 1.0, meta

    team_xg = team_row.get("xg_p90")
    if team_xg is None or team_xg != team_xg or team_xg <= 0:
        return 1.0, meta

    raw = league_avg / float(team_xg)
    xg_clamped = _clamp(raw, STRENGTH_ADJ_MIN, STRENGTH_ADJ_MAX)
    xg_eff = 1.0 + STRENGTH_ADJ_CONSERVATIVE_FRACTION * (xg_clamped - 1.0)

    dom_z = team_row.get("dominance_index_z") or 0.0
    if dom_z != dom_z:  # NaN
        dom_z = 0.0
    dom_clip = float(np.clip(dom_z, -TIER_DOMINANCE_Z_CLIP, TIER_DOMINANCE_Z_CLIP))
    tier_mult = 1.0 + TIER_WITHIN_LEAGUE_COEF * dom_clip

    if league in LEAGUE_POWER_BASE:
        lpm = get_league_power_multiplier(league)
        rng = LEAGUE_POWER_MAX_ADJUSTED - LEAGUE_POWER_MIN_ADJUSTED
        if rng > 1e-12:
            league_mult = STRENGTH_LEAGUE_ADJ_MIN + (
                lpm - LEAGUE_POWER_MIN_ADJUSTED
            ) / rng * (STRENGTH_LEAGUE_ADJ_MAX - STRENGTH_LEAGUE_ADJ_MIN)
        else:
            league_mult = 1.0
    else:
        league_mult = 1.0

    combined_raw = float(xg_eff) * tier_mult * float(league_mult)
    combined = _clamp(combined_raw, STRENGTH_ADJ_OUTPUT_MIN, STRENGTH_ADJ_OUTPUT_MAX)

    meta.update(
        {
            "xg_factor": float(xg_eff),
            "tier_factor": float(tier_mult),
            "league_factor": float(league_mult),
            "raw_team_xg_p90": float(team_xg),
            "raw_league_avg_xg_p90": float(league_avg),
            "dominance_z": float(dom_z),
            "available": True,
            "clamped": not math.isclose(combined_raw, combined, abs_tol=1e-5),
        }
    )

    return float(combined), meta


def translate_performance_index(
    source_index: float,
    source_league: str,
    target_league: str,
    *,
    strength_adj_source: float = 1.0,
    strength_adj_target: float = 1.0,
) -> float | None:
    """Project ``source_index`` into target league using legacy formula.

    ``raw = source_index * adj_src * (P_src / P_tgt) / adj_tgt``, capped at 100.
    """
    if source_index is None or not np.isfinite(source_index):
        return None
    if (
        not np.isfinite(strength_adj_source)
        or not np.isfinite(strength_adj_target)
        or strength_adj_target == 0.0
    ):
        return None
    p_src = LEAGUE_POWER_BASE.get(source_league)
    p_tgt = LEAGUE_POWER_BASE.get(target_league)
    if p_src is None or p_tgt is None or p_tgt == 0:
        return None
    raw = (
        float(source_index)
        * float(strength_adj_source)
        * (float(p_src) / float(p_tgt))
        / float(strength_adj_target)
    )
    if not np.isfinite(raw):
        return None
    return min(float(raw), 100.0)
