"""Leaderboard queries (performance index, etc.)."""

from __future__ import annotations

import duckdb

from app.core.config import AREA_INDEX_COLS
from app.core.duckdb_pool import fetch_all_dicts
from app.core.filters import not_goalkeeper_sql
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql, season_start_year_from_view
from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.player_image import player_image_select_sql


def _extras_select_clause(conn: duckdb.DuckDBPyConnection, view: str) -> str:
    """``player_image_url`` + game-area indices when present on the parquet view."""
    cols = column_names_in_view(conn, view)
    parts: list[str] = [player_image_select_sql(conn, view)]
    for key in AREA_INDEX_COLS:
        if key in cols:
            parts.append(f'"{key}"')
        else:
            parts.append(f'CAST(NULL AS DOUBLE) AS "{key}"')
    return ",\n            ".join(parts)


def top_by_performance_index(
    conn: duckdb.DuckDBPyConnection,
    view: str,
    minutes_min: int,
    limit: int,
    *,
    offset: int = 0,
    logo_season: int,
    leagues: list[str] | None = None,
    teams: list[str] | None = None,
    roles: list[str] | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
) -> tuple[list[dict], int]:
    """One row per Wyscout id (best performance_index); includes club_logo when present."""
    if "performance_index" not in column_names_in_view(conn, view):
        return [], 0

    logo_sql = club_logo_select_sql(conn, view, logo_season)
    extras_sql = _extras_select_clause(conn, view)
    vcols = column_names_in_view(conn, view)
    age_sel = player_age_sql(vcols, season_start_year_from_view(view))
    gk_sql, gk_params = not_goalkeeper_sql()

    where_parts = ['"Minutes played" >= ?', "performance_index IS NOT NULL", gk_sql]
    params: list = [minutes_min, *gk_params]

    if leagues:
        where_parts.append(f"league IN ({','.join(['?'] * len(leagues))})")
        params.extend(leagues)
    if teams:
        where_parts.append(f"club IN ({','.join(['?'] * len(teams))})")
        params.extend(teams)
    if age_min is not None:
        where_parts.append(f"({age_sel}) >= ?")
        params.append(age_min)
    if age_max is not None:
        where_parts.append(f"({age_sel}) <= ?")
        params.append(age_max)

    if roles:
        from app.core.filters import role_filter_tokens, role_position_regex

        tokens = role_filter_tokens(roles)
        pattern = role_position_regex(tokens)
        if pattern:
            where_parts.append(
                'regexp_matches(coalesce("Primary position", Position, \'\'), ?)'
            )
            params.append(pattern)

    where = " AND ".join(where_parts)
    olimit = max(1, min(int(limit), 500))
    ooff = max(0, int(offset))

    shared_cte = f"""
        WITH ranked AS (
          SELECT
            {logo_sql},
            {extras_sql},
            "Wyscout id" AS wyscout_id,
            "Player" AS player,
            club,
            league,
            "Primary position" AS position,
            ({age_sel}) AS age,
            "Minutes played" AS minutes,
            performance_index,
            ROW_NUMBER() OVER (
              PARTITION BY "Wyscout id"
              ORDER BY performance_index DESC NULLS LAST, "Minutes played" DESC NULLS LAST
            ) AS rn
          FROM {view}
          WHERE {where}
        ),
        dedup AS (
          SELECT *
          EXCLUDE (rn)
          FROM ranked
          WHERE rn = 1
        )
    """

    rows = fetch_all_dicts(
        conn,
        shared_cte
        + f"""
        ,
        meta AS (
          SELECT CAST(COUNT(*) AS BIGINT) AS leaderboard_total FROM dedup
        )
        SELECT
          d.*,
          m.leaderboard_total
        FROM dedup AS d
        CROSS JOIN meta AS m
        ORDER BY d.performance_index DESC NULLS LAST
        LIMIT {olimit} OFFSET {ooff}
        """,
        params,
    )

    total = 0
    if rows:
        raw = rows[0].get("leaderboard_total")
        total = int(raw) if raw is not None else 0
    else:
        count_rows = fetch_all_dicts(
            conn,
            shared_cte + "SELECT CAST(COUNT(*) AS BIGINT) AS leaderboard_total FROM dedup",
            params,
        )
        if count_rows:
            total = int(count_rows[0].get("leaderboard_total") or 0)

    for rec in rows:
        rec.pop("leaderboard_total", None)

    for rec in rows:
        rec["club_logo"] = normalize_club_logo(rec.get("club_logo"))
        for rk, rv in list(rec.items()):
            if isinstance(rv, float) and rv != rv:
                rec[rk] = None
        if isinstance(rec.get("player_image_url"), float):
            rec["player_image_url"] = None
    return rows, total
