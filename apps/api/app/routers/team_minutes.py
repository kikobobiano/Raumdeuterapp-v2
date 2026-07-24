"""Squad minutes distribution.

`/teams/minutes-distribution` — per-club view: every player rostered to ``club``
in ``season``'s parquet view with season minutes, matches, age, % of static
league max (``LEAGUE_MAX_GAMES[league] * 90``), age band, plus the squad-level
share of minutes per band.

`/teams/minutes-distribution/league` — league overview: one row per club in the
chosen league with that club's total minutes and per-band zone shares. Used to
compare squads across the league before drilling into a single club.

`/teams/minutes-distribution/leagues` — cross-league overview: one row per league
with median squad age-band shares across its clubs. Sorted by a chosen band.

Optional ``domestic_only=true`` recomputes age-band shares using only players
whose Passport country includes the league's domestic nationality.

Age bands are fixed: youth (<23), peak (<29), experienced (<34), veteran
(>=34). Missing age collapses to ``peak`` so a player never disappears.
"""
from __future__ import annotations

import statistics
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.config import league_max_games, league_max_minutes
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import view_name
from app.core.league_domestic import is_domestic_passport, league_domestic_label
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.schemas import (
    AgeBand,
    LeagueClubBand,
    LeagueMedianBand,
    LeagueMinutesOverviewResponse,
    LeaguesMinutesOverviewResponse,
    MinutesDistributionPlayer,
    MinutesDistributionResponse,
    ZoneShares,
)

router = APIRouter(prefix="/teams", tags=["teams"])

YOUTH_MAX = 22  # age < 23
PEAK_MAX = 28  # age < 29
EXPERIENCED_MAX = 33  # age < 34


def _age_band(age: int | None) -> AgeBand:
    """Map integer age to youth / peak / experienced / veteran.

    Missing age → ``peak`` so the player still contributes to the squad
    breakdown rather than vanishing.
    """
    if age is None:
        return "peak"
    if age <= YOUTH_MAX:
        return "youth"
    if age <= PEAK_MAX:
        return "peak"
    if age <= EXPERIENCED_MAX:
        return "experienced"
    return "veteran"


def _zone_shares_from_minutes(by_band: dict[str, int]) -> ZoneShares:
    total = sum(by_band.values())
    if total <= 0:
        return ZoneShares()
    return ZoneShares(
        youth=round(100.0 * by_band.get("youth", 0) / total, 1),
        peak=round(100.0 * by_band.get("peak", 0) / total, 1),
        experienced=round(100.0 * by_band.get("experienced", 0) / total, 1),
        veteran=round(100.0 * by_band.get("veteran", 0) / total, 1),
    )


def _require_passport_for_domestic(cols: set[str], domestic_only: bool) -> None:
    if domestic_only and "Passport country" not in cols:
        raise HTTPException(
            422,
            "Passport country column not available for this season — domestic filter disabled",
        )


def _include_player_row(
    row: dict[str, Any],
    *,
    league: str | None,
    domestic_only: bool,
) -> bool:
    if not domestic_only:
        return True
    passport = _nullable_str(row.get("passport"))
    return is_domestic_passport(passport, league) is True


def _clubs_from_rows(
    rows: list[dict[str, Any]],
    *,
    league: str | None = None,
    domestic_only: bool = False,
) -> list[LeagueClubBand]:
    """Aggregate player rows into one ``LeagueClubBand`` per club."""
    by_club: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not _include_player_row(r, league=league, domestic_only=domestic_only):
            continue
        club = str(r.get("club") or "").strip()
        if not club:
            continue
        bucket = by_club.setdefault(
            club,
            {
                "logo": None,
                "bands": {"youth": 0, "peak": 0, "experienced": 0, "veteran": 0},
            },
        )
        if bucket["logo"] is None:
            candidate = normalize_club_logo(r.get("club_logo"))
            if candidate:
                bucket["logo"] = candidate
        minutes = _safe_int(r.get("minutes")) or 0
        band = _age_band(_safe_int(r.get("age")))
        bucket["bands"][band] += minutes

    clubs: list[LeagueClubBand] = []
    for club_name, b in by_club.items():
        bands: dict[str, int] = b["bands"]
        clubs.append(
            LeagueClubBand(
                club=club_name,
                club_logo=b["logo"],
                total_minutes=sum(bands.values()),
                zone_shares=_zone_shares_from_minutes(bands),
            )
        )
    return clubs


