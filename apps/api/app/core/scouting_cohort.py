"""Cohort z-score / percentile helpers for the Scouting Discover endpoint.

Builds a *normalization pool* (players matching position + tier + season + min
minutes) and computes per-metric mean / sd in a single DuckDB pass. Includes
Bayesian shrinkage toward the cohort mean for low-minute players.
"""
from __future__ import annotations

from typing import Any, Literal

import duckdb

from app.core.filters import (
    PlayerFilters,
    not_goalkeeper_sql,
    role_filter_tokens,
    role_position_regex,
    view_name,
)
from app.core.league_tiers import expand_leagues_by_tier
from app.core.metric_modes import MetricMode
from app.core.metric_sql import metric_sql_expr

CohortTier = Literal["position_tier", "position_league", "position_global"]

DEFAULT_PRIOR_MINUTES = 900
COHORT_MIN_N = 30


def _cohort_where(
    filters: PlayerFilters,
    *,
    tier: CohortTier,
) -> tuple[str, list[Any]]:
    parts: list[str] = []
    params: list[Any] = []

    # League scope depends on tier.
    if tier == "position_league" and filters.leagues:
        parts.append(f"league IN ({','.join(['?'] * len(filters.leagues))})")
        params.extend(filters.leagues)
    elif tier == "position_tier" and filters.leagues:
        expanded = expand_leagues_by_tier(filters.leagues)
        if expanded:
            parts.append(f"league IN ({','.join(['?'] * len(expanded))})")
            params.extend(expanded)
    # tier == position_global → no league filter.

    # Position role (always applied for cohort to be apples-to-apples).
    if filters.roles:
        tokens = role_filter_tokens(filters.roles)
        pattern = role_position_regex(tokens)
        if pattern:
            parts.append('regexp_matches(coalesce("Primary position", Position, \'\'), ?)')
            params.append(pattern)

    # Minutes guard — cohort requires at least the user-requested floor, default 600.
    min_minutes = filters.minutes_min if filters.minutes_min is not None else 600
    parts.append('"Minutes played" >= ?')
    params.append(min_minutes)

    gk_sql, gk_params = not_goalkeeper_sql()
    parts.append(gk_sql)
    params.extend(gk_params)

    return " AND ".join(parts), params


def cohort_stats(
    conn: duckdb.DuckDBPyConnection,
    *,
    filters: PlayerFilters,
    tier: CohortTier,
    metrics_with_mode: list[tuple[str, MetricMode]],
) -> dict[str, Any]:
    """Return ``{n, means, sds, tier_used}`` for the cohort.

    Falls back to a wider tier when N < ``COHORT_MIN_N``:
    ``position_league`` → ``position_tier`` → ``position_global``.
    """
    view = view_name(filters.season)
    cascade: list[CohortTier]
    if tier == "position_league":
        cascade = ["position_league", "position_tier", "position_global"]
    elif tier == "position_tier":
        cascade = ["position_tier", "position_global"]
    else:
        cascade = ["position_global"]

    n_final = 0
    means: dict[str, float | None] = {}
    sds: dict[str, float | None] = {}
    used: CohortTier = cascade[0]

    for t in cascade:
        where_sql, params = _cohort_where(filters, tier=t)
        count_sql = f"SELECT COUNT(*) FROM {view} WHERE {where_sql}"
        n = int(conn.execute(count_sql, params).fetchone()[0])
        if n < COHORT_MIN_N and t != cascade[-1]:
            continue

        used = t
        n_final = n
        if n == 0:
            for m, _ in metrics_with_mode:
                means[m] = None
                sds[m] = None
            break

        select_parts: list[str] = []
        for i, (m, mode) in enumerate(metrics_with_mode):
            expr = metric_sql_expr(m, mode)
            select_parts.append(f"avg({expr}) AS m{i}")
            select_parts.append(f"stddev_samp({expr}) AS s{i}")
        stats_sql = f"SELECT {', '.join(select_parts)} FROM {view} WHERE {where_sql}"
        row = conn.execute(stats_sql, params).fetchone()
        for i, (m, _) in enumerate(metrics_with_mode):
            mu = row[2 * i]
            sd = row[2 * i + 1]
            means[m] = float(mu) if mu is not None else None
            sds[m] = float(sd) if sd is not None and sd > 1e-9 else None
        break

    return {"n": n_final, "means": means, "sds": sds, "tier_used": used}


def shrunk_zscore(
    value: float | None,
    *,
    mean: float | None,
    sd: float | None,
    player_minutes: int | None,
    prior_n: int = DEFAULT_PRIOR_MINUTES,
) -> float | None:
    """Bayesian-shrunken z-score: weights player value by minutes/(minutes+prior)."""
    if value is None or mean is None or sd is None or sd <= 0:
        return None
    m = float(player_minutes) if player_minutes else 0.0
    weight = m / (m + prior_n) if prior_n > 0 else 1.0
    shrunk = weight * value + (1.0 - weight) * mean
    z = (shrunk - mean) / sd
    if z > 6.0:
        z = 6.0
    elif z < -6.0:
        z = -6.0
    return float(z)


def percentile_rank(
    conn: duckdb.DuckDBPyConnection,
    *,
    view: str,
    where_sql: str,
    where_params: list[Any],
    metric: str,
    mode: MetricMode,
    value: float,
) -> float | None:
    """Fraction of cohort with metric <= value (0..1). NULL-safe via NULLIF guard."""
    expr = metric_sql_expr(metric, mode)
    sql = f"""
        SELECT
            COUNT(*) FILTER (WHERE ({expr}) IS NOT NULL) AS denom,
            COUNT(*) FILTER (WHERE ({expr}) IS NOT NULL AND ({expr}) <= ?) AS numer
        FROM {view}
        WHERE {where_sql}
    """
    row = conn.execute(sql, [value, *where_params]).fetchone()
    denom = int(row[0]) if row[0] is not None else 0
    if denom <= 0:
        return None
    return float(row[1]) / denom


def cohort_where_for_player_set(
    filters: PlayerFilters,
    *,
    tier: CohortTier,
) -> tuple[str, list[Any]]:
    """Public alias for percentile callers that need to reuse the cohort filter."""
    return _cohort_where(filters, tier=tier)
