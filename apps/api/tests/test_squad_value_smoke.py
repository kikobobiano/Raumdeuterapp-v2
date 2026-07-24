"""Smoke tests for /teams/squad-value endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import LEAGUES_EXCLUDED_FROM_SQUAD_VALUE
from app.main import app


def _pick_league_and_club(client: TestClient, season: int) -> tuple[str | None, str | None]:
    leagues = client.get(f"/meta/leagues?season={season}").json()
    if not leagues:
        return None, None
    eligible = [lg for lg in leagues if lg not in LEAGUES_EXCLUDED_FROM_SQUAD_VALUE]
    if not eligible:
        return None, None
    league = eligible[0]
    teams = client.get(f"/meta/teams?season={season}&league={league}").json()
    if not teams:
        return league, None
    return league, teams[0]


def test_squad_value_league_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        league, _ = _pick_league_and_club(c, season)
        if not league:
            return
        r = c.get(f"/teams/squad-value/league?season={season}&league={league}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["season"] == season
        assert body["league"] == league
        assert "xtv_supported" in body
        assert isinstance(body["teams"], list)
        assert len(body["teams"]) >= 1
        row = body["teams"][0]
        for k in (
            "club",
            "n_players",
            "avg_age",
            "total_xtv_eur",
            "avg_xtv_eur",
            "total_market_value_eur",
            "avg_market_value_eur",
            "foreign_share",
            "n_players_500",
            "avg_performance_index",
            "squad_xtv_zscore",
        ):
            assert k in row


def test_squad_value_league_rejects_excluded_league() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        r = c.get(
            f"/teams/squad-value/league?season={season}&league=Campeonato de Portugal"
        )
        assert r.status_code == 404, r.text


def test_squad_value_history_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        _, club = _pick_league_and_club(c, season)
        if not club:
            return
        r = c.get(f"/teams/squad-value/history?club={club}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["club"] == club
        assert "xtv_supported" in body
        assert isinstance(body["rows"], list)
        assert len(body["rows"]) >= 1
        row = body["rows"][0]
        assert "season" in row
        assert "total_xtv_eur" in row
        assert "avg_age" in row
