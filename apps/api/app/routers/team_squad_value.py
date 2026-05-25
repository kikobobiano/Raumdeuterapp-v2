"""Squad-level economic + demographic aggregates per team.

Endpoints
---------
- ``GET /teams/squad-value/league``  → per-team aggregates for all clubs in a
  given league + season (used for the league scatter on Team Metrics →
  Squad Value page).
- ``GET /teams/squad-value/history`` → per-season aggregates for a single
  club across the seasons currently loaded (used for the combo bar/line
  history chart on the same page).

Metrics: avg age, total xTV, avg xTV, total/avg Transfermarkt market value,
foreign-player share (passport != modal squad passport).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.club_logos import club_logo_select_sql
from app.core.duckdb_pool import (
    duckdb_session,
    fetch_all_dicts,
    list_seasons,
    list_views,
)
from app.core.filters import view_name
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.schemas import (
    SquadValueHistoryResponse,
    SquadValueHistoryRow,
    SquadValueLeagueResponse,
    SquadValueTeamRow,
)

router = APIRouter(prefix="/teams", tags=["teams"])


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        if isinstance(v, float) and v != v:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _aggregate_sql(view: str, cols: set[str], logo_sql: str, age_expr: str) -> str:
    """Build the squad-aggregate SQL for one season view.

    Returns rows keyed by ``club``; the caller adds the WHERE filter (league
    or club). Columns coalesce safely when a parquet lacks ``x_tv_eur``,
    ``tm_market_value_eur``, or ``Passport country`` (legacy seasons).
    """
    xtv_expr = (
        'CAST("x_tv_eur" AS DOUBLE)' if "x_tv_eur" in cols else "CAST(NULL AS DOUBLE)"
    )
    mv_expr = (
        'CAST("tm_market_value_eur" AS DOUBLE)'
        if "tm_market_value_eur" in cols
        else "CAST(NULL AS DOUBLE)"
    )
    passport_expr = (
        '"Passport country"' if "Passport country" in cols else "CAST(NULL AS VARCHAR)"
    )
    league_expr = "league" if "league" in cols else "CAST(NULL AS VARCHAR)"
    return f"""
        WITH base AS (
            SELECT
                club,
                {league_expr} AS league,
                ({age_expr}) AS age,
                {xtv_expr} AS x_tv_eur,
                {mv_expr} AS mv_eur,
                {passport_expr} AS passport,
                {logo_sql}
            FROM {view}
            WHERE "Minutes played" IS NOT NULL
              AND CAST("Minutes played" AS INTEGER) > 0
              {{extra_where}}
        ),
        modes AS (
            SELECT club, mode(passport) AS home_passport
            FROM base
            WHERE passport IS NOT NULL
            GROUP BY club
        )
        SELECT
            b.club AS club,
            any_value(b.club_logo) AS club_logo,
            any_value(b.league) AS league,
            COUNT(*) AS n_players,
            AVG(b.age) AS avg_age,
            SUM(b.x_tv_eur) AS total_xtv_eur,
            AVG(b.x_tv_eur) AS avg_xtv_eur,
            SUM(b.mv_eur) AS total_mv_eur,
            AVG(b.mv_eur) AS avg_mv_eur,
            AVG(
                CASE
                    WHEN b.passport IS NULL OR m.home_passport IS NULL THEN NULL
                    WHEN b.passport = m.home_passport THEN 0.0
                    ELSE 1.0
                END
            ) AS foreign_share
        FROM base b
        LEFT JOIN modes m ON m.club = b.club
        GROUP BY b.club
        ORDER BY total_xtv_eur DESC NULLS LAST
    """


def _row_to_team(rec: dict[str, Any]) -> SquadValueTeamRow:
    return SquadValueTeamRow(
        club=str(rec.get("club") or ""),
        club_logo=(str(rec["club_logo"]) if rec.get("club_logo") else None),
        league=(str(rec["league"]) if rec.get("league") else None),
        n_players=_to_int(rec.get("n_players")) or 0,
        avg_age=_to_float(rec.get("avg_age")),
        total_xtv_eur=_to_float(rec.get("total_xtv_eur")),
        avg_xtv_eur=_to_float(rec.get("avg_xtv_eur")),
        total_market_value_eur=_to_float(rec.get("total_mv_eur")),
        avg_market_value_eur=_to_float(rec.get("avg_mv_eur")),
        foreign_share=_to_float(rec.get("foreign_share")),
    )


@router.get("/squad-value/league", response_model=SquadValueLeagueResponse)
def squad_value_league(
    season: int = Query(..., description="Season start year, e.g. 2024 for 24-25"),
    league: str = Query(..., min_length=1, description="League name as stored in parquet `league`"),
) -> SquadValueLeagueResponse:
    view = view_name(season)
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        cols = column_names_in_view(conn, view)
        if "club" not in cols or "league" not in cols:
            raise HTTPException(422, "'club' or 'league' column missing from season view")
        if "Minutes played" not in cols:
            raise HTTPException(422, "'Minutes played' column missing from season view")

        age_expr = player_age_sql(cols, season)
        logo_sql = club_logo_select_sql(conn, view, season)
        sql = _aggregate_sql(view, cols, logo_sql, age_expr).format(
            extra_where="AND league = ?"
        )
        rows = fetch_all_dicts(conn, sql, [league])

    if not rows:
        raise HTTPException(
            404, f"No teams found for league {league!r} in season {season}"
        )

    teams = [_row_to_team(r) for r in rows]
    return SquadValueLeagueResponse(season=season, league=league, teams=teams)


@router.get("/squad-value/history", response_model=SquadValueHistoryResponse)
def squad_value_history(
    club: str = Query(..., min_length=1, description="Club name as stored in parquet `club`"),
    seasons: list[int] | None = Query(
        None,
        description="Optional explicit list of seasons; defaults to all loaded seasons.",
    ),
) -> SquadValueHistoryResponse:
    available = list_seasons()
    if not available:
        raise HTTPException(404, "no seasons loaded")

    target = sorted(set(seasons) & set(available)) if seasons else sorted(available)
    if not target:
        raise HTTPException(404, "no requested seasons are loaded")

    out: list[SquadValueHistoryRow] = []
    with duckdb_session() as conn:
        for season in target:
            view = view_name(season)
            if view not in list_views():
                continue
            cols = column_names_in_view(conn, view)
            if "club" not in cols or "Minutes played" not in cols:
                continue

            age_expr = player_age_sql(cols, season)
            logo_sql = club_logo_select_sql(conn, view, season)
            sql = _aggregate_sql(view, cols, logo_sql, age_expr).format(
                extra_where="AND club = ?"
            )
            rows = fetch_all_dicts(conn, sql, [club])
            if not rows:
                continue
            base = _row_to_team(rows[0])
            out.append(SquadValueHistoryRow(season=season, **base.model_dump()))

    if not out:
        raise HTTPException(404, f"No squad data for club {club!r}")

    return SquadValueHistoryResponse(club=club, rows=out)