def _median_zone_shares(clubs: list[LeagueClubBand]) -> ZoneShares:
    if not clubs:
        return ZoneShares()

    def _med(attr: str) -> float:
        vals = [getattr(c.zone_shares, attr) for c in clubs]
        return round(statistics.median(vals), 1)

    return ZoneShares(
        youth=_med("youth"),
        peak=_med("peak"),
        experienced=_med("experienced"),
        veteran=_med("veteran"),
    )


def _passport_select_sql(cols: set[str]) -> str:
    if "Passport country" in cols:
        return '"Passport country" AS passport'
    return "CAST(NULL AS VARCHAR) AS passport"


@router.get("/minutes-distribution", response_model=MinutesDistributionResponse)
def minutes_distribution(
    season: int = Query(..., description="Season start year (e.g. 2025 for 25-26)"),
    club: str = Query(..., min_length=1, description="Club name as stored in parquet `club`"),
    domestic_only: bool = Query(
        False,
        description="When true, age-band shares count only domestic-passport minutes",
    ),
) -> MinutesDistributionResponse:
    view = view_name(season)
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        cols = column_names_in_view(conn, view)
        if "Minutes played" not in cols:
            raise HTTPException(422, "'Minutes played' column missing from season view")
        if "club" not in cols:
            raise HTTPException(422, "'club' column missing from season view")
        _require_passport_for_domestic(cols, domestic_only)

        has_matches = "Matches played" in cols
        matches_sql = (
            'CAST("Matches played" AS INTEGER) AS matches'
            if has_matches
            else "CAST(NULL AS INTEGER) AS matches"
        )

        age_expr = player_age_sql(cols, season)
        logo_sql = club_logo_select_sql(conn, view, season)
        img_sql = player_image_select_sql(conn, view)
        passport_sql = _passport_select_sql(cols)

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
                league,
                {passport_sql}
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

    band_minutes: dict[str, int] = {"youth": 0, "peak": 0, "experienced": 0, "veteran": 0}
    players: list[MinutesDistributionPlayer] = []
    for r in rows:
        minutes = _safe_int(r.get("minutes")) or 0
        pct = 100.0 * minutes / max_minutes if max_minutes else 0.0
        pct = max(0.0, min(100.0, pct))
        age = _safe_int(r.get("age"))
        wid = _safe_int(r.get("wyscout_id"))
        band = _age_band(age)
        if _include_player_row(r, league=league_val, domestic_only=domestic_only):
            band_minutes[band] += minutes
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
                age_zone=band,
            )
        )

    return MinutesDistributionResponse(
        club=club,
        club_logo=club_logo,
        league=league_val,
        season=season,
        max_league_games=max_games,
        max_league_minutes=max_minutes,
        zone_shares=_zone_shares_from_minutes(band_minutes),
        domestic_only=domestic_only,
        domestic_country=league_domestic_label(league_val),
        players=players,
    )


