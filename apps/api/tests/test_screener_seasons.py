"""Unit tests for screener season resolution."""

from app.core.screener_seasons import assert_seasons_loaded, resolve_screener_seasons


def test_resolve_empty_falls_back() -> None:
    assert resolve_screener_seasons([], 2025) == [2025]


def test_resolve_keeps_explicit() -> None:
    assert resolve_screener_seasons([2023, 2024], 2025) == [2023, 2024]


def test_assert_seasons_loaded_ok() -> None:
    assert_seasons_loaded([2024, 2025], {"players_2024", "players_2025", "players_all"})


def test_assert_seasons_loaded_missing() -> None:
    try:
        assert_seasons_loaded([2024, 2099], {"players_2024"})
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert str(e) == "2099"
