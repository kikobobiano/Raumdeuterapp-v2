"""League tier grouping for scouting cohort z-scores.

Tiers are derived from ``LEAGUE_POWER_BASE`` (UEFA/club-power style ratings).
The point is to widen the z-score normalization pool when a user picks a
single low-data league: pool all leagues of similar strength so cohort n
is large enough for stable means/sds.
"""
from __future__ import annotations

from app.core.config import LEAGUE_POWER_BASE

TIER_T1 = "T1"  # Top-5 EU + similar
TIER_T2 = "T2"  # Strong second tiers + mid-Europe
TIER_T3 = "T3"  # Mid-tier
TIER_T4 = "T4"  # Lower

_TIER_BOUNDS: list[tuple[str, float]] = [
    (TIER_T1, 85.0),
    (TIER_T2, 78.0),
    (TIER_T3, 74.0),
    (TIER_T4, 0.0),
]


def tier_for(league: str | None) -> str:
    if not league:
        return TIER_T4
    rating = LEAGUE_POWER_BASE.get(league)
    if rating is None:
        return TIER_T4
    for name, lo in _TIER_BOUNDS:
        if rating >= lo:
            return name
    return TIER_T4


def leagues_in_tier(tier: str) -> list[str]:
    return [lg for lg in LEAGUE_POWER_BASE if tier_for(lg) == tier]


def tiers_of(leagues: list[str] | None) -> set[str]:
    if not leagues:
        return set()
    return {tier_for(lg) for lg in leagues}


def expand_leagues_by_tier(leagues: list[str] | None) -> list[str]:
    """Union of every league sharing a tier with any of the input leagues."""
    tiers = tiers_of(leagues)
    if not tiers:
        return list(LEAGUE_POWER_BASE.keys())
    out: set[str] = set()
    for t in tiers:
        out.update(leagues_in_tier(t))
    return sorted(out)
