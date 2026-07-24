"""Smoke test for POST /scouting/discover."""
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


def test_discover_smoke() -> None:
    with TestClient(app) as c:
        season, league = _pick_season_league(c)
        if not season or not league:
            return
        body = {
            "filters": {
                "season": season,
                "leagues": [league],
                "age_min": 17,
                "age_max": 30,
                "minutes_min": 600,
            },
            "metrics": [
                {"metric": "Goals", "mode": "p90", "weight": 1.0},
                {"metric": "Assists", "mode": "p90", "weight": 1.0},
            ],
            "normalization": "zscore",
            "cohort_tier": "position_tier",
            "archetype": "pca_kmeans",
            "k_clusters": 3,
            "limit": 10,
        }
        r = c.post("/scouting/discover", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert "rows" in out
        assert "cohort" in out
        assert out["cohort"]["n"] >= 0
        if out["rows"]:
            r0 = out["rows"][0]
            for k in ("player", "composite_score", "metric_values"):
                assert k in r0
            # Composite ordering: monotonic descending.
            scores = [row["composite_score"] for row in out["rows"]]
            assert scores == sorted(scores, reverse=True)


def test_discover_rejects_bad_metric() -> None:
    with TestClient(app) as c:
        season, league = _pick_season_league(c)
        if not season or not league:
            return
        body = {
            "filters": {"season": season, "leagues": [league], "minutes_min": 600},
            "metrics": [{"metric": "Does Not Exist", "weight": 1.0}],
        }
        r = c.post("/scouting/discover", json=body)
        assert r.status_code in (400, 422), r.text
