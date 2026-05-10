"""Stacked bar of multiple metrics for selected players (port of pages/10_Bar_Chart)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import view_name
from app.core.metric_modes import format_mode_label
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import selectable_metric_names
from app.core.sql_ident import q_ident as _q
from app.schemas import BarPlayerSeries, BarRequest, BarResponse

router = APIRouter(prefix="/bar", tags=["bar"])


@router.post("", response_model=BarResponse)
def bar(req: BarRequest) -> BarResponse:
    if not req.metrics:
        raise HTTPException(400, "Provide at least one metric")
    if len(req.metrics) > 12:
        raise HTTPException(400, "Maximum 12 metrics per request")
    if not req.player_ids:
        raise HTTPException(400, "Provide at least one player id")
    if len(req.player_ids) > 12:
        raise HTTPException(400, "Maximum 12 players per request")

    view = view_name(req.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.season} not loaded")

    with duckdb_session() as conn:
        allowed = set(selectable_metric_names(conn, view))
        for m in req.metrics:
            if m not in allowed:
                raise HTTPException(400, f"Unknown or unavailable metric: {m}")

        placeholders = ",".join(["?"] * len(req.player_ids))
        cols = [
            '"Wyscout id" AS wyscout_id',
            '"Player" AS player',
            "club",
            "league",
            '"Primary position" AS position',
            '"Minutes played" AS minutes',
        ]
        for m in req.metrics:
            cols.append(f"({metric_sql_expr(m, req.mode)}) AS {_q('m_' + m)}")
        sql = f"""
            SELECT {', '.join(cols)}
            FROM {view}
            WHERE "Wyscout id" IN ({placeholders})
        """
        rows = fetch_all_dicts(conn, sql, list(req.player_ids))

    series: list[BarPlayerSeries] = []
    for rec in rows:
        values: dict[str, float | None] = {}
        for m in req.metrics:
            v = rec.get(f"m_{m}")
            values[m] = float(v) if (v is not None and v == v) else None
        series.append(
            BarPlayerSeries(
                wyscout_id=rec.get("wyscout_id"),
                player=str(rec.get("player") or ""),
                club=rec.get("club"),
                league=rec.get("league"),
                position=rec.get("position"),
                minutes=rec.get("minutes"),
                values=values,
            )
        )

    labels = {m: format_mode_label(m, req.mode) for m in req.metrics}

    return BarResponse(
        metrics=req.metrics,
        labels=labels,
        players=series,
    )
