"""xTV history over loaded seasons (projected columns; mirror of pi_history)."""

from __future__ import annotations

import duckdb

from app.core.club_logos import (
    club_logo_from_parquet_row,
    normalize_club_logo,
    resolve_club_logo,
)
from app.core.duckdb_pool import list_seasons, list_views
from app.core.metrics_catalog import column_names_in_view
from app.core.profile_history_row import fetch_one_row_prefer_club
from app.core.sql_ident import q_ident

_XTV_HISTORY_PREF_COLS = (
    "club",
    "league",
    "x_tv_eur",
    "Minutes played",
    "club_logo",
    "Team",
    "Team logo",
    "Club logo",
)


def _xtv_cell(rec: dict) -> float | None:
    raw = rec.get("x_tv_eur")
    if raw is None or (isinstance(raw, float) and raw != raw):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _project_columns(avail: set[str]) -> list[str] | None:
    if "Minutes played" not in avail or "x_tv_eur" not in avail:
        return None
    return [c for c in _XTV_HISTORY_PREF_COLS if c in avail]


def build_xtv_history_payload(
    conn: duckdb.DuckDBPyConnection,
    wyscout_id: int,
    anchor_season: int,
    limit: int,
    preferred_club: str | None = None,
) -> list[dict[str, object | None]]:
    """Dict rows matching ``XtvHistoryPoint`` shape; chronological."""
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
        rec = fetch_one_row_prefer_club(conn, view, select_sql, wyscout_id, preferred_club)
        if not rec:
            continue
        xtv = _xtv_cell(rec)
        if xtv is None:
            continue
        club = rec.get("club")
        if club is not None and not isinstance(club, str):
            club = str(club)
        logo = (
            resolve_club_logo(conn, club, yr, rec.get("league")) or club_logo_from_parquet_row(rec)
        )
        logo = normalize_club_logo(logo)
        points.append(
            {
                "season": yr,
                "x_tv_eur": float(xtv),
                "club": club if isinstance(club, str) else None,
                "club_logo": logo,
            },
        )

    return points
