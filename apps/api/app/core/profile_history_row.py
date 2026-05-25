"""Select one player-season row for profile trajectory endpoints."""

from __future__ import annotations

import duckdb

from app.core.duckdb_pool import fetch_all_dicts
from app.core.sql_ident import q_ident

_WY_ID = "Wyscout id"
_CLUB = "club"
_MINUTES = "Minutes played"


def fetch_one_row_prefer_club(
    conn: duckdb.DuckDBPyConnection,
    view: str,
    select_cols_sql: str,
    wyscout_id: int,
    preferred_club: str | None,
) -> dict | None:
    """Prefer ``club = preferred_club`` when set; else dominant row by minutes."""
    wid_sql = q_ident(_WY_ID)
    club_sql = q_ident(_CLUB)
    minutes_sql = q_ident(_MINUTES)
    if preferred_club:
        rows = fetch_all_dicts(
            conn,
            f"SELECT {select_cols_sql} FROM {view} "
            f"WHERE {wid_sql} = ? AND {club_sql} = ? LIMIT 1",
            [wyscout_id, preferred_club],
        )
        if rows:
            return rows[0]
    rows = fetch_all_dicts(
        conn,
        f"SELECT {select_cols_sql} FROM {view} WHERE {wid_sql} = ? "
        f"ORDER BY {minutes_sql} DESC NULLS LAST LIMIT 1",
        [wyscout_id],
    )
    return rows[0] if rows else None
