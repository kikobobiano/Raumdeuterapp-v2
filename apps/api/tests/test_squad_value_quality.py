"""Unit tests for squad value quality metrics."""

from __future__ import annotations

from app.core.squad_value import compute_sample_zscores, merge_quality_metrics


def test_compute_sample_zscores_basic() -> None:
    z = compute_sample_zscores([10.0, 20.0, 30.0])
    assert z[0] is not None and z[0] < 0
    assert z[1] is not None and abs(z[1]) < 1e-9
    assert z[2] is not None and z[2] > 0


def test_merge_quality_metrics_attaches_zscore() -> None:
    teams = [{"club": "A"}, {"club": "B"}, {"club": "C"}]
    quality_rows = [
        {"club": "A", "n_players_500": 12, "avg_performance_index": 55.0, "total_xtv_eur": 10.0},
        {"club": "B", "n_players_500": 11, "avg_performance_index": 60.0, "total_xtv_eur": 20.0},
        {"club": "C", "n_players_500": 10, "avg_performance_index": 50.0, "total_xtv_eur": 30.0},
    ]
    merge_quality_metrics(teams, quality_rows)
    assert teams[0]["n_players_500"] == 12
    assert teams[0]["avg_performance_index"] == 55.0
    assert teams[1]["squad_xtv_zscore"] == 0.0
    assert teams[2]["squad_xtv_zscore"] is not None and teams[2]["squad_xtv_zscore"] > 0
