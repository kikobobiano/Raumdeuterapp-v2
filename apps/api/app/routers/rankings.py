"""Top-N rankings by a single metric, with global filters."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import build_where, view_name
from app.core.metric_modes import format_mode_label
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.schemas import RankingsRequest, RankingsResponse, RankingsRow

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.post("", response_model=RankingsResponse)
def rankings(req: RankingsRequest) -> RankingsResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    with duckdb_session() as conn:
        if req.metric not in set(selectable_metric_names(conn, view)):
            raise HTTPException(400, f"Unknown or unavailable metric: {req.metric}")

        where_sql, params = build_where(req.filters)
        where = f"WHERE {where_sql}" if where_sql else ""

        metric_expr = metric_sql_expr(req.metric, req.mode)
        direction = "DESC" if req.desc else "ASC"

        vcols = column_names_in_view(conn, view)
        age_sel = player_age_sql(vcols, req.filters.season)

        sql = f"""
            SELECT
              {club_logo_select_sql(conn, view, req.filters.season)},
              "Wyscout id" AS wyscout_id,
              "Player" AS player,
              club, league,
              "Primary position" AS position,
              ({age_sel}) AS age,
              "Minutes played" AS minutes,
              ({metric_expr}) AS metric_value
            FROM {view}
            {where}
            ORDER BY metric_value {direction} NULLS LAST
            LIMIT {int(req.limit)}
        """
        rows_raw = fetch_all_dicts(conn, sql, params)

    rows: list[RankingsRow] = []
    for i, rec in enumerate(rows_raw):
        v = rec.get("metric_value")
        rows.append(
            RankingsRow(
                rank=i + 1,
                wyscout_id=rec.get("wyscout_id"),
                player=str(rec.get("player") or ""),
                club=rec.get("club"),
                league=rec.get("league"),
                position=rec.get("position"),
                age=rec.get("age"),
                minutes=rec.get("minutes"),
                club_logo=normalize_club_logo(rec.get("club_logo")),
                value=float(v) if (v is not None and v == v) else None,
            )
        )

    return RankingsResponse(
        rows=rows,
        metric=req.metric,
        label=format_mode_label(req.metric, req.mode),
        n=len(rows),
    )
