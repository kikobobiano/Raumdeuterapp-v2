"""Unit tests for composite score criterion validation on screener."""

from app.routers.screener import _score_matches


def test_score_matches_ops() -> None:
    assert _score_matches(1.0, ">=", 1.0)
    assert not _score_matches(0.9, ">=", 1.0)
    assert _score_matches(None, ">=", 0.0) is False
    assert _score_matches(1.0, "!=", 0.0)
    assert _score_matches(0.0, "=", 0.0)
