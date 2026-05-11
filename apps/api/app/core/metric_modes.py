"""Classify metrics and convert between raw / per-90 (port of legacy utils/metric_modes)."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from app.core.config import format_metric_label

MetricKind = Literal["per90", "raw_count", "excluded"]
MetricMode = Literal["raw", "p90", "as_is"]

MINUTES_COL = "Minutes played"

RAW_COUNT_COLS: set[str] = {
    "Goals", "Assists", "xG", "xA", "NPxG",
    "Non-penalty goals", "Head goals",
    "Shots",
    "Yellow cards", "Red cards",
    "Conceded goals", "Shots against", "Clean sheets",
    "Prevented goals", "xG against",
    "Penalties taken",
}


def _is_team_impact(col: str) -> bool:
    return "% Team Impact" in col


def metric_kind(col: str) -> MetricKind:
    if not isinstance(col, str):
        return "excluded"
    if _is_team_impact(col):
        return "excluded"
    if col.endswith(" per 90"):
        return "per90"
    if col in RAW_COUNT_COLS:
        return "raw_count"
    return "excluded"


def metric_pair(col: str) -> tuple[str | None, str | None]:
    kind = metric_kind(col)
    if kind == "per90":
        base = col[: -len(" per 90")]
        return base, col
    if kind == "raw_count":
        return col, f"{col} per 90"
    return None, None


def supports_toggle(col: str) -> bool:
    return metric_kind(col) != "excluded"


def compute_metric_series(
    df: pd.DataFrame, col: str, mode: MetricMode = "as_is"
) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, name=col)

    series = df[col]
    kind = metric_kind(col)
    if kind == "excluded" or mode == "as_is":
        return series

    if (kind == "per90" and mode == "p90") or (kind == "raw_count" and mode == "raw"):
        return series

    if MINUTES_COL not in df.columns:
        return series

    minutes = pd.to_numeric(df[MINUTES_COL], errors="coerce")
    safe_minutes = minutes.where(minutes > 0)

    if kind == "per90" and mode == "raw":
        out = series * safe_minutes / 90.0
    elif kind == "raw_count" and mode == "p90":
        out = series / safe_minutes * 90.0
    else:
        out = series

    raw_name, p90_name = metric_pair(col)
    out.name = raw_name if mode == "raw" else p90_name
    return out


def output_column_name(col: str, mode: MetricMode) -> str:
    if metric_kind(col) == "excluded" or mode == "as_is":
        return col
    raw_name, p90_name = metric_pair(col)
    if mode == "raw":
        return raw_name or col
    return p90_name or col


def format_mode_label(col: str, mode: MetricMode) -> str:
    if metric_kind(col) == "excluded" or mode == "as_is":
        return format_metric_label(col)

    raw_name, p90_name = metric_pair(col)
    if mode == "raw":
        return f"{format_metric_label(raw_name or col)} (raw)"
    return format_metric_label(p90_name or col)


def format_selectbox_option_display(col: str) -> str:
    if not isinstance(col, str):
        return str(col)
    if col.endswith(" per 90"):
        base = col[: -len(" per 90")]
        return format_metric_label(base)
    return format_metric_label(col)


def dedupe_raw_p90_options(options: list[str]) -> list[str]:
    s = set(options)
    to_remove: set[str] = set()
    for c in options:
        if not supports_toggle(c) or metric_kind(c) != "raw_count":
            continue
        _r, p90 = metric_pair(c)
        if p90 and p90 in s:
            to_remove.add(p90)
    return [c for c in options if c not in to_remove]


def default_mode(col: str) -> MetricMode:
    kind = metric_kind(col)
    if kind == "per90":
        return "p90"
    if kind == "raw_count":
        return "raw"
    return "as_is"
