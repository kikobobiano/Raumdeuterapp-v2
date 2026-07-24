from fastapi import APIRouter, HTTPException, Query

from app.core.config import (
    BIG_FIVE_LEAGUES,
    GAME_AREAS,
    GAME_AREAS_COLS,
    LEAGUES,
    ROLE_PRIORITY_UI,
    ROLE_TO_TOKENS,
)
from app.core.duckdb_pool import duckdb_session, list_seasons, list_views
from app.core.league_list import distinct_leagues_in_view, sort_leagues_by_power
from app.core.metrics_catalog import metric_options_for_view
from app.core.top_players import top_by_performance_index
from app.schemas import MetricOption, TopPerformancePage, TopPerformancePlayer

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/seasons")
def seasons() -> list[int]:
    return list_seasons()


@router.get("/leagues")
def leagues(season: int | None = None) -> list[str]:
    view = f"players_{season}" if season else "players_all"
    with duckdb_session() as conn:
        return distinct_leagues_in_view(conn, view)


@router.get("/leagues/known")
def leagues_known() -> list[str]:
    return sort_leagues_by_power(list(LEAGUES))


@router.get("/leagues/big-five")
def leagues_big_five() -> list[str]:
    """Canonical Big 5 league names (same strings as in parquet `league`)."""
    return list(BIG_FIVE_LEAGUES)


@router.get("/roles")
def roles() -> list[str]:
    return ROLE_PRIORITY_UI


@router.get("/role-tokens")
def role_tokens() -> dict[str, list[str]]:
    """Wyscout position codes per tactical role (for sub-position filters in UI)."""
    return {r: list(ROLE_TO_TOKENS[r]) for r in ROLE_PRIORITY_UI if r in ROLE_TO_TOKENS}


@router.get("/teams")
def teams(
    season: int,
    league: str | None = None,
    leagues: list[str] | None = Query(None),
) -> list[str]:
    """Distinct clubs for a season, optionally scoped to one or more leagues.

    ``leagues`` (repeated query param) takes precedence over the legacy single
    ``league`` param; passing neither returns every club in the season.
    """
    view = f"players_{season}"
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")
    picked = leagues if leagues else ([league] if league else [])
    conds = ["club IS NOT NULL"]
    params: list[str] = []
    if picked:
        conds.append(f"league IN ({','.join(['?'] * len(picked))})")
        params.extend(picked)
    sql = f"SELECT DISTINCT club FROM {view} WHERE {' AND '.join(conds)} ORDER BY club"
    with duckdb_session() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [r[0] for r in rows]


@router.get("/players/top-performance", response_model=TopPerformancePage)
def players_top_performance(
    season: int = Query(..., description="Season start year"),
    minutes_min: int = Query(500, ge=0, description="Minimum minutes played"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0, description="Paging offset"),
    leagues: list[str] | None = Query(None, description="Filter by leagues"),
    teams: list[str] | None = Query(None, description="Filter by clubs"),
    roles: list[str] | None = Query(None, description="Filter by tactical roles"),
    age_min: int | None = Query(None, ge=14, le=50),
    age_max: int | None = Query(None, ge=14, le=50),
) -> TopPerformancePage:
    """Top players by performance index (paginated slice + total cohort size)."""
    view = f"players_{season}"
    if view not in list_views():
        # Same as /meta/metrics: no parquet for this year → empty body, not 404
        return TopPerformancePage(items=[], total=0)

    with duckdb_session() as conn:
        rows, total = top_by_performance_index(
            conn,
            view,
            minutes_min,
            limit,
            offset=offset,
            logo_season=season,
            leagues=leagues or None,
            teams=teams or None,
            roles=roles or None,
            age_min=age_min,
            age_max=age_max,
        )
        items = [TopPerformancePlayer.model_validate(r) for r in rows]
        return TopPerformancePage(items=items, total=total)


@router.get("/metrics", response_model=list[MetricOption])
def metrics(season: int) -> list[MetricOption]:
    """Curated metrics present in parquet (legacy METRIC_COLS ∩ columns), with Raw/Per-90 hints."""
    view = f"players_{season}"
    if view not in list_views():
        # Align with /meta/leagues: no parquet for this year → empty list, not 404
        return []

    with duckdb_session() as conn:
        return [MetricOption.model_validate(x) for x in metric_options_for_view(conn, view)]


@router.get("/game-areas")
def game_areas() -> dict[str, list[str]]:
    return {"areas": GAME_AREAS, "columns": GAME_AREAS_COLS}


@router.get("/views")
def views() -> list[str]:
    return list_views()
