from fastapi import APIRouter, HTTPException, Query

from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.core.filters import not_goalkeeper_sql
from app.core.text_search import strip_accents
from app.schemas import PlayerListItem

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/search", response_model=list[PlayerListItem])
def search(
    season: int = Query(..., description="Season start year"),
    q: str = Query("", description="Free text query — accent/case insensitive"),
    league: str | None = None,
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    view = f"players_{season}"
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    where_parts = []
    params: list = []

    if q.strip():
        # Accent-fold both sides via DuckDB strip_accents (ICU). Use OR across Player + Full name.
        params.append(f"%{strip_accents(q).lower()}%")
        params.append(f"%{strip_accents(q).lower()}%")
        where_parts.append(
            "(LOWER(strip_accents(\"Player\")) LIKE ? "
            "OR LOWER(strip_accents(coalesce(\"Full name\", ''))) LIKE ?)"
        )

    if league:
        where_parts.append("league = ?")
        params.append(league)

    gk_sql, gk_params = not_goalkeeper_sql()
    where_parts.append(gk_sql)
    params.extend(gk_params)

    where = "WHERE " + " AND ".join(where_parts)

    with duckdb_session() as conn:
        cols = column_names_in_view(conn, view)
        age_sel = player_age_sql(cols, season)
        return fetch_all_dicts(
            conn,
            f"""
            SELECT "Wyscout id" AS wyscout_id, "Player" AS player,
                   "Full name" AS full_name, club, league,
                   "Primary position" AS position, ({age_sel}) AS age,
                   "Minutes played" AS minutes, "Market value" AS market_value
            FROM {view}
            {where}
            ORDER BY "Minutes played" DESC NULLS LAST
            LIMIT {int(limit)}
            """,
            params,
        )


@router.get("/{wyscout_id}")
def get_player_basic(season: int, wyscout_id: int) -> dict:
    view = f"players_{season}"
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        rows = fetch_all_dicts(
            conn, f'SELECT * FROM {view} WHERE "Wyscout id" = ? LIMIT 1', [wyscout_id]
        )
        if not rows:
            raise HTTPException(404, f"player {wyscout_id} not found in {view}")
        rec = rows[0]
        return {k: (None if (isinstance(v, float) and v != v) else v) for k, v in rec.items()}
