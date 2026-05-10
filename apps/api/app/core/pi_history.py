"""Performance index history over loaded seasons (projected columns; no ``SELECT *``)."""

from __future__ import annotations

import duckdb

from app.core.club_logos import (
    club_logo_from_parquet_row,
    normalize_club_logo,
    resolve_club_logo,
)
from app.core.duckdb_pool import fetch_all_dicts, list_seasons, list_views
from app.core.metrics_catalog import column_names_in_view
from app.core.sql_ident import q_ident

_WY_ID = "Wyscout id"

_PI_HISTORY_PREF_COLS = (
    "club",
    "performance_index",
    "Minutes played",
    "club_logo",
    "Team",
    "Team logo",
    "Club logo",
)


def _performance_index_cell(rec: dict) -> float | None:
    raw = rec.get("performance_index")
    if raw is None or (isinstance(raw, float) and raw != raw):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _project_columns(avail: set[str]) -> list[str] | None:
    if "Minutes played" not in avail or "performance_index" not in avail:
        return None
    return [c for c in _PI_HISTORY_PREF_COLS if c in avail]


def build_pi_history_payload(
    conn: duckdb.DuckDBPyConnection,
    wyscout_id: int,
    anchor_season: int,
    limit: int,
) -> list[dict[str, object | None]]:
    """Dict rows matching ``PerformanceIndexHistoryPoint`` shape; chronological."""
    seasons_all = list_seasons()
    if not seasons_all:
        return []

    eligible = sorted([s for s in seasons_all if s <= anchor_season], reverse=True)[:limit]
    eligible_chrono = list(reversed(eligible))
    points: list[dict[str, object | None]] = []

    for yr in eligible_chrono:
        view = f"players_{yr}"
        if view not in list_views():
            continue
        avail = column_names_in_view(conn, view)
        proj = _project_columns(avail)
        if proj is None:
            continue
        select_sql = ", ".join(q_ident(c) for c in proj)
        wid_sql = q_ident(_WY_ID)
        minutes_sql = q_ident("Minutes played")
        sql = (
            f"SELECT {select_sql} FROM {view} WHERE {wid_sql} = ? "
            f"ORDER BY {minutes_sql} DESC NULLS LAST LIMIT 1"
        )
        rows = fetch_all_dicts(conn, sql, [wyscout_id])
        if not rows:
            continue
        rec = rows[0]
        pi = _performance_index_cell(rec)
        if pi is None:
            continue
        club = rec.get("club")
        if club is not None and not isinstance(club, str):
            club = str(club)
        logo = resolve_club_logo(conn, club, yr) or club_logo_from_parquet_row(rec)
        logo = normalize_club_logo(logo)
        points.append(
            {
                "season": yr,
                "performance_index": float(pi),
                "club": club if isinstance(club, str) else None,
                "club_logo": logo,
            },
        )

    return points
