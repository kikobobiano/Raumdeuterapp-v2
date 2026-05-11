"""DuckDB SQL fragments for metric values with Raw / Per 90 modes."""

from __future__ import annotations

from app.core.metric_modes import MetricMode, metric_kind

_MINUTES = '"Minutes played"'


def sql_quote_ident(name: str) -> str:
    if any(c in name for c in ('"', ";", "--")):
        raise ValueError(f"invalid column name: {name}")
    return f'"{name}"'


def metric_sql_expr(metric: str, mode: MetricMode) -> str:
    qm = sql_quote_ident(metric)
    kind = metric_kind(metric)
    if kind == "excluded" or mode == "as_is":
        return qm
    if (kind == "per90" and mode == "p90") or (kind == "raw_count" and mode == "raw"):
        return qm
    if kind == "per90" and mode == "raw":
        return f"({qm} * {_MINUTES} / 90.0)"
    if kind == "raw_count" and mode == "p90":
        return f"(({qm} * 90.0) / NULLIF({_MINUTES}, 0))"
    return qm
