"""Unit tests for screener composite scoring."""
from __future__ import annotations

from app.core.screener_composite import _mean_sd, _score_record


def test_mean_sd_basic() -> None:
    mu, sd = _mean_sd([1.0, 2.0, 3.0])
    assert mu == 2.0
    assert sd is not None and sd > 0


def test_score_record_weighted_z() -> None:
    stats = {
        "Goals|p90|value": (0.0, 1.0),
        "Assists|p90|value": (0.0, 1.0),
    }
    minutes = 10000
    rec = {"minutes": minutes, "g0": 2.0, "a0": 1.0}
    components = [
        ("Goals", "p90", "value", 0.5, "g0"),
        ("Assists", "p90", "value", 0.5, "a0"),
    ]
    score = _score_record(rec, components=components, stats=stats, team_median_maps={})
    weight = minutes / (minutes + 900)
    expected = 1.5 * weight
    assert score is not None
    assert abs(score - expected) < 1e-6


def test_score_record_team_median_ratio() -> None:
    stats = {"Dribbles|as_is|team_median": (1.0, 0.5)}
    team_maps = {"Dribbles|as_is|team_median": {"Arsenal": 2.0}}
    minutes = 10000
    rec = {"minutes": minutes, "club": "Arsenal", "d0": 3.0}
    components = [("Dribbles", "as_is", "team_median", 1.0, "d0")]
    score = _score_record(rec, components=components, stats=stats, team_median_maps=team_maps)
    weight = minutes / (minutes + 900)
    shrunk_ratio = weight * 1.5 + (1.0 - weight) * 1.0
    expected = (shrunk_ratio - 1.0) / 0.5
    assert score is not None
    assert abs(score - expected) < 1e-6


def test_score_record_skips_null_components() -> None:
    stats = {"Goals|p90|value": (0.0, 1.0)}
    rec = {"minutes": 1800, "g0": None}
    components = [("Goals", "p90", "value", 1.0, "g0")]
    assert _score_record(rec, components=components, stats=stats, team_median_maps={}) is None
