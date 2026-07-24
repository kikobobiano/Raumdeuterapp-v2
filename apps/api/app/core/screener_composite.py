"""Weighted z-score composite scoring for the Screener endpoint.

Supports two component bases:
- ``value``: z-score the metric within a position+league cohort.
- ``team_median``: z-score ``player_value / team_median`` within the same cohort.

Team medians are computed over outfield teammates with ``Minutes played >= 300``.
"""
from __future__ import annotations

from typing import Any, Literal

import duckdb
import numpy as np

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.filters import PlayerFilters, build_where, not_goalkeeper_sql, view_name
from app.core.metric_modes import MetricMode
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.core.scouting_cohort import cohort_stats, cohort_where_for_player_set, shrunk_zscore

CompositeBasis = Literal["value", "team_median"]
CompositeInput = tuple[str, MetricMode, CompositeBasis, float]

TEAM_MEDIAN_MIN_MINUTES = 300
MAX_CANDIDATES = 5000


def _component_key(metric: str, mode: MetricMode, basis: CompositeBasis) -> str:
    return f"{metric}|{mode}|{basis}"


def _mean_sd(values: list[float | None]) -> tuple[float | None, float | None]:
    arr = np.array([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return None, None
    mu = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1)) if arr.size > 1 else None
    if sd is not None and sd <= 1e-9:
        sd = None
    return mu, sd


def team_medians(
    conn: duckdb.DuckDBPyConnection,
    *,
    view: str,
    metric: str,
    mode: MetricMode,
) -> dict[str, float]:
    """Return ``club -> median(metric)`` for outfield players with enough minutes."""
    expr = metric_sql_expr(metric, mode)
    gk_sql, gk_params = not_goalkeeper_sql()
    sql = f"""
        SELECT club, median(({expr})) AS med
        FROM {view}
        WHERE club IS NOT NULL
          AND "Minutes played" >= ?
          AND {gk_sql}
        GROUP BY club
    """
    rows = conn.execute(sql, [TEAM_MEDIAN_MIN_MINUTES, *gk_params]).fetchall()
    out: dict[str, float] = {}
    for club, med in rows:
        if club is not None and med is not None and float(med) > 0:
            out[str(club)] = float(med)
    return out


def _build_component_stats(
    conn: duckdb.DuckDBPyConnection,
    *,
    view: str,
    filters: PlayerFilters,
    components: list[CompositeInput],
) -> tuple[dict[str, tuple[float | None, float | None]], dict[str, dict[str, float]]]:
    """Return per-component (mean, sd) and per-component team-median lookup tables."""
    stats: dict[str, tuple[float | None, float | None]] = {}
    team_median_maps: dict[str, dict[str, float]] = {}

    value_specs = [(m, mode) for m, mode, basis, _w in components if basis == "value"]
    cohort_tier_used = "position_league"
    if value_specs:
        cohort = cohort_stats(
            conn,
            filters=filters,
            tier="position_league",
            metrics_with_mode=value_specs,
        )
        cohort_tier_used = cohort["tier_used"]
        for metric, mode in value_specs:
            key = _component_key(metric, mode, "value")
            stats[key] = (cohort["means"].get(metric), cohort["sds"].get(metric))

    team_specs = [(m, mode) for m, mode, basis, _w in components if basis == "team_median"]
    if not team_specs:
        return stats, team_median_maps

    cohort_where, cohort_params = cohort_where_for_player_set(filters, tier=cohort_tier_used)
    alias_expr: dict[str, str] = {}
    for i, (metric, mode) in enumerate(team_specs):
        alias = f"tm{i}"
        alias_expr[alias] = metric_sql_expr(metric, mode)

    select_exprs = [f"({expr}) AS {alias}" for alias, expr in alias_expr.items()]
    cohort_sql = (
        f'SELECT club, "Minutes played" AS minutes, {", ".join(select_exprs)} '
        f"FROM {view} WHERE {cohort_where}"
    )
    cohort_res = conn.execute(cohort_sql, cohort_params)
    cohort_desc = cohort_res.description
    cohort_cols = [d[0] for d in cohort_desc] if cohort_desc else []
    cohort_rows = [dict(zip(cohort_cols, tup, strict=True)) for tup in cohort_res.fetchall()]

    for i, (metric, mode) in enumerate(team_specs):
        key = _component_key(metric, mode, "team_median")
        alias = f"tm{i}"
        med_map = team_medians(conn, view=view, metric=metric, mode=mode)
        team_median_maps[key] = med_map
        ratios: list[float | None] = []
        for rec in cohort_rows:
            raw = rec.get(alias)
            club = rec.get("club")
            if raw is None or club is None:
                ratios.append(None)
                continue
            med = med_map.get(str(club))
            if med is None or med <= 0:
                ratios.append(None)
                continue
            ratios.append(float(raw) / med)
        stats[key] = _mean_sd(ratios)

    return stats, team_median_maps


def _score_record(
    rec: dict[str, Any],
    *,
    components: list[tuple[str, MetricMode, CompositeBasis, float, str]],
    stats: dict[str, tuple[float | None, float | None]],
    team_median_maps: dict[str, dict[str, float]],
) -> float | None:
    num = 0.0
    wsum = 0.0
    any_z = False
    for metric, mode, basis, weight, alias in components:
        raw = rec.get(alias)
        if raw is None:
            continue
        value = float(raw)
        key = _component_key(metric, mode, basis)
        if basis == "team_median":
            club = rec.get("club")
            if club is None:
                continue
            med = team_median_maps.get(key, {}).get(str(club))
            if med is None or med <= 0:
                continue
            value = value / med
        mu, sd = stats.get(key, (None, None))
        z = shrunk_zscore(value, mean=mu, sd=sd, player_minutes=rec.get("minutes"))
        if z is None:
            continue
        num += weight * z
        wsum += abs(weight)
        any_z = True
    if not any_z or wsum <= 0:
        return None
    return num / wsum


