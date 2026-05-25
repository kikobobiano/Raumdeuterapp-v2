"""Smoke tests for /teams/squad-value endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _pick_league_and_club(client: TestClient, season: int) -> tuple[str | None, str | None]:
    leagues = client.get(f"/meta/leagues?season={season}").json()
    if not leagues:
        return None, None
    league = leagues[0]
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
        ):
            assert k in row


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
        assert isinstance(body["rows"], list)
        assert len(body["rows"]) >= 1
        row = body["rows"][0]
        assert "season" in row
        assert "total_xtv_eur" in row
        assert "avg_age" in row
