"""Squad-level aggregates for Team Metrics → Squad Value."""

from __future__ import annotations

import math
from typing import Any

from app.core.xtv_eligibility import xtv_parquet_sql

SQUAD_VALUE_QUALITY_MIN_MINUTES = 500


def compute_sample_zscores(values: list[float | None]) -> list[float | None]:
    """Sample z-scores; returns None when stdev is 0 or fewer than 2 finite values."""
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if len(finite) < 2:
        return [None] * len(values)
    mu = sum(finite) / len(finite)
    var = sum((v - mu) ** 2 for v in finite) / (len(finite) - 1)
    if var <= 0:
        return [None] * len(values)
    sigma = math.sqrt(var)
    out: list[float | None] = []
    for v in values:
        if v is None or not math.isfinite(v):
            out.append(None)
        else:
            out.append((v - mu) / sigma)
    return out


def quality_aggregate_sql(view: str, cols: set[str]) -> str:
    """Per-club avg PI and total xTV for players with >= ``SQUAD_VALUE_QUALITY_MIN_MINUTES``."""
    xtv_expr = xtv_parquet_sql(cols)
    pi_expr = (
        'CAST("performance_index" AS DOUBLE)'
        if "performance_index" in cols
        else "CAST(NULL AS DOUBLE)"
    )
    min_m = SQUAD_VALUE_QUALITY_MIN_MINUTES
    return f"""
        SELECT
            club,
            COUNT(*) AS n_players_500,
            AVG({pi_expr}) AS avg_performance_index,
            SUM({xtv_expr}) AS total_xtv_eur
        FROM {view}
        WHERE league = ?
          AND "Minutes played" IS NOT NULL
          AND CAST("Minutes played" AS INTEGER) >= {min_m}
        GROUP BY club
    """


def merge_quality_metrics(teams: list[dict[str, Any]], quality_rows: list[dict[str, Any]]) -> None:
    """Attach ``n_players_500``, ``avg_performance_index``, ``squad_xtv_zscore`` in-place."""
    by_club = {str(r["club"]): r for r in quality_rows if r.get("club")}
    totals: list[float | None] = []
    for team in teams:
        rec = by_club.get(team["club"], {})
        team["n_players_500"] = int(rec.get("n_players_500") or 0)
        avg_pi = rec.get("avg_performance_index")
        team["avg_performance_index"] = (
            float(avg_pi) if avg_pi is not None and float(avg_pi) == float(avg_pi) else None
        )
        total = rec.get("total_xtv_eur")
        team["_total_xtv_500"] = (
            float(total) if total is not None and float(total) == float(total) else None
        )
        totals.append(team["_total_xtv_500"])

    zscores = compute_sample_zscores(totals)
    for team, z in zip(teams, zscores, strict=True):
        team["squad_xtv_zscore"] = z
        team.pop("_total_xtv_500", None)
