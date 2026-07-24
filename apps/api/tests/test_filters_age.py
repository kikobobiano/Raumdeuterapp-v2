"""Age filter SQL uses season-aligned age, not raw Age column."""

from __future__ import annotations

from app.core.filters import PlayerFilters, age_filter_parts, build_where


def test_age_filter_parts_uses_birthday_anchor() -> None:
    f = PlayerFilters(season=2020, age_min=20, age_max=25)
    cols = {"Age", "Birthday", "Minutes played"}
    parts, params = age_filter_parts(f, cols)
    sql = " AND ".join(parts)
    assert "Birthday" in sql
    assert "make_date(2020" in sql
    assert params == [20, 25]
    assert '"Age" >=' not in sql


def test_build_where_with_cols_uses_season_age() -> None:
    f = PlayerFilters(season=2018, age_min=18)
    cols = {"Age", "Birthday"}
    where, params = build_where(f, cols=cols)
    assert "make_date(2018" in where
    assert 18 in params


def test_build_where_without_cols_falls_back_to_raw_age() -> None:
    f = PlayerFilters(season=2025, age_max=30)
    where, params = build_where(f)
    assert '"Age" <= ?' in where
    assert 30 in params
