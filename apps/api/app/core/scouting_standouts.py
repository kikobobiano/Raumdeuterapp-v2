"""League-relative 'Standouts' scoring for the Scouting area.

Given a single-league cohort (position + league + min minutes, GK excluded),
rank players by how far above the league average they perform. Two signals:

- ``overall``: z-score of the precomputed per-league ``performance_index``.
  The strength breakdown reports z of the six game-area indices so the user can
  see *where* a player excels.
- ``metrics``: weighted composite of z-scores over user-picked metrics; the
  breakdown reports those metrics.

Normalization pool = the single-league cohort from
:func:`app.core.scouting_cohort.cohort_where_for_player_set` (tier
``position_league``). Player z is Bayesian-shrunk toward the cohort mean for
low-minute players via :func:`app.core.scouting_cohort.shrunk_zscore`.
"""
from __future__ import annotations

from typing import Any

import duckdb
import numpy as np

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.config import AREA_INDEX_COLS, METRIC_DISPLAY_LABELS
from app.core.filters import PlayerFilters, build_where, view_name
from app.core.metric_modes import MetricMode, format_selectbox_option_display
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.core.scouting_cohort import cohort_where_for_player_set, shrunk_zscore

PERFORMANCE_INDEX_COL = "performance_index"
DEFAULT_MIN_MINUTES = 600
DISTRIBUTION_CAP = 1000

MetricInput = tuple[str, MetricMode, float]


def _dim_label(key: str) -> str:
    return METRIC_DISPLAY_LABELS.get(key) or format_selectbox_option_display(key)


def _mean_sd(values: list[float | None]) -> tuple[float | None, float | None]:
    arr = np.array([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return None, None
    mu = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1)) if arr.size > 1 else None
    if sd is not None and sd <= 1e-9:
        sd = None
    return mu, sd


def _percentile(cohort_values: list[float | None], value: float | None) -> float | None:
    if value is None:
        return None
    arr = np.array([v for v in cohort_values if v is not None], dtype=float)
    if arr.size == 0:
        return None
    return float(np.mean(arr <= value))


def _empty_result(
    *, league: str | None, min_minutes: int, signal: str, metric_labels: dict[str, str]
) -> dict[str, Any]:
    return {
        "rows": [],
        "total": 0,
        "league": league,
        "cohort_n": 0,
        "min_minutes": min_minutes,
        "signal": signal,
        "distribution": [],
        "league_mean": None,
        "league_sd": None,
        "metric_labels": metric_labels,
    }


