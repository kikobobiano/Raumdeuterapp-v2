"""Squad minutes distribution for a single club in a single season.

Returns every player rostered to the chosen ``club`` in the season's parquet
view, with their season minutes, matches, age, and share of the static league
maximum (``LEAGUE_MAX_GAMES[league] * 90``).

Used by ``/teams/minutes-distribution`` (Team Metrics → Minutes Distribution
page) for the squad scatter (age vs minutes) and the per-player league-share
bar chart.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.club_logos import normalize_club_logo
from app.core.config import league_max_games, league_max_minutes
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import view_name
from app.core.metrics_catalog import column_names_in_view
from app.core.club_logos import club_logo_select_sql
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.schemas import MinutesDistributionPlayer, MinutesDistributionResponse

router = APIRouter(prefix="/teams", tags=["teams"])


def _age_zone(age: int | None, young_max: int, prime_max: int) -> str:
    """Map an integer age to a young / prime / veteran band.

    Cutoffs are inclusive upper bounds (``young_max=22`` → ``age <= 22`` is
    young). Missing ages collapse to ``prime`` so they never disappear from the
    bar chart.
    """
    if age is None:
        return "prime"
    if age <= young_max:
        return "young"
    if age <= prime_max:
        return "prime"
    return "veteran"


@router.get("/minutes-distribution", response_model=MinutesDistributionResponse)
def minutes_distribution(
    season: int = Query(..., description="Season start year (e.g. 2025 for 25-26)"),
    club: str = Query(..., min_length=1, description="Club name as stored in parquet `club`"),
    young_max: int = Query(22, ge=15, le=40, description="Inclusive max age for the 'young' band"),
    prime_max: int = Query(30, ge=16, le=45, description="Inclusive max age for the 'prime' band"),
) -> MinutesDistributionResponse:
    if young_max >= prime_max:
        raise HTTPException(400, "young_max must be < prime_max")

    view = view_name(season)
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        cols = column_names_in_view(conn, view)
        if "Minutes played" not in cols:
            raise HTTPException(422, "'Minutes played' column missing from season view")
        if "club" not in cols:
            raise HTTPException(422, "'club' column missing from season view")

        has_matches = "Matches played" in cols
        matches_sql = (
            'CAST("Matches played" AS INTEGER) AS matches'
            if has_matches
            else "CAST(NULL AS INTEGER) AS matches"
        )

        age_expr = player_age_sql(cols, season)
        logo_sql = club_logo_select_sql(conn, view, season)
        img_sql = player_image_select_sql(conn, view)

        sql = f"""
            SELECT
                {logo_sql},
                {img_sql},
                "Wyscout id" AS wyscout_id,
                "Player" AS player,
                "Position" AS position,
                ({age_expr}) AS age,
                CAST("Minutes played" AS INTEGER) AS minutes,
                {matches_sql},
                league
            FROM {view}
            WHERE club = ?
              AND "Minutes played" IS NOT NULL
            ORDER BY CAST("Minutes played" AS INTEGER) DESC NULLS LAST
        """
        rows = fetch_all_dicts(conn, sql, [club])

    if not rows:
        raise HTTPException(404, f"No players found for club {club!r} in season {season}")

    league_val = next((r.get("league") for r in rows if r.get("league")), None)
    max_games = league_max_games(league_val)
    max_minutes = league_max_minutes(league_val)

    club_logo: str | None = None
    for r in rows:
        candidate = normalize_club_logo(r.get("club_logo"))
        if candidate:
            club_logo = candidate
            break

    players: list[MinutesDistributionPlayer] = []
    for r in rows:
        minutes = _safe_int(r.get("minutes")) or 0
        pct = 100.0 * minutes / max_minutes if max_minutes else 0.0
        pct = max(0.0, min(100.0, pct))
        age = _safe_int(r.get("age"))
        wid = _safe_int(r.get("wyscout_id"))
        players.append(
            MinutesDistributionPlayer(
                wyscout_id=wid,
                player=str(r.get("player") or ""),
                player_image_url=_nullable_str(r.get("player_image_url")),
                position=_nullable_str(r.get("position")),
                age=age,
                minutes=minutes,
                matches=_safe_int(r.get("matches")),
                league_minutes_pct=round(pct, 1),
                age_zone=_age_zone(age, young_max, prime_max),  # type: ignore[arg-type]
            )
        )

    return MinutesDistributionResponse(
        club=club,
        club_logo=club_logo,
        league=league_val,
        season=season,
        max_league_games=max_games,
        max_league_minutes=max_minutes,
        young_max_age=young_max,
        prime_max_age=prime_max,
        players=players,
    )


def _nullable_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    s = str(v).strip()
    return s if s else None


def _safe_int(v: Any) -> int | None:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None