@router.get(
    "/minutes-distribution/league",
    response_model=LeagueMinutesOverviewResponse,
)
def minutes_distribution_league(
    season: int = Query(..., description="Season start year (e.g. 2025 for 25-26)"),
    league: str = Query(..., min_length=1, description="League name as stored in parquet `league`"),
    domestic_only: bool = Query(
        False,
        description="When true, age-band shares count only domestic-passport minutes",
    ),
) -> LeagueMinutesOverviewResponse:
    view = view_name(season)
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        cols = column_names_in_view(conn, view)
        if "Minutes played" not in cols:
            raise HTTPException(422, "'Minutes played' column missing from season view")
        if "club" not in cols:
            raise HTTPException(422, "'club' column missing from season view")
        if "league" not in cols:
            raise HTTPException(422, "'league' column missing from season view")
        _require_passport_for_domestic(cols, domestic_only)

        age_expr = player_age_sql(cols, season)
        logo_sql = club_logo_select_sql(conn, view, season)
        passport_sql = _passport_select_sql(cols)

        sql = f"""
            SELECT
                club,
                {logo_sql},
                ({age_expr}) AS age,
                CAST("Minutes played" AS INTEGER) AS minutes,
                {passport_sql}
            FROM {view}
            WHERE league = ?
              AND "Minutes played" IS NOT NULL
        """
        rows = fetch_all_dicts(conn, sql, [league])

    if not rows:
        raise HTTPException(404, f"No players found for league {league!r} in season {season}")

    clubs = _clubs_from_rows(rows, league=league, domestic_only=domestic_only)
    clubs.sort(key=lambda c: (-c.zone_shares.youth, c.club.lower()))

    return LeagueMinutesOverviewResponse(
        league=league,
        season=season,
        max_league_games=league_max_games(league),
        max_league_minutes=league_max_minutes(league),
        domestic_only=domestic_only,
        domestic_country=league_domestic_label(league),
        clubs=clubs,
    )


@router.get(
    "/minutes-distribution/leagues",
    response_model=LeaguesMinutesOverviewResponse,
)
def minutes_distribution_leagues(
    season: int = Query(..., description="Season start year (e.g. 2025 for 25-26)"),
    sort_by: AgeBand = Query(
        "youth",
        description="Age band used to rank leagues (median share across clubs)",
    ),
    domestic_only: bool = Query(
        False,
        description="When true, age-band shares count only domestic-passport minutes",
    ),
) -> LeaguesMinutesOverviewResponse:
    view = view_name(season)
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        cols = column_names_in_view(conn, view)
        if "Minutes played" not in cols:
            raise HTTPException(422, "'Minutes played' column missing from season view")
        if "club" not in cols:
            raise HTTPException(422, "'club' column missing from season view")
        if "league" not in cols:
            raise HTTPException(422, "'league' column missing from season view")
        _require_passport_for_domestic(cols, domestic_only)

        age_expr = player_age_sql(cols, season)
        logo_sql = club_logo_select_sql(conn, view, season)
        passport_sql = _passport_select_sql(cols)

        sql = f"""
            SELECT
                league,
                club,
                {logo_sql},
                ({age_expr}) AS age,
                CAST("Minutes played" AS INTEGER) AS minutes,
                {passport_sql}
            FROM {view}
            WHERE "Minutes played" IS NOT NULL
              AND league IS NOT NULL
        """
        rows = fetch_all_dicts(conn, sql)

    if not rows:
        raise HTTPException(404, f"No player minutes found for season {season}")

    by_league: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        league_name = str(r.get("league") or "").strip()
        if not league_name:
            continue
        by_league.setdefault(league_name, []).append(r)

    leagues: list[LeagueMedianBand] = []
    for league_name, league_rows in by_league.items():
        clubs = _clubs_from_rows(
            league_rows,
            league=league_name,
            domestic_only=domestic_only,
        )
        if not clubs:
            continue
        leagues.append(
            LeagueMedianBand(
                league=league_name,
                n_clubs=len(clubs),
                median_zone_shares=_median_zone_shares(clubs),
            )
        )

    leagues.sort(
        key=lambda row: (
            -getattr(row.median_zone_shares, sort_by),
            row.league.lower(),
        )
    )

    return LeaguesMinutesOverviewResponse(
        season=season,
        sort_by=sort_by,
        domestic_only=domestic_only,
        leagues=leagues,
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
