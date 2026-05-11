"""Curated metric lists intersected with DuckDB view columns (legacy METRIC_COLS behavior)."""

from __future__ import annotations

import duckdb

from app.core.config import METRIC_COLS, metric_column_show_in_selectors
from app.core.metric_modes import (
    dedupe_raw_p90_options,
    default_mode,
    format_selectbox_option_display,
    supports_toggle,
)


def column_names_in_view(conn: duckdb.DuckDBPyConnection, view: str) -> set[str]:
    """Resolve column names for a registered view (duckdb_columns → information_schema → DESCRIBE)."""
    attempts: list[tuple[str, list]] = [
        (
            """
            SELECT DISTINCT column_name FROM duckdb_columns()
            WHERE database_name = current_database()
              AND schema_name = 'main'
              AND table_name = ?
            """,
            [view],
        ),
        (
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [view],
        ),
    ]
    for sql, params in attempts:
        try:
            rows = conn.execute(sql, params).fetchall()
            if rows:
                return {r[0] for r in rows}
        except (duckdb.Error, ValueError):
            continue
    try:
        rows = conn.execute(f"DESCRIBE {view}").fetchall()
        if rows:
            return {r[0] for r in rows}
    except duckdb.Error:
        pass
    return set()


def selectable_metric_names(conn: duckdb.DuckDBPyConnection, view: str) -> list[str]:
    cols = column_names_in_view(conn, view)
    candidates = [c for c in METRIC_COLS if metric_column_show_in_selectors(c) and c in cols]
    return dedupe_raw_p90_options(candidates)


def metric_options_for_view(conn: duckdb.DuckDBPyConnection, view: str) -> list[dict]:
    out: list[dict] = []
    for name in selectable_metric_names(conn, view):
        item: dict = {
            "name": name,
            "label": format_selectbox_option_display(name),
            "supports_mode": supports_toggle(name),
            "default_mode": default_mode(name),
        }
        out.append(item)
    return out
