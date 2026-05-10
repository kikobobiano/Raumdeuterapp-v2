"""Batch percentile computation over one league cohort (profile route)."""

from __future__ import annotations

from collections.abc import Sequence

import duckdb

from app.core.sql_ident import q_ident


def percentiles_for_cohort(
    conn: duckdb.DuckDBPyConnection,
    view: str,
    items: Sequence[tuple[str, float]],
    cohort_where_sql: str,
    cohort_params: list[object],
) -> dict[str, float | None]:
    """Mirror legacy per-metric percentile: among rows matching ``cohort_where``,

    percentile = 100 * count(m non-null AND m <= player_value) / count(m non-null).

    Caller supplies each metric once. Unknown keys are never added to the dict.
    """
    if not items:
        return {}

    selects: list[str] = []
    thresholds: list[object] = []
    for i, (metric, value) in enumerate(items):
        qm = q_ident(metric)
        alias = f"pct_{i}"
        selects.append(
            (
                "100.0 * SUM(CASE WHEN "
                f"{qm} IS NOT NULL AND {qm} <= ? THEN 1 ELSE 0 END) "
                f"/ NULLIF(CAST(SUM(CASE WHEN {qm} IS NOT NULL THEN 1 ELSE 0 END) AS DOUBLE), 0)"
                f" AS {alias}"
            )
        )
        thresholds.append(value)

    tail = cohort_where_sql.strip() if cohort_where_sql.strip() else "TRUE"
    sql = f"SELECT {', '.join(selects)} FROM {view} WHERE {tail}"
    row = conn.execute(sql, [*thresholds, *cohort_params]).fetchone()
    out: dict[str, float | None] = {}
    if row is None:
        for metric, _ in items:
            out[metric] = None
        return out

    for j, (metric, _) in enumerate(items):
        cell = row[j]
        out[metric] = float(cell) if cell is not None else None
    return out