def score_candidates(
    conn: duckdb.DuckDBPyConnection,
    *,
    filters: PlayerFilters,
    components: list[CompositeInput],
    candidates: list[dict[str, Any]],
    metric_aliases: dict[str, str],
) -> list[float | None]:
    """Return composite score per candidate row (same order as ``candidates``).

    Cohort / team-median baselines are computed **per season** when candidates
    span multiple seasons (``rec["season"]``).
    """
    if not components or not candidates:
        return [None] * len(candidates)

    comp_rows: list[tuple[str, MetricMode, CompositeBasis, float, str]] = []
    for metric, mode, basis, weight in components:
        alias = metric_aliases.get(_component_key(metric, mode, basis))
        if alias is None:
            continue
        comp_rows.append((metric, mode, basis, weight, alias))

    by_season: dict[int, list[int]] = {}
    for i, rec in enumerate(candidates):
        raw = rec.get("season")
        season = int(raw) if raw is not None else int(filters.season)
        by_season.setdefault(season, []).append(i)

    out: list[float | None] = [None] * len(candidates)
    for season, idxs in by_season.items():
        season_filters = filters.model_copy(update={"season": season})
        view = view_name(season)
        stats, team_median_maps = _build_component_stats(
            conn, view=view, filters=season_filters, components=components
        )
        for i in idxs:
            out[i] = _score_record(
                candidates[i],
                components=comp_rows,
                stats=stats,
                team_median_maps=team_median_maps,
            )
    return out


def _metric_select_exprs(
    criteria_metrics: list[tuple[str, MetricMode]],
    composite_components: list[CompositeInput],
    sort_by: str | None,
    sort_mode: MetricMode,
) -> tuple[dict[str, str], dict[str, str]]:
    metric_aliases: dict[str, str] = {}
    select_exprs: dict[str, str] = {}
    for i, (metric, mode) in enumerate(criteria_metrics):
        alias = f"_c{i}"
        select_exprs[alias] = metric_sql_expr(metric, mode)

    comp_idx = 0
    seen_keys: set[str] = set()
    for metric, mode, basis, _w in composite_components:
        key = _component_key(metric, mode, basis)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        alias = f"_comp{comp_idx}"
        comp_idx += 1
        metric_aliases[key] = alias
        select_exprs[alias] = metric_sql_expr(metric, mode)

    if sort_by:
        select_exprs["_sort"] = metric_sql_expr(sort_by, sort_mode)
    return select_exprs, metric_aliases


def fetch_screener_candidates(
    conn: duckdb.DuckDBPyConnection,
    *,
    seasons: list[int],
    filters: PlayerFilters,
    criteria_sql: str,
    criteria_params: list[Any],
    criteria_metrics: list[tuple[str, MetricMode]],
    composite_components: list[CompositeInput],
    sort_by: str | None,
    sort_mode: MetricMode,
) -> tuple[list[dict[str, Any]], int, dict[str, str]]:
    """Fetch filtered candidates across seasons (capped) for composite scoring."""
    select_exprs, metric_aliases = _metric_select_exprs(
        criteria_metrics, composite_components, sort_by, sort_mode
    )

    branch_sqls: list[str] = []
    all_params: list[Any] = []
    for season in seasons:
        view = view_name(season)
        vcols = column_names_in_view(conn, view)
        where_sql, params = build_where(filters, cols=vcols, season=season)
        if criteria_sql:
            where_sql = (where_sql + " AND " if where_sql else "") + criteria_sql
            params = [*params, *criteria_params]
        where = f"WHERE {where_sql}" if where_sql else ""
        age_sel = player_age_sql(vcols, season)

        base_cols = [
            f"{int(season)} AS season",
            club_logo_select_sql(conn, view, season),
            '"Wyscout id" AS wyscout_id',
            '"Player" AS player',
            "club",
            "league",
            '"Primary position" AS position',
            f"({age_sel}) AS age",
            '"Minutes played" AS minutes',
        ]
        select_parts = [*base_cols]
        for alias, expr in select_exprs.items():
            select_parts.append(f"({expr}) AS {alias}")

        branch_sqls.append(
            f"SELECT {', '.join(select_parts)} FROM {view} {where}"
        )
        all_params.extend(params)

    union_sql = " UNION ALL ".join(f"({b})" for b in branch_sqls)
    count_sql = f"SELECT COUNT(*) FROM ({union_sql}) AS screener_u"
    total = int(conn.execute(count_sql, all_params).fetchone()[0])

    sql = f"""
        SELECT * FROM ({union_sql}) AS screener_u
        LIMIT {MAX_CANDIDATES}
    """
    result = conn.execute(sql, all_params)
    desc = result.description
    col_names = [d[0] for d in desc] if desc else []
    records = [dict(zip(col_names, tup, strict=True)) for tup in result.fetchall()]
    for rec in records:
        rec["club_logo"] = normalize_club_logo(rec.get("club_logo"))
    return records, total, metric_aliases
