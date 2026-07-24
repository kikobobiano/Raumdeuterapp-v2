"""Smoke tests for POST /scouting/standouts."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _pick_season_league(client: TestClient) -> tuple[int | None, str | None]:
    seasons = client.get("/meta/seasons").json()
    if not seasons:
        return None, None
    season = seasons[0]
    leagues = client.get(f"/meta/leagues?season={season}").json()
    return season, (leagues[0] if leagues else None)


def _assert_sorted_desc(rows: list[dict]) -> None:
    scores = [r["standout_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_standouts_overall_smoke() -> None:
    with TestClient(app) as c:
        season, league = _pick_season_league(c)
        if not season or not league:
            return
        body = {
            "filters": {
                "season": season,
                "leagues": [league],
                "age_min": 16,
                "age_max": 40,
                "minutes_min": 600,
            },
            "signal": "overall",
            "min_standout_z": 0.5,
            "limit": 15,
        }
        r = c.post("/scouting/standouts", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["signal"] == "overall"
        assert out["league"] == league
        assert out["cohort_n"] >= 0
        if out["rows"]:
            _assert_sorted_desc(out["rows"])
            r0 = out["rows"][0]
            for k in ("player", "standout_score", "dimensions"):
                assert k in r0
            assert r0["standout_score"] >= 0.5


def test_standouts_metrics_smoke() -> None:
    with TestClient(app) as c:
        season, league = _pick_season_league(c)
        if not season or not league:
            return
        body = {
            "filters": {"season": season, "leagues": [league], "minutes_min": 600},
            "signal": "metrics",
            "metrics": [
                {"metric": "Goals", "mode": "p90", "weight": 1.0},
                {"metric": "Assists", "mode": "p90", "weight": 1.0},
            ],
            "min_standout_z": 0.0,
            "limit": 10,
        }
        r = c.post("/scouting/standouts", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["signal"] == "metrics"
        if out["rows"]:
            _assert_sorted_desc(out["rows"])


def test_standouts_allows_multiple_leagues() -> None:
    with TestClient(app) as c:
        season, league = _pick_season_league(c)
        if not season or not league:
            return
        leagues = c.get(f"/meta/leagues?season={season}").json()
        picked = leagues[:2] if len(leagues) >= 2 else leagues
        body = {
            "filters": {"season": season, "leagues": picked, "minutes_min": 600},
            "signal": "overall",
            "min_standout_z": 0.5,
        }
        r = c.post("/scouting/standouts", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        # Pooled cohort → league label unset when more than one league is selected.
        if len(picked) > 1:
            assert out["league"] is None


def test_standouts_metrics_requires_metric() -> None:
    with TestClient(app) as c:
        season, league = _pick_season_league(c)
        if not season or not league:
            return
        body = {
            "filters": {"season": season, "leagues": [league], "minutes_min": 600},
            "signal": "metrics",
            "metrics": [],
        }
        r = c.post("/scouting/standouts", json=body)
        assert r.status_code == 422, r.text
