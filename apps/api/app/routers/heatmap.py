"""Per-player Wyscout heatmap endpoint (current season(s) only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.duckdb_pool import duckdb_session
from app.core.player_heatmap import fetch_heatmap
from app.schemas import HeatmapPoint, HeatmapResponse

router = APIRouter(prefix="/players", tags=["heatmap"])


@router.get("/{wyscout_id}/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    wyscout_id: int,
    season: int = Query(..., ge=2015, le=2099),
    competition_id: int | None = Query(None),
) -> HeatmapResponse:
    with duckdb_session() as conn:
        data = fetch_heatmap(
            conn,
            wyscout_id=wyscout_id,
            season=season,
            competition_id=competition_id,
        )
    if data is None:
        raise HTTPException(404, "No heatmap for this player/season")

    return HeatmapResponse(
        wyscout_id=data.wyscout_id,
        competition_id=data.competition_id,
        competition=data.competition,
        season=data.season,
        points=[HeatmapPoint(**p) for p in data.points],
        n_points=len(data.points),
        max_count=data.max_count,
    )
