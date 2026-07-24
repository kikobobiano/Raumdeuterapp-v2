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


def test_player_profile_table_role_override() -> None:
    """Compare needs defender metrics on a forward (and vice versa) via table_role."""
    from app.core.config import ROLE_TABLE_METRICS

    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        rows = c.get(f"/players/search?season={season}&q=salah&limit=1").json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]

        overridden = c.get(
            f"/players/{wid}/profile",
            params={"season": season, "table_role": "Defender"},
        )
        assert overridden.status_code == 200, overridden.text
        got = [m["metric"] for m in overridden.json()["table"]]
        assert got, "expected defender preset rows"
        assert got[0] == "Minutes played"
        assert set(got) <= set(ROLE_TABLE_METRICS["Defender"])
        # Preset metrics present in the parquet must all be returned (order preserved).
        assert got == [m for m in ROLE_TABLE_METRICS["Defender"] if m in got]

        bad = c.get(
            f"/players/{wid}/profile",
            params={"season": season, "table_role": "NotARole"},
        )
        assert bad.status_code == 400, bad.text


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
        assert all(
            p["age_zone"] in ("youth", "peak", "experienced", "veteran")
            for p in body["players"]
        )
        zs = body["zone_shares"]
        for key in ("youth", "peak", "experienced", "veteran"):
            assert key in zs and 0 <= zs[key] <= 100
        if body["players"]:
            mins = [p["minutes"] for p in body["players"]]
            assert mins == sorted(mins, reverse=True)
            # Band assignments follow fixed cutoffs.
            for p in body["players"]:
                age = p.get("age")
                if age is None:
                    assert p["age_zone"] == "peak"
                elif age < 23:
                    assert p["age_zone"] == "youth"
                elif age < 29:
                    assert p["age_zone"] == "peak"
                elif age < 34:
                    assert p["age_zone"] == "experienced"
                else:
                    assert p["age_zone"] == "veteran"


def test_minutes_distribution_league_overview() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        s = max(seasons)
        leagues = c.get(f"/meta/leagues?season={s}").json()
        if not leagues:
            return
        league = leagues[0]
        r = c.get(
            f"/teams/minutes-distribution/league?season={s}&league={league}"
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["league"] == league
        assert body["season"] == s
        clubs = body["clubs"]
        assert isinstance(clubs, list) and len(clubs) > 0
        # Sorted by youth share desc, tie-break alphabetical.
        keys = [(-c["zone_shares"]["youth"], c["club"].lower()) for c in clubs]
        assert keys == sorted(keys)
        for cl in clubs:
            zs = cl["zone_shares"]
            total = zs["youth"] + zs["peak"] + zs["experienced"] + zs["veteran"]
            # Rounding leaves at most ~0.4pp slack.
            assert cl["total_minutes"] >= 0
            assert 99.0 <= total <= 101.0 or total == 0.0


def test_minutes_distribution_all_leagues_overview() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        s = max(seasons)
        for sort_by in ("youth", "peak", "experienced", "veteran"):
            r = c.get(
                f"/teams/minutes-distribution/leagues?season={s}&sort_by={sort_by}"
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["season"] == s
            assert body["sort_by"] == sort_by
            assert body["domestic_only"] is False
            leagues = body["leagues"]
            assert isinstance(leagues, list) and len(leagues) > 0
            keys = [
                (-row["median_zone_shares"][sort_by], row["league"].lower())
                for row in leagues
            ]
            assert keys == sorted(keys)
            for row in leagues:
                assert row["n_clubs"] >= 1
                zs = row["median_zone_shares"]
                assert all(k in zs for k in ("youth", "peak", "experienced", "veteran"))

        r_dom = c.get(
            f"/teams/minutes-distribution/leagues?season={s}&domestic_only=true"
        )
        assert r_dom.status_code == 200, r_dom.text
        assert r_dom.json()["domestic_only"] is True


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
        for row in data["rows"]:
            assert row["season"] == seasons[0]


def test_screener_multi_season_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if len(seasons) < 2:
            return
        picked = sorted(seasons[:2])
        body = {
            "filters": {"season": picked[-1], "minutes_min": 1000},
            "seasons": picked,
            "criteria": [
                {"metric": "xG", "mode": "p90", "operator": ">=", "value": 0.3},
            ],
            "sort_by": "xG",
            "sort_mode": "p90",
            "sort_desc": True,
            "limit": 20,
        }
        r = c.post("/screener", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data
        assert len(data["rows"]) <= 20
        assert data["total"] >= len(data["rows"])
        for row in data["rows"]:
            assert row["season"] in picked


def test_screener_composite_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        leagues = c.get(f"/meta/leagues?season={season}").json()
        filters: dict = {"season": season, "minutes_min": 600}
        if leagues:
            filters["leagues"] = [leagues[0]]
        body = {
            "filters": filters,
            "criteria": [],
            "composite": [
                {"metric": "Goals", "mode": "p90", "basis": "value", "weight": 1.0},
                {
                    "metric": "Successful dribbles, %",
                    "mode": "as_is",
                    "basis": "team_median",
                    "weight": 1.0,
                },
            ],
            "sort_by_composite": True,
            "sort_desc": True,
            "limit": 10,
        }
        r = c.post("/screener", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rows" in data
        for row in data["rows"]:
            assert row["season"] == season
        if data["rows"]:
            scores = [row["composite"] for row in data["rows"] if row["composite"] is not None]
            assert scores == sorted(scores, reverse=True)


def test_heatmap_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        season = seasons[0]
        rows = c.get(
            f"/players/search?season={season}&q=salah&limit=1"
        ).json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.get(f"/players/{wid}/heatmap", params={"season": season})
        # 404 is acceptable when the heatmaps parquet hasn't been generated yet
        # (CI / fresh checkout). 200 must return a valid shape.
        assert r.status_code in (200, 404), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["wyscout_id"] == wid
            assert isinstance(d["points"], list)
            assert "max_count" in d
            assert "n_points" in d
            for p in d["points"][:5]:
                assert set(p.keys()) >= {"x", "y", "count"}