def compute_standouts(
    conn: duckdb.DuckDBPyConnection,
    *,
    filters: PlayerFilters,
    signal: str,
    metrics: list[MetricInput],
    min_standout_z: float,
    limit: int,
) -> dict[str, Any]:
    """Rank single-league standouts. Returns a dict shaped for ``StandoutResponse``."""
    view = view_name(filters.season)
    vcols = column_names_in_view(conn, view)
    # Cohort pools all selected leagues; label the result only when it's unambiguous.
    league = filters.leagues[0] if filters.leagues and len(filters.leagues) == 1 else None
    min_minutes = filters.minutes_min if filters.minutes_min is not None else DEFAULT_MIN_MINUTES

    # Scoring columns build the standout score; dimension columns are the strength breakdown.
    # (key, sql_expr, weight, alias)
    score_cols: list[tuple[str, str, float, str]] = []
    dim_cols: list[tuple[str, str, str]] = []  # (key, sql_expr, alias)

    if signal == "overall":
        if PERFORMANCE_INDEX_COL not in vcols:
            return _empty_result(
                league=league, min_minutes=min_minutes, signal=signal, metric_labels={}
            )
        score_cols.append((PERFORMANCE_INDEX_COL, f'"{PERFORMANCE_INDEX_COL}"', 1.0, "s0"))
        for i, col in enumerate([c for c in AREA_INDEX_COLS if c in vcols]):
            dim_cols.append((col, f'"{col}"', f"d{i}"))
    else:
        for i, (name, mode, weight) in enumerate(metrics):
            alias = f"s{i}"
            expr = metric_sql_expr(name, mode)
            score_cols.append((name, expr, weight, alias))
            dim_cols.append((name, expr, alias))

    metric_labels = {key: _dim_label(key) for (key, *_rest) in (*score_cols, *dim_cols)}

    # Distinct (alias -> expr) so we fetch each expression once.
    alias_expr: dict[str, str] = {}
    for key, expr, _w, alias in score_cols:
        alias_expr[alias] = expr
    for key, expr, alias in dim_cols:
        alias_expr[alias] = expr

    select_exprs = [f"({expr}) AS {alias}" for alias, expr in alias_expr.items()]

    # ── Cohort pool (single league) → per-column mean/sd + score distribution. ──
    cohort_where, cohort_params = cohort_where_for_player_set(filters, tier="position_league")
    cohort_sql = (
        f'SELECT "Wyscout id" AS wyscout_id, "Minutes played" AS minutes, '
        f"{', '.join(select_exprs)} FROM {view} WHERE {cohort_where}"
    )
    cohort_res = conn.execute(cohort_sql, cohort_params)
    cohort_desc = cohort_res.description
    cohort_cols = [d[0] for d in cohort_desc] if cohort_desc else []
    cohort = [dict(zip(cohort_cols, tup, strict=True)) for tup in cohort_res.fetchall()]
    cohort_n = len(cohort)
    if cohort_n == 0:
        return _empty_result(
            league=league, min_minutes=min_minutes, signal=signal, metric_labels=metric_labels
        )

    stats: dict[str, tuple[float | None, float | None]] = {}
    cohort_values: dict[str, list[float | None]] = {}
    for alias in alias_expr:
        vals = [
            (float(r[alias]) if r.get(alias) is not None else None) for r in cohort
        ]
        cohort_values[alias] = vals
        stats[alias] = _mean_sd(vals)

    def _score_row(rec: dict[str, Any]) -> float | None:
        num = 0.0
        wsum = 0.0
        any_z = False
        for _key, _expr, weight, alias in score_cols:
            mu, sd = stats[alias]
            raw = rec.get(alias)
            z = shrunk_zscore(
                float(raw) if raw is not None else None,
                mean=mu,
                sd=sd,
                player_minutes=rec.get("minutes"),
            )
            if z is None:
                continue
            num += weight * z
            wsum += abs(weight)
            any_z = True
        if not any_z or wsum <= 0:
            return None
        return num / wsum

    dist_scores = [s for r in cohort if (s := _score_row(r)) is not None]
    dist_arr = np.array(dist_scores, dtype=float)
    league_mean = float(np.mean(dist_arr)) if dist_arr.size else None
    league_sd = float(np.std(dist_arr, ddof=1)) if dist_arr.size > 1 else None
    distribution = [round(v, 4) for v in dist_scores[:DISTRIBUTION_CAP]]

    # ── Candidate set (user filters) → score, filter, rank. ──
    age_sel = player_age_sql(vcols, filters.season)
    logo_sel = club_logo_select_sql(conn, view, filters.season)
    photo_sel = player_image_select_sql(conn, view)
    has_pi = PERFORMANCE_INDEX_COL in vcols

    where_sql, where_params = build_where(filters, cols=vcols)
    where_clause = f"WHERE {where_sql}" if where_sql else ""
    base_cols = [
        logo_sel,
        photo_sel,
        '"Wyscout id" AS wyscout_id',
        '"Player" AS player',
        "club",
        "league",
        '"Primary position" AS position',
        f"({age_sel}) AS age",
        '"Minutes played" AS minutes',
        (
            f'CAST("{PERFORMANCE_INDEX_COL}" AS DOUBLE) AS performance_index'
            if has_pi
            else "CAST(NULL AS DOUBLE) AS performance_index"
        ),
        *select_exprs,
    ]
    cand_sql = f"SELECT {', '.join(base_cols)} FROM {view} {where_clause}"
    cand_res = conn.execute(cand_sql, where_params)
    cand_desc = cand_res.description
    cand_cols = [d[0] for d in cand_desc] if cand_desc else []
    candidates = [dict(zip(cand_cols, tup, strict=True)) for tup in cand_res.fetchall()]

    scored: list[tuple[float, dict[str, Any]]] = []
    for rec in candidates:
        score = _score_row(rec)
        if score is None or score < min_standout_z:
            continue
        dims: list[dict[str, Any]] = []
        for key, _expr, alias in dim_cols:
            mu, sd = stats[alias]
            raw = rec.get(alias)
            v = float(raw) if raw is not None else None
            z = shrunk_zscore(v, mean=mu, sd=sd, player_minutes=rec.get("minutes"))
            dims.append(
                {
                    "key": key,
                    "label": metric_labels.get(key, key),
                    "value": v,
                    "z": z,
                    "percentile": _percentile(cohort_values[alias], v),
                }
            )
        dims.sort(key=lambda d: (d["z"] is not None, d["z"] or 0.0), reverse=True)
        pi_raw = rec.get("performance_index")
        scored.append(
            (
                score,
                {
                    "wyscout_id": rec.get("wyscout_id"),
                    "player": rec.get("player") or "",
                    "club": rec.get("club"),
                    "club_logo": normalize_club_logo(rec.get("club_logo")),
                    "league": rec.get("league"),
                    "position": rec.get("position"),
                    "age": rec.get("age"),
                    "minutes": rec.get("minutes"),
                    "player_image_url": rec.get("player_image_url"),
                    "performance_index": float(pi_raw) if pi_raw is not None else None,
                    "standout_score": score,
                    "dimensions": dims,
                },
            )
        )

    scored.sort(key=lambda t: t[0], reverse=True)
    total = len(scored)
    rows = [r for _s, r in scored[:limit]]

    return {
        "rows": rows,
        "total": total,
        "league": league,
        "cohort_n": cohort_n,
        "min_minutes": min_minutes,
        "signal": signal,
        "distribution": distribution,
        "league_mean": league_mean,
        "league_sd": league_sd,
        "metric_labels": metric_labels,
    }
