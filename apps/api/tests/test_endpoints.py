from fastapi.testclient import TestClient

from app.main import app


def test_meta_seasons() -> None:
    with TestClient(app) as c:
        r = c.get("/meta/seasons")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert all(isinstance(y, int) for y in r.json())


def test_meta_leagues_for_recent_season() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        s = seasons[0]
        r = c.get(f"/meta/leagues?season={s}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_meta_metrics() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        r = c.get(f"/meta/metrics?season={seasons[0]}")
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        assert {"name", "label", "supports_mode", "default_mode"} <= set(items[0].keys())


def test_player_search() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        r = c.get(f"/players/search?season={seasons[0]}&q=mes&limit=5")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)


def test_scatter_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        body = {
            "filters": {
                "season": seasons[0],
                "minutes_min": 500,
                "leagues": ["Premier League"],
            },
            "x_metric": "xG",
            "y_metric": "xA",
            "x_mode": "p90",
            "y_mode": "p90",
        }
        r = c.post("/scatter", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "points" in data
        assert isinstance(data["points"], list)


def test_progression_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        # find any player id
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.post(
            f"/players/{wid}/progression",
            json={"metrics": ["xG"], "target_season": seasons[0], "seasons_count": 3, "mode": "p90"},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "metrics" in d
        assert len(d["seasons"]) <= 3


def test_performance_index_history_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.get(f"/players/{wid}/performance-index-history", params={"season": seasons[0], "limit": 5})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "points" in d
        assert isinstance(d["points"], list)
        assert len(d["points"]) <= 5


def test_player_profile_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.get(f"/players/{wid}/profile", params={"season": seasons[0]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("wyscout_id") == wid
        assert "radar" in d and isinstance(d["radar"], list)
        assert d.get("performance_index_history") is None


def test_player_profile_embeds_pi_history() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.get(
            f"/players/{wid}/profile",
            params={
                "season": seasons[0],
                "performance_index_history_limit": 5,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("performance_index_history"), list)
        pts = d["performance_index_history"]
        assert len(pts) <= 5


def test_rankings_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        body = {
            "filters": {"season": seasons[0], "minutes_min": 500},
            "metric": "xG",
            "mode": "p90",
            "limit": 5,
        }
        r = c.post("/rankings", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "rows" in d and len(d["rows"]) <= 5


def test_bar_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        body = {
            "season": seasons[0],
            "player_ids": [rows[0]["wyscout_id"]],
            "metrics": ["xG", "xA"],
            "mode": "p90",
        }
        r = c.post("/bar", json=body)
        assert r.status_code == 200, r.text


def test_translation_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        body = {"player_id": rows[0]["wyscout_id"], "season": seasons[0]}
        r = c.post("/translation", json=body)
        assert r.status_code == 200, r.text
        payload = r.json()
        assert "league_style_fit" in payload
        assert isinstance(payload["league_style_fit"], list)


def test_replacement_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        rows = c.get(f"/players/search?season={seasons[0]}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        body = {
            "target_player_id": rows[0]["wyscout_id"],
            "target_season": seasons[0],
            "candidate_seasons": [seasons[0]],
            "candidate_filters": {"season": seasons[0], "minutes_min": 1000},
            "limit": 5,
        }
        r = c.post("/replacement", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["candidates"]) <= 5


def test_potential_cohort_pagination() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        body = {
            "filters": {"season": season, "minutes_min": 400},
            "age": 19,
            "limit": 5,
            "offset": 0,
        }
        r = c.post("/potential/cohort", json=body)
        if r.status_code == 503:
            return  # potential_scores view not loaded
        assert r.status_code == 200, r.text
        first = r.json()
        assert first["age"] == 19
        assert isinstance(first["total"], int) and first["total"] >= 0
        assert len(first["players"]) <= 5
        # Page 2 — non-overlapping ids when total > 5.
        if first["total"] > 5:
            r2 = c.post(
                "/potential/cohort",
                json={**body, "offset": 5},
            )
            assert r2.status_code == 200, r2.text
            second = r2.json()
            ids1 = {p["wyscout_id"] for p in first["players"]}
            ids2 = {p["wyscout_id"] for p in second["players"]}
            assert ids1.isdisjoint(ids2)
            # Ordering: every score in page 1 ≥ every score in page 2.
            if first["players"] and second["players"]:
                min_p1 = min(p["potential_score"] for p in first["players"])
                max_p2 = max(p["potential_score"] for p in second["players"])
                assert min_p1 >= max_p2


def test_minutes_distribution() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        s = max(seasons)
        clubs = c.get(f"/meta/teams?season={s}").json()
        if not clubs:
            return
        r = c.get(f"/teams/minutes-distribution?season={s}&club={clubs[0]}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["club"] == clubs[0]
        assert body["season"] == s
        assert body["max_league_games"] > 0
        assert body["max_league_minutes"] == body["max_league_games"] * 90
        assert isinstance(body["players"], list)
        assert all(0 <= p["league_minutes_pct"] <= 100 for p in body["players"])
        assert all(p["age_zone"] in ("young", "prime", "veteran") for p in body["players"])
        if body["players"]:
            mins = [p["minutes"] for p in body["players"]]
            assert mins == sorted(mins, reverse=True)


def test_screener_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        body = {
            "filters": {"season": seasons[0], "minutes_min": 1000},
            "criteria": [
                {"metric": "xG", "mode": "p90", "operator": ">=", "value": 0.3},
            ],
            "sort_by": "xG",
            "sort_mode": "p90",
            "sort_desc": True,
            "limit": 10,
        }
        r = c.post("/screener", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data
        assert len(data["rows"]) <= 10
