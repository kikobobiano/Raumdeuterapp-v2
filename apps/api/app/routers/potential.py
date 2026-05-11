"""Potential Score router — surfaces model output `potential_score` for U-25 players.

Joins the season's player view with the global ``potential_scores`` view (model
output keyed by ``Wyscout id`` + ``season_year``). Hard-gates ``Age ≤ 25`` and
``Minutes played ≥ 400`` regardless of incoming filters so the metric is always
interpretable (the model is only trained for that cohort).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import (
    not_goalkeeper_sql,
    role_filter_tokens,
    view_name,
)
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.schemas import (
    PotentialCohortRequest,
    PotentialCohortResponse,
    PotentialPlayer,
    PotentialRequest,
    PotentialResponse,
)

router = APIRouter(prefix="/potential", tags=["potential"])

AGE_MAX_HARD = 25
MINUTES_MIN_HARD = 400


@router.post("", response_model=PotentialResponse)
def potential(req: PotentialRequest) -> PotentialResponse:
    view = view_name(req.filters.season)
    views = list_views()
    if view not in views:
        raise HTTPException(404, f"season {req.filters.season} not loaded")
    if "potential_scores" not in views:
        raise HTTPException(503, "potential_scores view not loaded — check data/potential/")

    f = req.filters

    age_min = f.age_min or 15
    age_max = AGE_MAX_HARD if f.age_max is None else min(f.age_max, AGE_MAX_HARD)
    minutes_min = MINUTES_MIN_HARD if f.minutes_min is None else max(f.minutes_min, MINUTES_MIN_HARD)
    if age_min > age_max:
        return PotentialResponse(players=[], n=0)

    parts: list[str] = ['p."Age" >= ?', 'p."Age" <= ?', 'p."Minutes played" >= ?']
    params: list[Any] = [age_min, age_max, minutes_min]

    if f.leagues:
        parts.append(f"p.league IN ({','.join(['?'] * len(f.leagues))})")
        params.extend(f.leagues)

    if f.teams:
        parts.append(f"p.club IN ({','.join(['?'] * len(f.teams))})")
        params.extend(f.teams)

    if f.roles:
        tokens = role_filter_tokens(f.roles)
        if tokens:
            pattern = "(" + "|".join(sorted(tokens, key=len, reverse=True)) + ")"
            parts.append(
                'regexp_matches(coalesce(p."Primary position", p."Position", \'\'), ?)'
            )
            params.append(pattern)

    gk_sql, gk_params = not_goalkeeper_sql()
    # gk_sql references "Primary position" / "Position" — qualify
    parts.append(
        gk_sql.replace('"Primary position"', 'p."Primary position"')
              .replace("Position,", 'p."Position",')
    )
    params.extend(gk_params)

    parts.append("ps.potential_score IS NOT NULL")

    with duckdb_session() as conn:
        vcols = column_names_in_view(conn, view)
        age_sel = player_age_sql(vcols, f.season, table_alias="p")
        logo_sql = club_logo_select_sql(conn, view, f.season, table_alias="p")
        img_sql = player_image_select_sql(conn, view, table_alias="p")
        where = " AND ".join(parts)
        sql = f"""
            SELECT
              {logo_sql},
              p."Wyscout id"      AS wyscout_id,
              p."Player"          AS player,
              p.club              AS club,
              p.league            AS league,
              p."Primary position" AS position,
              ({age_sel})         AS age,
              p."Minutes played"  AS minutes,
              p.performance_index AS current_pi,
              ps.potential_score  AS potential_score,
              {img_sql}
            FROM {view} p
            JOIN potential_scores ps
              ON ps."Wyscout id" = p."Wyscout id"
             AND ps.season_year  = ?
            WHERE {where}
            ORDER BY ps.potential_score DESC NULLS LAST
        """
        rows = fetch_all_dicts(conn, sql, [f.season, *params])

    players = [
        PotentialPlayer(
            wyscout_id=int(r["wyscout_id"]) if r.get("wyscout_id") is not None else None,
            player=str(r.get("player") or ""),
            club=r.get("club"),
            club_logo=normalize_club_logo(r.get("club_logo")),
            league=r.get("league"),
            position=r.get("position"),
            age=int(r["age"]) if r.get("age") is not None else None,
            minutes=int(r["minutes"]) if r.get("minutes") is not None else None,
            current_pi=_safe_float(r.get("current_pi")),
            potential_score=float(r["potential_score"]),
            player_image_url=r.get("player_image_url") if isinstance(r.get("player_image_url"), str) else None,
        )
        for r in rows
        if r.get("potential_score") is not None
    ]
    return PotentialResponse(players=players, n=len(players))


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return None
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def _build_cohort_where(
    *,
    age: int,
    f: Any,
    require_potential: bool = True,
) -> tuple[str, list[Any]]:
    """SQL ``WHERE`` for a single age cohort. ``age`` overrides ``age_min/age_max``."""
    if age > AGE_MAX_HARD:
        return "1=0", []
    minutes_min = (
        MINUTES_MIN_HARD if f.minutes_min is None else max(f.minutes_min, MINUTES_MIN_HARD)
    )
    parts: list[str] = ['p."Age" = ?', 'p."Minutes played" >= ?']
    params: list[Any] = [age, minutes_min]

    if f.leagues:
        parts.append(f"p.league IN ({','.join(['?'] * len(f.leagues))})")
        params.extend(f.leagues)

    if f.teams:
        parts.append(f"p.club IN ({','.join(['?'] * len(f.teams))})")
        params.extend(f.teams)

    if f.roles:
        tokens = role_filter_tokens(f.roles)
        if tokens:
            pattern = "(" + "|".join(sorted(tokens, key=len, reverse=True)) + ")"
            parts.append(
                'regexp_matches(coalesce(p."Primary position", p."Position", \'\'), ?)'
            )
            params.append(pattern)

    gk_sql, gk_params = not_goalkeeper_sql()
    parts.append(
        gk_sql.replace('"Primary position"', 'p."Primary position"')
              .replace("Position,", 'p."Position",')
    )
    params.extend(gk_params)

    if require_potential:
        parts.append("ps.potential_score IS NOT NULL")

    return " AND ".join(parts), params


@router.post("/cohort", response_model=PotentialCohortResponse)
def potential_cohort(req: PotentialCohortRequest) -> PotentialCohortResponse:
    """Paginated age-cohort slice — ordered by ``potential_score`` desc, with total count."""
    view = view_name(req.filters.season)
    views = list_views()
    if view not in views:
        raise HTTPException(404, f"season {req.filters.season} not loaded")
    if "potential_scores" not in views:
        raise HTTPException(503, "potential_scores view not loaded — check data/potential/")

    f = req.filters
    if req.age > AGE_MAX_HARD:
        return PotentialCohortResponse(age=req.age, players=[], total=0)

    where, params = _build_cohort_where(age=req.age, f=f, require_potential=True)

    with duckdb_session() as conn:
        vcols = column_names_in_view(conn, view)
        age_sel = player_age_sql(vcols, f.season, table_alias="p")
        logo_sql = club_logo_select_sql(conn, view, f.season, table_alias="p")
        img_sql = player_image_select_sql(conn, view, table_alias="p")
        join_sql = (
            f"JOIN potential_scores ps "
            "ON ps.\"Wyscout id\" = p.\"Wyscout id\" "
            "AND ps.season_year = ? "
        )
        sql = f"""
            SELECT
              {logo_sql},
              p."Wyscout id"      AS wyscout_id,
              p."Player"          AS player,
              p.club              AS club,
              p.league            AS league,
              p."Primary position" AS position,
              ({age_sel})         AS age,
              p."Minutes played"  AS minutes,
              p.performance_index AS current_pi,
              ps.potential_score  AS potential_score,
              {img_sql}
            FROM {view} p
            {join_sql}
            WHERE {where}
            ORDER BY ps.potential_score DESC NULLS LAST, p."Minutes played" DESC NULLS LAST
            LIMIT ? OFFSET ?
        """
        rows = fetch_all_dicts(
            conn, sql, [f.season, *params, int(req.limit), int(req.offset)]
        )

        count_sql = f"""
            SELECT COUNT(*) FROM {view} p
            {join_sql}
            WHERE {where}
        """
        total = int(conn.execute(count_sql, [f.season, *params]).fetchone()[0])

    players = [
        PotentialPlayer(
            wyscout_id=int(r["wyscout_id"]) if r.get("wyscout_id") is not None else None,
            player=str(r.get("player") or ""),
            club=r.get("club"),
            club_logo=normalize_club_logo(r.get("club_logo")),
            league=r.get("league"),
            position=r.get("position"),
            age=int(r["age"]) if r.get("age") is not None else None,
            minutes=int(r["minutes"]) if r.get("minutes") is not None else None,
            current_pi=_safe_float(r.get("current_pi")),
            potential_score=float(r["potential_score"]),
            player_image_url=r.get("player_image_url") if isinstance(r.get("player_image_url"), str) else None,
        )
        for r in rows
        if r.get("potential_score") is not None
    ]
    return PotentialCohortResponse(age=req.age, players=players, total=total)
