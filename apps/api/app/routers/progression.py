"""Multi-season progression for a single player.

Given a Wyscout id and a list of metrics + seasons, returns time-series:
one entry per (metric, season) with the metric value and league info.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_seasons, list_views
from app.core.metric_modes import format_mode_label
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import selectable_metric_names
from app.core.sql_ident import q_ident as _q
from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.schemas import (
    ProgressionMetricSeries,
    ProgressionPoint,
    ProgressionRequest,
    ProgressionResponse,
)

router = APIRouter(prefix="/players", tags=["progression"])


@router.post("/{wyscout_id}/progression", response_model=ProgressionResponse)
def progression(wyscout_id: int, req: ProgressionRequest) -> ProgressionResponse:
    if not req.metrics:
        raise HTTPException(400, "Provide at least one metric")
    if len(req.metrics) > 10:
        raise HTTPException(400, "Maximum 10 metrics per request")

    seasons_all = list_seasons()
    if not seasons_all:
        return ProgressionResponse(player=None, metrics=[], seasons=[])

    # Pick `count` most recent seasons (target season + (count-1) prior).
    eligible = sorted([s for s in seasons_all if s <= req.target_season], reverse=True)
    seasons = eligible[: req.seasons_count]
    if not seasons:
        return ProgressionResponse(player=None, metrics=[], seasons=[])

    player_name: str | None = None
    metric_series: dict[str, list[ProgressionPoint]] = {m: [] for m in req.metrics}

    with duckdb_session() as conn:
        for season in sorted(seasons):
            view = f"players_{season}"
            if view not in list_views():
                continue
            allowed = set(selectable_metric_names(conn, view))
            per_season_metrics = [m for m in req.metrics if m in allowed]
            if not per_season_metrics:
                continue

            logo_sql = club_logo_select_sql(conn, view, season)
            select_parts = [
                '"Player" AS player',
                "club",
                "league",
                '"Minutes played" AS minutes',
                logo_sql,
            ]
            for m in per_season_metrics:
                select_parts.append(f"({metric_sql_expr(m, req.mode)}) AS {_q('m_' + m)}")

            sql = f"""
                SELECT {', '.join(select_parts)}
                FROM {view}
                WHERE "Wyscout id" = ?
                ORDER BY "Minutes played" DESC NULLS LAST
                LIMIT 1
            """
            rows = fetch_all_dicts(conn, sql, [wyscout_id])
            if not rows:
                for m in per_season_metrics:
                    metric_series[m].append(
                        ProgressionPoint(
                            season=season,
                            value=None,
                            club=None,
                            league=None,
                            minutes=None,
                            club_logo=None,
                        )
                    )
                continue

            rec = rows[0]
            if player_name is None:
                player_name = rec.get("player")

            logo = normalize_club_logo(rec.get("club_logo"))
            for m in req.metrics:
                if m not in per_season_metrics:
                    metric_series[m].append(
                        ProgressionPoint(
                            season=season,
                            value=None,
                            club=None,
                            league=None,
                            minutes=None,
                            club_logo=None,
                        )
                    )
                    continue
                v = rec.get(f"m_{m}")
                val = float(v) if (v is not None and v == v) else None
                metric_series[m].append(
                    ProgressionPoint(
                        season=season,
                        value=val,
                        club=rec.get("club"),
                        league=rec.get("league"),
                        minutes=rec.get("minutes"),
                        club_logo=logo,
                    )
                )

    series = [
        ProgressionMetricSeries(
            metric=m,
            label=format_mode_label(m, req.mode),
            points=metric_series[m],
        )
        for m in req.metrics
    ]

    return ProgressionResponse(
        player=player_name,
        metrics=series,
        seasons=sorted(seasons),
    )
